"""Pure unselected complete stream with immutable accepted-baseline parse caching.

Preserves original raw API/TCP/log/FD evidence and strict192 actor ownership.
Every exception requires a completed <=2s before/after window. The two kinds
share one four-leg frequency/time budget. Caller-authenticated raw replay and
all physical/source/recipe/pipeline/bank/autosave checks remain mandatory.
"""
import copy
import hashlib
import re

SCHEMA='robotron-owned-transport-stream-summary-v4'
LIMITS=dict(max_case_groups=8192,max_case_exception_groups=1024,max_case_charged_s=600.)



READINESS_SCHEMA='robotron-owned-initial-readiness-record-v1'
INITIAL_LIMITS=dict(max_wait_s=2.,max_samples=11,max_case_readiness_groups=4)


def readiness_view(p,cap,proc,item,expected_uid):
    """Account for EVERY original row, with an explicitly counted identity map.

    The unique identity projection is used only to prove the owner bijection.
    Original rows/counts/bytes remain intact in the caller's raw sample, and the
    exact multiplicities and both repeated rows remain in this readiness record.
    This is startup readiness, never a two-sided scientific transport certificate.
    """
    sample=item['sample']
    p.require(item['API']['client_count']==192 and not sample['log_chunks'],
              'Initial readiness requires unique192 and no cap/log bytes')
    table=item['table'];counts={};projection={}
    for row in table:
        identity=proc.key(row)
        counts[identity]=counts.get(identity,0)+1
        projection.setdefault(identity,row)
        if row['state']=='01':p.require(row['uid']==expected_uid,'Initial socket UID differs')
    joined=cap.full_owned_join(p,list(projection.values()),item['view'])
    expected={proc.key(row)for pair in joined.values()for row in pair.values()}
    original_established=[row for row in table if row['state']=='01']
    p.require(len(expected)==384 and len({key[3]for key in expected})==384
        and {proc.key(row)for row in original_established}==expected,
        'Initial readiness lacks the exact384 owned socket identities')
    _,repeats=proc.original_tcp(p,sample['raw_tcp'])
    p.require(len(repeats)<=1 and len(original_established)==384+len(repeats)
        and all(counts[key]in (1,2)for key in expected),
        'Initial readiness has unsupported row multiplicity')
    for repeat in repeats:
        key=tuple(repeat['connection'][name]for name in ('local','peer','state','inode','uid'))
        p.require(key in expected and counts[key]==2
            and int(key[0][9:],16)==9998,'Initial repeated row is not an owned trainer socket')
    signature={slot:tuple(proc.key(pair[role])for role in ('client','server'))
        for slot,pair in joined.items()}
    epochs={slot:(rows[0]['client_id'],item['API']['ts']-rows[0]['connected_seconds'])
        for slot,rows in item['rows'].items()}
    record=dict(index=sample['index'],observed_unix_s=sample['observed_unix_s'],
        raw_API_sha256=hashlib.sha256(sample['raw_API']).hexdigest(),
        raw_TCP_sha256=hashlib.sha256(sample['raw_tcp']).hexdigest(),
        raw_FD_sha256=hashlib.sha256(sample['raw_fds']).hexdigest(),
        original_established_rows=len(original_established),distinct_owned_socket_identities=len(expected),
        raw_API_count=item['API']['client_count'],expected_uid=expected_uid,
        original_repeats=copy.deepcopy(repeats))
    return joined,signature,epochs,record


def readiness_budget(p,groups):
    p.require(len(groups)<=INITIAL_LIMITS['max_case_readiness_groups'],
              'Too many initial readiness groups in the four-leg case')
    total=0.;seen=set()
    for group in groups:
        p.require(group['schema']==READINESS_SCHEMA and group['kind']=='initial_owned_readiness'
            and group['limits']==INITIAL_LIMITS and group['scientific_observations_accepted']is False,
            'Unknown or mislabelled initial readiness proof')
        records=group['observations'];span=group['end_unix_s']-group['begin_unix_s']
        p.require(type(records)is list and 2<=len(records)<=INITIAL_LIMITS['max_samples']
            and p.finite(span)and 0<span<=INITIAL_LIMITS['max_wait_s']
            and span==group['window_s']==group['charged_s']
            and records[0]['observed_unix_s']==group['begin_unix_s']
            and records[-1]['observed_unix_s']==group['end_unix_s']
            and records[0]['index']==group['first_index']
            and records[-1]['index']==group['last_index'],'Initial readiness interval/charge differs')
        repeated=None
        for index,record in enumerate(records):
            p.require(type(record['index'])is int and record['index']==group['first_index']+index
                and record['raw_API_count']==192 and record['distinct_owned_socket_identities']==384
                and type(record['expected_uid'])is int and record['expected_uid']>0,
                'Initial readiness rows/owners/indices differ')
            if index:p.require(0<record['observed_unix_s']-records[index-1]['observed_unix_s']<=.5,
                               'Initial readiness observation gap exceeds the fixed bound')
            for key in ('raw_API_sha256','raw_TCP_sha256','raw_FD_sha256'):
                p.require(type(record[key])is str and re.fullmatch('[0-9a-f]{64}',record[key])is not None,
                          'Original readiness wire hash required')
            event=(record['index'],record['observed_unix_s'],record['raw_API_sha256'],record['raw_TCP_sha256'])
            p.require(event not in seen,'Initial readiness evidence reused');seen.add(event)
            repeats=record['original_repeats']
            if index==len(records)-1:
                p.require(not repeats and record['original_established_rows']==384,
                          'Readiness must end at an actual clean full192 baseline')
            else:
                p.require(len(repeats)==1 and record['original_established_rows']==385,
                          'Every pending readiness sample must retain its known repeat')
                connection=repeats[0]['connection']
                identity=tuple(connection[name]for name in ('local','peer','state','inode','uid'))
                p.require(identity[2]=='01'and identity[3]>0 and identity[4]==record['expected_uid']
                    and int(identity[0][9:],16)==9998 and len(repeats[0]['occurrences'])==2,
                    'Initial repeat identity/multiplicity differs')
                p.require(repeated is None or repeated==identity,'Initial repeated connection changed')
                repeated=identity
        total+=span
    return total

def closed_budget(p,cap,proc,groups):
    p.require(type(groups)is list and len(groups)<=LIMITS['max_case_groups'],'Whole-case transport group budget exceeded')
    cap_groups=[];proc_groups=[];initial_groups=[];previous_end=None
    for group in groups:
        if group['schema']==cap.SCHEMA:cap_groups.append(group)
        elif group['schema']==proc.SCHEMA:proc_groups.append(group)
        elif group['schema']==READINESS_SCHEMA:initial_groups.append(group)
        else:raise ValueError('Unknown source-bound transport proof schema')
        p.require(previous_end is None or group['begin_unix_s']>=previous_end,
                  'Mixed transport evidence windows overlap or regress')
        previous_end=group['end_unix_s']
    caps=cap.closed_budget(p,cap_groups);repeats=proc.closed_budget(p,proc_groups)
    initial_charge=readiness_budget(p,initial_groups)
    exceptions=caps['overlap_groups']+repeats['events']+len(initial_groups)
    charged=caps['total_overlap_charged_s']+repeats['total_charged_s']+initial_charge
    p.require(exceptions<=LIMITS['max_case_exception_groups']and charged<=LIMITS['max_case_charged_s'],
              'Shared four-leg transport exception count/time budget exceeded')
    return dict(groups=len(groups),normal_reconnects=caps['normal_reconnects'],
        cap_overlap_groups=caps['overlap_groups'],proc_repeat_groups=repeats['events'],
        initial_readiness_groups=len(initial_groups),initial_readiness_charged_s=initial_charge,
        total_exception_groups=exceptions,total_charged_s=charged,all_closed=True,
        all_nontransport_main_checks_still_required=True,quality_qualified=False)


class Stream:
    """One unfiltered original stream. A rejection/unfinished close is sticky."""
    def __init__(self,p,cap,proc,binding,cursors,lua_sha,prior_groups=(),*,expected_uid):
        p.require(lua_sha==p.LUA_SHA and set(cursors)==p.SLOTS,'Exact source-bound registry/cursors required')
        self.p=p;self.cap=cap;self.proc=proc;self.binding=copy.deepcopy(binding)
        self.cursors=copy.deepcopy(cursors);self.lua_sha=lua_sha;self.groups=copy.deepcopy(list(prior_groups))
        closed_budget(p,cap,proc,self.groups);self.prior_group_count=len(self.groups)
        self.used={cap.cap_key(value)for group in self.groups for value in group.get('caps',[])}
        self.previous=None;self.baseline=None;self.baseline_cursors=None;self.pending=None;self.pending_cursors=None
        self.failed=None;self.samples=0;self.closed=False
        self._baseline_decoded=None;self._baseline_joined=None
        p.require(type(expected_uid)is int and expected_uid>0,'Explicit owned readiness UID required')
        self.expected_uid=expected_uid;self.initial_signature=None;self.initial_epochs=None
        self.initial_begin=None;self.initial_records=[];self.ready_index=None;self.ready_unix_s=None
        self.initial_unaccepted_samples=0
        class OriginalRows:
            def __getattr__(inner,name):return getattr(p,name)
            def tcp(inner,raw):return proc.original_tcp(p,raw)[0]
        self.original_rows=OriginalRows()

    def observe(self,source_sample):
        self.p.require(self.failed is None and not self.closed,'Original stream rejected/closed; no recovery/retry')
        try:return self._observe(copy.deepcopy(source_sample))
        except Exception as error:self.failed=repr(error);raise

    def _observe(self,sample):
        p=self.p;cap=self.cap;before_cursors=copy.deepcopy(self.cursors)
        item=cap.decode_sample(self.original_rows,self.binding,sample,self.previous)
        cap.append_logs(p,self.binding,self.cursors,sample)
        self.previous=sample;self.samples+=1;stable=False;joined=None
        if item['API']['client_count']==192:
            try:joined=cap.full_owned_join(p,item['table'],item['view']);stable=True
            except ValueError:pass
        if self.baseline is None:
            p.require(self.samples<=INITIAL_LIMITS['max_samples'],
                      'Initial readiness sample bound exceeded')
            ready_join,signature,epochs,record=readiness_view(p,cap,self.proc,item,self.expected_uid)
            if self.initial_signature is None:
                self.initial_signature=signature;self.initial_epochs=epochs
                self.initial_begin=sample['observed_unix_s']
            p.require(0<=sample['observed_unix_s']-self.initial_begin<=INITIAL_LIMITS['max_wait_s'],
                      'Initial readiness time bound exceeded')
            p.require(signature==self.initial_signature and all(
                epochs[slot][0]==self.initial_epochs[slot][0]and
                abs(epochs[slot][1]-self.initial_epochs[slot][1])<=cap.LIMITS['max_epoch_skew_s']
                for slot in p.SLOTS),'Initial owned socket or logical epoch changed')
            if record['original_repeats']:
                self.initial_records.append(record)
                p.require(all(value['original_repeats'][0]['connection']==record['original_repeats'][0]['connection']
                    for value in self.initial_records),'Initial repeated connection changed')
                # This is an explicit unaccepted readiness phase. The original
                # scientific baseline has not started; no rejected stream resets.
                self.pending=[sample]
                return dict(phase='awaiting_initial_full192_baseline',accepted=False,
                            overlap_pending=True,readiness_pending=True)
            p.require(stable and joined==ready_join,'Actual clean full192 baseline required')
            if self.initial_records:
                records=[*self.initial_records,record]
                span=sample['observed_unix_s']-self.initial_begin
                group=dict(schema=READINESS_SCHEMA,kind='initial_owned_readiness',
                    limits=dict(INITIAL_LIMITS),first_index=records[0]['index'],last_index=record['index'],
                    begin_unix_s=self.initial_begin,end_unix_s=sample['observed_unix_s'],
                    window_s=span,charged_s=span,observations=copy.deepcopy(records),
                    scientific_observations_accepted=False,raw_rows_and_counts_preserved=True,
                    all_nontransport_main_checks_still_required=True,quality_qualified=False)
                self.groups.append(group);closed_budget(p,cap,self.proc,self.groups)
            self.ready_index=sample['index'];self.ready_unix_s=sample['observed_unix_s']
            self.initial_unaccepted_samples=len(self.initial_records);self.initial_records=[]
            self.pending=None
            self.baseline=sample;self.baseline_cursors=before_cursors
            self._baseline_decoded=item;self._baseline_joined=joined
            return dict(phase='full192',accepted=True,overlap_pending=False)
        if self.pending is None:
            old=self._baseline_decoded;old_join=self._baseline_joined
            unchanged=stable and all(item['rows'][slot][0]['client_id']==old['rows'][slot][0]['client_id']
                and joined[slot]['client']==old_join[slot]['client']for slot in p.SLOTS)
            if unchanged and not sample['log_chunks']:
                p.require(all(abs((item['API']['ts']-item['rows'][slot][0]['connected_seconds'])-
                    (old['API']['ts']-old['rows'][slot][0]['connected_seconds']))
                    <=cap.LIMITS['max_epoch_skew_s']for slot in p.SLOTS),
                    'Unexplained connection epoch change on an unchanged owned socket')
                self.baseline=sample;self.baseline_cursors=before_cursors
                self._baseline_decoded=item;self._baseline_joined=joined
                return dict(phase='full192',accepted=True,overlap_pending=False)
            self.pending=[self.baseline];self.pending_cursors=copy.deepcopy(self.baseline_cursors)
        self.pending.append(sample)
        p.require(len(self.pending)<=32 and
            sample['observed_unix_s']-self.pending[0]['observed_unix_s']<=cap.LIMITS['max_window_s'],
            'Original pending transport proof exceeded its fixed window')
        if stable:
            repeats=any(self.proc.original_tcp(p,entry['raw_tcp'])[1]for entry in self.pending)
            try:
                if repeats:
                    group=self.proc.certify(p,cap,self.binding,self.lua_sha,self.pending)
                else:
                    group=cap.certify_window(p,self.binding,self.pending_cursors,self.lua_sha,self.pending,self.used)
            except cap.AwaitEvidence:
                return dict(phase='awaiting_original_evidence',accepted=False,overlap_pending=True)
            self.groups.append(group);closed_budget(p,cap,self.proc,self.groups)
            self.used.update(cap.cap_key(value)for value in group.get('caps',[]))
            self.pending=None;self.pending_cursors=None;self.baseline=sample;self.baseline_cursors=before_cursors
            self._baseline_decoded=item;self._baseline_joined=joined
            return dict(phase='full192',accepted=True,overlap_pending=False,closed_group=group)
        return dict(phase='awaiting_original_evidence',accepted=False,overlap_pending=True)

    def close(self):
        try:
            self.p.require(self.failed is None and not self.closed and self.baseline is not None and self.pending is None,
                'Rejected/uninitialized/incomplete original stream cannot close valid')
            self.p.require(self.previous['index']==self.baseline['index'],'Final full192 mapping missing')
            result=dict(schema=SCHEMA,samples=self.samples,groups=copy.deepcopy(self.groups[self.prior_group_count:]),
                case_groups=copy.deepcopy(self.groups),budget=closed_budget(self.p,self.cap,self.proc,self.groups),
                final_full192=True,all_nontransport_main_checks_still_required=True,quality_qualified=False,
                initial_readiness=dict(first_qualified_baseline_index=self.ready_index,
                    first_qualified_baseline_unix_s=self.ready_unix_s,
                    unaccepted_samples=self.initial_unaccepted_samples,
                    completed_before_any_scientific_setup_required=True))
            self.closed=True;return result
        except Exception as error:self.failed=repr(error);self.closed=True;raise
