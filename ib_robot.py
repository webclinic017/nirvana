import os
import sys

from ib_insync import IB, LimitOrder, Stock, util
from random import choice
import pprint
import math

import argparse
import asyncio
import json
import pprint

import pandas as pd
import time
import math
import rebalancer

f = open('ib_accounts.json',)
accounts_config = json.load(f)
f.close()

def get_accounts_config():
    f = open('ib_accounts.json',)
    accounts_config = json.load(f)

    return accounts_config

def ib_available_cash(ib, account):
    avs = ib.accountValues(account)

    for i in range(len(avs)):
        print(avs[i])
        if avs[i].tag == "AvailableFunds":
            available_funds = float(avs[i].value)
    return available_funds

def ib_get_quote(ib, symbol):
    contract = Stock(symbol=symbol, exchange='SMART', currency='USD')
    # print(contract)
    d = ib.reqMktData(contract, symbol, snapshot=True, regulatorySnapshot=False)

    while (util.isNan(d.last)):
        ib.sleep(0.1)

    # bars = ib.reqHistoricalData(
    #         contract,
    #         endDateTime='',
    #         durationStr='1 D',
    #         barSizeSetting='1 min',
    #         whatToShow='MIDPOINT',
    #         useRTH=False,
    #         formatDate=1)
    # df = util.df(bars)

    # print("current price:", df.close.iloc[-1])
    # print(df.close.iloc[-1])

    return d.last


def get_ib_accounts(ib, accounts_config):

    ib_accounts = ib.managedAccounts()

    accounts = {}
    for account in ib_accounts:
        acct_type = 'MARGIN'
        if (acct_type == 'MARGIN'):
            available_funds = ib_available_cash(ib, account)
        elif (acct_type == 'CASH'):
            print('CASH accounts are not supported')
            continue
        
        if account in accounts_config:
            if 'cash_reserve' in accounts_config[account]:
                cash_reserve = accounts_config[account]['cash_reserve']
            else:
                cash_reserve = 0
            email = accounts_config[account]['email']
            portfolio = accounts_config[account]['portfolio']
        else:
            cash_reserve = 0
            email = ''
            portfolio = []

        if (cash_reserve > available_funds):
            total_cash = 0
        else:
            total_cash = int((available_funds - cash_reserve) * 100)/100

        accounts[account] = {
            'type': acct_type,
            'total_cash': total_cash,
            'email': email,
            'portfolio': portfolio
        }

    return accounts

def get_buy_orders():
    accounts_config = get_accounts_config()
    accounts = get_ib_accounts(accounts_config)

    orders = []
    for account in accounts:

        if account not in accounts_config:
            continue

        print('xxxxx' + account[5:] + ' ' + accounts_config[account]['desc'])
        email = accounts[account]['email']
        for position in accounts[account]['portfolio']:
            symbol = position['symbol']
            cash = (position['percentage'] / 100) * accounts[account]['total_cash']
            print('  BUY ' + symbol + ' (amount = $' + str(cash) + ')')
            orders.append([account, symbol, cash, email])
    
    return orders

def get_sell_orders():
    accounts_config = get_accounts_config()
    accounts = get_ib_accounts(accounts_config)

    orders = []
    for account in accounts:

        if account not in accounts_config:
            continue
        
        ib_positions = ib.positions(account)
        print(ib_positions)
    
        print('xxxxx' + account[5:] + ' ' + accounts_config[account]['desc'])
        email = accounts[account]['email']

        for ib_position in ib_positions:
            print(ib_position.position)
            symbol = ib_position.contract.symbol
            shares = ib_position.position

            for position in accounts[account]['portfolio']:
                if symbol == position['symbol']:
                    print('  SELL ' + symbol + ' (shares ' + str(shares) + ')')
                    orders.append([account, symbol, shares, email])

    return orders

def place_buy_order(ib, acct_id, symbol, cash, email, test=False):

    price = ib_get_quote(symbol)
    limit_price = price * 1.01
    limit_price = math.ceil(limit_price*100)/100
    shares = math.floor(cash/limit_price)

    if (shares < 1):
        return

    contract = Stock(symbol, 'SMART', 'USD')
    order = LimitOrder('BUY', shares, limit_price, account=acct_id, tif='GTC', outsideRth=True)

    pprint.pprint(order)

    if (test):
        return

    trade = ib.placeOrder(contract, order)

    print(trade)
    return trade


def place_sell_order(ib, acct_id, symbol, shares, email, test=False):
    if (shares < 1):
        return

    price = ib_get_quote(symbol)
    limit_price = price * 0.99
    limit_price = math.floor(limit_price*100)/100

    contract = Stock(symbol, 'SMART', 'USD')
    order = LimitOrder('SELL', shares, limit_price, account=acct_id, tif='GTC', outsideRth=True)
    pprint.pprint(order)

    if (test):
        return

    trade = ib.placeOrder(contract, order)

    print(trade)

    time.sleep(5)

    trade = ib.openTrades()
    return trade

def print_ib_positions():
    print("Not implemented")
    # accounts_config = get_accounts_config()
    # accounts = get_ib_accounts(accounts_config)
    # for account in accounts:
    #     info = c.get_account(account_id=account,fields=[c.Account.Fields.POSITIONS])
    #     assert info.status_code == 200, info.raise_for_status()
    #     info = info.json()

    #     if account not in accounts_config:
    #         continue

    #     print('  xxxxx' + account[5:] + ' ' + accounts_config[account]['desc'])
    #     print('    ' + 'cash = ' + str(accounts[account]['total_cash']))
    #     if 'positions' in info['securitiesAccount']:
    #         for position in info['securitiesAccount']['positions']:
    #             symbol = position['instrument']['symbol']
    #             shares = position['longQuantity']
    #             for position in accounts[account]['portfolio']:
    #                 if symbol == position['symbol']:
    #                     print('    ' + symbol + ' (shares ' + str(shares) + ')')

def parse_args(pargs=None):

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='IB Robot Trader')

    parser.add_argument('--forcebuy', action='store_true', help='Force buy')
    parser.add_argument('--forcesell', action='store_true', help='Force sell')
    parser.add_argument('--positions', action='store_true', help='Print portfolio positions')
    parser.add_argument('--test', action='store_true', help='Test mode')

    if pargs is not None:
        return parser.parse_args(pargs)

    return parser.parse_args()

def main(args=None):
    args = parse_args(args)

    rb = rebalancer.Rebalancer(absolute_deviation_limit = 0.05, relative_deviation_limit = 0.25)

    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)
    # ib.sleep(5)

    accounts = get_ib_accounts(ib, accounts_config)

    for account in accounts:
        print('Account: ' + account)
        pprint.pprint(accounts[account])

        if (args.positions):
            print_ib_positions()
        
        # exit(0)

        # update portfolio holdings at broker
        # for data in self.datas:
        #     if (data._name in self.target):
        #         portfolio[data._name] = {'shares': self.broker.getposition(data).size, 'last_price': data.close[0]}

        # check if any positions in portfolio are outside rebalancing bands using updated positions and target allocations
        # rebalance_bands = rb.rebalance_check(cash, portfolio, self.target_update)

        # if (rebalance_bands or rebalance_ma):
        #     print("rebalance_bands: " + str(rebalance_bands) + " rebalance_ma: " + str(rebalance_ma) + " (cash = " + str(cash) + ")")

        #     # generate trades to rebalance back to the updated target allocation
        #     trades = rb.rebalance(self.portfolio, self.target_update)

        #     # process sell orders
        #     for data in self.datas:
        #         if (data._name in trades and trades[data._name]['action'] == 'SELL'):
        #             size = math.ceil(trades[data._name]['amount'] / self.portfolio[data._name]['last_price'])
        #             if size > self.broker.getposition(data).size:
        #                 size = self.broker.getposition(data).size
        #             if int(size) < 1:
        #                 continue

        #             self.order = self.sell(data=data, size=int(size))

        #             if not self.p.optimizer:
        #                 print("{}: SELL {} {} shares at {}".format(
        #                     date, "%5s" % data._name,"%9d" % self.order.size, "%7.2f" % data.close[0]))



    # if (args.forcebuy):
    #     print("Force buying")
    #     buy_orders = get_buy_orders()
    #     for order in buy_orders:
    #         account = order[0]
    #         symbol = order[1]
    #         cash = order[2]
    #         email = order[3]
    #         place_buy_order(account, symbol, cash, email, args.test)
    # elif (args.forcesell):
    #     print("Force selling")
    #     sell_orders = get_sell_orders()
    #     for order in sell_orders:
    #         account = order[0]
    #         symbol = order[1]
    #         shares = order[2]
    #         email = order[3]
    #         place_sell_order(account, symbol, shares, email, args.test)
    
    # time.sleep(1)
    for x in range(1, 10):
        for symbol in ['SPY', 'GBTC', 'ETHE']:
            print(ib_get_quote(ib, symbol))
    ib.disconnect()

if __name__ == "__main__":
    main()
