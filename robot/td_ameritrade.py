import math
import pprint
import time
import pandas as pd

from tda.auth import easy_client
from tda.client import Client
from tda.orders.equities import equity_buy_limit, equity_sell_limit
from tda.orders.common import Duration, Session
from tda.utils import Utils

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
        r = self.tda.get_account(account_id=account, fields=[self.tda.Account.Fields.POSITIONS])
        assert r.status_code == 200, r.raise_for_status()
        info = r.json()

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
                r = self.tda.get_quote(symbol)
                price = r.json()[symbol]['lastPrice']
                break
            except:
                attempts -= 1
                if attempts == 0:
                    return
                time.sleep(1)

        return price

    def get_historical_data(self, symbol, duration='200 D', bar_size = '1 day'):
        r = self.tda.get_price_history(symbol,
                period_type=Client.PriceHistory.PeriodType.YEAR,
                period=Client.PriceHistory.Period.ONE_YEAR,
                frequency_type=Client.PriceHistory.FrequencyType.DAILY,
                frequency=Client.PriceHistory.Frequency.DAILY)
        assert r.status_code == 200

        df = pd.json_normalize(r.json()['candles'])

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
