import os
import sys

import datetime
import time

import pandas_market_calendars as mcal
import pandas as pd
from datetime import timedelta
import datetime
import pytz
import time
from tzlocal import get_localzone

ONE_DAY = datetime.timedelta(days=1)
ONE_MINUTE = datetime.timedelta(minutes=1)

def wait_until(execute_it_now):
    while True:
        diff = (execute_it_now - datetime.datetime.now()).total_seconds()
        if diff <= 0:
            return
        elif diff <= 0.1:
            time.sleep(0.001)
        elif diff <= 0.5:
            time.sleep(0.01)
        elif diff <= 1.5:
            time.sleep(0.1)
        else:
            time.sleep(1)

def get_next_market_close(start_day):
    nyse = mcal.get_calendar('NYSE')

    next_day = pd.to_datetime(start_day).replace(tzinfo=pytz.utc)
    while next_day.weekday() in [5,6] or next_day not in nyse.valid_days(start_date=next_day, end_date=next_day):
        next_day += ONE_DAY

    next_market_close = nyse.schedule(next_day, next_day).loc[next_day, 'market_close']
    next_market_close = next_market_close.to_pydatetime().astimezone(get_localzone())

    return next_market_close 

def get_next_market_times(start_day):
    nyse = mcal.get_calendar('NYSE')

    next_day = pd.to_datetime(start_day).replace(tzinfo=pytz.utc)
    while next_day.weekday() in [5,6] or next_day not in nyse.valid_days(start_date=next_day, end_date=next_day):
        next_day += ONE_DAY

    next_market_open = nyse.schedule(next_day, next_day).loc[next_day, 'market_open']
    next_market_open = next_market_open.to_pydatetime().astimezone(get_localzone())
    next_market_close = nyse.schedule(next_day, next_day).loc[next_day, 'market_close']
    next_market_close = next_market_close.to_pydatetime().astimezone(get_localzone())

    return next_market_open, next_market_close 
