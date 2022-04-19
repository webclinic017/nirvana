import math
import pprint
import time
import pandas as pd

from tda.auth import easy_client
from tda import client
from tda.client import Client
from tda.orders.equities import equity_buy_limit, equity_sell_limit
from tda.orders.common import Duration, Session
from tda.utils import Utils

from ib_insync import IB, LimitOrder, Stock, util

def chrome_webdriver():
    from selenium import webdriver

    options = webdriver.chrome.options.Options()
    # options.headless = True
    return webdriver.Chrome(options=options)

class TDAmeritrade():
    def __init__(self, api_key=None):
        self.tda = easy_client(
            webdriver_func=chrome_webdriver,
            api_key=api_key,
            redirect_uri='https://localhost',
            token_path='token.pickle')
        self.managed_accounts = {}

    def connect(self):
        pass

    def disconnect(self):
        pass

    def get_managed_accounts(self):
        r = self.tda.get_accounts()
        assert r.status_code == 200, r.raise_for_status()
        pprint.pprint(r.json())

        for account in r.json():
            account_id = account['securitiesAccount']['accountId']
            available_cash = account['securitiesAccount']['currentBalances']['availableFundsNonMarginableTrade']

            self.managed_accounts[account_id] = {}
            self.managed_accounts[account_id]['available_cash'] = available_cash

        return self.managed_accounts

    def get_account_summary(self, account):
        pass

    def get_positions(self, account):
        info = self.tda.get_account(account_id=account, fields=[self.tda.Account.Fields.POSITIONS])
        assert info.status_code == 200, info.raise_for_status()
        info = info.json()

        positions_dict = {}
        if 'positions' in info['securitiesAccount']:
            for position in info['securitiesAccount']['positions']:
                symbol = position['instrument']['symbol']
                size = position['longQuantity']
                positions_dict[symbol] = {'size': size}

        return positions_dict

    def get_available_cash(self, account):
        return self.managed_accounts[account]['available_cash']

    def get_quote(self, symbol):
        attempts = 3
        while (attempts > 0):
            try:
                price = self.tda.get_quote(symbol).json()[symbol]['lastPrice']
                break
            except:
                attempts -= 1
                if attempts == 0:
                    return
                time.sleep(1)

        return price

    def get_historical_data(self, symbol, duration='200 D', bar_size = '1 day'):
        resp = self.tda.get_price_history(symbol,
                period_type=Client.PriceHistory.PeriodType.YEAR,
                period=Client.PriceHistory.Period.ONE_YEAR,
                frequency_type=Client.PriceHistory.FrequencyType.DAILY,
                frequency=Client.PriceHistory.Frequency.DAILY)
        assert resp.status_code == 200
        data = resp.json()
        df = pd.json_normalize(data['candles'])

        return df

    def get_open_trades(self):
        pass

    def place_buy_order(self, account, symbol, cash, price, test=False):
        limit_price = price * 1.01
        limit_price = math.ceil(limit_price * 100) / 100
        shares = math.floor(cash / limit_price)

        if (shares < 1):
            return

        builder = equity_buy_limit(symbol, shares, limit_price)
        builder.set_duration(Duration.GOOD_TILL_CANCEL)

        builder.set_session(Session.SEAMLESS) # AM, PM, NORMAL, SEAMLESS
        build = builder.build()

        duration = build['duration']
        instruction = build['orderLegCollection'][0]['instruction']
        print("{}: {} {}".format(account, instruction, duration))

        if (test):
            return

        r = self.tda.place_order(account, build)
        try:
            order_id = Utils(self.tda, account).extract_order_id(r)
        except:
            return -1

        r = self.tda.get_order(order_id, account)

        order_info = r.json()
        order_info['accountId'] = 'xxxxx' + str(order_info['accountId'])[5:]
        order_info.pop('tag', None)
        pprint.pprint(order_info)

        return order_info

    def place_sell_order(self, account, symbol, shares, last_price, test=False):
        if (shares < 1):
            return

        limit_price = last_price * 0.99
        limit_price = math.floor(limit_price * 100) / 100

        builder = equity_sell_limit(symbol, shares, limit_price)
        builder.set_duration(Duration.GOOD_TILL_CANCEL)
        builder.set_session(Session.NORMAL)

        pprint.pprint(builder.build())

        if (test):
            return

        r = self.tda.place_order(account, builder.build())
        try:
            order_id = Utils(self.tda, account).extract_order_id(r)
        except:
            return -1
        r = self.tda.get_order(order_id, account)

        pprint.pprint(r.json())
        order_info = r.json()
        order_info['accountId'] = 'xxxxx' + str(order_info['accountId'])[5:]
        order_info.pop('tag', None)
        pprint.pprint(order_info)

        return order_info

    def wait_for_trades(self, trades):
        pass

class InteractiveBrokers():
    def __init__(self):
        self.ib = IB()
        self.connect()

    def connect(self):
        # gateway: port 4001 (live), port 4002 (paper)
        #     tws: port 7496 (live), port 7497 (paper)
        self.ib.connect('127.0.0.1', port=7497, clientId=1)
    
    def disconnect(self):
        self.ib.disconnect()

    def get_managed_accounts(self):
        return self.ib.managedAccounts()

    def get_account_summary(self, account):
        return self.ib.accountSummary(account)

    def get_positions(self, account):
        positions = self.ib.positions(account)

        positions_dict = {}
        for position in positions:
            symbol = position.contract.symbol
            size = position.position
            positions_dict[symbol] = {'size': size}

        return positions_dict

    def get_available_cash(self, account):
        avs = self.ib.accountValues(account)
        for i in range(len(avs)):
            if avs[i].tag == "TotalCashBalance" and avs[i].currency == "USD":
                available_cash = float(avs[i].value)
        return available_cash

    def get_quote(self, symbol):
        contract = Stock(symbol=symbol, exchange='SMART', currency='USD')
        self.ib.qualifyContracts(contract)
        self.ib.reqMarketDataType(2) # 2 = Frozen
        data = self.ib.reqMktData(contract, symbol, snapshot=True, regulatorySnapshot=False)

        # TODO: add timeout or max attempts
        while util.isNan(data.last):
            self.ib.sleep(0.1)

        return data.marketPrice()

    def get_historical_data(self, symbol, duration='200 D', bar_size = '1 day'):
        contract = Stock(symbol=symbol, exchange='SMART', currency='USD')
        self.ib.qualifyContracts(contract)
        bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='MIDPOINT',
                useRTH=False,
                formatDate=1)
        df = util.df(bars)

        return df

    def get_open_trades(self):
        return self.ib.openTrades()

    def place_buy_order(self, account, symbol, cash, price, test=False):
        limit_price = price * 1.01
        limit_price = math.ceil(limit_price * 100) / 100
        shares = math.floor(cash / limit_price)

        if (shares < 1):
            return

        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)
        order = LimitOrder('BUY', shares, limit_price, account=account, tif='GTC', outsideRth=True)
        pprint.pprint(order)

        if (test):
            return

        return self.ib.placeOrder(contract, order)

    def place_sell_order(self, account, symbol, shares, last_price, test=False):
        if (shares < 1):
            return

        limit_price = last_price * 0.99
        limit_price = math.floor(limit_price * 100) / 100

        contract = Stock(symbol, 'SMART', 'USD')
        self.ib.qualifyContracts(contract)

        order = LimitOrder('SELL', shares, limit_price, account=account, tif='GTC', outsideRth=True)
        pprint.pprint(order)

        if (test):
            return

        return self.ib.placeOrder(contract, order)

    def wait_for_trades(self, trades):
        trades_pending = True
        while trades_pending:
            trades_pending = False
            for trade in trades:
                if not trade.isDone():
                    trades_pending = True
                self.ib.sleep(0.1)
