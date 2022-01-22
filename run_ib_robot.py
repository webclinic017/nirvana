import os
import sys
sys.path.append(os.path.abspath('../lib'))
sys.path.append(os.path.abspath('../config'))

from tda.auth import easy_client
from tda import client
from tda.orders.equities import equity_buy_limit, equity_sell_limit
from tda.orders.common import Duration, Session
from tda.utils import Utils

import asyncio
import json
import pprint

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import pandas_market_calendars as mcal
import pandas as pd
from datetime import timedelta
import datetime
import pytz
import time
import math
import requests

from robot import get_tda_client
from robot import get_sell_orders, get_buy_orders, place_buy_order, place_sell_order  
from robot import print_tda_positions
from vixray import wait_until, get_next_market_close, ONE_MINUTE, ONE_DAY

VIXRAY_REST_API = "http://dashboard.vixray.net/vixray"

c = get_tda_client()

response = requests.get(VIXRAY_REST_API)
print(response.json())

while True:
    print_tda_positions(c)

    next_market_close = get_next_market_close(datetime.date.today()).replace(tzinfo=None)
    if (datetime.datetime.now() > next_market_close - ONE_MINUTE):
        next_market_close = get_next_market_close(datetime.date.today() + ONE_DAY).replace(tzinfo=None)
    wait_until_dt = next_market_close - ONE_MINUTE
    print("Waiting until... " + str(wait_until_dt))
    wait_until(wait_until_dt)

    print("BUYING")
    action_valid = True
    buy_orders = get_buy_orders(c)
    for order in buy_orders:
        account = order[0]
        symbol = order[1]
        cash = order[2]
        email = order[3]
        place_buy_order(c, account, symbol, cash, email)
    
    print("SELLING")
    action_valid = True
    sell_orders = get_sell_orders(c)
    for order in sell_orders:
        account = order[0]
        symbol = order[1]
        shares = order[2]
        email = order[3]
        place_sell_order(c, account, symbol, shares, email)

    wait_until_dt = next_market_close + datetime.timedelta(minutes=15)
    print("Waiting until... " + str(wait_until_dt))
    wait_until(wait_until_dt)
