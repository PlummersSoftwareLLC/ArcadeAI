"""Verify a narrow cached-API reconnect projection against physical ownership.

Never rewrite raw API data. The ordinary unique-slot API predicate remains the
fast path. This exception needs a preceding accepted registration, the same
original MAME birth, one physically owned TCP connection per declared actor,
and a fresh new registration alongside the old cached row. Unknown physical
clients, missing slots and unproved retirements remain invalid.
"""
import hashlib
import importlib.util
import math
from pathlib import Path

TCP_SOURCE=Path(__file__).with_name('round_health_transport_v4.py')
TCP_SHA='54f3c764473f33b8c20533d7020cfb99b2f2ea51ea8e3c46d7e85c9625aaf88f'


def require(value,message):
    if not value:raise ValueError(message)


def number(value):
    require(type(value)in (int,float)and math.isfinite(value)and value>=0,
            'Invalid reconnect age')
    return value


def verify(case,sample,previous):
    require(previous is not None and sample['status']['round']==previous['status']['round'],
            'Reconnect projection needs a preceding accepted same-round census')
    require(0<=sample['monotonic_s']-previous['monotonic_s']<=.5,
            'Reconnect projection exceeds500ms accepted-proof gap')
    api=sample['api'];rows=api['client_rows'];actors=sample['actors'];results=sample['results']
    active=set(actors)-set(results);frozen=set(actors)&set(results)
    require(type(api['client_count'])is int and 0<len(rows)==api['client_count']<=192,
            'Reconnect API count/list differs')
    identifiers=[row['client_id']for row in rows]
    require(all(type(value)is int and value>=0 for value in identifiers)
            and len(set(identifiers))==len(identifiers),'Duplicate or invalid API client IDs')
    groups={}
    for row in rows:groups.setdefault(str(row['client_slot']),[]).append(row)
    require(set(groups)-frozen==active and set(groups)<=set(actors)
            and set(groups)<=set(map(str,range(192))), 'Reconnect projection has an unknown or missing slot')
    duplicates={slot:values for slot,values in groups.items()if len(values)>1}
    require(bool(duplicates)and all(len(values)==2 for values in duplicates.values()),
            'Only an old/new registration pair may project one slot')
    before={row['client_id']:row for row in previous['api']['client_rows']}
    api_age=sample['unix_s']-api['ts']
    require(0<=api_age<=.5,'Reconnect API snapshot is stale')
    require(hashlib.sha256(TCP_SOURCE.read_bytes()).hexdigest()==TCP_SHA,
            'Original physical TCP verifier changed')
    spec=importlib.util.spec_from_file_location('_reconnect_original_physical_TCP',TCP_SOURCE)
    tcp=importlib.util.module_from_spec(spec);spec.loader.exec_module(tcp)
    # This is the unchanged kernel/socket-inode/namespace/UID/PID ownership
    # verifier, including one socket per actor and no unmatched server socket.
    tcp.validate_transport(sample)
    witnesses=[]
    for slot,values in sorted(duplicates.items()):
        require(slot in previous['actors']and slot not in results
                and slot not in previous['results'],'Reconnect actor lacks a live original predecessor')
        old_actor=previous['actors'][slot];actor=actors[slot]
        require((old_actor['pid'],old_actor['starttime_ticks'])==(actor['pid'],actor['starttime_ticks']),
                'Reconnect changed original MAME birth')
        older,newer=sorted(values,key=lambda row:number(row['connected_seconds']),reverse=True)
        require(older['connected_seconds']>newer['connected_seconds'], 'Reconnect registrations have no age order')
        predecessor=before.get(older['client_id'])
        require(predecessor is not None and str(predecessor['client_slot'])==slot
                and number(older['connected_seconds'])>=number(predecessor['connected_seconds']),
                'Old reconnect row has no accepted predecessor')
        new_age=number(newer['connected_seconds'])+api_age
        require(new_age<=.5,'New reconnect registration is stale')
        if newer['client_id']in before:
            prior=before[newer['client_id']]
            prior_pair=[row for row in previous['api']['client_rows']if str(row['client_slot'])==slot]
            require(str(prior['client_slot'])==slot and len(prior_pair)==2
                    and {row['client_id']for row in prior_pair}=={older['client_id'],newer['client_id']}
                    and number(newer['connected_seconds'])>=number(prior['connected_seconds']),
                    'New reconnect ID belongs to another or unproved registration')
        for row in values:
            require(type(row['eval'])is bool and row['eval']==case['slot_eval'][slot],
                    'Reconnect API role differs')
        witnesses.append(dict(schema='robotron-source-bound-API-reconnect-projection-v1',slot=slot,
            pid=actor['pid'],birth=actor['starttime_ticks'],old_client_id=older['client_id'],
            new_client_id=newer['client_id'],API_age_s=api_age,new_registration_effective_age_s=new_age,
            unchanged_physical_TCP_ownership_verified=True,raw_API_rewritten=False))
    return witnesses
