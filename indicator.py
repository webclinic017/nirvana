import pandas as pd
import ta

def add(df):
    
    df['Daily Return'] = 0.0
    days = len(df.index)
    for x in range(1, days):
        prev_close = df.iloc[x-1, 3]
        close = df.iloc[x, 3]
        change = (close - prev_close)/prev_close * 100.0
        df.iat[x, 7] = change

    rsi = ta.momentum.RSIIndicator(close=df['Close'], fillna=True)
    df['RSI'] =  rsi.rsi()
    macd = ta.trend.MACD(close=df['Close'], fillna=True)
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()
    df['MACD_diff'] = macd.macd_diff()
    ema200 = ta.trend.ema_indicator(df['Close'], window=200, fillna=True)
    df['EMA_200'] = ema200
    ema50 = ta.trend.ema_indicator(df['Close'], window=50, fillna=True)
    df['EMA_50'] = ema50
    ema20 = ta.trend.ema_indicator(df['Close'], window=20, fillna=True)
    df['EMA_20'] = ema20
    atr = ta.volatility.AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], fillna=True)
    df['ATR'] =  atr.average_true_range()
    # Supertrend
    # basic upper band = ((high + low) / 2) + (multiplier * atr)
    # basic lower band = ((high + low) / 2) - (multiplier * atr)
    multiplier = 0.25
    df['upperband'] = ((df['High'] + df['Low']) / 2) + (multiplier * df['ATR'])
    df['lowerband'] = ((df['High'] + df['Low']) / 2) - (multiplier * df['ATR'])
    df['in_uptrend'] = True
    for current in range(1, len(df.index)):
        previous = current - 1

        if df['Close'][current] > df['upperband'][previous]:
            df['in_uptrend'][current] = True
        elif df['Close'][current] < df['lowerband'][previous]:
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]
    vwap = ta.volume.VolumeWeightedAveragePrice(high=df['High'], low=df['Low'], close=df['Close'], volume=df['Volume'], window=14, fillna=True)
    df['VWAP'] = vwap.volume_weighted_average_price()

    return df
