"""Prepare NEW unselected transport/health sources; never touch old selected sources."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'tools/training_connection_lifecycle_proposal_20261023'
D=G/'logs/managed-learning-20261015/run-26/initial-owned-main-readiness-protocol-original01-preparation-20261023'

HELPERS=r'''
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

'''

BUDGET=r'''def closed_budget(p,cap,proc,groups):
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


'''

INITIAL=r'''        if self.baseline is None:
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
'''

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def write(path,source):
    ast.parse(source)
    with path.open('xb')as f:
        f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    return h.pin(path)

if __name__=='__main__':
    h=load(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py','_readiness_source_h')
    original=(P/'owned_transport_stream_v4.py').read_text()
    assert hashlib.sha256(original.encode()).hexdigest()=='94d945f0b805cddd196e96c6ea9c03f5df3c70054884f85d97fed42bc4ce7f93'
    source=original.replace('import copy','import copy\nimport hashlib\nimport re',1)
    source=source.replace("SCHEMA='robotron-owned-transport-stream-summary-v3'",
                          "SCHEMA='robotron-owned-transport-stream-summary-v4'")
    begin=source.index('def closed_budget(');end=source.index('class Stream:',begin)
    old_budget=source[begin:end];source=source[:begin]+HELPERS+BUDGET+source[end:]
    source=source.replace('def __init__(self,p,cap,proc,binding,cursors,lua_sha,prior_groups=()):',
        'def __init__(self,p,cap,proc,binding,cursors,lua_sha,prior_groups=(),*,expected_uid):')
    needle='        self._baseline_decoded=None;self._baseline_joined=None\n'
    addition=needle+'''        p.require(type(expected_uid)is int and expected_uid>0,'Explicit owned readiness UID required')
        self.expected_uid=expected_uid;self.initial_signature=None;self.initial_epochs=None
        self.initial_begin=None;self.initial_records=[];self.ready_index=None;self.ready_unix_s=None
        self.initial_unaccepted_samples=0
'''
    assert source.count(needle)==1;source=source.replace(needle,addition)
    begin=source.index('        if self.baseline is None:\n')
    end=source.index('        if self.pending is None:\n',begin)
    old_initial=source[begin:end];source=source[:begin]+INITIAL+source[end:]
    needle='                final_full192=True,all_nontransport_main_checks_still_required=True,quality_qualified=False)'
    replacement='''                final_full192=True,all_nontransport_main_checks_still_required=True,quality_qualified=False,
                initial_readiness=dict(first_qualified_baseline_index=self.ready_index,
                    first_qualified_baseline_unix_s=self.ready_unix_s,
                    unaccepted_samples=self.initial_unaccepted_samples,
                    completed_before_any_scientific_setup_required=True))'''
    assert source.count(needle)==1;source=source.replace(needle,replacement)
    transport=write(P/'owned_transport_stream_v5.py',source)
    # Entire-source reversal proves the post-baseline protocol is untouched.
    reverse=source.replace(HELPERS+BUDGET,old_budget).replace(INITIAL,old_initial)
    reverse=reverse.replace(addition,needle) if False else reverse
    reverse=reverse.replace(addition,'        self._baseline_decoded=None;self._baseline_joined=None\n')
    reverse=reverse.replace(replacement,needle)
    reverse=reverse.replace('def __init__(self,p,cap,proc,binding,cursors,lua_sha,prior_groups=(),*,expected_uid):',
        'def __init__(self,p,cap,proc,binding,cursors,lua_sha,prior_groups=()):')
    reverse=reverse.replace('import copy\nimport hashlib\nimport re','import copy',1)
    reverse=reverse.replace("SCHEMA='robotron-owned-transport-stream-summary-v4'",
                            "SCHEMA='robotron-owned-transport-stream-summary-v3'")
    assert reverse==original
    engine_original=(P/'owned_main_health_v3.py').read_text()
    engine=engine_original
    needle="def dependencies(job,h):\n"
    replacement=needle+'''    require(job.get('initial_readiness_protocol')==dict(
        schema='robotron-bounded-initial-owned-readiness-v1',max_wait_s=2.,max_samples=11),
        'Explicit prospective initial readiness selection required')
'''
    assert engine.count(needle)==1;engine=engine.replace(needle,replacement)
    a='collector.main,collector.initial_cursors,collector.p.LUA_SHA,prior_groups)'
    b="collector.main,collector.initial_cursors,collector.p.LUA_SHA,prior_groups,expected_uid=job['binding']['identity']['uid'])"
    assert engine.count(a)==1;engine=engine.replace(a,b)
    c='stream=mixed.Stream(p,cap,proc,main,initial_cursors,p.LUA_SHA,prior_groups)'
    d="stream=mixed.Stream(p,cap,proc,main,initial_cursors,p.LUA_SHA,prior_groups,expected_uid=job['binding']['identity']['uid'])"
    assert engine.count(c)==1;engine=engine.replace(c,d)
    engine=engine.replace('robotron-owned-main-full-health-closed-report-v2',
                          'robotron-owned-main-full-health-closed-report-v3')
    engine=engine.replace('robotron-owned-main-full-health-raw-replay-v2',
                          'robotron-owned-main-full-health-raw-replay-v3')
    eng=write(P/'owned_main_health_v4.py',engine)
    e_reverse=engine.replace(replacement,needle).replace(b,a).replace(d,c)
    e_reverse=e_reverse.replace('robotron-owned-main-full-health-closed-report-v3','robotron-owned-main-full-health-closed-report-v2')
    e_reverse=e_reverse.replace('robotron-owned-main-full-health-raw-replay-v3','robotron-owned-main-full-health-raw-replay-v2')
    assert e_reverse==engine_original
    print(json.dumps(h.put(D/'unselected-transport5-engine4-source-provenance.json',dict(
        schema='robotron-unselected-initial-readiness-sources-v1',
        original_transport=h.pin(P/'owned_transport_stream_v4.py'),subject_transport=transport,
        original_engine=h.pin(P/'owned_main_health_v3.py'),subject_engine=eng,
        exact_reverse_source_checks=True,post_baseline_observation_and_all_nontransport_bodies_unchanged=True,
        raw_samples_and_indices_retained=True,readiness_charged_to_existing_shared_budget=True,
        scientific_guard_selected=False,quality_qualified=False))))
