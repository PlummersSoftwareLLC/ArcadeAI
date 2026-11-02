"""Preserve resource maxima while feeding new-format synthetic socket evidence."""
import ast,copy,importlib.util,json,os
from pathlib import Path
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');R=G/'logs/managed-learning-20261015/run-26';P=G/'tools/training_connection_lifecycle_proposal_20261023'
OLD=R/'initial-readiness-fullscope-CPU-original01-preparation-20261023'
C=R/'inet-diag-serialized-free314-client-CPU-original01-preparation-20261024'
F=R/'inet-diag-capture-family-contracts-CPU-original01-preparation-20261024'
D=R/'inet-diag-fullscope-CPU-original01-preparation-20261024'
def load(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
h=load(G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py','_inet_scale_h')
cpu=load(P/'control_owned_health_CPU660_v2.py','_inet_scale_cpu')
oldjob=json.loads((OLD/'job.json').read_text());oldpath=P/'validate_initial_readiness_fullscope_v1.py';source=oldpath.read_text();changes=[]
def change(a,b):
    global source
    assert source.count(a)==1,(a,source.count(a));position=source.index(a);source=source[:position]+b+source[position+len(a):];changes.append(dict(old=a,new=b,position=position))
change('"""Indexed full-health raw equivalence and explicit synthetic worst-scope scaling.','"""New kernel-socket format raw equivalence and explicit worst-scope scaling.')
change("job['schema']=='robotron-initial-readiness-fullscope-CPU-job-v1'","job['schema']=='robotron-inet-diag-fullscope-CPU-job-v1'")
change("real_expected=read(job['real_expected'])['actual_replay']","real_expected=read(job['real_expected'])['independent_original_raw_replay']")
change('test_01_actual600_full_raw_replay_matches_the_original_closed_independent_engine4_review','test_01_actual_client_full_raw_replay_matches_original_independent_kernel_format_review')
change("name='real_readiness_engine600'","name='real_inet_diag_client_original'")
change("progress='real600_engine4'","progress='real_inet_diag_client_original'")
change("proc_group=real_expected['transport']['groups'][0]","proc_group=read(job['legacy_proc_budget_fixture'])['actual_replay']['transport']['groups'][0]")
change('''            # Explicit synthetic history:7168 normal caps,1020 proc proofs and
            # three maximal readiness records. Current synthetic raw startup
            # adds the fourth readiness record to reach8192 groups/1024 events.
            for number in range(8191):''','''            # Explicitly synthetic worst-budget history, never current-source
            # runtime proofs:7168 normal caps,1020 proc-shaped records and four
            # maximal readiness records. New-format raw observations reject all
            # duplicate socket rows and start from a clean baseline at index0.
            for number in range(8192):''')
change('begin=start-3*(8191-number)-10','begin=start-3*(8192-number)-10')
begin=source.index("            lines=sample['raw_tcp'].splitlines(keepends=True)");end=source.index('            pins=[dict(explicit_synthetic_index',begin)
change(source[begin:end],"            socket_dump=json.loads(sample['raw_tcp'])\n            assert socket_dump['schema']=='robotron-original-inet-diag-snapshot-v2'\n")
change("                current=dict(sample,index=index,observed_unix_s=tick+.05,API_begin_unix_s=tick+.02,", "                current_dump=copy.deepcopy(socket_dump);current_dump.update(begin_unix_s=tick+.026,end_unix_s=tick+.03)\n                current=dict(sample,index=index,observed_unix_s=tick+.05,API_begin_unix_s=tick+.02,")
change("raw_tcp=explicitly_synthetic_duplicate if index<10 else sample['raw_tcp'],","raw_tcp=json.dumps(current_dump,separators=(',',':'),allow_nan=False).encode()+b'\\n',")
change("self.assertEqual(len(result['transport']['groups']),1)","self.assertEqual(len(result['transport']['groups']),0)")
change("self.assertEqual(result['transport']['initial_readiness']['unaccepted_samples'],10)","self.assertEqual(result['transport']['initial_readiness']['unaccepted_samples'],0)")
change("self.assertEqual(result['transport']['initial_readiness']['first_qualified_baseline_index'],10)","self.assertEqual(result['transport']['initial_readiness']['first_qualified_baseline_index'],0)")
change('prior_case_groups=8191,final_case_groups=8192','prior_case_groups=8192,final_case_groups=8192')
change('synthetic_pending_startup_samples=10','synthetic_pending_startup_samples=0')
change('INITIAL_READINESS_ENGINE4_EXACT600_AND_SYNTHETIC48332_WITH8192_CASE_GROUPS_PASS_NOT_NATIVE_SELECTED','INET_DIAG_ORIGINAL_CLIENT_AND_SYNTHETIC48332_WITH8192_CASE_GROUPS_PASS_NOT_NATIVE_SELECTED')
change("source_equivalence_proof=job['source_equivalence'],initial_readiness_component=job['readiness_component'],","source_equivalence_proof=job['source_equivalence'],initial_readiness_component=job['readiness_component'],inet_diag_capture_provenance=job['inet_diag_capture_provenance'],")
reverse=source
for item in reversed(changes):
    position=item['position'];assert reverse[position:position+len(item['new'])]==item['new'];reverse=reverse[:position]+item['old']+reverse[position+len(item['new']):]
assert reverse==oldpath.read_text()
path=P/'validate_inet_diag_fullscope_v1.py';compile(source,str(path),'exec')
with path.open('xb')as f:f.write(source.encode());f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
D.mkdir(mode=0o700);job=copy.deepcopy(oldjob)
job.update(schema='robotron-inet-diag-fullscope-CPU-job-v1',output=str(D/'output-original01'),driver=h.pin(path),health_job=h.pin(F/'unselected-health-job.json'),
    real_report=h.pin(C/'output-original01/main-observations/closed-full-health-report.json'),real_cursors=h.pin(C/'output-original01/main-observations/initial-log-cursors.json'),
    real_expected=h.pin(C/'independent-original-inet-diag-client-runtime-and-raw-closeout.json'),legacy_proc_budget_fixture=oldjob['real_expected'],
    inet_diag_capture_provenance=h.pin(F/'source-family-provenance.json'))
jp=h.put(D/'job.json',job)
provenance=h.put(D/'source-scaling-changes-and-fixed-resource-maxima.json',dict(schema='robotron-inet-diag-fullscope-source-provenance-v1',original_driver=h.pin(oldpath),prospective_driver=h.pin(path),source_changes=changes,exact_source_reverse_verified=True,
    samples=48332,prior_groups=8192,exception_groups=1024,readiness_groups=4,original_elapsed_limit_s=600,original_memory_limits_unchanged=True,
    clean_new_format_startup_index0_and_no_new_proc_or_readiness_group=True,prior_budget_groups_explicitly_synthetic_and_not_new_format_runtime_certificates=True,
    original_replay_engine_and_all_qualification_limits_unchanged=True,real_native_or_quality_evidence=False))
cfg=json.loads((OLD/'controller-config.json').read_text());health=json.loads((F/'unselected-health-job.json').read_text())
pins=[v for v in job.values()if isinstance(v,dict)and 'path'in v]+[jp,provenance,*health['sources'].values(),health['binding']]
cfg.update(unit='robotron-inet-diag-fullscope-original01-20261024.service',output=str(D/'execution-original01'),argv=['/usr/bin/python3.12','-I','-B',str(path),'--execute','--job',jp['path'],'--job-sha256',jp['sha256'],'--source-sha256',job['driver']['sha256']],pins=[cpu.pin(p['path'])for p in {p['path']:p for p in pins}.values()])
cp=h.put(D/'controller-config.json',cfg);cpu.checked_config(cp['path']);print(json.dumps(dict(config=cp,provenance=provenance)))
