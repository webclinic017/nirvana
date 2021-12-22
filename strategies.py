import os
import sys
sys.path.append(os.path.abspath('../lib'))
import backtrader as bt
import math
import pandas as pd
import os
import indicator
from scipy import stats
import datetime
import rebalancer
import quantstats as qs
qs.extend_pandas()

class Nirvana(bt.Strategy):
    params = (
        ('a', 0.0),
        ('b', 0.0),
        ('c', 0.0),
        ('d', 0.0),
        ('optimizer', False),
        ('portin', {}),
        ('portout', {}),
        ('tearsheet', False),
        ('args', None)
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.inout = 0
        self.order = None
        if not self.p.optimizer:
            self.rows = []
            self.rows.append("Date,Transaction,Symbol,Shares,Price")
        self.buy_price = {}
        self.first_run = True
        if (self.p.tearsheet):
            self.portvalue = self.broker.getvalue()
            self.gains = []
            self.dates = []

        self.target = self.p.portin.copy()
        self.target_update = self.target.copy()

        self.ticker = {}
        self.ma_above = {}
        self.portfolio = {}
        self.df_history = {}
        for symbol in self.target:
            self.df_history[symbol] = pd.read_csv("history/" + symbol + ".csv").set_index("Date")

        # create rebalancer and set absolute and relative deviation limits
        self.rb = rebalancer.Rebalancer(absolute_deviation_limit = 0.05, relative_deviation_limit = 0.25)

        # set moving average type and period plus upper and lower limits
        self.ma_limits = {
            'SPY':   {'ma': 'SMA_200', 'upper': 1.04, 'lower': 0.95},
            'SPXL':  {'ma': 'SMA_200', 'upper': 1.05, 'lower': 0.90},
            'TQQQ':  {'ma': 'SMA_180', 'upper': 1.03, 'lower': 0.95},
            'TLT':   {'ma': 'SMA_180', 'upper': 1.05, 'lower': 0.90},
            'TMF':   {'ma': 'SMA_180', 'upper': 1.05, 'lower': 0.90},
            'GBTC':  {'ma': 'SMA_50',  'upper': 1.05, 'lower': 0.90},
            'ETHE':  {'ma': 'SMA_100', 'upper': 1.05, 'lower': 0.90},
            'GLD':   {'ma': 'SMA_180', 'upper': 1.05, 'lower': 0.90},
            'UGL':   {'ma': 'SMA_180', 'upper': 1.05, 'lower': 0.90},
            'TSLA':  {'ma': 'SMA_180', 'upper': 1.05, 'lower': 0.90}
        }

    def notify_order(self, order):
        debug = False
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # NOTE: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                if debug:
                    self.log('BUY EXECUTED, %.2f' % order.executed.price)
            elif order.issell():
                if debug:
                    self.log('SELL EXECUTED, %.2f' % order.executed.price)

            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected (status = ' + str(order.status) + ')')

        # Write down: no pending order
        self.order = None

    def next(self):
        date_dt = self.datas[0].datetime.date(0)
        date = date_dt.strftime('%Y-%m-%d')

        # update daily closing price and moving average from historical data
        for symbol in self.target:
            ma = self.ma_limits[symbol]['ma']
            self.ticker[symbol] = {
                'price': self.df_history[symbol].loc[date]['Adj Close'],
                'ma': self.df_history[symbol].loc[date][ma]
            }

        # determine if we are above the moving average at the start of the backtest
        if self.first_run:
            for symbol in self.target:
                self.ma_above[symbol] = self.ticker[symbol]['price'] >= self.ticker[symbol]['ma']
                if not self.ma_above[symbol]:
                    self.target_update[symbol] = 0

        rebalance_ma = False

        # check if price crossed moving average and update target allocations
        for symbol in self.target:
            if (self.ticker[symbol]['price'] < self.ticker[symbol]['ma'] * self.ma_limits[symbol]['lower'] and self.ma_above[symbol]):
                self.target_update[symbol] = 0
                self.ma_above[symbol] = False
                rebalance_ma = True
            elif (self.ticker[symbol]['price'] >= self.ticker[symbol]['ma'] * self.ma_limits[symbol]['upper'] and not self.ma_above[symbol]):
                self.target_update[symbol] = self.target[symbol]
                self.ma_above[symbol] = True
                rebalance_ma = True

        # update cash at broker
        cash = self.broker.getcash()

        # update portfolio holdings at broker
        for data in self.datas:
            if (data._name in self.target):
                self.portfolio[data._name] = {'shares': self.broker.getposition(data).size, 'last_price':data.close[0]}

        # check if any positions in portfolio are outside rebalancing bands using updated positions and target allocations
        rebalance_bands = self.rb.rebalance_check(cash, self.portfolio, self.target_update)
        
        if (rebalance_bands or rebalance_ma or self.first_run):
            print("rebalance_bands: " + str(rebalance_bands) + " rebalance_ma: " + str(rebalance_ma))
            print("cash = " + str(cash))

            # generate trades to rebalance back to the updated target allocation
            trades = self.rb.rebalance(self.portfolio, self.target_update)

            # process sell orders
            for data in self.datas:
                if (data._name in trades and trades[data._name]['action'] == 'SELL'):
                    size = math.ceil(trades[data._name]['amount'] / self.portfolio[data._name]['last_price'])
                    if size > self.broker.getposition(data).size:
                        size = self.broker.getposition(data).size
                    if int(size) < 1:
                        continue

                    self.order = self.sell(data=data, size=int(size))

                    if not self.p.optimizer:
                        print("{}: SELL {} {} shares at {}".format(
                            date, "%5s" % data._name,"%9d" % self.order.size, "%7.2f" % data.close[0]))
                        self.rows.append("{},{},{},{},{}".format(date, "SELL", data._name, self.order.size, data.close[0]))

            # process buy orders
            for data in self.datas:
                if (data._name in trades and trades[data._name]['action'] == 'BUY'):
                    size = math.floor(trades[data._name]['amount'] / self.portfolio[data._name]['last_price'])
                    if size == 0:
                        continue

                    self.order = self.buy(data=data, size=size)
 
                    if not self.p.optimizer:
                        print("{}:  BUY {} {} shares at {}".format(
                            date, "%5s" % data._name,"%9d" % self.order.size, "%7.2f" % data.close[0]))
                        self.rows.append("{},{},{},{},{}".format(date, "BUY", data._name, self.order.size, data.close[0],))

        if (self.p.tearsheet):
            gain = (self.broker.getvalue() - self.portvalue) / self.portvalue
            self.gains.append(float(gain))
            self.dates.append(date)
            self.portvalue = self.broker.getvalue()
        
        self.first_run = False

    def stop(self):
        if (self.p.tearsheet):
            df_performance = pd.DataFrame()
            df_performance.insert(0, "Date", self.dates)
            df_performance.insert(1, "Returns", self.gains)
            df_performance['Date'] = pd.to_datetime(df_performance['Date'])
            ts = pd.Series(df_performance['Returns'].values, index=df_performance['Date'])
            qs.reports.html(ts, "SPY", title='Tearsheet', output='performance.html')

        if not self.p.optimizer:
            with open('trades.csv', 'w') as filehandle:
                filehandle.writelines("%s\n" % row for row in self.rows)

class GuardDog(bt.Strategy):

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None
        self.sma = bt.indicators.SimpleMovingAverage(period=180)

        # To set the stop price
        self.macd_quick = bt.indicators.MACD(self.data, period_me1=12, period_me2=26, period_signal=9)
        self.macd = bt.indicators.MACD(self.data, period_me1=12, period_me2=26, period_signal=9)

    def next(self):

        if self.position.size == 0:
            if not ((self.macd.macd[0] < self.macd.signal[0]) or (self.data.close[0] < self.sma[0])):
                self.order = self.buy()
                self.log("Buying {} shares at {}".format(
                    self.order.size, self.data.close[0]))

        if self.position.size > 0:
            if (self.macd_quick.macd[0] < self.macd_quick.signal[0]) and (self.data.close[0] < self.sma[0]):
                self.order = self.close()
                self.log("Selling {} shares at {}".format(
                    self.order.size, self.data.close[0]))

class SMACrossover(bt.Strategy):

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None
        self.sma = bt.indicators.SimpleMovingAverage(period=180)

    def next(self):

        if not self.position:
            if self.data.close[0] >= self.sma[0] * 1.05:
                self.order = self.buy()
                self.log("Buying {} shares at {} (sma={})".format(
                    self.order.size, self.data.close[0], self.sma[0]))
        elif self.data.close[0] < self.sma[0] * 0.9:
            self.order = self.close()
            self.log("Selling {} shares at {} (sma={})".format(
                    self.order.size, self.data.close[0], self.sma[0]))

class BuyHold(bt.Strategy):
    params = (('portfolio', {}),)

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def next(self):
    
        if self.position.size == 0:
            for data in self.datas:
                if data._name not in self.p.portfolio:
                    continue
                self.order = self.buy(data=data)
                self.log("BUY {} {} shares at {}".format(
                    "%5s" % data._name, "%9d" % self.order.size, "%7.2f" % data.close[0]))
