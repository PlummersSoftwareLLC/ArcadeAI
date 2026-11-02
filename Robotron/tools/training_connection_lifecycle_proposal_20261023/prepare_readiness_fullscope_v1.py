"""Prepare one explicit synthetic maximum-scope review benchmark."""
import ast
import importlib.util
import json
import os
from pathlib import Path

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
R=G/'logs/managed-learning-20261015/run-26'
P=G/'tools/training_connection_lifecycle_proposal_20261023'
D=R/'initial-readiness-fullscope-CPU-original01-preparation-20261023'

PRIOR=r'''            cap_group=long_expected['transport']['groups'][0]
            proc_group=real_expected['transport']['groups'][0]
            initial_group=read(job['readiness_component'])['actual_readiness_record']
            prior=[]
            # Explicit synthetic history:7168 normal caps,1020 proc proofs and
            # three maximal readiness records. Current synthetic raw startup
            # adds the fourth readiness record to reach8192 groups/1024 events.
            for number in range(8191):
                begin=start-3*(8191-number)-10
                if number>=8188:
                    group=copy.deepcopy(initial_group)
                    originals=group['observations'];records=[]
                    for index in range(11):
                        record=copy.deepcopy(originals[-1]if index==10 else originals[0])
                        record.update(index=900000+number*100+index,observed_unix_s=begin+index*.2)
                        records.append(record)
                    end=begin+2.
                    group.update(first_index=records[0]['index'],last_index=records[-1]['index'],
                        begin_unix_s=begin,end_unix_s=end,window_s=end-begin,charged_s=end-begin,observations=records)
                else:
                    group=copy.deepcopy(cap_group if number<7168 else proc_group)
                    end=begin+.4
                    group.update(begin_unix_s=begin,end_unix_s=end,window_s=end-begin,
                        charged_s=0. if number<7168 else end-begin)
                    for marker in group.get('caps',[]):marker['marker_offset']+=number*100000
                    for event in group.get('original_repeat_events',[]):event.update(index=number,observed_unix_s=begin+.2)
                prior.append(group)
            lines=sample['raw_tcp'].splitlines(keepends=True)
            owned=[line for line in lines[1:]if len(line.split())>=10 and line.split()[9]==b'359713499']
            assert len(owned)==1
            cells=owned[0].split();cells[0]=str(max(int(line.split()[0][:-1])for line in lines[1:])+1).encode()+b':'
            explicitly_synthetic_duplicate=sample['raw_tcp']+b' '.join(cells)+b'\n'
'''

def load(path,name):
    s=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def once(source,old,new):
    assert source.count(old)==1,(old,source.count(old))
    return source.replace(old,new)

if __name__=='__main__':
    h=load(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py','_fullready_h')
    oldjob=json.loads((R/'cached-indexed-main-health-v4-fullscope-CPU-original01-preparation-20261023/job.json').read_text())
    source=(P/'validate_cached_indexed_main_health_v4.py').read_text()
    source=once(source,"job['schema']=='robotron-cached-indexed-main-health-v4-CPU-job-v1'",
        "job['schema']=='robotron-initial-readiness-fullscope-CPU-job-v1'")
    begin=source.index('        def test_01_actual_replays_')
    end=source.index('        def test_02_synthetic_',begin)
    source=source[:begin]+'''        def test_01_actual600_full_raw_replay_matches_the_original_closed_independent_engine4_review(self):
            started=time.monotonic()
            result=engine.replay(selected,real['samples'],read(job['real_cursors']),read,h,
                original_statuses=real['actual_status'])
            self.assertEqual(result,real_expected)
            actual.append(dict(name='real_readiness_engine600',samples=result['samples'],
                wall_s=time.monotonic()-started,exact_original_closed_engine4_replay=True,
                transport_budget=result['transport']['budget']))
            print(json.dumps(dict(progress='real600_engine4',samples=result['samples'],wall_s=actual[-1]['wall_s'])),flush=True)
'''+source[end:]
    begin=source.index("            cap_group=long_expected['transport']['groups'][0]")
    end=source.index('            pins=[dict(explicit_synthetic_index',begin)
    source=source[:begin]+PRIOR+source[end:]
    source=once(source,"                    raw_API=json.dumps(current_API,separators=(',',':'),allow_nan=False).encode(),",
        "                    raw_tcp=explicitly_synthetic_duplicate if index<10 else sample['raw_tcp'],\n                    raw_API=json.dumps(current_API,separators=(',',':'),allow_nan=False).encode(),")
    source=once(source,"self.assertEqual(result['transport']['groups'],[]);self.assertEqual(len(result['transport']['case_groups']),8192)",
        "self.assertEqual(len(result['transport']['groups']),1);self.assertEqual(len(result['transport']['case_groups']),8192)\n            self.assertEqual(result['transport']['initial_readiness']['unaccepted_samples'],10)\n            self.assertEqual(result['transport']['initial_readiness']['first_qualified_baseline_index'],10)\n            self.assertEqual(result['transport']['budget']['initial_readiness_groups'],4)")
    source=once(source,'prior_case_groups=8192,normal_prior_groups=7168,proc_prior_groups=1024,',
        'prior_case_groups=8191,final_case_groups=8192,normal_prior_groups=7168,proc_prior_groups=1020,initial_readiness_groups=4,synthetic_pending_startup_samples=10,')
    source=source.replace('CACHED_INDEXED_FULL_HEALTH_EXACT3599_AND_SYNTHETIC48332_WITH8192_HISTORY_PASS_NOT_NATIVE_SELECTED',
        'INITIAL_READINESS_ENGINE4_EXACT600_AND_SYNTHETIC48332_WITH8192_CASE_GROUPS_PASS_NOT_NATIVE_SELECTED')
    source=source.replace("source_equivalence_proof=job['source_equivalence'],",
        "source_equivalence_proof=job['source_equivalence'],initial_readiness_component=job['readiness_component'],")
    ast.parse(source)
    path=P/'validate_initial_readiness_fullscope_v1.py'
    with path.open('xb')as f:
        f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
    D.mkdir(mode=0o700)
    A=R/'owned-main-initial-readiness120-v4-original01-preparation-20261023'
    V=R/'owned-main-initial-readiness120-v4-independent-review-CPU-original01-preparation-20261023'
    C=R/'initial-owned-main-readiness-procV3-CPU-original01-preparation-20261023'
    job=oldjob.copy();job.update(schema='robotron-initial-readiness-fullscope-CPU-job-v1',
        output=str(D/'output-original01'),subject=h.pin(P/'owned_main_health_v4.py'),
        driver=h.pin(path),health_job=h.pin(A/'job.json'),real_report=h.pin(A/'output-original01/report.json'),
        real_expected=h.pin(V/'output-original01/review.json'),
        real_cursors=h.pin(A/'output-original01/initial-log-cursors.json'),
        source_equivalence=h.pin(R/'initial-owned-main-readiness-protocol-original01-preparation-20261023/unselected-transport5-engine4-source-provenance.json'),
        readiness_component=h.pin(C/'output-original01/report.json'))
    jp=h.put(D/'job.json',job)
    cpu=load(P/'control_owned_health_CPU660_v2.py','_fullready_cpu')
    selected=json.loads((A/'job.json').read_text())
    entries=[jp,h.pin(path),*selected['sources'].values(),selected['binding'],
        *[v for v in job.values()if isinstance(v,dict)and 'path'in v]]
    cfg=dict(unit='robotron-initial-readiness-fullscope-CPU-original01-20261023.service',
        output=str(D/'execution-original01'),
        argv=['/usr/bin/python3.12','-I','-B',str(path),'--execute','--job',jp['path'],
            '--job-sha256',jp['sha256'],'--source-sha256',h.pin(path)['sha256']],
        properties=['CPUQuota=200%','MemoryMax=4G','MemorySwapMax=0','RuntimeMaxSec=660',
            'TasksMax=128','TimeoutStopSec=5','SendSIGKILL=no'],
        pins=[cpu.pin(v['path'])for v in {entry['path']:entry for entry in entries}.values()],
        observation_s=720)
    h.put(D/'controller-config.json',cfg)
    print(str(D/'controller-config.json'))
