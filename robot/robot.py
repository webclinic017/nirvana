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
import brokers

def get_active_accounts(broker, configured_accounts):
    broker_accounts = broker.get_managed_accounts()

    active_accounts = {}
    for account in broker_accounts:
        if account in configured_accounts:
            desc = configured_accounts[account]['desc']
            email = configured_accounts[account]['email']
            portfolio = configured_accounts[account]['portfolio']
            if 'cash_reserve' in configured_accounts[account]:
                cash_reserve = configured_accounts[account]['cash_reserve']
            else:
                cash_reserve = 0

            available_cash = broker.get_available_cash(account)
            if (cash_reserve > available_cash):
                total_cash = 0
            else:
                total_cash = int((available_cash - cash_reserve) * 100) / 100 # 2 decimal places

            active_accounts[account] = {
                'desc': desc,
                'email': email,
                'portfolio': portfolio,
                'total_cash': total_cash
            }
        else:
            print("Account " + str(account) + "is not configured for trading")

    return active_accounts

def print_positions(broker, active_accounts):
    for account in active_accounts:
        print('  xxxxx' + account[5:] + ' ' + active_accounts[account]['desc'])
        print('    ' + 'cash = ' + str(active_accounts[account]['total_cash']))
        positions = broker.get_positions(account)
        print(positions)

def parse_args(pargs=None):
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='Robot Trader')

    parser.add_argument('--positions', action='store_true', help='Print portfolio positions')
    parser.add_argument('--test', action='store_true', help='Test mode')

    if pargs is not None:
        return parser.parse_args(pargs)

    return parser.parse_args()

def main(args=None):
    args = parse_args(args)

    with open('config.json', 'r') as f:
        config = json.load(f)

    if config['broker'] == 'InteractiveBrokers':
        broker = brokers.InteractiveBrokers()
    elif config['broker'] == 'TDAmeritrade':
        broker = brokers.TDAmeritrade()
    else:
        print("No valid broker configured in config.json")
        exit(1)

    active_accounts = get_active_accounts(broker, config['accounts'])

    if (args.positions):
        print_positions(broker, active_accounts)

    for account in active_accounts:
        portfolio = {}
        print('Account: ' + account)
        pprint.pprint(active_accounts[account])

        # update portfolio holdings at broker
        positions = broker.get_positions(account)
        #[Position(account='DU4980388', 
        # contract=Stock(conId=349966059, symbol='GBTC', exchange='PINK', currency='USD', localSymbol='GBTC', tradingClass='PRIMQX'), 
        # position=100.0, avgCost=28.45)]
        for position in positions:
            symbol = position.contract.symbol
            size = position.position
            print(broker.get_historical_data(symbol))
            if (symbol in active_accounts[account]['portfolio']):
                portfolio[symbol] = {'shares': size, 'last_price': broker.get_quote(symbol)}
        
        cash = active_accounts[account]['total_cash']
        print(portfolio)
        # TODO: update target allocations based on rules

        rb = rebalancer.Rebalancer(absolute_deviation_limit = 0.05, relative_deviation_limit = 0.25)

        # check if any positions in portfolio are outside rebalancing bands using updated positions and target allocations
        rebalance_bands = rb.rebalance_bands(cash, portfolio, active_accounts[account]['portfolio'])

        if (rebalance_bands):
            # generate trades to rebalance back to the updated target allocation
            trades = rb.rebalance(cash, portfolio, active_accounts[account]['portfolio'])

            # process sell orders
            for symbol in trades:
                if (trades[symbol]['action'] == 'SELL'):
                    shares = int(math.ceil(trades[symbol]['amount'] / portfolio[symbol]['last_price']))
                    if shares > portfolio[symbol]['shares']:
                        shares = int(portfolio[symbol]['shares'])
                    if shares < 1:
                        continue
                    broker.place_sell_order(account, symbol, shares, args.test)
            
            # TODO: monitor sell orders until complete before placing buy orders

            # process buy orders
            for symbol in trades:
                if (trades[symbol]['action'] == 'BUY'):
                    shares = int(math.floor(trades[symbol]['amount'] / portfolio[symbol]['last_price']))
                    if shares == 0:
                        continue
                    broker.place_buy_order(account, symbol, shares, args.test)

    broker.disconnect()

if __name__ == "__main__":
    main()
