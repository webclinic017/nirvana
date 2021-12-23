import os
import sys
sys.path.append(os.path.abspath('../lib'))
import pandas as pd
import argparse
import backtrader as bt
import datetime
import math
import numpy
from strategies import Nirvana
from strategies import SMACrossover
from strategies import GuardDog
from strategies import BuyHold
from analyzers import CAGRAnalyzer
from backtrader.feeds import GenericCSVData

class LongOnly(bt.Sizer):
    params = (('portfolio', {}),)
    def _getsizing(self, comminfo, cash, data, isbuy):
        if isbuy:
            percent = self.p.portfolio[data._name] / 100.0
            divide = math.floor((cash * percent) / data.close[0])
            self.p.stake = divide

            # Remove shares if cost is more than available cash. This can happen due to 
            # rounding/truncation of share price.
            while (self.p.stake * data.close[0] > cash):
                self.p.stake -= 1

            return self.p.stake
        # Sell situation
        position = self.broker.getposition(data)
        print(position)
        if not position.size:
            return 0  # do not sell if nothing is open
        return self.p.stake

def backtest(a, b, c, d, optimizer=False, args=None):
    cerebro = bt.Cerebro()
    cerebro.broker.set_coc(True) # cheat-on-close, othersize places order at open price the next day
    cerebro.broker.set_cash(int(args.setcash))
    comminfo = bt.commissions.CommInfo_Stocks_Perc(commission=0.0, percabs=True)

    cerebro.broker.addcommissioninfo(comminfo)

    dkwargs = dict()
    if args.fromdate is not None:
        fromdate = datetime.datetime.strptime(args.fromdate, '%Y-%m-%d')
        dkwargs['fromdate'] = fromdate

    if args.todate is not None:
        todate = datetime.datetime.strptime(args.todate, '%Y-%m-%d')
        dkwargs['todate'] = todate

    if (not args.portin and not args.portout):
        print("Must supply --portin, --portout or both. Use --help for more info.")
        exit()

    portin = {}
    if (args.portin):
        positions = args.portin.split(',')
        for position in positions:
            ticker, allocation = position.split('/')
            portin[ticker] = float(allocation)

    portout = {}
    if (args.portout):
        positions = args.portout.split(',')
        for position in positions:
            ticker, allocation = position.split('/')
            portout[ticker] = float(allocation)

    tickers = []
    for ticker in portin:
        if ticker not in tickers:
            tickers.append(ticker)

    for ticker in portout:
        if ticker not in tickers:
            tickers.append(ticker)

    for ticker in tickers:
        data = bt.feeds.YahooFinanceCSVData(dataname='history/' + ticker + '.csv', **dkwargs)
        if (ticker != args.benchmark): # need to add benchmark data last so skip here
            cerebro.adddata(data, name=ticker)

    data = bt.feeds.YahooFinanceCSVData(dataname='history/' + args.benchmark + '.csv', **dkwargs)
    cerebro.adddata(data, name=args.benchmark)

    if (args.buyhold):
        cerebro.addstrategy(BuyHold, portfolio=portin)
    else:
        cerebro.addstrategy(Nirvana, a=a, b=b, c=c, d=d,
            optimizer=optimizer, portfolio=portin, tearsheet=args.tearsheet, args=args)

    cerebro.addsizer(LongOnly, portfolio=portin)

    cerebro.addanalyzer(CAGRAnalyzer)

    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='alltime_roi', 
                        timeframe=bt.TimeFrame.NoTimeFrame)

    cerebro.addanalyzer(bt.analyzers.TimeReturn, data=data, _name='benchmark', 
                        timeframe=bt.TimeFrame.Years)

    cerebro.addanalyzer(bt.analyzers.TimeReturn, timeframe=bt.TimeFrame.Years)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, timeframe=bt.TimeFrame.Years,
                        riskfreerate=0.01)

    cerebro.addanalyzer(bt.analyzers.SQN)

    cerebro.addanalyzer(bt.analyzers.DrawDown)

    cerebro.addobserver(bt.observers.DrawDown)

    results = cerebro.run()

    st0 = results[0]

    if (optimizer == False):
        for analyzer in st0.analyzers:
            analyzer.print()

    end_value = cerebro.broker.getvalue()
    max_drawdown = st0.analyzers.drawdown.get_analysis().max.drawdown
    start_date = st0.analyzers.cagranalyzer.rets.start_date
    end_date = st0.analyzers.cagranalyzer.rets.end_date

    if (optimizer == False):
        print("\nend_value: " + "%.2f" % end_value + ", max_drawdown: " + "%.2f" % max_drawdown + 
            "% [" + str(start_date) + " to " + str(end_date) + "]")

    if (args.plot and not optimizer):
        cerebro.plot()

    return end_value, max_drawdown

def parse_args(pargs=None):

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='VixRay backtest simulator')

    parser.add_argument('--fromdate', required=False, default='1993-01-29',help='Starting date in YYYY-MM-DD format')
    parser.add_argument('--todate', required=False, default=None, help='Ending date in YYYY-MM-DD format')
    parser.add_argument('-p', '--plot', action='store_true', help='Plot results')
    parser.add_argument('-b', '--buyhold', action='store_true', help='Buy and Hold backtest')
    parser.add_argument('-f', '--finetune', action='store_true', help='Perform fine tune adjustments for a,b,c,d')
    parser.add_argument('--parameters', required=False, default=None, help='Parameters string "a,b,c,d"')
    parser.add_argument('--portin', required=False, default=None, help='Portfolio ie. "TQQQ/50,SPXL/50"')
    parser.add_argument('--portout', required=False, default=None, help='Portfolio ie. "TQQQ/50,SPXL/50"')
    parser.add_argument('--benchmark', required=False, default='SPY', help='Benchmark ticker to use')
    parser.add_argument('--setcash', required=False, default='100000', help='Starting cash available')
    parser.add_argument('--addcash', required=False, default='monthly/0', help='Add cash periodically (ie, "montly/100" or "yearly/1000")')
    parser.add_argument('-t', '--tearsheet', action='store_true', help='Generate tearsheet (performance.html)')
    parser.add_argument('-m', '--model', action='store_true', help='Trade TMF on 180-day moving average')
    parser.add_argument('-s', '--seasonality', action='store_true', help='Skip buying in September')

    if pargs is not None:
        return parser.parse_args(pargs)

    return parser.parse_args()

def main(args=None):
    args = parse_args(args)

    if (args.parameters):
        parameters = args.parameters.split(',')
        a = float(parameters[5])
        b = float(parameters[6])
        c = float(parameters[7])
        d = float(parameters[8])
    else:

        a = 0.0
        b = 0.0
        c = 0.0
        d = 0.0

    end_value, max_drawdown = backtest(a, b, c, d, optimizer=False, args=args)

if __name__ == "__main__":
    main()
