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
from utils import round_down, round_up

class Nirvana(bt.Strategy):
    params = (
        ('a', 0.0),
        ('b', 0.0),
        ('c', 0.0),
        ('d', 0.0),
        ('optimizer', False),
        ('portfolio', {}),
        ('args', None)
    )

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.order = None

        self.addcash_period, self.addcash_amount = self.p.args.addcash.split('/')
        if not self.p.optimizer:
            self.rows = []
            self.rows.append("Date,Transaction,Symbol,Shares,Price")

        self.count = 1
        self.first_run = True
        if (self.p.args.tearsheet):
            self.portvalue = self.broker.getvalue()
            self.gains = []
            self.dates = []

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
            'SPY':     {'enable': True,  'sym': 'SPY',  'type': 'SMA_175', 'upper': 1.03, 'lower': 0.97},
            'SPXL':    {'enable': True,  'sym': 'SPY',  'type': 'SMA_175', 'upper': 1.04, 'lower': 0.97},
            'SPXL--125':    {'enable': True,  'sym': 'SPY',  'type': 'SMA_125', 'upper': 1.04, 'lower': 0.97},
            'SPXL--150':    {'enable': True,  'sym': 'SPY',  'type': 'SMA_150', 'upper': 1.04, 'lower': 0.97},
            'SPXL--175':    {'enable': True,  'sym': 'SPY',  'type': 'SMA_175', 'upper': 1.04, 'lower': 0.97},
            'SPXL--200':    {'enable': True,  'sym': 'SPY',  'type': 'SMA_200', 'upper': 1.04, 'lower': 0.97},
            'SPXL--225':    {'enable': True,  'sym': 'SPY',  'type': 'SMA_225', 'upper': 1.04, 'lower': 0.97},
            'QQQ':     {'enable': True,  'sym': 'QQQ',  'type': 'SMA_175', 'upper': 1.02, 'lower': 0.98},
            'QLD':     {'enable': True,  'sym': 'SPY',  'type': 'SMA_175', 'upper': 1.02, 'lower': 0.98},
            'TQQQ':    {'enable': True,  'sym': 'SPY',  'type': 'SMA_175', 'upper': 1.04, 'lower': 0.95},
            'TNA':     {'enable': True,  'sym': 'IWM',  'type': 'SMA_175', 'upper': 1.02, 'lower': 0.98},
            'EEM':     {'enable': False,  'sym': 'EEM',  'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'TLT':     {'enable': True,  'sym': 'TLT',  'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'GLD':     {'enable': False, 'sym': 'GLD',  'type': 'SMA_200', 'upper': 1.01, 'lower': 0.95},
            'SLV':     {'enable': False,  'sym': 'SLV',  'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'ARKG':    {'enable': True,  'sym': 'ARKG',  'type': 'SMA_50', 'upper': 1.01, 'lower': 0.96},
            'TSLA':    {'enable': True, 'sym': 'SPY',  'type': 'SMA_175', 'upper': 1.04, 'lower': 0.95},
            'MSTR':    {'enable': True,  'sym': 'GBTC', 'type': 'SMA_100', 'upper': 1.01, 'lower': 0.96},
            'GBTC':    {'enable': True,  'sym': 'GBTC', 'type': 'SMA_20', 'upper': 1.02, 'lower': 0.98},
            'ETHE':    {'enable': True,  'sym': 'ETHE', 'type': 'SMA_20', 'upper': 1.02, 'lower': 0.98},
            'BTC-USD': {'enable': True,  'sym': 'BTC-USD', 'type': 'SMA_20', 'upper': 1.02, 'lower': 0.98},
            'ETH-USD': {'enable': True,  'sym': 'ETH-USD', 'type': 'SMA_20', 'upper': 1.02, 'lower': 0.98},
            'LUNA1-USD': {'enable': True,  'sym': 'LUNA1-USD', 'type': 'SMA_20', 'upper': 1.02, 'lower': 0.98},
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
        month = int(date_dt.strftime('%m'))
        year = int(date_dt.strftime('%Y'))
        if (self.first_run):
            self.current_month = month
            self.current_year = year

        if (self.addcash_period == 'monthly'):
            if (self.current_month != month):
                self.current_month = month
                self.broker.add_cash(int(self.addcash_amount))
        elif (self.addcash_period == 'yearly'):
            if (self.current_year != year):
                self.current_year = year
                self.broker.add_cash(int(self.addcash_amount))
        else:
            print("Requires 'monthly' or 'yearly' for contribution period")
            exit(0)

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
        for symbol in self.ticker:
            if self.ticker[symbol]['ma_enable'] == True:
                risk_off = (
                    self.ticker[symbol]['price'] < self.ticker[symbol]['ma'] * self.ticker[symbol]['ma_lower']
                    and self.ticker[symbol]['ppo'] < 0.75
                    and self.ticker[symbol]['rsi'] > 22
                )
                risk_on = (
                    self.ticker[symbol]['price'] >= self.ticker[symbol]['ma'] * self.ticker[symbol]['ma_upper']
                    or self.ticker[symbol]['ppo'] > 1.0
                    or self.ticker[symbol]['rsi'] < 21
                )

                if (risk_off):
                    self.target_update[symbol] = 0
                    self.risk_on[symbol] = False
                elif (risk_on or self.risk_on[symbol]):
                    self.target_update[symbol] = self.target[symbol]
                    self.risk_on[symbol] = True
                else:
                    self.target_update[symbol] = 0
                    self.risk_on[symbol] = False

        # update cash at broker
        cash = self.broker.getcash()

        # aggregate target positions from aliases
        target_positions = {}
        for target in self.target:
            name = target.split('--')[0] # deconstruct alias
            if name not in target_positions:
                target_positions[name] = self.target_update[target]
            else:
                target_positions[name] += self.target_update[target]

        # update portfolio holdings from broker
        for data in self.datas:
            if (data._name in target_positions):
                self.portfolio[data._name] = {'shares': self.broker.getposition(data).size, 'last_price': data.close[0]}

        # check if portfolio need rebalancing based on time or bands
        if (self.rebalance_days > 0):
            if (self.count % self.rebalance_days == 0):
                rebalance = True
            else:
                rebalance = False
            self.count += 1
        else:
            rebalance = self.rb.rebalance_bands(cash, self.portfolio, target_positions)

        if (rebalance or self.first_run):
            print(date + ": " + str(self.target_update))

            # generate trades to rebalance back to the updated target allocation
            trades = self.rb.rebalance(cash, self.portfolio, target_positions)

            # process sell orders
            for data in self.datas:
                if (data._name in trades and trades[data._name]['action'] == 'SELL'):
                    size = trades[data._name]['amount'] / self.portfolio[data._name]['last_price']

                    # round up to make sure we sell enough to cover our buys
                    if data._name.endswith('-USD'):
                        size = round_up(size, 2)
                    else:
                        size = round_up(size, 0)

                    if size > self.broker.getposition(data).size:
                        size = self.broker.getposition(data).size

                    if size == 0:
                        continue

                    self.order = self.sell(data=data, size=size)

                    if not self.p.optimizer:
                        print("{}: SELL {} {} shares at {}".format(
                            date, "%5s" % data._name,"%9d" % self.order.size, "%7.2f" % data.close[0]))
                        self.rows.append("{},{},{},{},{}".format(date, "SELL", data._name, self.order.size, data.close[0]))

            # process buy orders
            for data in self.datas:
                if (data._name in trades and trades[data._name]['action'] == 'BUY'):
                    size = trades[data._name]['amount'] / self.portfolio[data._name]['last_price']

                    # round down to avoid using too much cash
                    if data._name.endswith('-USD'):
                        size = round_down(size, 2)
                    else:
                        size = round_down(size, 0)

                    if size == 0:
                        continue

                    self.order = self.buy(data=data, size=size)
 
                    if not self.p.optimizer:
                        print("{}:  BUY {} {} shares at {}".format(
                            date, "%5s" % data._name,"%9d" % self.order.size, "%7.2f" % data.close[0]))
                        self.rows.append("{},{},{},{},{}".format(date, "BUY", data._name, self.order.size, data.close[0],))

        if (self.p.args.tearsheet):
            gain = (self.broker.getvalue() - self.portvalue) / self.portvalue
            self.gains.append(float(gain))
            self.dates.append(date)
            self.portvalue = self.broker.getvalue()
        
        self.first_run = False

    def stop(self):
        if (self.p.args.tearsheet):
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
