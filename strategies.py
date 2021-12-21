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

        self.df_spy = pd.read_csv("history/SPY.csv").set_index("Date")
        self.df_spxl = pd.read_csv("history/SPXL.csv").set_index("Date")
        self.df_tqqq = pd.read_csv("history/TQQQ.csv").set_index("Date")
        self.df_gbtc = pd.read_csv("history/GBTC.csv").set_index("Date")
        self.df_ethe = pd.read_csv("history/ETHE.csv").set_index("Date")
        self.df_gld = pd.read_csv("history/GLD.csv").set_index("Date")
        self.df_ugl = pd.read_csv("history/UGL.csv").set_index("Date")
        self.df_tlt = pd.read_csv("history/TLT.csv").set_index("Date")
        self.df_tmf = pd.read_csv("history/TMF.csv").set_index("Date")
        self.df_tsla = pd.read_csv("history/TSLA.csv").set_index("Date")

        if not self.p.optimizer:
            self.rows = []
            self.rows.append("Date,Transaction,Ticker,Shares,Price")
        self.buy_price = {}
        self.first_run = True

        if (self.p.tearsheet):
            self.portvalue = self.broker.getvalue()
            self.gains = []
            self.dates = []

        self.target = self.p.portin.copy()
        self.target['CASHX'] = 0
        print(self.target)
        self.target_update = self.target.copy()
        self.portfolio = {}
        self.rb = rebalancer.Rebalancer(absolute_deviation_limit = 0.05, relative_deviation_limit = 0.25)

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

        if 'SPY' in self.target:
            spy_price = self.df_spy.loc[date]['Adj Close']
            spy_sma_200 = self.df_spy.loc[date]['SMA_180']
        if 'SPXL' in self.target:
            spxl_price = self.df_spxl.loc[date]['Adj Close']
            sma_200 = self.df_spxl.loc[date]['SMA_180']
        if 'TQQQ' in self.target:
            tqqq_price = self.df_tqqq.loc[date]['Adj Close']
            tqqq_sma_200 = self.df_tqqq.loc[date]['SMA_180']
        if 'TLT' in self.target:
            tlt_price = self.df_tlt.loc[date]['Adj Close']
            tlt_sma_200 = self.df_tlt.loc[date]['SMA_180']
        if 'TMF' in self.target:
            tmf_price = self.df_tmf.loc[date]['Adj Close']
            tmf_sma_200 = self.df_tmf.loc[date]['SMA_180']
        if 'GBTC' in self.target:
            gbtc_price = self.df_gbtc.loc[date]['Adj Close']
            gbtc_sma_200 = self.df_gbtc.loc[date]['SMA_50']
        if 'ETHE' in self.target:
            ethe_price = self.df_ethe.loc[date]['Adj Close']
            ethe_sma_200 = self.df_ethe.loc[date]['SMA_100']
        if 'GLD' in self.target:
            gld_price = self.df_gld.loc[date]['Adj Close']
            gld_sma_200 = self.df_gld.loc[date]['SMA_180']
        if 'UGL' in self.target:
            ugl_price = self.df_ugl.loc[date]['Adj Close']
            ugl_sma_200 = self.df_ugl.loc[date]['SMA_180']
        if 'TSLA' in self.target:
            tsla_price = self.df_tsla.loc[date]['Adj Close']
            tsla_sma_200 = self.df_tsla.loc[date]['SMA_180']

        if self.first_run:
            if 'SPY' in self.target:
                self.spy_sma_above = spy_price >= spy_sma_200 * 1.0
                if not self.spy_sma_above:
                    self.target_update['SPY'] = 0
            if 'SPXL' in self.target:
                self.sma_above = spxl_price >= sma_200 * 1.0
                if not self.sma_above:
                    self.target_update['SPXL'] = 0
            if 'TQQQ' in self.target:
                self.tqqq_sma_above = tqqq_price >= tqqq_sma_200 * 1.0
                if not self.tqqq_sma_above:
                    self.target_update['TQQQ'] = 0
            if 'TLT' in self.target:
                self.tlt_sma_above = tlt_price >= tlt_sma_200 * 1.0
                if not self.tlt_sma_above:
                    self.target_update['TLT'] = 0
            if 'TMF' in self.target:
                self.tmf_sma_above = tmf_price >= tmf_sma_200 * 1.0
                if not self.tmf_sma_above:
                    self.target_update['TMF'] = 0
            if 'GBTC'in self.target:
                self.gbtc_sma_above = gbtc_price >= gbtc_sma_200 * 1.0
                if not self.gbtc_sma_above:
                    self.target_update['GBTC'] = 0
            if 'ETHE' in self.target:
                self.ethe_sma_above = ethe_price >= ethe_sma_200 * 1.0
                if not self.ethe_sma_above:
                    self.target_update['ETHE'] = 0
            if 'GLD' in self.target:
                self.gld_sma_above = gld_price >= gld_sma_200 * 1.0
                if not self.gld_sma_above:
                    self.target_update['GLD'] = 0
            if 'UGL' in self.target:
                self.ugl_sma_above = ugl_price >= ugl_sma_200 * 1.0
                if not self.ugl_sma_above:
                    self.target_update['UGL'] = 0
            if 'TSLA' in self.target:
                self.tsla_sma_above = tsla_price >= tsla_sma_200 * 1.0
                if not self.tsla_sma_above:
                    self.target_update['TSLA'] = 0

        current = {}
        for symbol in self.target:
            current[symbol] = {'shares': 0, 'last_price': 0}
        
        current['CASHX'] = {'value': self.broker.getcash()}

        # Update current portfolio allocation
        for data in self.datas:
            if (data._name in self.target):
                current[data._name]['shares'] = self.broker.getposition(data).size
                current[data._name]['last_price'] = data.close[0]

        rebalance_sma = False

        if 'SPY' in self.target:
            if (spy_price < spy_sma_200 * 0.90 and self.spy_sma_above):
                self.target_update['SPY'] = 0
                rebalance_sma = True
                self.spy_sma_above = False
            elif (spy_price >= spy_sma_200 * 1.05 and not self.spy_sma_above):
                self.target_update['SPY'] = self.target['SPY']
                rebalance_sma = True
                self.spy_sma_above = True
        if 'SPXL' in self.target:
            if (spxl_price < sma_200 * 0.90 and self.sma_above):
                self.target_update['SPXL'] = 0
                rebalance_sma = True
                self.sma_above = False
            elif (spxl_price >= sma_200 * 1.05 and not self.sma_above):
                self.target_update['SPXL'] = self.target['SPXL']
                rebalance_sma = True
                self.sma_above = True
        if 'TQQQ' in self.target:
            if (tqqq_price < tqqq_sma_200 * 0.95 and self.tqqq_sma_above):
                self.target_update['TQQQ'] = 0
                rebalance_sma = True
                self.tqqq_sma_above = False
            elif (tqqq_price >= tqqq_sma_200 * 1.03 and not self.tqqq_sma_above):
                self.target_update['TQQQ'] = self.target['TQQQ']
                rebalance_sma = True
                self.tqqq_sma_above = True
        if 'TLT' in self.target:
            if (tlt_price < tlt_sma_200 * 0.90 and self.tlt_sma_above):
                self.target_update['TLT'] = 0
                rebalance_sma = True
                self.tlt_sma_above = False
            elif (tlt_price >= tlt_sma_200 * 1.05 and not self.tlt_sma_above):
                self.target_update['TLT'] = self.target['TLT']
                rebalance_sma = True
                self.tlt_sma_above = True
        if 'TMF' in self.target:
            if (tmf_price < tmf_sma_200 * 0.90 and self.tmf_sma_above):
                self.target_update['TMF'] = 0
                rebalance_sma = True
                self.tmf_sma_above = False
            elif (tmf_price >= tmf_sma_200 * 1.05 and not self.tmf_sma_above):
                self.target_update['TMF'] = self.target['TMF']
                rebalance_sma = True
                self.tmf_sma_above = True
        if 'GBTC' in self.target:
            if (gbtc_price < gbtc_sma_200 * 0.9 and self.gbtc_sma_above):
                self.target_update['GBTC'] = 0
                rebalance_sma = True
                self.gbtc_sma_above = False
            elif (gbtc_price >= gbtc_sma_200 * 1.05 and not self.gbtc_sma_above):
                self.target_update['GBTC'] = self.target['GBTC']
                rebalance_sma = True
                self.gbtc_sma_above = True
        if 'ETHE' in self.target:
            if (ethe_price < ethe_sma_200 * 0.9 and self.ethe_sma_above):
                self.target_update['ETHE'] = 0
                rebalance_sma = True
                self.ethe_sma_above = False
            elif (ethe_price >= ethe_sma_200 * 1.05 and not self.ethe_sma_above):
                self.target_update['ETHE'] = self.target['ETHE']
                rebalance_sma = True
                self.ethe_sma_above = True
        if 'GLD' in self.target:
            if (gld_price < gld_sma_200 * 0.9 and self.gld_sma_above):
                self.target_update['GLD'] = 0
                rebalance_sma = True
                self.gld_sma_above = False
            elif (gld_price >= gld_sma_200 * 1.05 and not self.gld_sma_above):
                self.target_update['GLD'] = self.target['GLD']
                rebalance_sma = True
                self.gld_sma_above = True
        if 'UGL' in self.target:
            if (ugl_price < ugl_sma_200 * 0.9 and self.ugl_sma_above):
                self.target_update['UGL'] = 0
                rebalance_sma = True
                self.ugl_sma_above = False
            elif (ugl_price >= ugl_sma_200 * 1.05 and not self.ugl_sma_above):
                self.target_update['UGL'] = self.target['UGL']
                rebalance_sma = True
                self.ugl_sma_above = True
        if 'TSLA' in self.target:
            if (tsla_price < tsla_sma_200 * 0.90 and self.tsla_sma_above):
                self.target_update['TSLA'] = 0
                rebalance_sma = True
                self.tsla_sma_above = False
            elif (tsla_price >= tsla_sma_200 * 1.05 and not self.tsla_sma_above):
                self.target_update['TSLA'] = self.target['TSLA']
                rebalance_sma = True
                self.tsla_sma_above = True

        rebalance = self.rb.rebalance_check(current, self.target_update)
        
        if (rebalance or rebalance_sma or self.first_run):
            print("rebalance: " + str(rebalance) + " rebalance_sma: " + str(rebalance_sma))
            print("Cash = " + str(current['CASHX']))
            trades = self.rb.rebalance(current, self.target_update)

            for data in self.datas:
                if (data._name in trades and trades[data._name]['action'] == 'SELL'):
                    size = math.ceil(trades[data._name]['amount'] / current[data._name]['last_price'])
                    if size > self.broker.getposition(data).size:
                        size = self.broker.getposition(data).size
                    if int(size) < 1:
                        continue

                    self.order = self.sell(data=data, size=int(size))

                    if not self.p.optimizer:
                        print("{}: SELL {} {} shares at {}".format(
                            date, "%5s" % data._name,"%9d" % self.order.size, "%7.2f" % data.close[0]))
                        self.rows.append("{},{},{},{},{}".format(date, "SELL", data._name, self.order.size, data.close[0]))
    
            for data in self.datas:
                if (data._name in trades and trades[data._name]['action'] == 'BUY'):
                    size = math.floor(trades[data._name]['amount'] / current[data._name]['last_price'])
                    if size == 0:
                        continue

                    self.order = self.buy(data=data, size=size)
 
                    if not self.p.optimizer and self.order:
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
