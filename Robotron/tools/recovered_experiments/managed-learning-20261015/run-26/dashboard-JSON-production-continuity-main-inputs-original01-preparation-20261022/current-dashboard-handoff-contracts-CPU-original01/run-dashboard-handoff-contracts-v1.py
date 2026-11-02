"""Original CPU contracts for the fresh current-owner bundle; kernel behavior is mocked here."""
from pathlib import Path
import argparse,copy,hashlib,importlib.util,json,os,sys,tempfile,time,types,unittest
from unittest.mock import patch
SOURCES={}
def load(entry,name):
 p=Path(entry['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==entry['sha256'];spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
OWNER=dict(pid=3295795,starttime_ticks=64995335,unit='robotron-managed-run-26-d3b365c9-trainer.service',invocation_id='160d2b4b1f6e4e2f8839790658a7d01c',cgroup='/user.slice/user-1001.slice/user@1001.service/app.slice/robotron-managed-run-26-d3b365c9-trainer.service')
class SourceContracts(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
 def tearDown(self):self.temp.cleanup()
 def construct(self,*,owner=None,old_sha=None,new_sha=None):
  owner=copy.deepcopy(owner or OWNER);base=self.root/str(len(list(self.root.iterdir())));base.mkdir();control=base/'control.json';control.write_text(json.dumps(dict(measurement=None,lr_scale=.25)));rawcontrol=control.read_bytes();prepared=base/'prepared.json';out=base/'live';fleetgroup='/user.slice/user-'+str(os.getuid())+'.slice/fleet';raws={str(prepared):dict(status='PREPARED_IMMUTABLE_PROPOSAL_LIVE_CONTROLLER_NOT_SELECTED',installed_before=dict(sha256=old_sha or L.OLD_SOCKET_SHA),proposed_source=dict(sha256=new_sha or L.NEW_SOCKET_SHA),selected_source_relative="Scripts/dqn/metrics_dashboard.py",original_main=dict(path='main'),original_listener=dict(path='listener'),original_fleet=dict(path='fleet'),component_proofs=dict(original_boot_anchor=dict(path='anchor'))),'main':dict(owner=owner,actors=[],held_hashes={},experiment='cpu-only',baseline_API=dict(path='baseline')),'listener':dict(tid=7,starttime_ticks=8),'fleet':dict(cgroup=fleetgroup),'anchor':dict(owner=owner,inferred_replay_pressure_anchor=None,original_boot_saved_clocks=dict(optimized_samples=27292198912))}
  class Adapter:
   verify_stopped=install=start_once=verify_startup=verify_progress=sealed_bank_semantics=lambda *a:None
   def recovery_state(self):return {}
  guard=types.SimpleNamespace(owner_and_files=lambda *a:None,healthy=lambda *a:None)
  def module(entry,name):
   if 'poststop_adapter' in name:return types.SimpleNamespace(prepare=lambda backend:Adapter(),recover_committed=lambda *a:None)
   if 'recovery' in name:return types.SimpleNamespace(recover=lambda *a:None)
   if 'main_guard' in name:return guard
   return types.SimpleNamespace()
  def checked(e):return rawcontrol if e['path']=='base_control' else json.dumps(raws[e['path']]).encode()
  deps={k:dict(path=k) for k in ['reader','raw_API','main_guard','bank_witness','bank_shutdown_intent','socket_seal']};job=dict(schema='robotron-score-carry-live-handoff-job-v1',authorized=True,case='scorecarry-current-owner-test',prepared=dict(path=str(prepared)),output=str(out),dependencies=deps,poststop_adapter=dict(path='adapter'),recovery_source=dict(path='recovery'),base_control_archive=dict(path='base_control'),base_control_sha256=hashlib.sha256(rawcontrol).hexdigest())
  with patch.object(L,'module',module),patch.object(L,'checked',checked),patch.object(L,'full_pin',lambda p:dict(path=str(p))),patch.object(L,'CONTROL',control),patch.object(L,'ROOT_CGROUP',base/'cgroups'):
   backend=L.LinuxBackend(job)
  return backend,base,out
 def preflight(self,backend,base,boot_samples):
  backend.anchor['original_boot_saved_clocks']['optimized_samples']=boot_samples;backend.fleet_root.mkdir(parents=True);(backend.fleet_root/'cgroup.freeze').write_text('0\n');model=base/'models';model.mkdir();api=dict(memory_buffer_size=6000000,host_pipeline=dict(inference_graphs=dict(postload_validations=1),learning_exposure=dict(optimizer=dict(epoch=1))),client_rows=[dict(client_slot=i,client_id=i,session_seconds=0,eval=False) for i in range(192)]);backend.api=lambda:api;backend.reader.read_pin=lambda p:{};backend.rescue_live=lambda:None
  with patch.object(L,'live_owner',lambda *a:None),patch.object(L,'potential_handlers',lambda *a:{i:{} for i in range(192)}),patch.object(L,'MODEL',model):return backend.preflight()
 def test_current_owner_is_accepted(self):
  b,_,out=self.construct();self.assertEqual(b.owner,OWNER);self.assertTrue((out/'recovery-state.json').exists())
 def test_old_owner_is_rejected(self):
  old=dict(OWNER,pid=826357,starttime_ticks=46132657,invocation_id='5bd70cfc44474eba8b0732bcc4bdf486')
  with self.assertRaisesRegex(RuntimeError,'explicitly prepared original trainer'):self.construct(owner=old)
 def test_previous_socket_is_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'original/proposed parser'):self.construct(old_sha='5314c4fc70449b2f94520ce27d0f08374a68aba23175fcb49fa2e55ad4522408')
 def test_unselected_target_is_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'original/proposed parser'):self.construct(new_sha=L.OLD_SOCKET_SHA)
 def test_current_boot_budget_is_accepted(self):
  b,base,_=self.construct();self.assertEqual(len(self.preflight(b,base,27292198912)['original192_rows']),192)
 def test_previous_boot_budget_is_rejected(self):
  b,base,_=self.construct()
  with self.assertRaisesRegex(RuntimeError,'budget provenance'):self.preflight(b,base,16168077312)
 def group_fixture(self,*,frozen=False,foreign=False,never_frozen=False):
  owner=dict(pid=99900001,starttime_ticks=1234,unit='robotron-current-owner-save-fixture.service',invocation_id='a'*32,cgroup='/user.slice/user-'+str(os.getuid())+'.slice/user@'+str(os.getuid())+'.service/app.slice/robotron-current-owner-save-fixture.service');root=self.root/'cg';group=root/owner['cgroup'].lstrip('/');group.mkdir(parents=True);(group/'cgroup.procs').write_text(str(owner['pid'])+('\n99900002' if foreign else '')+'\n');(group/'cgroup.freeze').write_text('1\n' if frozen else '0\n');(group/'cgroup.events').write_text('populated 1\nfrozen '+('1' if frozen else '0')+'\n');events=[]
  def live(value):
   if value!=owner:raise RuntimeError('Exact live owner changed')
   bit='0' if never_frozen else (group/'cgroup.freeze').read_text().strip();(group/'cgroup.events').write_text('populated 1\nfrozen '+bit+'\n');events.append(('owner_checked',bit))
  linux=types.SimpleNamespace(ROOT_CGROUP=root,live_owner=live,process_start=lambda pid:owner['starttime_ticks'] if pid==owner['pid'] else None)
  adapter=types.SimpleNamespace(linux=linux,startup_save_paused_owner=None)
  def state():events.append(('state',copy.deepcopy(adapter.startup_save_paused_owner),(group/'cgroup.freeze').read_text().strip()))
  adapter.b=types.SimpleNamespace(state=state)
  return owner,group,linux,adapter,events
 def test_save_cgroup_freezes_before_publication_and_thaws(self):
  owner,group,linux,a,events=self.group_fixture()
  with P.startup_save_pause(a,owner):
   self.assertEqual((group/'cgroup.freeze').read_text(),'1\n');self.assertEqual(a.startup_save_paused_owner,owner);self.assertIn(('state',owner,'0'),events)
  self.assertEqual((group/'cgroup.freeze').read_text(),'0\n');self.assertIsNone(a.startup_save_paused_owner)
 def test_publication_exception_releases_exact_hold(self):
  owner,group,linux,a,_=self.group_fixture()
  with self.assertRaisesRegex(RuntimeError,'injected publication failure'):
   with P.startup_save_pause(a,owner):raise RuntimeError('injected publication failure')
  self.assertEqual((group/'cgroup.freeze').read_text(),'0\n');self.assertIsNone(a.startup_save_paused_owner)
 def test_existing_freeze_is_not_adopted(self):
  owner,group,linux,a,events=self.group_fixture(frozen=True)
  with self.assertRaisesRegex(RuntimeError,'existing cgroup freeze'):
   with P.startup_save_pause(a,owner):self.fail('foreign hold adopted')
  self.assertEqual((group/'cgroup.freeze').read_text(),'1\n');self.assertIsNone(a.startup_save_paused_owner)
 def test_foreign_process_in_leaf_is_rejected(self):
  owner,group,linux,a,_=self.group_fixture(foreign=True)
  with self.assertRaisesRegex(RuntimeError,'foreign process'):
   with P.startup_save_pause(a,owner):self.fail('foreign process frozen')
  self.assertEqual((group/'cgroup.freeze').read_text(),'0\n')
 def test_wrong_save_owner_is_rejected_before_write(self):
  owner,group,linux,a,_=self.group_fixture()
  with self.assertRaisesRegex(RuntimeError,'Exact live owner'):
   with P.startup_save_pause(a,dict(owner,invocation_id='b'*32)):self.fail('changed owner frozen')
  self.assertEqual((group/'cgroup.freeze').read_text(),'0\n')
 def test_freeze_timeout_thaws_and_preserves_failure(self):
  owner,group,linux,a,_=self.group_fixture(never_frozen=True);ticks=iter(i*.5 for i in range(100))
  with patch.object(P.time,'monotonic',lambda:next(ticks)),patch.object(P.time,'sleep',lambda _:None):
   with self.assertRaisesRegex(RuntimeError,'did not freeze'):
    with P.startup_save_pause(a,owner):self.fail('unfrozen request published')
  self.assertEqual((group/'cgroup.freeze').read_text(),'0\n');self.assertIsNone(a.startup_save_paused_owner)
 def test_committed_rescue_thaws_only_recorded_replacement(self):
  owner,group,linux,a,_=self.group_fixture(frozen=True);original=dict(owner,pid=99900000,starttime_ticks=1222);job=dict(case='scorecarry-unit',prepared=dict(path='prepared'));prepared=dict(original_main=dict(path='main'));linux.checked=lambda e:json.dumps(prepared if e['path']=='prepared' else dict(owner=original)).encode();state=dict(original_owner=original,case=job['case'],original_stop_sent=True,replacement=owner,poststop=dict(startup_save_paused_owner=owner))
  with patch.object(P,'load_linux',lambda _:linux),patch.object(P.os,'kill',lambda *a:(_ for _ in ()).throw(AssertionError('Signal forbidden'))):result=P.recover_committed(job,state,observation_pending=True)
  self.assertEqual((group/'cgroup.freeze').read_text(),'0\n');self.assertTrue(result['original_handle_preserved']);self.assertFalse(result['restart_retry']);self.assertFalse(result['replacement_terminated'])
 def test_committed_rescue_rejects_foreign_pause_owner(self):
  owner,group,linux,a,_=self.group_fixture(frozen=True);original=dict(owner,pid=99900000,starttime_ticks=1222);job=dict(case='scorecarry-unit',prepared=dict(path='prepared'));prepared=dict(original_main=dict(path='main'));linux.checked=lambda e:json.dumps(prepared if e['path']=='prepared' else dict(owner=original)).encode();state=dict(original_owner=original,case=job['case'],original_stop_sent=True,replacement=owner,poststop=dict(startup_save_paused_owner=dict(owner,pid=99900002)))
  with patch.object(P,'load_linux',lambda _:linux):
   with self.assertRaisesRegex(RuntimeError,'captured save-publication owner'):P.recover_committed(job,state,observation_pending=True)
  self.assertEqual((group/'cgroup.freeze').read_text(),'1\n')
 def test_archive_preserves_normal_source_and_seals_copy(self):
  source=self.root/'normal.pt';source.write_bytes(b'fixture model bytes');os.chmod(source,0o664);before=L.full_pin(source);copied=P.archive(L,source,self.root/'copy.pt');self.assertEqual(L.full_pin(source),before);self.assertEqual(copied['identity']['mode'],'0o444');self.assertEqual(copied['sha256'],before['sha256'])
 def test_actual_startup_snapshot_keeps_producer_mode(self):
  owner,group,linux,_,_=self.group_fixture();model=self.root/'models';(model/'managed-checkpoints').mkdir(parents=True);out=self.root/'live';out.mkdir();linux.MODEL=model;linux.full_pin=L.full_pin;linux.publish=L.publish;linux.checked=lambda _:b'{}';b=types.SimpleNamespace(job=dict(case='scorecarry-mode-fixture'),out=out);b.state=lambda:None;b.event=lambda name,value:L.publish(out/name,value);adapter=object.__new__(P.Poststop);adapter.b=b;adapter.linux=linux;adapter.phase_pin=dict(sha256='a'*64);adapter.startup_save_paused_owner=None;copied=[]
  def wait(predicate,seconds,message):
   req=model/'managed_save.request.json';value=json.loads(req.read_bytes());source=model/'managed-checkpoints'/(value['tag']+'.pt');source.write_bytes(b'newest startup fixture');os.chmod(source,0o664);os.replace(req,model/'managed_save.request.json.completed');self.assertTrue(predicate());return True
  b.wait=wait
  def cpu(purpose,source,*args,**kwargs):
   before=L.full_pin(source);self.assertEqual(before['identity']['mode'],'0o664');copy_pin=P.archive(L,source,out/'startup-copy.pt');self.assertEqual(L.full_pin(source),before);self.assertEqual(copy_pin['identity']['mode'],'0o444');copied.append(copy_pin);return dict(status='PASS_UNIT_FIXTURE_ONLY'),dict(path='unit-proof'),None,None
  adapter.cpu=cpu
  with patch.object(P,'expected_phase',lambda *a:{}):report,proof=adapter.startup_snapshot(owner,dict(report=dict(path='report'),checkpoint=dict(path='boot',sha256='b'*64,bytes=1),clocks={}))
  self.assertEqual(len(copied),1);self.assertEqual((group/'cgroup.freeze').read_text(),'0\n');self.assertIsNone(adapter.startup_save_paused_owner)
 def test_owned_metrics_child_is_safe_for_freeze_and_rescue(self):
  import subprocess
  raw=Path('/proc/self/stat').read_text();owner=dict(pid=os.getpid(),starttime_ticks=int(raw[raw.rfind(')')+2:].split()[19]),cgroup=Path('/proc/self/cgroup').read_text().strip().split('::',1)[1],invocation_id='a'*32);owner['unit']=owner['cgroup'].rsplit('/',1)[1]
  root=self.root/'owned-child-cg';group=root/owner['cgroup'].lstrip('/');group.mkdir(parents=True);(group/'cgroup.freeze').write_text('0\n');(group/'cgroup.events').write_text('populated 1\nfrozen 0\n')
  def live(value):
   self.assertEqual(value,owner);(group/'cgroup.events').write_text('populated 1\nfrozen '+(group/'cgroup.freeze').read_text().strip()+'\n')
  linux=types.SimpleNamespace(ROOT_CGROUP=root,live_owner=live);adapter=types.SimpleNamespace(linux=linux,startup_save_paused_owner=None,b=types.SimpleNamespace(state=lambda:None))
  child=subprocess.Popen(['/usr/bin/python3.12','-c','import time; time.sleep(0.5)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   (group/'cgroup.procs').write_text(str(owner['pid'])+'\n'+str(child.pid)+'\n');self.assertTrue(P.startup_save_owned_child(owner,child.pid))
   with P.startup_save_pause(adapter,owner):self.assertEqual((group/'cgroup.freeze').read_text(),'1\n')
   self.assertEqual((group/'cgroup.freeze').read_text(),'0\n');self.assertIsNone(adapter.startup_save_paused_owner)
  finally:child.wait(timeout=5)
 def test_selected_bundle_has_no_stop_signals_or_source_chmod(self):
  raw=Path(SOURCES['handoff_poststop_v1.py']['path']).read_text();self.assertNotIn('SIGSTOP',raw);self.assertNotIn('SIGCONT',raw);self.assertNotIn('os.chmod(source',raw)

 def transaction_fixture(self):
  game=self.root/'game';scripts=game/'Scripts/dqn';scripts.mkdir(parents=True);model=game/'models_dqn';model.mkdir();out=self.root/'transaction';out.mkdir();source=scripts/'metrics_dashboard.py';source.write_bytes(Path(INPUTS['original_dashboard']['path']).read_bytes());os.chmod(source,0o664);socket=scripts/'socket_server.py';socket.write_bytes(b'held socket fixture');os.chmod(socket,0o664);other=scripts/'agent.py';other.write_bytes(b'held numerical fixture');os.chmod(other,0o664);checkpoint=model/'robotron_dqn_latest.pt';checkpoint.write_bytes(b'current newest-stopped fixture');os.chmod(checkpoint,0o664);control=model/'learning_control.json';control.write_text('{"measurement":null,"lr_scale":0.25}');os.chmod(control,0o664);settings=model/'game_settings.json';settings.write_text('{"fixture":true}');os.chmod(settings,0o664)
  settings_archive=P.archive(L,settings,out/'settings-original.json');control_bytes=control.read_bytes();report=Path(INPUTS['finite_phase_report']['path']);phase_path=Path(INPUTS['original_phase_record']['path']);phase=L.full_pin(phase_path);dropin=out/'91-per-priority-phase.conf';dropin.write_text('Environment="DQN_PRIORITY_PHASE_RECORD='+phase['path']+'"\nEnvironment="DQN_PRIORITY_PHASE_RECORD_SHA256='+phase['sha256']+'"\n');os.chmod(dropin,0o664);commands=[]
  b=types.SimpleNamespace(job=dict(case='scorecarry-dashboardJSON-fixture'),out=out,prepared=dict(proposed_source=INPUTS['candidate_dashboard']),control_pin=L.full_pin(control),control_bytes=control_bytes,main=dict(held_hashes={str(p):L.full_pin(p)['sha256'] for p in [source,socket,other,control,settings]}));b.state=lambda:None;b.event=lambda name,value:L.publish(out/name,value)
  adapter=object.__new__(P.Poststop);adapter.b=b;adapter.linux=L;adapter.absent_original=lambda:None;adapter.fleet_held=lambda:None;adapter.command=lambda argv:commands.append(argv);adapter.config=dict(settings_archive=settings_archive,phase_dropin=L.full_pin(dropin),original_phase_record=phase)
  saved=dict(checkpoint=L.full_pin(checkpoint),report=L.full_pin(report));originals={str(p):L.full_pin(p) for p in [source,socket,other,checkpoint,control,settings]}
  return adapter,game,model,saved,originals,commands,source,socket,other
 def test_dashboard_transaction_installs_only_selected_source_and_current_phase(self):
  a,game,model,saved,before,commands,source,socket,other=self.transaction_fixture()
  with patch.object(L,'GAME',game),patch.object(L,'MODEL',model),patch.object(L,'CONTROL',model/'learning_control.json'):
   result=a.install({}, {}, saved)
  self.assertEqual(L.full_pin(source)['sha256'],L.NEW_SOCKET_SHA);self.assertEqual(L.full_pin(source)['identity']['mode'],'0o664');self.assertEqual(L.full_pin(socket),before[str(socket)]);self.assertEqual(L.full_pin(other),before[str(other)]);self.assertEqual(L.full_pin(saved['checkpoint']['path']),saved['checkpoint']);self.assertEqual(commands,[['systemctl','--user','daemon-reload']]);self.assertTrue(result['only_selected_source_changed']);phase=json.loads(Path(result['phase_record']['path']).read_bytes());self.assertEqual(phase['checkpoint'],{k:saved['checkpoint'][k] for k in ['path','sha256','bytes']});self.assertEqual(phase['action'],'resume')
 def test_dashboard_transaction_rejects_foreign_source_before_any_publication(self):
  a,game,model,saved,before,commands,source,socket,other=self.transaction_fixture();source.write_bytes(b'foreign source update');foreign=L.full_pin(source)
  with patch.object(L,'GAME',game),patch.object(L,'MODEL',model),patch.object(L,'CONTROL',model/'learning_control.json'):
   with self.assertRaisesRegex(RuntimeError,'Original parser changed'):a.install({}, {}, saved)
  self.assertEqual(L.full_pin(source),foreign);self.assertEqual(L.full_pin(socket),before[str(socket)]);self.assertEqual(L.full_pin(other),before[str(other)]);self.assertEqual(commands,[])
 def test_dashboard_transaction_rejects_changed_numerical_hold(self):
  a,game,model,saved,before,commands,source,socket,other=self.transaction_fixture();other.write_bytes(b'foreign numerical update')
  with patch.object(L,'GAME',game),patch.object(L,'MODEL',model),patch.object(L,'CONTROL',model/'learning_control.json'):
   with self.assertRaisesRegex(RuntimeError,'unselected held input changed'):a.install({}, {}, saved)
  self.assertEqual(L.full_pin(source),before[str(source)]);self.assertEqual(L.full_pin(socket),before[str(socket)]);self.assertEqual(commands,[])
 def test_dashboard_transaction_rejects_unpinned_candidate(self):
  a,game,model,saved,before,commands,source,socket,other=self.transaction_fixture();a.b.prepared['proposed_source']=dict(INPUTS['candidate_dashboard'],sha256='0'*64)
  with patch.object(L,'GAME',game),patch.object(L,'MODEL',model),patch.object(L,'CONTROL',model/'learning_control.json'):
   with self.assertRaisesRegex(RuntimeError,'Immutable/source input changed'):a.install({}, {}, saved)
  self.assertEqual(L.full_pin(source),before[str(source)]);self.assertEqual(L.full_pin(socket),before[str(socket)]);self.assertEqual(commands,[])
 def test_original_kernel_primitives_and_controller_are_unchanged(self):
  import ast
  def methods(path):
   tree=ast.parse(Path(path).read_bytes());result={}
   def visit(nodes,prefix=''):
    for n in nodes:
     if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):result[prefix+n.name]=ast.dump(n,include_attributes=False)
     elif isinstance(n,ast.ClassDef):visit(n.body,prefix+n.name+'.')
   visit(tree.body);return result
  allowed={'handoff_linux_v1.py':{'LinuxBackend.__init__','LinuxBackend.preflight'},'handoff_poststop_v1.py':{'Poststop.install'},'handoff_recovery_v1.py':{'recover'},'prepare_handoff_poststop_v1.py':{'prepare','main'}}
  for name,change in INPUTS['bundle_changes'].items():
   old=methods(change['original']['path']);new=methods(change['proposed']['path']);self.assertEqual(set(old),set(new));self.assertLessEqual({k for k in old if old[k]!=new[k]},allowed.get(name,set()))
  self.assertEqual(Path(SOURCES['handoff_controller_v1.py']['path']).read_bytes(),Path(INPUTS['bundle_changes']['handoff_controller_v1.py']['original']['path']).read_bytes())


def main(args):
 global L,P,SOURCES,INPUTS
 assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==args.source_sha256
 raw=args.job.read_bytes();assert hashlib.sha256(raw).hexdigest()==args.job_sha256;job=json.loads(raw);output=Path(job['output']);assert not output.exists();SOURCES=job['sources'];INPUTS=job['inputs']
 L=load(SOURCES['handoff_linux_v1.py'],'_current_context_contract_linux');P=load(SOURCES['handoff_poststop_v1.py'],'_current_context_contract_poststop')
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(SourceContracts);result=unittest.TextTestRunner(stream=sys.stderr,verbosity=2).run(suite)
 for entry in SOURCES.values():assert hashlib.sha256(Path(entry['path']).read_bytes()).hexdigest()==entry['sha256']
 assert 'torch' not in sys.modules
 report=dict(schema='dashboard-JSON-current-owner-handoff-CPU-contract-report-v1',status='CURRENT_OWNER_HANDOFF_CONTRACTS_PASS' if result.wasSuccessful() else 'CURRENT_OWNER_HANDOFF_CONTRACTS_FAIL',observed_unix_s=time.time(),tested_sources=SOURCES,tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),mocked_OS_and_kernel_events=True,temporary_files_only=True,new_actual_private_kernel_test_executed=False,kernel_behavior_not_exercised_by_this_CPU_suite=True,production_source_control_process_or_model_changed=False,live_handoff_selected=False,scientific_quality_claimed=False)
 with output.open('xb') as f:f.write((json.dumps(report,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
 print(json.dumps(dict(status=report['status'],tests=result.testsRun,failures=len(result.failures),errors=len(result.errors))));return 0 if result.wasSuccessful() else 1
if __name__=='__main__':
 if '--execute' in sys.argv[1:]:
  p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--job',type=Path,required=True);p.add_argument('--job-sha256',required=True);p.add_argument('--source-sha256',required=True);raise SystemExit(main(p.parse_args()))
 print('PLAN_ONLY: one original CPU contract run; no live handoff, model or kernel operations')
