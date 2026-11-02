"""Pure unselected certificate for an exact repeated trainer TCP enumeration.

Retains every original row and proves its multiplicity; never rewrites API counts
or discards raw rows. Only stable192-to-stable192, unchanged owned connections,
one trainer inode, an exact repeated body, fresh evidence and a <=2s completed
window are covered. Full physical/source/recipe/pipeline/bank/autosave checks and
a source-authenticated caller remain mandatory. This is not runtime acceptance.
"""
import hashlib

SCHEMA='robotron-owned-proc-repeat-certificate-v1'
LIMITS=dict(max_window_s=2.,max_sample_gap_s=.5,max_API_age_s=1.,max_FD_age_s=1.25,
            max_epoch_skew_s=.5,max_distinct_repeated_connections=1,
            max_occurrences_per_sample=2,max_case_events=1024,max_case_charged_s=600.)


def key(row):return tuple(row[name]for name in ('local','peer','state','inode','uid'))


def original_tcp(p,raw):
    """Parse every original row, including exact repeated rows, with v1 syntax."""
    try:return p.tcp(raw),[]
    except ValueError as error:
        p.require(str(error)=='Duplicate proc TCP row','Original TCP parser rejected unrelated evidence')
    lines=raw.splitlines(keepends=True);table=[];seen={};repeated=[];ordinals=set()
    for number,line in enumerate(lines[1:],1):
        fields=line.split();ordinal=fields[0]
        p.require(ordinal.endswith(b':')and ordinal[:-1].isdigit()and ordinal not in ordinals,
                  'Repeated/malformed proc ordinal')
        ordinals.add(ordinal)
        parsed=p.tcp(lines[0]+line)
        p.require(len(parsed)==1,'Every original TCP line must parse exactly once')
        row=parsed[0];table.append(row);identity=key(row)
        body=tuple(fields[1:]);entry=seen.setdefault(identity,dict(body=body,occurrences=[]))
        p.require(entry['body']==body,'Same TCP inode/endpoints/UID repeated with conflicting body')
        entry['occurrences'].append(dict(selected_line=number,proc_ordinal=ordinal.decode(),
            raw_sha256=hashlib.sha256(line).hexdigest(),raw_line=line.decode()))
        p.require(len(entry['occurrences'])<=LIMITS['max_occurrences_per_sample'],'Too many repeated row copies')
    for identity,entry in seen.items():
        if len(entry['occurrences'])==1:continue
        local,peer,state,inode,uid=identity
        p.require(state=='01'and inode>0 and int(local[9:],16)==9998,
                  'Only an established nonzero trainer inode repeat is covered')
        repeated.append(dict(connection=dict(zip(('local','peer','state','inode','uid'),identity)),
            occurrences=entry['occurrences']))
    p.require(0<len(repeated)<=LIMITS['max_distinct_repeated_connections'],
              'Several or absent exact repeated connections')
    return table,repeated


def certify(p,transport,binding,lua_sha,samples):
    p.require(lua_sha==p.LUA_SHA,'Exact held Lua source required')
    p.require(type(samples)is list and 3<=len(samples)<=32,'Complete bounded before/anomaly/after evidence required')
    class OriginalRows:
        def __getattr__(self,name):return getattr(p,name)
        def tcp(self,raw):return original_tcp(p,raw)[0]
    proxy=OriginalRows();decoded=[];repeat_events=[];previous=None
    for sample in samples:
        item=transport.decode_sample(proxy,binding,sample,previous)
        p.require(item['API']['client_count']==192,'This proof covers unique192 only; API overlap needs a separate proof')
        p.require(not sample['log_chunks'],'Concurrent log/cap activity is outside this stable proc-repeat proof')
        table,repeats=original_tcp(p,sample['raw_tcp']);item['repeats']=repeats;decoded.append(item)
        for repeat in repeats:repeat_events.append(dict(index=sample['index'],
            observed_unix_s=sample['observed_unix_s'],original_raw_tcp_sha256=hashlib.sha256(sample['raw_tcp']).hexdigest(),
            **repeat))
        previous=sample
    start,end=decoded[0],decoded[-1]
    duration=end['sample']['observed_unix_s']-start['sample']['observed_unix_s']
    p.require(0<duration<=LIMITS['max_window_s']and not start['repeats']and not end['repeats']and repeat_events,
              'Stable complete anchors around an actual repeat required within2s')
    before=transport.full_owned_join(p,start['table'],start['view'])
    after=transport.full_owned_join(p,end['table'],end['view'])
    p.require(before==after,'Any socket handover is outside this stable repeat proof')
    expected={key(row):(slot,role)for slot,pair in before.items()for role,row in pair.items()}
    p.require(len(expected)==384 and len({row[3]for row in expected})==384,
              'All384 client/trainer socket inodes must be distinct and owned')
    repeated_connections=set()
    for item in decoded:
        established=[row for row in item['table']if row['state']=='01'];counts={}
        for row in established:
            identity=key(row);p.require(identity in expected,'Unknown established peer/inode/UID in original TCP rows')
            counts[identity]=counts.get(identity,0)+1
            slot,role=expected[identity]
            owner=item['view']['trainer']if role=='server'else item['view']['actors'][slot]
            p.require(row['inode']in owner['socket_fds'].values(),'Original row lacks a fresh same-process FD owner')
        p.require(set(counts)==set(expected),'A physical owned socket pair is missing in the original TCP rows')
        for repeat in item['repeats']:
            identity=key(repeat['connection']);p.require(identity in expected and expected[identity][1]=='server',
                'Repeated connection is not a known trainer reverse socket')
            p.require(counts[identity]==len(repeat['occurrences'])==2,'Original row multiplicity not proved')
            repeated_connections.add(identity)
        for slot in p.SLOTS:
            initial=start['rows'][slot][0];actual=item['rows'][slot][0]
            p.require(len(item['rows'][slot])==1 and actual['client_id']==initial['client_id']
                and abs((item['API']['ts']-actual['connected_seconds'])-
                        (start['API']['ts']-initial['connected_seconds']))<=LIMITS['max_epoch_skew_s'],
                'Original API slot/CID/connection epoch changed during stable proc-repeat window')
    p.require(len(repeated_connections)==1,'Several repeated trainer connections in the window')
    connection=next(iter(repeated_connections));slot,role=expected[connection]
    owner=next(actor for actor in binding['actors']if str(actor['slot'])==slot)
    return dict(schema=SCHEMA,kind='exact_owned_trainer_proc_repeat',slot=int(slot),
        actor_pid=owner['pid'],actor_birth=owner['starttime_ticks'],
        trainer_pid=binding['owner']['pid'],trainer_birth=binding['owner']['starttime_ticks'],
        owned_pair=before[slot],original_repeat_events=repeat_events,
        first_index=samples[0]['index'],last_index=samples[-1]['index'],
        begin_unix_s=samples[0]['observed_unix_s'],end_unix_s=samples[-1]['observed_unix_s'],
        window_s=duration,charged_s=duration,raw_API_counts_preserved=[item['API']['client_count']for item in decoded],
        raw_TCP_rows_preserved=True,all_nontransport_main_checks_still_required=True,
        scientific_guard_selected=False,quality_qualified=False)


def closed_budget(p,certificates):
    p.require(type(certificates)is list and len(certificates)<=LIMITS['max_case_events'],'Whole-case proc-repeat event budget exceeded')
    total=0.;previous_end=None;seen=set()
    for entry in certificates:
        p.require(entry['schema']==SCHEMA and entry['kind']=='exact_owned_trainer_proc_repeat','Unknown proc-repeat certificate')
        span=entry['end_unix_s']-entry['begin_unix_s']
        p.require(p.finite(span)and 0<span<=2 and span==entry['window_s']==entry['charged_s'],
                  'Full proc-repeat window not charged within the fixed bound')
        p.require(previous_end is None or entry['begin_unix_s']>=previous_end,'Reordered/overlapping proc-repeat windows')
        previous_end=entry['end_unix_s'];total+=span
        p.require(entry['original_repeat_events'],'Actual original repeated rows required')
        for event in entry['original_repeat_events']:
            identity=(event['original_raw_tcp_sha256'],event['index'],event['observed_unix_s'])
            p.require(identity not in seen,'Original repeat evidence reused');seen.add(identity)
    p.require(total<=LIMITS['max_case_charged_s'],'Whole-case proc-repeat charged seconds exceeded')
    return dict(events=len(certificates),total_charged_s=total,all_closed=True,
        must_share_total_case_budget_with_other_transport_exceptions=True,quality_qualified=False)
