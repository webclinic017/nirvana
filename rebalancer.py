class Rebalancer:
    def __init__(self, absolute_deviation_limit = 0.05, relative_deviation_limit = 0.25):
        self.account_value = 0
        self.absolute_deviation_limit = absolute_deviation_limit
        self.relative_deviation_limit = relative_deviation_limit
        self.absolute_rebalance = False
        self.relative_rebalance = False

    def rebalance_check(self, cash, current, target):
        # calculate position and account_value
        # print(current)
        # print(target)
        self.account_value = cash
        for position in current:
            current[position]['value'] = current[position]['shares'] * current[position]['last_price']
            self.account_value += current[position]['value']
        
        # check if need to reblance
        self.absolute_rebalance = False
        self.relative_rebalance = False

        for position in current:
            if target[position] == 0:
                continue
            current[position]['percent'] = current[position]['value'] / self.account_value
            deviation = abs(current[position]['percent'] - target[position] / 100)
            # print(str(position) + ": " + str(current[position]['value']))
            # print("account_value: " + str(self.account_value))
            # print("deviation: " + str(deviation))
            if (deviation > self.absolute_deviation_limit):
                # print("absolute_rebalance " + str(position))
                self.absolute_rebalance = True
            if (deviation > (target[position] / 100 * self.relative_deviation_limit)):
                # print(target[position])
                # print("relative_rebalance " + str(position))
                # print(target[position] / 100 * self.relative_deviation_limit)
                self.relative_rebalance = True

        return self.absolute_rebalance or self.relative_rebalance

    def rebalance(self, current, target):
        trades = {}

        for position in current:
            # print(target[position])
            target_value = self.account_value * target[position] / 100
            current_value = current[position]['value']
            # print("target_value: " + str(target_value))
            # print("current_value: " + str(current_value))
            delta = target_value - current_value
            # print("delta: " + str(delta))
            if delta == 0:
                continue
            if (delta < 0):
                trades[position] = {'action': 'SELL', 'amount': -delta}
            else:
                trades[position] = {'action': 'BUY', 'amount': delta}
             
        return trades
