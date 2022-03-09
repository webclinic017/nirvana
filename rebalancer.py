class Rebalancer:
    def __init__(self, absolute_deviation_limit = 0.05, relative_deviation_limit = 0.25):
        self.absolute_deviation_limit = absolute_deviation_limit
        self.relative_deviation_limit = relative_deviation_limit

    def rebalance_bands(self, cash, current, target):
        # calculate position and account_value
        account_value = cash
        for position in current:
            current[position]['value'] = current[position]['shares'] * current[position]['last_price']
            account_value += current[position]['value']
        
        # check if need to reblance
        absolute_rebalance = False
        relative_rebalance = False

        for position in current:
            if target[position] == 0:
                continue

            current[position]['percent'] = current[position]['value'] / account_value
            deviation = abs(current[position]['percent'] - target[position] / 100)

            if (deviation > self.absolute_deviation_limit):
                absolute_rebalance = True
            if (deviation > (target[position] / 100 * self.relative_deviation_limit)):
                relative_rebalance = True

        return absolute_rebalance or relative_rebalance

    def rebalance(self, cash, current, target):
        trades = {}

        account_value = cash
        for position in current:
            current[position]['value'] = current[position]['shares'] * current[position]['last_price']
            account_value += current[position]['value']

        for position in current:
            target_value = account_value * target[position] / 100
            current_value = current[position]['value']
            delta = target_value - current_value
            if delta == 0:
                continue
            if (delta < 0):
                trades[position] = {'action': 'SELL', 'amount': -delta}
            else:
                trades[position] = {'action': 'BUY', 'amount': delta}
             
        return trades
