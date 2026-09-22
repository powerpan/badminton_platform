#!/usr/bin/env python3
"""Deterministic candidate-generation microbenchmark, not an HTTP/load benchmark."""
import json
from datetime import date
from pathlib import Path
from random import Random
from statistics import median
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from utils.booking_operations import rank_windows


def run():
    results=[]
    for count in (1,10,50,200):
        for interval in (15,60):
            for occupancy in (.1,.3,.7):
                random=Random(20260916+count+interval)
                courts=[{'id':i,'court_no':f'A{i:03}','court_name':str(i),'price_per_hour_cents':10000+i%5*1000} for i in range(count)]
                slots={c['id']:[{'start_time':f'{m//60:02}:{m%60:02}','end_time':f'{(m+interval)//60:02}:{(m+interval)%60:02}',
                    'status':'available' if random.random()>occupancy else 'reserved'} for m in range(540,1260,interval)] for c in courts}
                times=[]
                for _ in range(30):
                    start=perf_counter()
                    items=rank_windows(courts,slots,day=date(2026,9,17),earliest='09:00',duration=120,interval=interval,account={})
                    times.append((perf_counter()-start)*1000)
                results.append({'courts':count,'slot_interval_minutes':interval,'slots':count*720//interval,
                    'occupancy_probability':occupancy,'samples':30,'median_ms':round(median(times),3),'p95_ms':round(sorted(times)[28],3),'returned':len(items)})
    return {'scope':'Pure Python candidate generation only; no database, Redis, HTTP or browser latency.',
        'seed':20260916,'occupancy_probabilities':[.1,.3,.7],'duration_minutes':120,'results':results}


if __name__=='__main__': print(json.dumps(run(),ensure_ascii=False,indent=2))
