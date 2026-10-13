"""Synthetic discovery benchmark; no tools, model providers or targets execute."""
from pathlib import Path
import json
import platform
import statistics
import sys
import tempfile
import time
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from foxworx.tool_discovery import ToolDiscovery

results=[]
for count in (4000,20000,50000):
    rows=[{'name':f'utility-{i:06d}','description':'Additional installed executable',
           'category':'System / additional','mode':'unknown','installed':True,
           'path':'/bin/true','version':'','package':'','note':''} for i in range(count)]
    rows[-1]={**rows[-1],'name':'late-dns-tool','description':'DNS records and resolver inspection','category':'DNS','mode':'cli'}
    registry=SimpleNamespace(scanned=time.time(),list=lambda:rows)
    with tempfile.TemporaryDirectory() as state:
        discovery=ToolDiscovery(registry,state)
        start=time.perf_counter();discovery.rebuild();build_ms=(time.perf_counter()-start)*1000
        timings=[]
        for _ in range(25):
            start=time.perf_counter();result=discovery.shortlist('DNS records and resolver inspection')
            timings.append((time.perf_counter()-start)*1000)
        assert result['results'][0]['name']=='late-dns-tool'
        broad=discovery.search('utility',limit=40)
        assert broad['returned']==40 and broad['next_cursor']
        results.append({'tools':count,'index_build_ms':round(build_ms,2),
                        'warm_query_median_ms':round(statistics.median(timings),3),
                        'warm_query_p95_ms':round(sorted(timings)[23],3),
                        'shortlist_bytes':len(json.dumps(result).encode()),
                        'page_bytes':len(json.dumps(broad).encode())})
        discovery.close()
print(json.dumps({'host':{'architecture':platform.machine(),'python':platform.python_version(),
                          'cpu':platform.processor(),'platform':platform.platform()},
                  'kind':'Synthetic in-memory inventory; metadata enrichment and filesystem scan not timed',
                  'results':results},indent=2))
