"""Pure unselected streaming transport review using the source-bound v1 primitives.

This consumes every original sample and never normalizes an API count or time.
Only192/193 are covered. Several independently witnessed normal handovers may
share a window; simultaneous API194 remains unsupported. Physical/source/recipe/
pipeline/bank/autosave checks remain mandatory outside this transport layer.
"""
import copy
import hashlib

SCHEMA='robotron-owned-cap-transport-window-v2'
LIMITS=dict(max_window_s=2.,max_sample_gap_s=.5,max_fd_age_s=1.25,max_API_age_s=1.,
            max_epoch_skew_s=.5,min_old_connection_age_s=2.,max_changed_actors=4,
            max_groups=8192,max_overlap_groups=1024,max_overlap_charged_s=600.)


class AwaitEvidence(ValueError):
    """Not a valid health observation; more original evidence is still required."""


def cap_key(cap):
    return tuple(cap[key] for key in ('path','device','inode','marker_offset','marker_sha256'))


def decode_sample(p,binding,sample,previous=None):
    now=sample['observed_unix_s'];p.require(p.finite(now) and now>0,'Original observation time required')
    p.integer(sample['index'])
    if previous is not None:
        p.require(sample['index']==previous['index']+1 and
            0<now-previous['observed_unix_s']<=LIMITS['max_sample_gap_s'],
            'Skipped, reordered or delayed original stream sample')
    API=p.decode(sample['raw_API']);rows=p.rows(API)
    p.require(p.finite(API.get('ts')) and 0<=now-API['ts']<=LIMITS['max_API_age_s'],
              'Stale/future original API')
    times=[sample[key] for key in ('API_begin_unix_s','API_end_unix_s',
                                 'tcp_begin_unix_s','tcp_end_unix_s')]+[now]
    p.require(all(p.finite(value) for value in times) and times==sorted(times)
              and now-times[0]<=.5,'Slow/unbracketed original sample')
    return dict(sample=sample,API=API,rows=rows,table=p.tcp(sample['raw_tcp']),
                view=p.fd_view(sample['raw_fds'],binding,now))


def full_owned_join(p,table,view):
    """Stable means every established row belongs to the exact192 joined pairs."""
    joined=p.full_join(table,view)
    allowed={(row['local'],row['peer'],row['inode'],row['uid'])
             for pair in joined.values() for row in pair.values()}
    p.require(all((row['local'],row['peer'],row['inode'],row['uid']) in allowed
                  for row in table if row['state']=='01'),
              'Unknown established TCP row outside the full192 owned pairs')
    return joined


def append_logs(p,binding,cursors,sample):
    registry={str(actor['slot']):actor for actor in binding['actors']};pieces=[]
    for chunk in sample['log_chunks']:
        slot=str(p.integer(chunk['slot']));p.require(slot in p.SLOTS,'Unknown log actor')
        cursor=cursors[slot];raw=chunk['raw']
        p.require(type(raw) is bytes and 0<len(raw)<=256<<10 and chunk['bytes']==len(raw)
            and chunk['actor_pid']==registry[slot]['pid'] and chunk['path']==cursor['path']
            and chunk['device']==cursor['device'] and chunk['inode']==cursor['inode']
            and chunk['offset']==cursor['offset'],'Wrong actor/log origin or skipped original bytes')
        lower,upper=chunk['lower_observed_unix_s'],chunk['upper_observed_unix_s']
        p.require(p.finite(lower) and p.finite(upper) and lower<=upper<=sample['observed_unix_s'],
                  'Unbracketed original log bytes')
        cursor['offset']+=len(raw)
        pieces.append(dict(slot=slot,path=chunk['path'],device=chunk['device'],inode=chunk['inode'],
            offset=chunk['offset'],raw=raw,lower_unix_s=lower,upper_unix_s=upper))
    return pieces


def parse_caps(p,pieces,known_keys,start_time):
    per_slot={}
    for piece in pieces:
        slot=piece['slot']
        p.require(piece['lower_unix_s']>=start_time-.5,'Cap/log evidence predates the window')
        entry=per_slot.setdefault(slot,dict(slot=slot,path=piece['path'],device=piece['device'],
            inode=piece['inode'],offset=piece['offset'],raw=b''))
        p.require(piece['offset']==entry['offset']+len(entry['raw']),
                  'Original combined actor log bytes are not contiguous')
        entry['raw']+=piece['raw']
    result=[];incomplete=False
    for entry in per_slot.values():
        raw=entry['raw'];incomplete|=not raw.endswith(b'\n')
        position=0
        while True:
            index=raw.find(p.CAP,position)
            if index<0:break
            position=index+len(p.CAP)
            if index>0:p.require(raw[index-1:index]==b'\n','Cap marker is not an original full line')
            if len(raw)<position+1:
                incomplete=True;continue
            p.require(raw[position:position+1]==b'\n','Cap marker line changed')
            cap=dict(slot=entry['slot'],path=entry['path'],device=entry['device'],inode=entry['inode'],
                marker_offset=entry['offset']+index,marker_sha256=hashlib.sha256(p.CAP+b'\n').hexdigest(),
                combined_offset=entry['offset'],combined_bytes=len(raw),
                combined_raw_sha256=hashlib.sha256(raw).hexdigest())
            if cap_key(cap) in known_keys:
                continue
            tail=raw[position:]
            if b'MAME interface initialized.' not in tail or b'Socket connection opened to socket.dell:9998' not in tail:
                incomplete=True;continue
            result.append(cap)
    return result,incomplete


def certify_window(p,binding,cursors,lua_sha,samples,known_keys=()):
    p.require(lua_sha==p.LUA_SHA,'Exact held Lua source required')
    p.require(type(samples) is list and 2<=len(samples)<=32,'Bounded complete transport window required')
    p.require(set(cursors)==p.SLOTS,'All192 original log cursors required')
    current=copy.deepcopy(cursors);decoded=[];pieces=[];previous=None
    for sample in samples:
        item=decode_sample(p,binding,sample,previous);decoded.append(item)
        pieces.extend(append_logs(p,binding,current,sample));previous=sample
    start,end=decoded[0],decoded[-1]
    duration=end['sample']['observed_unix_s']-start['sample']['observed_unix_s']
    p.require(0<duration<=LIMITS['max_window_s'],'Transport evidence window expired')
    p.require(start['API']['client_count']==192,'Window did not begin at full unique192')
    before=full_owned_join(p,start['table'],start['view'])
    if end['API']['client_count']!=192:
        raise AwaitEvidence('Unique192 restoration is pending')
    try:
        after=full_owned_join(p,end['table'],end['view'])
    except ValueError as error:
        raise AwaitEvidence('Fresh full owned-socket restoration is pending') from error
    changed=[slot for slot in sorted(p.SLOTS) if
        start['rows'][slot][0]['client_id']!=end['rows'][slot][0]['client_id']
        or before[slot]['client']!=after[slot]['client']]
    p.require(len(changed)<=LIMITS['max_changed_actors'],'Too many simultaneous actor handovers')
    caps,incomplete=parse_caps(p,pieces,set(known_keys),start['sample']['observed_unix_s'])
    if incomplete:
        raise AwaitEvidence('Complete original reset/reconnect log lines are pending')
    if not changed:
        if caps:
            raise AwaitEvidence('A source-certified cap has not completed its socket/API handover')
        p.require(all(item['API']['client_count']==192 for item in decoded),
                  'An overlap was not followed by a fresh epoch')
        for item in decoded:
            p.require(all(len(item['rows'][slot])==1 and
                item['rows'][slot][0]['client_id']==start['rows'][slot][0]['client_id']
                for slot in p.SLOTS),'Unexplained intermediate client change')
            full_owned_join(p,item['table'],item['view'])
            p.require(all(abs((item['API']['ts']-item['rows'][slot][0]['connected_seconds'])-
                (start['API']['ts']-start['rows'][slot][0]['connected_seconds']))
                <=LIMITS['max_epoch_skew_s'] for slot in p.SLOTS),
                'Unexplained connection epoch change in log-only window')
        return dict(schema=SCHEMA,kind='log_only',actors=[],caps=[],overlap_indices=[],
            first_index=samples[0]['index'],last_index=samples[-1]['index'],
            begin_unix_s=samples[0]['observed_unix_s'],end_unix_s=samples[-1]['observed_unix_s'],
            window_s=duration,charged_s=0.,all_nontransport_main_checks_still_required=True,quality_qualified=False)
    cap_slots=[cap['slot'] for cap in caps]
    if set(cap_slots)!=set(changed):
        raise AwaitEvidence('Every changed actor needs its own fresh original cap/reconnect bytes')
    p.require(len(cap_slots)==len(set(cap_slots)),'Several ambiguous cap epochs for one actor')
    registry={str(actor['slot']):actor for actor in binding['actors']};links=[]
    for slot in changed:
        old=start['rows'][slot][0]['client_id'];new=end['rows'][slot][0]['client_id']
        old_age=start['rows'][slot][0]['connected_seconds'];new_age=end['rows'][slot][0]['connected_seconds']
        old_epoch=start['API']['ts']-old_age;new_epoch=end['API']['ts']-new_age
        p.require(old_age>=LIMITS['min_old_connection_age_s'] and new_age<=LIMITS['max_window_s']
            and new_epoch-old_epoch>=LIMITS['min_old_connection_age_s']-LIMITS['max_epoch_skew_s'],
            'Old/new connection epochs are not distinguishable and fresh')
        p.require(before[slot]['client']['inode']!=after[slot]['client']['inode']
            and before[slot]['client']['local']!=after[slot]['client']['local'],
            'Changed actor lacks a fresh API epoch and owned TCP endpoint')
        links.append(dict(slot=int(slot),actor_pid=registry[slot]['pid'],actor_birth=registry[slot]['starttime_ticks'],
            before_client_id=old,after_client_id=new,before_connection_epoch=old_epoch,
            after_connection_epoch=new_epoch,old_socket=before[slot]['client'],
            new_socket=after[slot]['client'],cap=next(cap for cap in caps if cap['slot']==slot)))
    allowed={}
    for slot in p.SLOTS:
        for connection in [before[slot]['client']]+([after[slot]['client']] if slot in changed else []):
            endpoint=(connection['local'],connection['peer'])
            p.require(endpoint not in allowed,'Actor TCP endpoint reused across slots')
            allowed[endpoint]=slot
    stages={slot:0 for slot in changed};overlaps=[]
    for item in decoded:
        for slot in p.SLOTS-set(changed):
            p.require(len(item['rows'][slot])==1 and
                item['rows'][slot][0]['client_id']==start['rows'][slot][0]['client_id'],
                'Uncertified actor/client change inside the window')
            epoch=item['API']['ts']-item['rows'][slot][0]['connected_seconds']
            old_epoch=start['API']['ts']-start['rows'][slot][0]['connected_seconds']
            p.require(abs(epoch-old_epoch)<=LIMITS['max_epoch_skew_s'],'Another connection epoch changed')
        for link in links:
            slot=str(link['slot']);ids={row['client_id'] for row in item['rows'][slot]}
            old,new=link['before_client_id'],link['after_client_id']
            p.require(ids in ({old},{old,new},{new}),'Unknown API epoch in a certified actor slot')
            if old==new:
                p.require(len(item['rows'][slot])==1,'One CID cannot represent two simultaneous connections')
                epoch=item['API']['ts']-item['rows'][slot][0]['connected_seconds']
                if abs(epoch-link['before_connection_epoch'])<=LIMITS['max_epoch_skew_s']:
                    stage=0
                else:
                    p.require(abs(epoch-link['after_connection_epoch'])<=LIMITS['max_epoch_skew_s'],
                              'Reused CID has an unrecognized connection epoch')
                    stage=2
            else:
                stage=0 if ids=={old} else 1 if ids=={old,new} else 2
            p.require(stage>=stages[slot],'Actor API epoch regressed')
            stages[slot]=stage
            for row in item['rows'][slot]:
                epoch=item['API']['ts']-row['connected_seconds']
                if row['client_id']==new and (old!=new or stage==2):
                    p.require(row['connected_seconds']<=LIMITS['max_window_s'],'New API connection is not fresh')
                    p.require(abs(epoch-link['after_connection_epoch'])<=LIMITS['max_epoch_skew_s'],
                              'New connection epoch changed within the window')
                else:
                    p.require(abs(epoch-link['before_connection_epoch'])<=LIMITS['max_epoch_skew_s'],
                              'Old CID was reused by a different connection epoch')
        if item['API']['client_count']==193:
            overlaps.append(item['sample']['index'])
        for connection in item['table']:
            if connection['state']!='01':continue
            if int(connection['peer'][9:],16)==9998:
                endpoint=(connection['local'],connection['peer'])
                p.require(endpoint in allowed,'Unknown local/remote training TCP endpoint')
                slot=allowed[endpoint]
                p.require(any(connection['inode'] in sample['view']['actors'][slot]['socket_fds'].values()
                              for sample in decoded),'TCP client inode has no original actor owner')
            if int(connection['local'][9:],16)==9998:
                p.require((connection['peer'],connection['local']) in allowed,'Unknown trainer-side TCP peer')
                p.require(connection['inode']==0 or any(connection['inode'] in
                    sample['view']['trainer']['socket_fds'].values() for sample in decoded),
                    'Unknown trainer-side TCP socket inode')
    p.require(all(stage==2 for stage in stages.values()),'Incomplete actor handover')
    return dict(schema=SCHEMA,kind='overlap' if overlaps else 'normal_reconnect',actors=links,caps=caps,
        overlap_indices=overlaps,first_index=samples[0]['index'],last_index=samples[-1]['index'],
        begin_unix_s=samples[0]['observed_unix_s'],end_unix_s=samples[-1]['observed_unix_s'],
        window_s=duration,charged_s=duration if overlaps else 0.,
        all_nontransport_main_checks_still_required=True,quality_qualified=False)


def closed_budget(p,groups):
    p.require(type(groups) is list and len(groups)<=LIMITS['max_groups'],'Whole-case group budget exceeded')
    seen=set();previous_end=None;overlaps=0;total=0.;normal=0
    for group in groups:
        p.require(group['schema']==SCHEMA and group['kind'] in ('log_only','normal_reconnect','overlap'),
                  'Unknown completed transport group')
        duration=group['end_unix_s']-group['begin_unix_s']
        p.require(p.finite(duration) and 0<duration<=LIMITS['max_window_s'] and duration==group['window_s'],
                  'Invalid/overlong group clock bounds')
        p.require(previous_end is None or group['begin_unix_s']>=previous_end,
                  'Overlapping/reordered group evidence windows')
        previous_end=group['end_unix_s']
        for cap in group['caps']:
            key=cap_key(cap);p.require(key not in seen,'Cap marker byte range reused across groups/legs');seen.add(key)
        if group['kind']=='overlap':
            p.require(group['overlap_indices'] and group['charged_s']==duration,'Overlap duration not fully charged')
            overlaps+=1;total+=duration
        else:
            p.require(not group['overlap_indices'] and group['charged_s']==0.,'Healthy handover consumes an exception')
            normal+=int(group['kind']=='normal_reconnect')
    p.require(overlaps<=LIMITS['max_overlap_groups'] and total<=LIMITS['max_overlap_charged_s'],
              'Cumulative four-leg overlap budget exceeded')
    return dict(groups=len(groups),normal_reconnects=normal,overlap_groups=overlaps,
        total_overlap_charged_s=total,all_closed=True,quality_qualified=False,
        all_nontransport_main_checks_still_required=True)


class Stream:
    """Single original stream; any rejection is sticky and incomplete tails fail."""
    def __init__(self,p,binding,cursors,lua_sha,prior_groups=()):
        p.require(lua_sha==p.LUA_SHA and set(cursors)==p.SLOTS,'Source-bound original registry/cursors required')
        self.p=p;self.binding=copy.deepcopy(binding);self.cursors=copy.deepcopy(cursors);self.lua_sha=lua_sha
        self.groups=copy.deepcopy(list(prior_groups));closed_budget(p,self.groups)
        self.prior_group_count=len(self.groups)
        self.used={cap_key(cap) for group in self.groups for cap in group['caps']}
        self.previous=None;self.baseline=None;self.baseline_cursors=None;self.pending=None;self.pending_cursors=None
        self.failed=None;self.samples=0;self.closed=False

    def observe(self,source_sample):
        self.p.require(self.failed is None and not self.closed,'Original stream rejected/closed; no recovery/retry')
        sample=copy.deepcopy(source_sample)
        try:
            return self._observe(sample)
        except Exception as error:
            self.failed=repr(error)
            raise

    def _observe(self,sample):
        p=self.p;before_cursors=copy.deepcopy(self.cursors)
        item=decode_sample(p,self.binding,sample,self.previous)
        append_logs(p,self.binding,self.cursors,sample)
        self.previous=sample;self.samples+=1
        stable=False;joined=None
        if item['API']['client_count']==192:
            try:
                joined=full_owned_join(p,item['table'],item['view']);stable=True
            except ValueError:
                pass
        if self.baseline is None:
            p.require(stable and not sample['log_chunks'],'Stream must begin at a full stable192 baseline')
            self.baseline=sample;self.baseline_cursors=before_cursors
            return dict(phase='full192',accepted=True,overlap_pending=False)
        if self.pending is None:
            old=decode_sample(p,self.binding,self.baseline)
            old_join=full_owned_join(p,old['table'],old['view'])
            unchanged=stable and all(item['rows'][slot][0]['client_id']==old['rows'][slot][0]['client_id']
                and joined[slot]['client']==old_join[slot]['client'] for slot in p.SLOTS)
            if unchanged and not sample['log_chunks']:
                p.require(all(abs((item['API']['ts']-item['rows'][slot][0]['connected_seconds'])-
                    (old['API']['ts']-old['rows'][slot][0]['connected_seconds']))
                    <=LIMITS['max_epoch_skew_s'] for slot in p.SLOTS),
                    'Unexplained connection epoch change on an unchanged owned socket')
                self.baseline=sample;self.baseline_cursors=before_cursors
                return dict(phase='full192',accepted=True,overlap_pending=False)
            self.pending=[self.baseline];self.pending_cursors=copy.deepcopy(self.baseline_cursors)
        self.pending.append(sample)
        p.require(len(self.pending)<=32 and
            sample['observed_unix_s']-self.pending[0]['observed_unix_s']<=LIMITS['max_window_s'],
            'Original pending handover exceeded its fixed evidence window')
        if stable:
            try:
                group=certify_window(p,self.binding,self.pending_cursors,self.lua_sha,self.pending,self.used)
            except AwaitEvidence:
                return dict(phase='awaiting_original_evidence',accepted=False,overlap_pending=True)
            self.groups.append(group);closed_budget(p,self.groups)
            self.used.update(cap_key(cap) for cap in group['caps'])
            self.pending=None;self.pending_cursors=None
            self.baseline=sample;self.baseline_cursors=before_cursors
            return dict(phase='full192',accepted=True,overlap_pending=False,closed_group=group)
        return dict(phase='awaiting_original_evidence',accepted=False,overlap_pending=True)

    def close(self):
        try:
            self.p.require(self.failed is None and not self.closed and self.baseline is not None and self.pending is None,
                           'Rejected/uninitialized/incomplete original stream cannot close valid')
            self.p.require(self.previous['index']==self.baseline['index'],'Final full192 mapping missing')
            result=dict(schema='robotron-owned-cap-transport-stream-summary-v2',samples=self.samples,
                groups=copy.deepcopy(self.groups[self.prior_group_count:]),
                case_groups=copy.deepcopy(self.groups),budget=closed_budget(self.p,self.groups),
                final_full192=True,all_nontransport_main_checks_still_required=True,quality_qualified=False)
            self.closed=True
            return result
        except Exception as error:
            self.failed=repr(error)
            self.closed=True
            raise
