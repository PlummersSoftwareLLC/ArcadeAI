"""Bounded existing192M reference readiness; no future224/256 file access or launch."""
import ast
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

D = Path(__file__).resolve().parent
RUN, C, G = D.parent, D.parents[1], D.parents[3]
GPU0 = 'GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0'
GB = 'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'
SLOTS = list(range(4096,4112))
LABEL = 'sidecar-gpu0-192M-reference1200-01'
started = datetime.datetime.now(datetime.timezone.utc).isoformat()
cache = {}
def raw(path, expected=None):
    path = Path(path)
    if str(path) not in cache:
        cache[str(path)] = path.read_bytes()
    value = cache[str(path)]
    assert expected is None or hashlib.sha256(value).hexdigest() == expected, str(path)
    return value
def doc(path, expected=None):
    return json.loads(raw(path,expected))
def digest(path):
    return hashlib.sha256(raw(path)).hexdigest()
def process(pid):
    fields = Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=pid,start_ticks=int(fields[19]),state=fields[0])
def environment(pid):
    return dict(item.decode().split('=',1) for item in Path('/proc',str(pid),'environ').read_bytes().split(b'\0') if b'=' in item)
def stat_only(path):
    path=Path(path); s=path.stat()
    return dict(size=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino,device=s.st_dev,
                mode=s.st_mode&0o777,nlink=s.st_nlink,symlink=path.is_symlink())

contract_path=RUN/'private1200-deferred-launch-contract.json'
contract=doc(contract_path,'52b38998d49a3d73ef07bf3f969d9f5b57cebd89d483fa8c86605ef7bb397d92')
design_path=C/'run-23/future-quality1200-root-design-adoption.json'
design=doc(design_path,'21de3c8b681f97bb9894e52251737f2ea089539bfb9127270c7dc868bcfb74da')
plan_path=D/'quality1200-plan.json'; plan=doc(plan_path)
campaign_path=C/'sidecar-fresh3-192M-confirmed-campaign.json'
campaign=doc(campaign_path,'23f01f6e377dd1a34fb3a10ab9f2a14439b58ffd03fed4acccdcb7513349ecaa')
common=campaign['common_runtime']
protected=G/'models_dqn/managed-incumbents/fresh3-192M-confirmed.pt'
metadata_path=protected.with_suffix('.pt.json')
metadata=doc(metadata_path,'f5a0ef9c1c0c046abfcdf8c98456dd58644d38a9073ca2f601d140a034a94e09')
lineage_path=C/'run-23/fresh3-192M-checkpoint-lineage.json'
lineage=doc(lineage_path,'1fa656bc42cf62e9f63e0b97d09d39b7c686326b4d69140d99fea56c215c5ba2')
protected_stat=stat_only(protected)
source_stat=stat_only(lineage['candidate']['path'])
sources={name:digest(G/name) for name in contract['source12']}
sys.path.insert(0,str(G/'tools'))
from sidecar_boot import load_snapshot
boot=load_snapshot(common['job']['boot_assets'])
manifest_path=RUN/'actor192-all-connected.json'; manifest=doc(manifest_path)
main_actors=[]
for actor in manifest['actors']:
    try:
        item=process(actor['pid']); same=item['start_ticks']==actor['start_ticks'] and item['state'] not in ('Z','X')
    except (OSError,ValueError,IndexError):
        same=False
    main_actors.append(dict(pid=actor['pid'],slot=actor['slot'],same_start_ticks=same))
main=process(2148801); supervisor=process(2149551)
supervisor_expected=next(row['start_ticks'] for row in manifest['supervisor_identities'] if row['pid']==2149551)
main_env=environment(2148801)
actor_env=environment(main_actors[0]['pid'])
library=Path(actor_env['LD_PRELOAD']); library_sha=digest(library)
listeners=[]
for table in ('/proc/net/tcp','/proc/net/tcp6'):
    for line in Path(table).read_text().splitlines()[1:]:
        f=line.split()
        if int(f[1].rsplit(':',1)[1],16)==9999 and f[3]=='0A':listeners.append(dict(table=table,line=line))
mames=[]; runners=[]; unreadable=[]
for entry in Path('/proc').iterdir():
    if not entry.name.isdecimal():continue
    try: args=[a.decode(errors='replace') for a in entry.joinpath('cmdline').read_bytes().split(b'\0') if a]
    except OSError:continue
    if any(Path(a).name=='run_frozen_sidecar.py' for a in args):runners.append(dict(pid=int(entry.name),argv=args))
    if not args or Path(args[0]).name!='mame' or 'robotron' not in args:continue
    try:
        e=environment(int(entry.name)); mames.append(dict(pid=int(entry.name),slot=e.get('ROBOTRON_CLIENT_SLOT'),wait_port=e.get('ROBOTRON_SOCKET_WAIT_PORT')))
    except OSError as error:unreadable.append(dict(pid=int(entry.name),error=str(error)))
high=[row for row in mames if row['slot'] in set(map(str,SLOTS))]
probe_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
gpu=subprocess.run(['nvidia-smi','--query-gpu=index,uuid,name,utilization.gpu,memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
apps=subprocess.run(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,process_name,used_memory','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
gpu_rows=[[v.strip() for v in line.split(',')] for line in gpu.stdout.splitlines() if line.strip()]
app_rows=[[v.strip() for v in line.split(',')] for line in apps.stdout.splitlines() if line.strip()]
main_gpu=[row for row in app_rows if row[0]=='2148801']; private_gpu=[row for row in app_rows if row[1]==GPU0]
with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=3) as response:api=json.load(response)
hp=api['host_pipeline']; graphs=hp['inference_graphs']; native=hp['native_batch_update']; banks=api['bank_persistence']
opt,replay=hp['learning_exposure']['optimizer'],hp['learning_exposure']['replay']
tee=[]
for entry in Path('/proc').iterdir():
    if not entry.name.isdecimal():continue
    try:
        command=entry.joinpath('cmdline').read_bytes().replace(b'\0',b' ').decode()
        if command.startswith('tee ') and str(RUN/'console.log') in command:
            fds={fd.name:os.readlink(fd) for fd in entry.joinpath('fd').iterdir()}
            tee.append(dict(pid=int(entry.name),cmdline=command,fds=fds))
    except (OSError,ProcessLookupError):pass

# Compare every deferred command against the ALREADY reviewed600s launch list.
# Future224/256 paths below remain opaque strings, never stat/open/validate them.
prior_readiness=doc(C/'run-23/quality192M-private-launch-readiness-independent.json')
base_argv=prior_readiness['deferred_argv']
expected_roles={label:str(protected) for label in design['fixed_labels']['192M_reference']}
expected_roles.update({label:str(G/'models_dqn/managed-checkpoints/fresh3-224M.pt') for label in design['fixed_labels']['224M_guard']})
expected_roles.update({label:str(G/'models_dqn/managed-checkpoints/fresh3-256M.pt') for label in design['fixed_labels']['256M_full']})
argv_checks={}
for label,checkpoint in expected_roles.items():
    expected=list(base_argv)
    for flag,value in {'--checkpoint':checkpoint,'--job-dir':str(C/label),'--label':label,'--cohort-s':'1200','--timeout-s':'2400'}.items():expected[expected.index(flag)+1]=value
    argv_checks[label]=contract['jobs'].get(label)==expected
tree=ast.parse(raw(G/'tools/run_frozen_sidecar.py').decode())
known_flags={arg.value for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='add_argument' for arg in node.args if isinstance(arg,ast.Constant) and isinstance(arg.value,str)}
argv=contract['jobs'][LABEL]
requested={value for value in argv[argv.index(str(G/'tools/run_frozen_sidecar.py'))+1:] if value.startswith('--')}
checks={
 'root_deferred_contract_and_adopted1200_design_byte_pins':contract['root_design_sha256']==digest(design_path) and design['root_adopted_design'] is True,
 'exact_fixed5_deferred_commands_only_allowed_role_changes':len(contract['jobs'])==5 and set(contract['jobs'])==set(expected_roles) and all(argv_checks.values()) and requested<=known_flags,
 'reference01_exact_protected192_path_and1200_2400':argv[argv.index('--checkpoint')+1]==str(protected) and argv[argv.index('--cohort-s')+1]=='1200' and argv[argv.index('--timeout-s')+1]=='2400' and LABEL==design['fixed_labels']['192M_reference'][0],
 'two_reference_legs_no_quality_selection_old600claim_kept':len(design['fixed_labels']['192M_reference'])==2 and design['no_reference_score_selection'] and design['old600s_claim_immutable'] and not design['operational_replacement_authorized'],
 'protected192_small_metadata_campaign_root_lineage_pins_match':metadata['sha256']==campaign['policy_identity']['sha256']==lineage['candidate']['sha256']==design['reference_checkpoint_sha256']=='5076199285752a8748ce9566bc74c6b67210a03ae7f04f132f92b786dea102da' and metadata['saved_checkpoint_metadata']==lineage['candidate']['saved_metadata'],
 'protected192_current_stat0444_nlink1_independent_source_inode':not protected_stat['symlink'] and protected_stat['mode']==0o444 and protected_stat['nlink']==1 and all(protected_stat[key]==value for key,value in plan['reference']['checkpoint']['stat'].items()) and (protected_stat['device'],protected_stat['inode'])!=(source_stat['device'],source_stat['inode']),
 'private12_exact_existing_backend':len(sources)==12 and sources==contract['source12']==common['source_hashes'],
 'boot_manifest_and_all3_existing_files_exact':boot['identity']==common['boot_identity']==contract['boot_identity'] and boot['files']==common['boot_files'] and boot['manifest_sha256']==contract['boot_manifest_sha256'],
 'existing_native_shim_exact_no_build':library_sha==common['socket_wait_sha256']=='13d496b6f268d28c0b732e88635c0e05c7eaa5f7aa622d4e783767b0ace2ff4d',
 'frozen_private16_highslots_EPS0_expert0_difficulty5_wave1':common['job']['actors']==16 and common['job']['actor_slots']==SLOTS and common['job']['epsilon']==common['job']['expert_ratio']==0 and common['job']['difficulty']==5 and common['job']['start_level']==1 and not common['job']['replay_enabled'],
 'expected_FP32_TF32_Inductor_warm1to16':common['numeric_policy']['weights']==common['numeric_policy']['inputs']=='float32' and common['numeric_policy']['backend']=='inductor' and common['numeric_policy']['compiled'] is True and common['numeric_policy']['cuda_matmul_allow_tf32'] and common['numeric_policy']['cudnn_allow_tf32'] and not common['numeric_policy']['autocast'] and not common['numeric_policy']['suppress_errors'] and common['numeric_policy']['warm_shapes']==list(range(1,17)) and common['numeric_policy']['serving_thread_checked'],
 'main192_actual_PID_startticks_slots_preserved':len(main_actors)==192 and all(row['same_start_ticks'] for row in main_actors) and sorted(row['slot'] for row in main_actors)==list(range(192)),
 'main_run25_trainer_and_supervisor_actual_identity':main['start_ticks']==26264365 and supervisor['start_ticks']==supervisor_expected and main['state'] not in ('Z','X') and supervisor['state'] not in ('Z','X'),
 'main_API192_training_not_measurement_and_held_recipe':api['client_count']==192 and api['training_enabled'] and not api['measurement_active'] and api['measurement_frames']==7550388 and api['epsilon']==.1 and abs(api['expert_ratio']-.1)<1e-12 and api['lr']==2.5e-5 and api['memory_buffer_size']==6000000 and main_env['DQN_INFERENCE_BATCH_WAIT_MS']=='1' and main_env['ROBOTRON_RUN_DIR']==str(RUN),
 'main_graph_native_bank_and_metadata_read_health':graphs['ready'] and graphs['capture_count']==128 and graphs['validation_cpu_returns']==640 and graphs['postload_validations']==1 and graphs['runtime_capture_count']==graphs['fallback_count']==0 and graphs['fatal_error'] is None and native['enabled'] and native['available'] and native['success_count']==native['completed_count'] and native['fallback_count']==native['error_count']==0 and not api['pipeline_read_error'] and not api['bank_persistence_read_error'] and banks['output']['backend']=='stream' and banks['write_failures']==0 and banks['last_error'] is None and all(v['errors']==0 for v in banks['output']['totals'].values()),
 'main_counter_epochs_partitions_and_unknown0':opt['process_id']==replay['process_id']==2148801 and opt['epoch']==replay['epoch']==1 and opt['total']['unavailable']==opt['prior_epoch_outcomes_total']==0 and opt['unclassified_started_total'] in (0,1) and opt['total']['outcomes_recorded']==opt['total']['applied']+opt['total']['amp_skipped'] and replay['accepted_learner_total']==replay['accepted_by_source_total']['dqn']+replay['accepted_by_source_total']['epsilon'],
 'actual_console_tee_pts2_visible':len(tee)==1 and str(RUN/'console.log') in tee[0]['fds'].values() and '/dev/pts/2' in tee[0]['fds'].values(),
 'time_local_GPU0_compute_idle':gpu.returncode==apps.returncode==0 and not private_gpu and any(row[1]==GPU0 and row[3]=='0' for row in gpu_rows),
 'main_context_physical_GB300_only':bool(main_gpu) and all(row[1]==GB for row in main_gpu) and main_env.get('CUDA_VISIBLE_DEVICES')=='1' and 'LD_PRELOAD' not in main_env,
 'port9999_no_listener':not listeners,
 'private_highslots_and_runners_absent':not high and not runners and not unreadable,
 'only_pinned192_Robotron_MAME_present':len(mames)==192 and {row['pid'] for row in mames}=={row['pid'] for row in main_actors},
 'first_reference_exclusive_job_path_unused':not (C/LABEL).exists(),
}
report=dict(schema='robotron-reference1200-01-prospective-launch-readiness-independent-v1',PASS=all(checks.values()),checks=checks,started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 deferred_argv_contract_sha256=digest(contract_path),root_design_sha256=digest(design_path),observed_draft_plan_sha256=digest(plan_path),first_reference_deferred_argv=argv,all5_exact_argv_comparison=argv_checks,
 private12=sources,boot_identity=boot['identity'],boot_files=boot['files'],boot_manifest_sha256=boot['manifest_sha256'],existing_native_shim=dict(path=str(library),sha256=library_sha),
 frozen_expected_numeric_policy=common['numeric_policy'],frozen_expected_runtime=common['runtime'],protected192=dict(checkpoint_path=str(protected),expected_root_attested_sha256=design['reference_checkpoint_sha256'],stat=protected_stat,metadata_sha256=digest(metadata_path),campaign_sha256=digest(campaign_path),lineage_sha256=digest(lineage_path),model_payload_read=False),
 main=main,supervisor=supervisor,main192=main_actors,actor_manifest_sha256=digest(manifest_path),tee=tee,main_health={key:api[key] for key in ('ts','client_count','measurement_active','training_steps','optimized_samples','learner_frame_count','frame_count','measurement_frames')},main_counter_snapshot=dict(optimizer=opt,replay=replay),
 resource_probe=dict(utc=probe_utc,gpu_rows=gpu_rows,compute_apps=app_rows,listeners9999=listeners,private_highslot_mames=high,private_runners=runners,unreadable_mames=unreadable),
 before_actual_root_launch_required=['Root adopts exact final plan/history/reference helper with focused fake-fixture and independent source review. Draft plan hash here is observation, not adoption.', 'Root repeats time-local GPU0 compute-idle/9999/highslot/owned-process/source12/boot/shim/protected-stat/main192/console checks immediately before launch.','Only root launches. Keep source12/main fleet frozen during owned private cohort, preserve all starters/full tails and positive cleanup; no score-based reference selection.'],
 scope='Existing protected192 smallJSON/stat/SHA attestations and current cheap process/resource/API checks only; no protected or old model body hash/load, Torch/GPU context, jobdir creation, CLI Job.validate invocation, MAME/runner launch, process/control/state/source action. Future224/256 checkpoint/gate/lineage/quality paths stay opaque command strings and are never visited. Actual new runner numeric/compile metadata remains final-receipt evidence, not proven by this prospective report.')
out=D/'reference1200-01-launch-readiness-independent.json'
with out.open('x') as file:
    json.dump(report,file,indent=2,allow_nan=False);file.write('\n');file.flush();os.fchmod(file.fileno(),0o444);os.fsync(file.fileno())
print(json.dumps(dict(PASS=report['PASS'],checks=len(checks),failed=[key for key,value in checks.items() if not value],sha256=digest(out),probe_utc=probe_utc),indent=2))
