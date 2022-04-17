import math
import pprint

from ib_insync import IB, LimitOrder, Stock, util

class TDAmeritrade():
    def __init__(self):
        self.tda = None

class InteractiveBrokers():
    def __init__(self):
        self.ib = IB()
        self.ib.connect('127.0.0.1', 7497, clientId=1)

    def connect(self):
        self.ib.connect('127.0.0.1', 7497, clientId=1)
    
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
            if avs[i].tag == "AvailableFunds":
                available_funds = float(avs[i].value)
        return available_funds

    def get_quote(self, symbol):
        contract = Stock(symbol=symbol, exchange='SMART', currency='USD')
        self.ib.qualifyContracts(contract)

        # data = self.ib.reqMktData(contract, symbol, snapshot=True, regulatorySnapshot=False)

        # # TODO: add timeout or max attempts
        # while (util.isNan(data.last)):
        #     self.ib.sleep(0.1)

        # return data.last

        df = self.get_historical_data(symbol, duration='1 D', bar_size ='1 day')

        return df.close.iloc[-1]

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

        print("current price:", df.close.iloc[-1])

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
