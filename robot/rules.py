import pprint
import ta

class RulesProcessor():
    def __init__(self, broker):
        self.broker = broker
        self.historical_data = {}

    def update_historical_data(self, rules):
        for symbol in rules:
            for symbol in rules:
                rules_symbol = rules[symbol]['sym']
                if rules[symbol]['enable'] and rules_symbol not in self.historical_data:
                    self.historical_data[rules_symbol] = self.broker.get_historical_data(rules_symbol, duration='200 D', bar_size = '1 day')

    def apply_rules(self, rules, portfolio, allocations):
        self.update_historical_data(rules)

        target = {}
        for symbol in allocations:
            if symbol in rules and rules[symbol]['enable']:
                rules_symbol = rules[symbol]['sym']
                ma_type, window = rules[symbol]['type'].split('_')
                upper = rules[symbol]['upper']
                lower = rules[symbol]['lower']

                df = self.historical_data[rules_symbol]
                
                if ma_type == 'SMA':
                    ma = ta.trend.sma_indicator(df['close'], window=int(window), fillna=True).iloc[-1]
                elif ma_type == 'EMA':
                    ma = ta.trend.ema_indicator(df['close'], window=int(window), fillna=True).iloc[-1]

                price = df['close'].iloc[-1]
                ppo = ta.momentum.PercentagePriceOscillator(df['close'], window_slow = 26, window_fast = 12, window_sign = 9, fillna = False)
                ppo = ppo.ppo_hist().iloc[-1]
                rsi = ta.momentum.RSIIndicator(df['close'], window = 14, fillna = False).rsi().iloc[-1]
                print("{0:>7}: price={1:10.2f} ma={2:10.2f} ppo={3:6.2f} rsi={4:6.2f}".format(rules_symbol, price, ma, ppo, rsi))

                risk_off_signal = (
                    price < ma * lower
                    and ppo < 0.75 
                    and rsi > 22
                )

                risk_on_signal = (
                    price >= ma * upper
                    or ppo > 1.0
                    or rsi < 21
                )

                risk_on_position = False if portfolio[symbol]['shares'] == 0 else True

                if risk_off_signal:
                    target[symbol] = 0
                elif risk_on_signal or risk_on_position:
                    target[symbol] = allocations[symbol]
                else:
                    target[symbol] = 0

            else:
                target[symbol] = allocations[symbol]

        return target
