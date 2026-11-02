"""Independently bind one actual prepared current1741 comparison; never launch."""
from pathlib import Path
import hashlib,importlib.util,json,os,re,shlex,sys,time
G=Path('/home/dave/source/repos/ArcadeAI/Robotron');H=G/'tools/quality_capacity_proposal';R=G/'logs/managed-learning-20261015/run-26';P=R/'post-production-profile06-fresh-main-next8M-original01-preparation-20261021';Q=R/'quality32-reference1597-vs-production1741-original01-preparation-20261021';T=P/'campaign-metadata-original01'
def load(path,sha,name):
 assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def main():
 reader=load(G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py','c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','_1741_prep_reader');pin=reader.pin;read=lambda e,as_json=True:reader.read_pin(e,as_json=as_json)
 runtime=load(G/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py','2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445','_1741_prep_runtime')
 control=load(H/'control_quality32_review_v1.py','218e7f861deb82c340527d218ed9f92ef5c5836c8cb9d32452c0598e61ff9a14','_1741_prep_control')
 prepin=pin(P/'reference1597-tested-quality-precommit.json');pre=read(prepin);testpin=pre['original_metadata_CPU21'];test=read(testpin);assert test['status']=='ACTUAL_REFERENCE1597_METADATA_CPU21_ALL6_AND_RELEASE_PASS'
 for entry in pre['selected_sources'].values():assert entry in test['tested_sources'].values();read(entry,False)
 tested_report=read(test['actual_tests']);assert tested_report['status']=='PASS' and tested_report['tests']==21 and tested_report['failures']==tested_report['errors']==tested_report['skipped']==0
 oldowner=read(test['original_owner']);runtime.archived_closure(read(test['original_closure']),oldowner,read,exit_zero=True)
 prep_pin=pin(T/'source-and-controller-preparation.json');prep=read(prep_pin);assert prep['precommit']==prepin and prep['root_job']==pre['new_preparation_root_job'] and prep['source']==pre['selected_sources']['prepare_quality32_campaign_v8.py']
 config=read(prep['config']);ownerpin=pin(T/'controller-execution/root-original-identity.json');owner=read(ownerpin);closurepin=pin(T/'controller-execution/root-original-result-and-owned-release.json');fields=runtime.archived_closure(read(closurepin),owner,read,exit_zero=True)
 expected=['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=','PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')]+config['argv']
 match=re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart']);assert match and shlex.split(match[1])==expected and config['unit']==owner['unit']
 assert runtime.duration_seconds(fields['CPUQuotaPerSecUSec'])==2 and fields['MemoryMax']==str(4<<30) and runtime.duration_seconds(fields['RuntimeMaxUSec'])==180 and fields['SendSIGKILL']==fields['Restart']=='no'
 for owner in [oldowner,owner]:
  assert not Path('/proc',str(owner['pid'])).exists()
  for unit in [owner['unit'],owner['timer']]:assert control.show(unit)['LoadState']=='not-found'
 root=read(prep['root_job']);actual=read(pin(Q/'campaign-preparation.json'));assert actual['status']=='PREPARED_NOT_LAUNCHED' and actual['root_job']==prep['root_job'] and actual['quality_qualified'] is actual['promotion'] is actual['actual_runtime_changed'] is False
 acquisition=reader.checked_module('_1741_prep_acquisition',pre['selected_sources']['quality32_acquisition_v5.py']);binding=read(actual['binding_template']);acquired=acquisition.review_acquisition(binding,read,runtime.archived_closure)
 assert acquired==actual['acquisition'] and binding['candidate']==root['candidate']==pre['candidate'] and binding['reference']==root['reference']==pre['reference']
 assert binding['candidate']['sha256']=='e19557810df3e2c18a6f64660bde6cb300eb597967f9074dc4aff6e42a1f0b83' and binding['reference']['sha256']=='c5b5bf2441c9e1a41551a93e0c7e9e4c9d36d984a2d7bfc141cda1a09a25596c'
 prior=read(pre['closed_predecessor_final_review']);assert prior['valid'] is prior['quality_qualified'] is True and prior['status']=='VALID_CLOSED_FOUR_LEG_QUALITY32_REVIEW';read(pre['closed_predecessor_adoption'])
 for item in root['preceding_originals']:
  old=read(item['owner']);runtime.archived_closure(read(item['closure']),old,read,exit_zero=True);assert not Path('/proc',str(old['pid'])).exists()
  for unit in [old['unit'],old['timer']]:assert control.show(unit)['LoadState']=='not-found'
 main=read(actual['main_binding']);reviewer=reader.checked_module('_1741_prep_review',pre['selected_sources']['review_closed_quality32_v9.py']);reviewer.validate_main_binding(main,binding)
 supervision=reader.checked_module('_1741_prep_supervision',pre['selected_sources']['supervised_main_fleet_v2.py']);joins=reader.checked_module('_1741_prep_joins',pre['selected_sources']['supervised_main_observations_v2.py']);policy=read(main['supervision_policy']);joins.validate_binding(main,policy,supervision);census=supervision.collect(policy);fleet=supervision.validate_snapshot(policy,census,192);assert fleet['full_capacity']
 observer=reader.checked_module('_1741_prep_observer',pre['selected_sources']['quality32_runtime_guard_v9.py']);native=read(actual['native_controller_config']);outer=read(actual['outer_launch_plan']);assert native['argv']==observer.campaign_command(dict(campaign_parameters=root['campaign_parameters']),binding) and outer['native_config']==actual['native_controller_config']
 for unit in [root['native_unit'],root['outer_unit'],root['review_unit']]:
  for name in [unit,unit.removesuffix('.service')+'.timer']:assert control.show(name)['LoadState']=='not-found'
 for entry in native['pins']:assert control.pin(entry['path'])==entry
 assert not Path(root['campaign_parameters']['directory']).exists() and not Path(native['output']).exists() and not Path(outer['output']).exists()
 base=load(observer.BASE,observer.BASE_SHA,'_1741_prep_base');base.idle_GPU(root,dict(job=dict(gpu_uuid='GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0')))
 guard=reader.checked_module('_1741_prep_main_guard',reader.pin(G/'logs/managed-learning-20261015/run-26/capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py'));guard.owner_and_files(main);wire=base.read_API_bytes();api=base.raw_witness_module().parse_wire(wire);guard.healthy(api,read(main['baseline_API']),main['experiment'],time.time());assert api['client_count']==192
 assert 'torch' not in sys.modules
 record=dict(status='ACTUAL_FIRST_BOTH8M_STRICT_CPU_AND_ACQUISITION_VERIFIED_NOT_LAUNCHED',observed_unix_s=time.time(),source=pin(Path(__file__)),precommit=prepin,new_source_CPU21=testpin,actual_metadata_preparation=prep_pin,original_metadata_owner=ownerpin,original_metadata_closure=closurepin,all6_original_metadata_descriptors_and_owned_releases_verified=True,acquisition=acquired,main_binding=actual['main_binding'],main196_holds_and_current192_fleet_verified=True,normal_checkpoint_producer_mode_preserved=True,native_config=actual['native_controller_config'],outer_plan=actual['outer_launch_plan'],binding_template=actual['binding_template'],source_package=pre['source_package'],closed_predecessor_final_review=pre['closed_predecessor_final_review'],original_capture_or_verifier_repeated=False,quality_qualified=False,promotion=False,learning_speed_gain_verified=False,private_GPU_and_port_free=True)
 path=Q/'root-window-and-CPU-acquisition-independent-readback.json'
 with path.open('x')as f:json.dump(record,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 print(json.dumps(dict(status=record['status'],readback=pin(path))))
if __name__=='__main__':main()
