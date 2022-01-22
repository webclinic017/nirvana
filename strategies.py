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

        self.first_run = True
        if (self.p.tearsheet):
            self.portvalue = self.broker.getvalue()
            self.gains = []
            self.dates = []

        self.target = self.p.portfolio.copy()
        self.target_update = self.target.copy()
        self.ticker = {}
        self.ma_above = {}
        self.portfolio = {}
        self.df_history = {}

        for symbol in self.target:
            self.df_history[symbol] = pd.read_csv("history/" + symbol + ".csv").set_index("Date")

        if 'SPY' not in self.target:
            self.df_history['SPY'] = pd.read_csv("history/SPY.csv").set_index("Date")

        if 'QQQ' not in self.target and ('QLD' in self.target or 'TQQQ' in self.target):
            self.df_history['QQQ'] = pd.read_csv("history/QQQ.csv").set_index("Date")

        if 'TLT' not in self.target and ('UBT' in self.target or 'TMF' in self.target):
            self.df_history['TLT'] = pd.read_csv("history/TLT.csv").set_index("Date")

        if 'GLD' not in self.target and 'UGL' in self.target:
            self.df_history['GLD'] = pd.read_csv("history/GLD.csv").set_index("Date")

        if 'SLV' not in self.target and 'AGQ' in self.target:
            self.df_history['SLV'] = pd.read_csv("history/SLV.csv").set_index("Date")

        # create rebalancer and set absolute and relative deviation limits
        self.rb = rebalancer.Rebalancer(absolute_deviation_limit = 0.05, relative_deviation_limit = 0.25)

        # set moving average type and period plus upper and lower limits
        self.ma_limits = {
            'SPY':     {'type': 'SMA_100', 'upper': 1.01, 'lower': 0.97},
            'QQQ':     {'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'EEM':     {'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'TLT':     {'type': 'SMA_150', 'upper': 1.01, 'lower': 0.96},
            'GBTC':    {'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'ETHE':    {'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'GLD':     {'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'SLV':     {'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'default': {'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96}
        }

        for symbol in self.df_history:
            if symbol in self.ma_limits:
                ma_type = self.ma_limits[symbol]['type']
                ma_upper = self.ma_limits[symbol]['upper']
                ma_lower = self.ma_limits[symbol]['lower']
            else:
                ma_type = self.ma_limits['default']['type']
                ma_upper = self.ma_limits['default']['upper']
                ma_lower = self.ma_limits['default']['lower']
            self.ticker[symbol] = {
                'ma_type': ma_type,
                'ma_upper': ma_upper,
                'ma_lower': ma_lower,
                'price': 0.0,
                'ma': 0.0,
                'ppo': 0.0,
                'rsi': 0.0,
                'in_uptrend': 0.0
            }

        self.count = 1

    def next(self):
        date_dt = self.datas[0].datetime.date(0)
        date = date_dt.strftime('%Y-%m-%d')

        # update daily closing price and moving average from historical data
        for symbol in self.df_history:
            self.ticker[symbol]['price'] = self.df_history[symbol].loc[date]['Adj Close']
            self.ticker[symbol]['ma'] = self.df_history[symbol].loc[date][self.ticker[symbol]['ma_type']]
            self.ticker[symbol]['ppo'] = self.df_history[symbol].loc[date]['PPO']
            self.ticker[symbol]['rsi'] = self.df_history[symbol].loc[date]['RSI']
            self.ticker[symbol]['in_uptrend'] = self.df_history[symbol].loc[date]['in_uptrend']

        # determine if we are above the moving average at the start of the backtest
        if self.first_run:
            for symbol in self.target:
                if symbol in ['SPY', 'SSO', 'SPXL', 'FNGU', 'RSP']:
                    self.ma_above[symbol] = self.ticker['SPY']['price'] >= self.ticker['SPY']['ma']
                if symbol in ['QQQ', 'QLD', 'TQQQ']:
                    self.ma_above[symbol] = self.ticker['QQQ']['price'] >= self.ticker['QQQ']['ma']
                elif symbol in ['TLT', 'UBT', 'TMF']:
                    self.ma_above[symbol] = self.ticker['TLT']['price'] >= self.ticker['TLT']['ma']
                elif symbol in ['GLD', 'UGL']:
                    self.ma_above[symbol] = self.ticker['GLD']['price'] >= self.ticker['GLD']['ma']
                elif symbol in ['SLV', 'AGQ']:
                    self.ma_above[symbol] = self.ticker['SLV']['price'] >= self.ticker['SLV']['ma']
                else:
                    self.ma_above[symbol] = True # self.ticker[symbol]['price'] >= self.ticker[symbol]['ma']

                # set target position to zero if below moving average at the start
                if not self.ma_above[symbol]:
                    self.target_update[symbol] = 0

        # check if price crossed moving average and update target allocations
        # MACD is based on absolute values while PPO is based on percentages so use PPO here
        use_ppo = True

        for symbol in self.target:
            ma_below = False
            ma_above = True

            if symbol in ['SPY', 'SSO', 'SPXL', 'RSP']: # Use SPY moving average for SP500 related equities
                ma_below = self.ticker['SPY']['price'] < self.ticker['SPY']['ma'] * self.ticker['SPY']['ma_lower'] and (not use_ppo or self.ticker['SPY']['ppo'] < 0.75)
                ma_above = self.ticker['SPY']['price'] >= self.ticker['SPY']['ma'] * self.ticker['SPY']['ma_upper'] or (use_ppo and self.ticker['SPY']['ppo'] > 1.0) or self.ticker['SPY']['rsi'] < 21
            elif symbol in ['QQQ', 'QLD', 'TQQQ']: # Use QQQ moving average for QQQ related equities
                ma_below = self.ticker['QQQ']['price'] < self.ticker['QQQ']['ma'] * self.ticker['QQQ']['ma_lower'] and (not use_ppo or self.ticker['QQQ']['ppo'] < 0.75)
                ma_above = self.ticker['QQQ']['price'] >= self.ticker['QQQ']['ma'] * self.ticker['QQQ']['ma_upper'] or (use_ppo and self.ticker['QQQ']['ppo'] > 1.0) or self.ticker['QQQ']['rsi'] < 21
            elif symbol in ['TLT', 'UBT', 'TMF']: # Use TLT moving average for 20-year treasury related equities
                ma_below = self.ticker['TLT']['price'] < self.ticker['TLT']['ma'] * self.ticker['TLT']['ma_lower'] and (not use_ppo or self.ticker['TLT']['ppo'] < 0.75)
                ma_above = self.ticker['TLT']['price'] >= self.ticker['TLT']['ma'] * self.ticker['TLT']['ma_upper'] or (use_ppo and self.ticker['TLT']['ppo'] > 1.0) or self.ticker['TLT']['rsi'] < 20
            elif symbol in ['GLD', 'UGL']: # Use GLD moving average for gold related equities
                ma_below = self.ticker['GLD']['price'] < self.ticker['GLD']['ma'] * self.ticker['GLD']['ma_lower'] and (not use_ppo or self.ticker['GLD']['ppo'] < 0.75)
                ma_above = self.ticker['GLD']['price'] >= self.ticker['GLD']['ma'] * self.ticker['GLD']['ma_upper'] or (use_ppo and self.ticker['GLD']['ppo'] > 1.0) or self.ticker['GLD']['rsi'] < 20
            elif symbol in ['SLV', 'AGQ']: # Use SLV moving average for silver related equities
                ma_below = self.ticker['SLV']['price'] < self.ticker['SLV']['ma'] * self.ticker['SLV']['ma_lower'] and (not use_ppo or self.ticker['SLV']['ppo'] < 0.75)
                ma_above = self.ticker['SLV']['price'] >= self.ticker['SLV']['ma'] * self.ticker['SLV']['ma_upper'] or (use_ppo and self.ticker['SLV']['ppo'] > 1.0) or self.ticker['GLD']['rsi'] < 20
            else:
                ma_below = self.ticker[symbol]['price'] < self.ticker[symbol]['ma'] * self.ticker[symbol]['ma_lower'] and (not use_ppo or self.ticker[symbol]['ppo'] < 0.75) or self.ticker[symbol]['rsi'] < 20
                ma_above = self.ticker[symbol]['price'] >= self.ticker[symbol]['ma'] * self.ticker[symbol]['ma_upper'] or (use_ppo and self.ticker[symbol]['ppo'] > 1.0) or self.ticker[symbol]['rsi'] < 20

            # logic to determine if we need to move completely in or out of an ETF base on moving average
            if (ma_below and self.ma_above[symbol]): # if we fall below MA after being above threshold then set allocation to 0
                self.target_update[symbol] = 0
                self.ma_above[symbol] = False
                rebalance_ma = True
            elif (ma_above and not self.ma_above[symbol]): # if we rise above MA after being below threshold then set allocation back to target
                self.target_update[symbol] = self.target[symbol]
                self.ma_above[symbol] = True
                rebalance_ma = True
            else:
                rebalance_ma = False

        # update cash at broker
        cash = self.broker.getcash()

        # update portfolio holdings from broker
        for data in self.datas:
            if (data._name in self.target):
                self.portfolio[data._name] = {'shares': self.broker.getposition(data).size, 'last_price': data.close[0]}

        # check if any positions in portfolio are outside rebalancing bands using updated target allocations
        rebalance_bands = self.rb.rebalance_check(cash, self.portfolio, self.target_update)

        if (rebalance_bands or rebalance_ma or self.first_run):
            print("rebalance_bands: " + str(rebalance_bands) + " rebalance_ma: " + str(rebalance_ma) + " (cash = " + str(cash) + ")")

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
