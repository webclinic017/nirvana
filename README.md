# nirvana

## Installation
```
git clone git@github.com:seekingsharpe/nirvana.git
cd nirvana
python3 -m venv venv
source venv/bin/activate
pip install -r requirement.txt
```

:warning: edit venv/lib/python3.8/site-packages/backtrader/plot/locator.py and remove **', warning'** from line 39 pos 49

## Update History
```
python update_history.py
```

## Run Backtest
```
python trader.py --portin=SPXL/100 --fromdate 1993-01-29 --benchmark SPXL
```
