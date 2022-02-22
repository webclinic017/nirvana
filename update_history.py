import pandas as pd
import requests
import datetime
import csv
import yfinance as yf
import pathlib
import ta

pathlib.Path("history").mkdir(parents=True, exist_ok=True)

date_format = '%Y-%m-%d'

tickers = [
    # SP500
    'SPY',
    'SSO',
    'RSP',

    # NASDAQ-100
    'QQQ',
    'QLD',

    # Emerging Markets
    'EET',
    'EEM',

    'IEF', # iShares 7-10 Year Treasury Bond ETF
    'TYD', # Direxion Daily 7-10 Year Treasury Bull 3X Shares
    'UST', # ProShares Ultra 7-10 Year Treasury

    'TLT', # iShares 20+ Year Treasury Bond ETF
    'UBT', # ProShares Ultra 20+ Year Treasury

    'GSY', # Invesco Ultra Short Duration ETF

    # Gold
    'GLD',
    'UGL',
    'GDX',

    # Silver
    'SLV',
    'AGQ',

    # Crypto
    'GBTC',
    'ETHE',
    'RIOT',

    'ARKG',
    'ARKK',

    'FNGU', # MicroSectors FANG+ Index 3X Leveraged ETN
    'DIG', # ProShares Ultra Oil & Gas
    'UTSL', # Direxion Daily Utilities Bull 3X Shares

    # Stocks
    'TSLA',
    'AAPL',
    'MSFT',
    'SBUX',
    'GOOG',
    'AMZN',
    'CSCO',
    'SQ'
    ]

def add_ta(df):
    # classta.trend.MACD(close: pandas.core.series.Series, window_slow: int = 26, window_fast: int = 12, window_sign: int = 9, fillna: bool = False)
    macd_diff = ta.trend.MACD(df['Adj Close']).macd_diff()
    df['MACD_diff'] = macd_diff
    ppo = ta.momentum.PercentagePriceOscillator(df['Adj Close'], window_slow = 26, window_fast = 12, window_sign = 9, fillna = False)
    df['PPO'] = ppo.ppo_hist()
    rsi = ta.momentum.RSIIndicator(df['Adj Close'], window = 14, fillna = False)
    df['RSI'] = rsi.rsi()
    sma_250 = ta.trend.sma_indicator(df['Adj Close'], window=250, fillna=True)
    df['SMA_250'] = sma_250
    sma_225 = ta.trend.sma_indicator(df['Adj Close'], window=225, fillna=True)
    df['SMA_225'] = sma_225
    sma_200 = ta.trend.sma_indicator(df['Adj Close'], window=200, fillna=True)
    df['SMA_200'] = sma_200
    sma_180 = ta.trend.sma_indicator(df['Adj Close'], window=180, fillna=True)
    df['SMA_180'] = sma_180
    sma_150 = ta.trend.sma_indicator(df['Adj Close'], window=150, fillna=True)
    df['SMA_150'] = sma_150
    sma_100 = ta.trend.sma_indicator(df['Adj Close'], window=100, fillna=True)
    df['SMA_100'] = sma_100
    sma_50 = ta.trend.sma_indicator(df['Adj Close'], window=50, fillna=True)
    df['SMA_50'] = sma_50
    sma_20 = ta.trend.sma_indicator(df['Adj Close'], window=20, fillna=True)
    df['SMA_20'] = sma_20
    atr = ta.volatility.AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], fillna=True, window=14)
    df['ATR'] =  atr.average_true_range()
    # Supertrend
    # basic upper band = ((high + low) / 2) + (multiplier * atr)
    # basic lower band = ((high + low) / 2) - (multiplier * atr)
    multiplier = 3
    df['upperband'] = ((df['High'] + df['Low']) / 2) + (3 * df['ATR'])
    df['lowerband'] = ((df['High'] + df['Low']) / 2) - (2 * df['ATR'])
    df['in_uptrend'] = 1
    for current in range(1, len(df.index)):
        previous = current - 1
        date = df.index[current]
        prev_date = df.index[previous]
        if df['Close'][current] > df['upperband'][previous]:
            df.loc[date, 'in_uptrend'] = 1
        elif df['Close'][current] < df['lowerband'][previous]:
            df.loc[date, 'in_uptrend'] = 0
        else:
            df.loc[date, 'in_uptrend'] = df.loc[prev_date, 'in_uptrend']

            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df.loc[date, 'lowerband'] = df.loc[prev_date, 'lowerband']

            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df.loc[date, 'upperband'] = df.loc[prev_date, 'upperband']
    return df

def merge_history(df, ticker):
    index = df.index
    last_date = index[-1]
    last_date_dt = datetime.datetime.strptime(last_date, date_format)
    if (last_date_dt.date() < datetime.date.today()):
        start_date_dt = (last_date_dt + datetime.timedelta(days=1))
    else:
        print("already up-to-date")
        return
    start_date = start_date_dt.strftime(date_format)
    print('')
    history = yf.download(tickers=[ticker], start=start_date).reset_index()
    history['Date'] = pd.to_datetime(history['Date']).dt.date
    history = history[~(history['Date'] <= last_date_dt.date())]
    history = history.set_index("Date")
    merge = pd.concat([df,history])
    merge = add_ta(merge)
    merge.to_csv('history/' + ticker + '.csv', date_format='%Y-%m-%d')

# update synthetics
for ticker in ['TQQQ','SPXL','TNA','UDOW','TMF']:
    print('Updating ' + ticker + '... ', end='')
    if (pathlib.Path('history/' + ticker + '.csv').exists()):
        df = pd.read_csv('history/' + ticker + '.csv').set_index("Date")
    else:
        df = pd.read_csv('synthetic/' + ticker + '_synth.csv').set_index("Date")
    merge_history(df, ticker)

for ticker in tickers:
    
    if (pathlib.Path('history/' + ticker + '.csv').exists()):
        print('Updating ' + ticker + '... ', end='')
        df = pd.read_csv('history/' + ticker + '.csv').set_index("Date")
        merge_history(df, ticker)
    else:
        print('Downloading ' + ticker + '... ')
        history = yf.download(tickers=[ticker]).reset_index()
        history['Date'] = pd.to_datetime(history['Date']).dt.date
        history = history.set_index('Date')
        history = add_ta(history)
        history.to_csv('history/' + ticker + '.csv', date_format='%Y-%m-%d')

start_date_dt = datetime.datetime.strptime("1999-03-10", date_format)

df_qqq = pd.read_csv('history/QQQ.csv')
df_spy = pd.read_csv('history/SPY.csv')

df_qqq['Date'] = pd.to_datetime(df_qqq['Date']).dt.date
df_spy['Date'] = pd.to_datetime(df_spy['Date']).dt.date

df_qqq = df_qqq[~(df_qqq['Date'] < start_date_dt.date())].reset_index()
df_spy = df_spy[~(df_spy['Date'] < start_date_dt.date())].reset_index()

df_ratios = pd.DataFrame()
df_ratios.insert(0, "Date", df_qqq["Date"])
df_ratios.insert(1, "QQQ", df_qqq["Close"])
df_ratios.insert(2, "SPY", df_spy["Close"])

df_ratios["Ratio"] = df_ratios["QQQ"]/df_ratios["SPY"]

rsi = ta.momentum.RSIIndicator(close=df_ratios['Ratio'], fillna=True)
df_ratios['RSI'] =  rsi.rsi()
macd = ta.trend.MACD(close=df_ratios['Ratio'], fillna=True)
df_ratios['MACD'] = macd.macd()
df_ratios['MACD_signal'] = macd.macd_signal()
df_ratios['MACD_diff'] = macd.macd_diff()

df_ratios.to_csv('history/ratios.csv', date_format='%Y-%m-%d', index=False)

end_date = df_spy.set_index('Date').index[-1]
print("---\nBacktest data available up to " + str(end_date))
