import os
import sys
from datetime import timedelta
import datetime

import pandas_market_calendars as mcal

from robot import Robot
from helpers import wait_until, get_next_market_close, ONE_MINUTE, ONE_DAY

while True:
    next_market_close = get_next_market_close(datetime.date.today()).replace(tzinfo=None)
    if (datetime.datetime.now() > next_market_close - ONE_MINUTE):
        next_market_close = get_next_market_close(datetime.date.today() + ONE_DAY).replace(tzinfo=None)
    wait_until_dt = next_market_close - ONE_MINUTE

    print("Waiting until... " + str(wait_until_dt))
    wait_until(wait_until_dt)

    robot = Robot()
    robot.set_robot_accounts()
    robot.rebalance()
    robot.disconnect()

    print("Finished rebalancing accounts.")
