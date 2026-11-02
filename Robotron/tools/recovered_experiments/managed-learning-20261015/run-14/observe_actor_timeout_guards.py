#!/usr/bin/env python3
"""Bounded stdlib actor-log guard, including exact embedded Lua timestamps."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,re,time
BASE=Path(__file__).resolve().parent
OUT=BASE/'socket-action-timeout-observations.jsonl'
start=time.monotonic();previous=None
with OUT.open('x') as stream:
 for index in range(451):
  files=[]
  for path in sorted(BASE.glob('fleet*.log')):
   data=path.read_bytes();prefix=data[:data.rfind(b'\n')+1]
   matches=[line for line in prefix.decode(errors='replace').splitlines() if '[SOCKET ACTION TIMEOUT]' in line]
   reports=[];by_slot={}
   for line in matches:
    fields={k:int(v) for k,v in re.findall(r'\b(slot|count|suppressed|partial_bytes|unix_s)=(\d+)',line)}
    if 'slot' in fields and 'count' in fields:by_slot[str(fields['slot'])]=max(by_slot.get(str(fields['slot']),0),fields['count'])
    reports.append(dict(fields,raw=line,embedded_utc=datetime.fromtimestamp(fields['unix_s'],timezone.utc).isoformat() if 'unix_s' in fields else None))
   files.append(dict(path=str(path),complete_prefix_bytes=len(prefix),sha256=hashlib.sha256(prefix).hexdigest(),timeout_report_lines=len(matches),reported_count_by_slot=by_slot,reports=reports))
  row=dict(utc=datetime.now(timezone.utc).isoformat(),elapsed_s=time.monotonic()-start,index=index,files=files,total_timeout_report_lines=sum(x['timeout_report_lines'] for x in files))
  stream.write(json.dumps(row,separators=(',',':'))+'\n');stream.flush()
  counts=tuple((x['path'],x['timeout_report_lines']) for x in files)
  if counts!=previous or index%30==0:print(json.dumps(dict(utc=row['utc'],elapsed_s=row['elapsed_s'],counts=counts)),flush=True)
  previous=counts
  if index<450:time.sleep(2)
print(json.dumps(dict(status='complete',elapsed_s=time.monotonic()-start)),flush=True)
