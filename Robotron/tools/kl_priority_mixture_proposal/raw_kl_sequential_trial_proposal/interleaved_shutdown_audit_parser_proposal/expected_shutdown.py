"""Pure, bounded reconciliation of one exact pinned intentional-shutdown trace family."""
import collections
import hashlib
import json
import math
from pathlib import PurePosixPath
import re

SOCKET_SHA256='d99dd2782fc3e8f67670aefb398ed0dfdc1fd859432e24c8bd8dea4da2825214'
SIDECAR_SHA256='cd034413c2fd8a56bb9d22f8df86889939edfad041ee4e2e0210a831b5f9fe90'
STOP='Stopping async inference batcher...'
ERROR='Inference batcher stopped before completion'
PROBLEM=re.compile(r'Traceback|\b\w*(?:Error|Exception)\b|\bfailed\b|\bfallback\b|\bunavailable\b|\bdisconnected\b|param mismatch|\[INGEST\] dropped implausible',re.I)

def require(value,message):
    if not value:raise ValueError(message)

def reconcile_expected_shutdown(console,receipt,*,socket_source,sidecar_source,expected_socket_path):
    """Caller already validated original rows, registry, slots and runtime. No I/O or actions."""
    require(type(console) is str and len(console.encode())<=1<<20,'Bounded console text required')
    lines=console.splitlines();require(len(lines)<=4096,'Too many console lines')
    require(type(socket_source) is bytes and hashlib.sha256(socket_source).hexdigest()==SOCKET_SHA256
            and type(sidecar_source) is bytes and hashlib.sha256(sidecar_source).hexdigest()==SIDECAR_SHA256,'Exact source/latch proof required')
    path=PurePosixPath(expected_socket_path)
    require(path.is_absolute() and '..' not in path.parts and path.parts[-3:]==('Scripts','dqn','socket_server.py'),'Exact pinned socket source path required')
    require(receipt.get('complete') is True and receipt.get('valid') is True and receipt.get('active') is False
            and receipt.get('pending')==receipt.get('abandoned')==0 and receipt.get('reason') is None
            and receipt.get('server_error') is None and receipt.get('inference_error') is None
            and receipt.get('cleanup_errors')==receipt.get('invalidity_reasons')==[],'Clean valid complete inactive receipt required')
    rows=receipt.get('rows');count=receipt.get('count');cutoff=receipt.get('timeout_snapshot_unix_s')
    require(type(count) is int and count>0 and receipt.get('started')==count and isinstance(rows,list) and len(rows)==count,'Full admitted row coverage required')
    require(type(cutoff) in (int,float) and math.isfinite(cutoff) and cutoff>0,'Actual shutdown boundary required')
    ends=[row.get('end_unix_s') for row in rows]
    require(all(type(v) in (int,float) and math.isfinite(v) and 0<v<=cutoff for v in ends),'Required tail extends past shutdown boundary')
    require(isinstance(receipt.get('actor_timeout_logs'),dict) and len(receipt['actor_timeout_logs'])==16
            and all(type(v) is int and v==0 for v in receipt['actor_timeout_logs'].values()),'Measured actor timeout cannot be reconciled')
    clients=receipt.get('boundary',{}).get('acknowledged_client_ids')
    require(isinstance(clients,list) and len(clients)==len(set(clients))==16 and all(type(v) is int for v in clients),'Exact owned16 client set required')
    stops=[i for i,line in enumerate(lines) if line==STOP]
    require(len(stops)==1,'One exact intentional stop boundary required');stop=stops[0]
    require(not any(PROBLEM.search(line) for line in lines[:stop]),'Pre-stop runtime/exception text remains unclassified')
    nonempty=[i for i,line in enumerate(lines) if line]
    require(nonempty and nonempty[-1]>stop,'Final original summary required');last=nonempty[-1]
    try:summary=json.loads(lines[last])
    except (ValueError,TypeError) as error:raise ValueError('Final original summary missing') from error
    require(isinstance(summary,dict) and set(summary)=={'valid','reason','label','count','mean','elapsed_s'}
            and summary['valid'] is True and summary['reason'] is None and summary['label']==receipt.get('label')
            and summary['count']==count and summary['mean']==receipt.get('mean')
            and type(summary['elapsed_s']) in (int,float) and math.isfinite(summary['elapsed_s']) and summary['elapsed_s']>0,'Original final summary/receipt differs')
    counts=collections.Counter();ids=[];accounted=[]
    for i in range(stop+1,last):
        line=lines[i]
        if not line:continue
        if re.fullmatch(r'(?:Client \d+ error: '+re.escape(ERROR)+r')+',line):
            found=[int(v) for v in re.findall(r'Client (\d+) error:',line)];ids.extend(found);counts['clients']+=len(found)
        elif line=='Traceback (most recent call last):':counts['headers']+=1
        elif line=='  File "'+expected_socket_path+'", line 2389, in handle_client':counts['handle_frames']+=1
        elif line=='  File "'+expected_socket_path+'", line 995, in infer':counts['infer_frames']+=1
        elif line=='    mv_idx, fr_idx, is_eps = self.inference_batcher.infer(model_state, epsilon, locked_fire=locked_fire)':counts['handle_calls']+=1
        elif re.fullmatch(r'\s+[~^]{1,256}',line):counts['carets']+=1
        elif line=='    raise RuntimeError(error)':counts['raises']+=1
        elif re.fullmatch(r'(?:RuntimeError: '+re.escape(ERROR)+r')+',line):counts['endings']+=line.count('RuntimeError: '+ERROR)
        else:raise ValueError('Foreign/unknown post-stop line '+str(i+1)+': '+line)
        accounted.append(i+1)
    n=counts['clients']
    require(1<=n<=16 and len(ids)==len(set(ids))==n and set(ids)<=set(clients),'Unknown/repeated client stop identity')
    require(all(counts[name]==n for name in ('headers','handle_frames','infer_frames','handle_calls','carets','raises','endings')),'Incomplete or mixed interleaved trace multiset')
    return dict(schema='robotron-exact-interleaved-owned-shutdown-review-v1',accepted=True,stop_line=stop+1,
        accounted_line_numbers=accounted,owned_client_ids=ids,counts=dict(counts),source_hashes=dict(socket=SOCKET_SHA256,sidecar=SIDECAR_SHA256),
        last_required_game_end=max(ends),shutdown_boundary=cutoff,individual_thread_pairing='not reconstructed; exact multiset plus pinned sticky-latch/post-join receipt proof',
        scope='Only this complete known stop trace family. No row/gate validation, runtime waiver, retry or qualification.')
