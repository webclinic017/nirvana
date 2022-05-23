import math
import pandas as pd
import ta

def truncate(n, decimals=0):
    multiplier = 10 ** decimals
    print(multiplier)
    return int(n * multiplier) / multiplier

def round_up(n, decimals=0):
    multiplier = 10 ** decimals
    return math.ceil(n * multiplier) / multiplier

def round_down(n, decimals=0):
    multiplier = 10 ** decimals
    return math.floor(n * multiplier) / multiplier

def get_ma(history, type, window, date_dt, last_price):
    date = date_dt.strftime('%Y-%m-%d')
    history['Date'] = pd.to_datetime(history['Date']).dt.date
    history = history[~(history['Date'] >= date_dt)]
    history = history.append({'Date': date}, ignore_index=True)
    history = history.set_index("Date")
    history.loc[date]['Adj Close'] = last_price
    sma = ta.trend.sma_indicator(history['Adj Close'], window=window, fillna=True)
    history['SMA'] = sma
    ma = history.loc[date]['SMA']

    return ma
