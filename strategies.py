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
import ta
qs.extend_pandas()

def get_ma(history, type, window, date_dt, last_price):
    date = date_dt.strftime('%Y-%m-%d')
    history['Date'] = pd.to_datetime(history['Date']).dt.date
    history = history[~(history['Date'] >= date_dt)]
    history = history.append({'Date': date}, ignore_index=True)
    history = history.set_index("Date")
    history.loc[date]['Adj Close'] = last_price
    sma = ta.trend.sma_indicator(history['Adj Close'], window=window, fillna=True)
    history['SMA'] = sma
    ma = history.loc[date]['SMA']

    return ma

class Nirvana(bt.Strategy):
    params = (
        ('a', 0.0),
        ('b', 0.0),
        ('c', 0.0),
        ('d', 0.0),
        ('optimizer', False),
        ('portfolio', {}),
        ('tearsheet', False),
        ('args', None)
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None

        if not self.p.optimizer:
            self.rows = []
            self.rows.append("Date,Transaction,Symbol,Shares,Price")

        self.count = 1
        self.first_run = True
        if (self.p.tearsheet):
            self.portvalue = self.broker.getvalue()
            self.gains = []
            self.dates = []

        # MACD is based on absolute values while PPO is based on percentages so use PPO here
        self.use_ppo = True

        self.target = self.p.portfolio.copy()
        self.target_update = self.target.copy()
        self.ticker = {}
        self.risk_on = {}
        self.portfolio = {}
        self.df_history = {}

        # set to non-zero for time-based rebalancing
        self.rebalance_days = 0

        # create rebalancer and set absolute and relative deviation limits
        self.rb = rebalancer.Rebalancer(absolute_deviation_limit = 0.05, relative_deviation_limit = 0.25)

        # set moving average type and period plus upper and lower limits
        self.rules = {
            'SPY':     {'enable': True,  'sym': 'SPY',  'type': 'SMA_180', 'upper': 1.03, 'lower': 0.97},
            'SPXL':    {'enable': True,  'sym': 'SPY',  'type': 'SMA_180', 'upper': 1.04, 'lower': 0.95},
            'QQQ':     {'enable': True,  'sym': 'QQQ',  'type': 'SMA_180', 'upper': 1.02, 'lower': 0.98},
            'QLD':     {'enable': True,  'sym': 'SPY',  'type': 'SMA_180', 'upper': 1.02, 'lower': 0.98},
            'TQQQ':    {'enable': True,  'sym': 'SPY',  'type': 'SMA_180', 'upper': 1.02, 'lower': 0.98},
            'EEM':     {'enable': True,  'sym': 'EEM',  'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'TLT':     {'enable': True,  'sym': 'TLT',  'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'GBTC':    {'enable': True,  'sym': 'GBTC', 'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'ETHE':    {'enable': True,  'sym': 'ETHE', 'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'GLD':     {'enable': True,  'sym': 'GLD',  'type': 'SMA_100', 'upper': 0.00, 'lower': 0.00},
            'SLV':     {'enable': True,  'sym': 'SLV',  'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96}
        }

        # find all symbols needed for indicators
        for symbol in self.target:
            if symbol in self.rules:
                rules_symbol = self.rules[symbol]['sym']
                if rules_symbol not in self.df_history:
                    self.df_history[rules_symbol] = pd.read_csv("history/" + rules_symbol + ".csv").set_index("Date")
                self.ticker[symbol] = {
                    'ma_enable': self.rules[symbol]['enable'],
                    'ma_symbol': self.rules[symbol]['sym'],
                    'ma_type': self.rules[symbol]['type'],
                    'ma_upper': self.rules[symbol]['upper'],
                    'ma_lower': self.rules[symbol]['lower'],
                    'price': 0.0,
                    'ma': 0.0,
                    'ppo': 0.0,
                    'rsi': 0.0,
                    'in_uptrend': 0.0
                }

    def next(self):
        date_dt = self.datas[0].datetime.date(0)
        date = date_dt.strftime('%Y-%m-%d')

        # update daily closing price and moving average for indicators
        for symbol in self.ticker:
            rules_sym = self.rules[symbol]['sym']
            self.ticker[symbol]['price'] = self.df_history[rules_sym].loc[date]['Adj Close']
            self.ticker[symbol]['ma'] = self.df_history[rules_sym].loc[date][self.ticker[symbol]['ma_type']]
            self.ticker[symbol]['ppo'] = self.df_history[rules_sym].loc[date]['PPO']
            self.ticker[symbol]['rsi'] = self.df_history[rules_sym].loc[date]['RSI']
            self.ticker[symbol]['in_uptrend'] = self.df_history[rules_sym].loc[date]['in_uptrend']

        # determine if we are above the moving average at the start of the backtest
        if self.first_run:
            for symbol in self.ticker:
                if self.ticker[symbol]['ma_enable'] == True:
                    self.risk_on[symbol] = self.ticker[symbol]['price'] >= self.ticker[symbol]['ma']
                else:
                    self.risk_on[symbol] = True

                # set target position to zero if below moving average at the start
                if not self.risk_on[symbol]:
                    self.target_update[symbol] = 0

        # check if price crossed moving average threshold, if so, update target allocations and rebalance
        rebalance_ma = False
        for symbol in self.ticker:
            if self.ticker[symbol]['ma_enable'] == True:
                risk_off = (
                    self.ticker[symbol]['price'] < self.ticker[symbol]['ma'] * self.ticker[symbol]['ma_lower']
                    and (not self.use_ppo or self.ticker[symbol]['ppo'] < 0.75) 
                    and self.ticker[symbol]['rsi'] > 22
                )
                risk_on = (
                    self.ticker[symbol]['price'] >= self.ticker[symbol]['ma'] * self.ticker[symbol]['ma_upper']
                    or (self.use_ppo and self.ticker[symbol]['ppo'] > 1.0)
                    or self.ticker[symbol]['rsi'] < 21
                )

                if (risk_off and self.risk_on[symbol]):
                    self.target_update[symbol] = 0
                    self.risk_on[symbol] = False
                    rebalance_ma = True
                elif (risk_on and not self.risk_on[symbol]):
                    self.target_update[symbol] = self.target[symbol]
                    self.risk_on[symbol] = True
                    rebalance_ma = True

        # update cash at broker
        cash = self.broker.getcash()

        # update portfolio holdings from broker
        for data in self.datas:
            if (data._name in self.target):
                self.portfolio[data._name] = {'shares': self.broker.getposition(data).size, 'last_price': data.close[0]}

        # check if portfolio need rebalancing based on time or bands
        if (self.rebalance_days > 0):
            if (self.count % self.rebalance_days == 0):
                rebalance = True
            else:
                rebalance = False
            self.count += 1
        else:
            rebalance = self.rb.rebalance_bands(cash, self.portfolio, self.target_update)

        if (rebalance or rebalance_ma or self.first_run):
            print(date + ": " + str(self.target_update))

            # generate trades to rebalance back to the updated target allocation
            trades = self.rb.rebalance(cash, self.portfolio, self.target_update)

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
