import math
import pprint

from ib_insync import IB, LimitOrder, Stock, util

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
        attempts = 0
        while True:
            contracts = self.ib.qualifyContracts(contract)
            if (len(contracts) == 0):
                attempts += 1
                if attempts == 10:
                    raise Exception("Failed to qualify contract for %s" % symbol)
                self.ib.sleep(0.1)
            else:
                break
        self.ib.reqMarketDataType(2) # 2 = Frozen
        data = self.ib.reqMktData(contract, symbol, snapshot=True, regulatorySnapshot=False)

        attempts = 0
        while True:
            if util.isNan(data.last):
                attempts += 1
                if attempts == 30:
                    raise Exception("Failed to download last price for %s" % symbol)
                self.ib.sleep(0.1)
            else:
                break

        return data.last

    def get_historical_data(self, symbol, duration='200 D', bar_size = '1 day'):
        while (True):
            try:
                contract = Stock(symbol=symbol, exchange='SMART', currency='USD')
                self.ib.qualifyContracts(contract)
                bars = self.ib.reqHistoricalData(
                        contract,
                        endDateTime='',
                        durationStr=duration,
                        barSizeSetting=bar_size,
                        whatToShow='ADJUSTED_LAST',
                        useRTH=True,
                        formatDate=1)
                df = util.df(bars)
                if df is not None:
                    return df
            except Exception as e:
                print(e)

            print("Failed to download historical data for %s" % symbol)

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
        print(symbol + ": " + str(order))

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
        print(symbol + ": " + str(order))

        if (test):
            return

        return self.ib.placeOrder(contract, order)

    def cancel_all_orders(self):
        self.ib.reqGlobalCancel()

    # TODO: need to wait until all trades are filled not just done
    def wait_for_trades(self, trades):
        attempts = 0
        while True:
            trades_pending = False
            for trade in trades:
                if not trade.isDone():
                    trades_pending = True

            if not trades_pending:
                break

            attempts += 1
            if attempts == 5:
                raise Exception("Trades failed to execute in 5 seconds")
            self.ib.sleep(1)
