"""Unselected pure transport certificate; no I/O or runtime/quality decision.

The caller must authenticate every raw sample and independently retain all
original physical-census, source, control, recipe, pipeline and bank checks.
A completed certificate covers one source-bound, unchanged actor's brief
cap75 reconnect. It cannot validate an old failed study or a missing actor.
"""
import hashlib
import json
import math

LUA_SHA = '060f838359d35ef6c87b96dfe02ad34618ef974d5a43fefcb74320ebe9deecaf'
CAP = b'[WAVECAP] wave advance 74 -> 75 - soft reset (training-data rebalance)'
LIMITS = dict(max_window_s=2.,max_sample_gap_s=.5,max_fd_age_s=1.25,
              max_API_age_s=1.,max_episodes=1024,max_total_s=600.)
SLOTS = set(map(str,range(192)))
SCHEMA = 'robotron-owned-cap-overlap-transport-certificate-v1'


def require(value, message):
    if not value:
        raise ValueError(message)


def finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum,'Malformed integer')
    return value


def decode(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 2<<20,'Bounded original raw JSON bytes required')
    def unique(pairs):
        result={}
        for key,value in pairs:
            require(key not in result,'Duplicate JSON key')
            result[key]=value
        return result
    value=json.loads(raw,object_pairs_hook=unique)
    require(type(value) is dict,'Original JSON object required')
    return value


def rows(API):
    require(type(API.get('client_count')) is int and API['client_count'] in (192,193),
            'Only full192 or single duplicate193 is covered; no191/other-count exception')
    data=API.get('client_rows')
    require(type(data) is list and len(data)==API['client_count'],'API rows/count differ')
    result={};ids=set()
    for row in data:
        slot=integer(row.get('client_slot'));cid=integer(row.get('client_id'))
        require(str(slot) in SLOTS and cid not in ids,'Unknown slot or duplicate client ID')
        require(finite(row.get('connected_seconds')) and row['connected_seconds']>=0,
                'Missing/nonfinite connection age')
        ids.add(cid);result.setdefault(str(slot),[]).append(row)
    require(set(result)==SLOTS and all(len(value) in (1,2) for value in result.values()),
            'Missing actor slot or more than one duplicate')
    require(sum(len(value)==2 for value in result.values())==API['client_count']-192,
            'Duplicate-slot coverage differs')
    return result


def tcp(raw):
    require(type(raw) is bytes and 0 < len(raw) <= 2<<20 and raw.endswith(b'\n'),
            'Complete bounded selected proc TCP bytes required')
    result=[];seen=set()
    for line in raw.splitlines()[1:]:
        values=line.split()
        require(len(values)>=10,'Malformed original proc TCP row')
        local,peer=values[1].decode(),values[2].decode()
        for endpoint in (local,peer):
            require(len(endpoint)==13 and endpoint[8]==':' and
                    all(c in '0123456789ABCDEF' for c in endpoint[:8]+endpoint[9:]),
                    'Exact IPv4 proc endpoints required')
        require(int(local[9:],16)==9998 or int(peer[9:],16)==9998,'Foreign port in selected TCP bytes')
        state=values[3].decode();inode=int(values[9]);uid=int(values[7])
        require(len(state)==2 and all(c in '0123456789ABCDEF' for c in state),'Malformed TCP state')
        require(inode>=0 and uid>=0,'Malformed inode/uid')
        key=(local,peer,state,inode)
        require(key not in seen,'Duplicate proc TCP row')
        seen.add(key);result.append(dict(local=local,peer=peer,state=state,inode=inode,uid=uid))
    return result


def fd_view(raw, binding, now):
    value=decode(raw)
    require(finite(value.get('begin_unix_s')) and finite(value.get('end_unix_s'))
            and 0<=value['end_unix_s']-value['begin_unix_s']<=.5
            and 0<=now-value['end_unix_s']<=LIMITS['max_fd_age_s'],'Stale/slow/future FD census')
    require(set(value['actors'])==SLOTS,'All192 original FD owners required')
    expected={str(actor['slot']):actor for actor in binding['actors']}
    require(set(expected)==SLOTS and len({actor['pid'] for actor in expected.values()})==192,
            'Original192 unique actor registry required')
    for role,claim in [('trainer',binding['owner']),*[(slot,expected[slot]) for slot in sorted(SLOTS)]]:
        actual=value['trainer'] if role=='trainer' else value['actors'][role]
        require(actual['pid']==claim['pid'] and actual['starttime_ticks']==claim['starttime_ticks'],
                'Original process birth changed')
        require(type(actual['socket_fds']) is dict and actual['socket_fds']
                and all(type(number) is str and number.isdecimal() and type(inode) is int and inode>0
                        for number,inode in actual['socket_fds'].items()),'Malformed socket FD ownership')
    return value


def established(table, view):
    by_slot={}
    for slot,actor in view['actors'].items():
        inodes=set(actor['socket_fds'].values())
        by_slot[slot]=[row for row in table if row['state']=='01' and row['inode'] in inodes
                       and int(row['peer'][9:],16)==9998]
    server=[row for row in table if row['state']=='01' and int(row['local'][9:],16)==9998]
    return by_slot,server


def full_join(table,view):
    by_slot,server=established(table,view)
    require(len(server)==192 and all(len(value)==1 for value in by_slot.values()),
            'Before/after must have exactly192 owned socket pairs')
    server_inodes=set(view['trainer']['socket_fds'].values())
    joined={}
    for slot,connections in by_slot.items():
        client=connections[0]
        peers=[row for row in server if row['local']==client['peer'] and row['peer']==client['local']
               and row['inode'] in server_inodes]
        require(len(peers)==1,'Trainer reverse socket ownership missing')
        joined[slot]=dict(client=client,server=peers[0])
    require(len({entry['client']['inode'] for entry in joined.values()})==192,
            'Actor socket inode reused across slots')
    return joined


def certify(binding, log_cursors, lua_sha256, samples):
    """Certify a contiguous, completed observational window; never accept a partial one.

    Each sample supplies raw_API, raw_tcp, raw_fds, index, observed_unix_s,
    API_begin_unix_s/API_end_unix_s, tcp_begin_unix_s/tcp_end_unix_s and
    original log_chunks with raw bytes. Authentication and all nontransport
    runtime checks remain mandatory at the caller.
    """
    require(lua_sha256==LUA_SHA,'Exact held Lua source required')
    require(type(samples) is list and 3<=len(samples)<=32,'Completed bounded sample sequence required')
    require(set(log_cursors)==SLOTS,'All192 bound original log cursors required')
    actor_registry={str(actor['slot']):actor for actor in binding['actors']}
    require(set(actor_registry)==SLOTS,'All192 bound original actors required')
    cursors={slot:dict(value) for slot,value in log_cursors.items()}
    decoded=[];caps=[];previous=None
    for sample in samples:
        now=sample['observed_unix_s']
        require(finite(now) and now>0,'Original observation timestamp required')
        if previous is not None:
            require(sample['index']==previous['index']+1 and
                    0<now-previous['observed_unix_s']<=LIMITS['max_sample_gap_s'],
                    'Skipped, reordered or excessively spaced original sample')
        integer(sample['index'])
        API=decode(sample['raw_API']);API_rows=rows(API)
        require(finite(API.get('ts')) and 0<=now-API['ts']<=LIMITS['max_API_age_s'],
                'Stale/future API evidence')
        times=[sample[key] for key in ('API_begin_unix_s','API_end_unix_s',
                                     'tcp_begin_unix_s','tcp_end_unix_s')]+[now]
        require(all(finite(value) for value in times) and times==sorted(times)
                and now-times[0]<=.5,'Unbracketed or slow original capture')
        view=fd_view(sample['raw_fds'],binding,now);table=tcp(sample['raw_tcp'])
        for chunk in sample['log_chunks']:
            slot=str(integer(chunk['slot']));require(slot in SLOTS,'Foreign log slot')
            cursor=cursors[slot];raw=chunk['raw']
            require(chunk.get('actor_pid')==actor_registry[slot]['pid'],'Cap log belongs to another actor')
            require(type(raw) is bytes and 0<len(raw)<=256<<10
                and chunk['path']==cursor['path'] and chunk['device']==cursor['device']
                and chunk['inode']==cursor['inode'] and chunk['offset']==cursor['offset']
                and chunk['bytes']==len(raw),'Log origin changed or original byte range skipped')
            require(finite(chunk['lower_observed_unix_s']) and finite(chunk['upper_observed_unix_s'])
                and samples[0]['observed_unix_s']-.5<=chunk['lower_observed_unix_s']
                <=chunk['upper_observed_unix_s']<=now,'Unbounded cap-log observation interval')
            cursor['offset']+=len(raw)
            count=raw.count(CAP)
            if count:
                require(count==1,'Ambiguous multiple cap markers')
                tail=raw.split(CAP,1)[1]
                require(b'MAME interface initialized.' in tail
                    and b'Socket connection opened to socket.dell:9998' in tail,
                    'Original cap did not show initialization and reconnect')
                caps.append(dict(slot=slot,raw_sha256=hashlib.sha256(raw).hexdigest(),
                    path=chunk['path'],device=chunk['device'],inode=chunk['inode'],
                    offset=chunk['offset'],bytes=len(raw)))
        decoded.append(dict(sample=sample,API=API,rows=API_rows,table=table,view=view))
        previous=sample
    start,end=decoded[0],decoded[-1]
    duration=end['sample']['observed_unix_s']-start['sample']['observed_unix_s']
    require(0<duration<=LIMITS['max_window_s'],'Handover exceeded fixed observation window')
    require(start['API']['client_count']==end['API']['client_count']==192,
            'No full192 before/after restoration')
    before=full_join(start['table'],start['view']);after=full_join(end['table'],end['view'])
    changed=[slot for slot in sorted(SLOTS) if
             start['rows'][slot][0]['client_id']!=end['rows'][slot][0]['client_id']
             or before[slot]['client']!=after[slot]['client']]
    require(len(changed)==1,'Exactly one owned actor handover required')
    slot=changed[0]
    require(len(caps)==1 and caps[0]['slot']==slot,'Fresh same-slot cap certificate missing or ambiguous')
    old=start['rows'][slot][0]['client_id'];new=end['rows'][slot][0]['client_id']
    require(old!=new and before[slot]['client']['inode']!=after[slot]['client']['inode'],
            'Fresh API epoch and owned socket inode required')
    require(before[slot]['client']['local']!=after[slot]['client']['local'],
            'Old/new connection endpoints did not change')
    allowed_clients={}
    for current in SLOTS:
        allowed_clients[current]=[before[current]['client']]
        if current==slot:
            allowed_clients[current].append(after[current]['client'])
    allowed={ (client['local'],client['peer']):current
             for current,clients in allowed_clients.items() for client in clients }
    require(len(allowed)==193,'Original/new actor endpoint set overlaps')
    overlap_count=0;stage=0
    for item in decoded:
        API_rows=item['rows'];ids={row['client_id'] for row in API_rows[slot]}
        require(ids in ({old},{old,new},{new}),'Unexpected target-slot client epoch')
        phase=0 if ids=={old} else 1 if ids=={old,new} else 2
        require(phase>=stage,'API epoch regressed during handover')
        stage=phase
        overlap_count+=int(phase==1)
        for current in SLOTS-{slot}:
            require(len(API_rows[current])==1 and
                API_rows[current][0]['client_id']==start['rows'][current][0]['client_id'],
                'Another actor changed API epochs or duplicated')
        for row in API_rows[slot]:
            if row['client_id']==new:
                require(row['connected_seconds']<=LIMITS['max_window_s'],
                        'Replacement API connection is not fresh')
        server_inodes=set(item['view']['trainer']['socket_fds'].values())
        for connection in item['table']:
            if connection['state']!='01':
                continue
            if int(connection['peer'][9:],16)==9998:
                endpoint=(connection['local'],connection['peer'])
                require(endpoint in allowed,'Unknown training TCP peer/endpoint')
                current=allowed[endpoint]
                # A middle capture can precede the next FD census; original
                # same-process ownership must still exist in this bounded window.
                require(any(connection['inode'] in sample['view']['actors'][current]['socket_fds'].values()
                            for sample in decoded),'Live client socket is not owned by the original actor')
            if int(connection['local'][9:],16)==9998:
                require((connection['peer'],connection['local']) in allowed,
                        'Unknown trainer-side peer/endpoint')
                require(connection['inode']==0 or connection['inode'] in server_inodes or
                    any(connection['inode'] in sample['view']['trainer']['socket_fds'].values()
                        for sample in decoded),'Trainer reverse socket has unknown owner')
    require(overlap_count>=1 and stage==2,'No observed duplicate interval or final fresh epoch')
    actor=next(actor for actor in binding['actors'] if str(actor['slot'])==slot)
    return dict(schema=SCHEMA,slot=int(slot),actor_pid=actor['pid'],actor_birth=actor['starttime_ticks'],
        before_client_id=old,after_client_id=new,old_socket=before[slot]['client'],new_socket=after[slot]['client'],
        cap=caps[0],first_index=start['sample']['index'],last_index=end['sample']['index'],
        begin_unix_s=start['sample']['observed_unix_s'],end_unix_s=end['sample']['observed_unix_s'],
        charged_s=duration,overlap_samples=overlap_count,samples=len(samples),
        all_nontransport_main_checks_still_required=True,quality_qualified=False,promotion=False)


def closed_budget(certificates):
    """Fold recomputed certificates across all four legs; never trust cached flags."""
    require(type(certificates) is list and len(certificates)<=LIMITS['max_episodes'],
            'Whole-case handover count exceeded')
    seen=set();total=0.;previous_end=None
    for certificate in certificates:
        require(certificate['schema']==SCHEMA and finite(certificate['charged_s'])
                and 0<certificate['charged_s']<=LIMITS['max_window_s'],
                'Malformed or overlong completed certificate')
        require(finite(certificate['begin_unix_s']) and finite(certificate['end_unix_s'])
                and certificate['charged_s']==certificate['end_unix_s']-certificate['begin_unix_s'],
                'Certificate duration differs from captured bounds')
        key=(certificate['slot'],certificate['cap']['inode'],certificate['cap']['offset'],
             certificate['cap']['raw_sha256'])
        require(key not in seen and (previous_end is None or certificate['begin_unix_s']>=previous_end),
                'Reused cap bytes or overlapping/reordered episode windows')
        seen.add(key);previous_end=certificate['end_unix_s'];total+=certificate['charged_s']
    require(total<=LIMITS['max_total_s'],'Whole-case handover duration exceeded')
    return dict(episodes=len(certificates),total_charged_s=total,all_closed=True,
                quality_qualified=False,all_nontransport_main_checks_still_required=True)
