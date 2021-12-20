# nirvana

## Installation
```
python3 -m venv venv
source venv/bin/activate
pip install -r requirement.txt
```

:warning: edit /opt/vixray/venv/lib/python3.8/site-packages/backtrader/plot/locator.py and remove **', warning'** from line 39 pos 49

```
python update_history.py # only run once
```

## Running
```
python trader.py --portin=SPXL/60,TMF/40 --fromdate 1993-01-29 --benchmark SPXL
```
