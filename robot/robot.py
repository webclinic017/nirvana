import os
import sys
import math
import time
import argparse
import asyncio
import json
import pprint

sys.path.insert(0, '..')
import rebalancer
import rules
import brokers

class Robot:
    def __init__(self):
        self.test = False
        self.robot_accounts = {}
        with open('config.json', 'r') as f:
            self.config = json.load(f)

        self.configured_accounts = self.config['accounts']

        if self.config['broker'] == 'InteractiveBrokers':
            self.broker = brokers.InteractiveBrokers()
        elif self.config['broker'] == 'TDAmeritrade':
            self.broker = brokers.TDAmeritrade()

        self.rp = rules.RulesProcessor(self.broker, self.config['rules'])
        self.rb = rebalancer.Rebalancer(absolute_deviation_limit = 0.05, relative_deviation_limit = 0.25)

    def set_robot_accounts(self):
        broker_accounts = self.broker.get_managed_accounts()

        for account in broker_accounts:
            if account in self.configured_accounts:
                desc = self.configured_accounts[account]['desc']
                email = self.configured_accounts[account]['email']
                portfolio = self.configured_accounts[account]['portfolio']
                if 'cash_reserve' in self.configured_accounts[account]:
                    cash_reserve = self.configured_accounts[account]['cash_reserve']
                else:
                    cash_reserve = 0

                available_cash = self.broker.get_available_cash(account)
                if (cash_reserve > available_cash):
                    total_cash = 0
                else:
                    total_cash = int((available_cash - cash_reserve) * 100) / 100 # 2 decimal places

                self.robot_accounts[account] = {
                    'desc': desc,
                    'email': email,
                    'portfolio': portfolio,
                    'total_cash': total_cash
                }
            else:
                print("Account " + str(account) + "is not configured for trading")

    def print_positions(self):
        for account in self.robot_accounts:
            print('  xxxxx' + account[5:] + ' ' + self.robot_accounts[account]['desc'])
            print('    ' + 'cash = ' + str(self.robot_accounts[account]['total_cash']))
            positions = self.broker.get_positions(account)
            for symbol in positions:
                print('    ' + symbol + " : " + str(positions[symbol]['size']) + " shares")

    def rebalance(self):
        for account in self.robot_accounts:
            portfolio = {}
            print('Account: ' + account)
            pprint.pprint(self.robot_accounts[account])

            # update portfolio holdings at broker
            positions = self.broker.get_positions(account)
            for symbol in positions:
                size = positions[symbol]['size']
                if (symbol in self.robot_accounts[account]['portfolio']):
                    portfolio[symbol] = {'shares': size, 'last_price': self.broker.get_quote(symbol)}

            for symbol in self.robot_accounts[account]['portfolio']:
                if symbol not in portfolio:
                    portfolio[symbol] = {'shares': 0, 'last_price': self.broker.get_quote(symbol)}

            print(portfolio)
            cash = self.robot_accounts[account]['total_cash']

            # update target allocations based on rules
            self.rp.update_historical_data()
            target = self.rp.apply_rules(portfolio, self.robot_accounts[account]['portfolio'])

            # check if any positions in portfolio are outside rebalancing bands using updated positions and target allocations
            rebalance_bands = self.rb.rebalance_bands(cash, portfolio, target)

            if (rebalance_bands):
                # generate orders to rebalance back to the updated target allocation
                orders = self.rb.rebalance(cash, portfolio, target)

                # process sell orders
                trades = []
                for symbol in orders:
                    if (orders[symbol]['action'] == 'SELL'):
                        last_price = portfolio[symbol]['last_price']

                        shares = int(math.ceil(orders[symbol]['amount'] / last_price))
                        if shares > portfolio[symbol]['shares']:
                            shares = int(portfolio[symbol]['shares'])
                        if shares < 1:
                            continue

                        trade = self.broker.place_sell_order(account, symbol, shares, last_price, self.test)
                        if (trade):
                            trades.append(trade)

                # wait until sell orders complete before placing buy orders
                self.broker.wait_for_trades(trades)

                # process buy orders
                trades = []
                for symbol in orders:
                    if (orders[symbol]['action'] == 'BUY'):
                        cash = orders[symbol]['amount']
                        last_price = portfolio[symbol]['last_price']
                        trade = self.broker.place_buy_order(account, symbol, cash, last_price, self.test)
                        if (trade):
                            trades.append(trade)

    def disconnect(self):
        self.broker.disconnect()

def parse_args(pargs=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='Robot Trader')

    parser.add_argument('-r', '--rebalance', action='store_true', help='Print portfolio positions')
    parser.add_argument('--positions', action='store_true', help='Print portfolio positions')
    parser.add_argument('-t', '--test', action='store_true', help='Test mode')

    if pargs is not None:
        return parser.parse_args(pargs)

    return parser.parse_args()

def main(args=None):
    args = parse_args(args)

    robot = Robot()
    robot.set_robot_accounts()

    if (args.test):
        robot.test = True

    if (args.positions):
        robot.print_positions()

    if (args.rebalance):
        robot.rebalance()

    robot.disconnect()

if __name__ == "__main__":
    main()
