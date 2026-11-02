"""Root-only fresh metadata acquisition; never signal actors or install sources."""
import ast
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.request

REPO = Path('/home/dave/source/repos/ArcadeAI')
GAME = REPO/'Robotron'
RUN = GAME/'logs/managed-learning-20261015/run-26'
OUT = Path(__file__).resolve().parent
PACK = RUN/'accepted-newgame-healthy-CE-maintenance-source-preparation-20261017'
SOURCE = PACK/'run_healthy_ce_maintenance.py'
SOURCE_SHA = 'f007ad2723fd5fe5b2fd4c0c95723e23b931c60c0938b63114f73e1f71c4b1ae'

def require(value, message):
    if not value:
        raise RuntimeError(message)

def load(path, name, expected):
    require(hashlib.sha256(path.read_bytes()).hexdigest()==expected, 'Source changed: '+str(path))
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module
    spec.loader.exec_module(module)
    return module

def main():
    require(not (OUT/'root-actual-job.json').exists(), 'New-only actual job')
    maintenance=load(SOURCE,'_root_healthy_maintenance_case',SOURCE_SHA)
    adapter=maintenance.load(maintenance.ADAPTER,maintenance.ADAPTER_SHA,'_root_healthy_case_adapter')
    base=adapter.load_v4()
    def full(path, maximum=base.MAX_JSON):
        return base.fingerprint(path,maximum)
    def save(name,value):
        if isinstance(value,bytes):
            target=OUT/name
            with target.open('xb') as stream:
                stream.write(value);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
            base.fsync_directory(OUT)
            return full(target,base.MAX_SOURCE)
        return base.publish(OUT/name,value)

    prior_path=RUN/'CE2048-trial02-failed-return-forward-CE4096-repair-20261017/result.json'
    prior_pin=full(prior_path)
    require(prior_pin['sha256']=='b4019062ff5275e842156a643818a6d8205d702e0fce0c5a51ab18d493f5d3b0','Wrong actual healthy ancestor')
    prior=base.read_json(prior_pin)
    prior_job=base.read_json(prior['root_job'])
    seed=base.read_json(prior_job['activation_job'])
    save('historical-seed-and-ancestor-pins.json',dict(prior=prior_pin,prior_job=prior['root_job'],historical_seed=prior_job['activation_job'],scope='Historical dictionary seed and genuine ancestry only; no current health or restart source.'))
    keep=('mode','experiment','game_root','model_dir','trainer_unit','fleet_unit','bank_spec','verifier','phase_verifier','insurance_verification','insurance_receipt','helper_pins')
    cfg={k:copy.deepcopy(seed[k]) for k in keep}
    cfg.update(mode='return_ce',output_directory=str(RUN/'accepted-newgame-healthy-CE-maintenance-20261017'),
        phase_id='ce4096_accepted_newgame_replay_boundary_fix_20261017',
        request_id='accepted_newgame_healthy_CE_start_20261017',
        startup_tag='CE4096-accepted-newgame-boundary-startup-20261017',
        timeouts=dict(ready_s=600,save_s=60,cpu_s=120),
        running_phase=copy.deepcopy(prior['startup']['phase']),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    require(re.fullmatch(r'[0-9a-f-]{36}',cfg['boot_id']), 'Actual boot UUID required')
    require(not Path(cfg['output_directory']).exists(),'Fresh maintenance output required')
    target=GAME/'models_dqn/managed-checkpoints'/(cfg['startup_tag']+'.pt')
    require(all(not Path(str(target)+suffix).exists() for suffix in ('','.tmp','.bak')),'New startup tag required before any stop')
    require(cfg['bank_spec']==dict(ring='/dev/shm/robotron_dqn_latest_replay',model_dir=str(GAME/'models_dqn'),capacity=6000000,state_size=11128,episode_capacity=192,bank_strides=dict(hof=1536,ephof=2048)), 'Exact proven bank/ring geometry required')

    entry_release_path=RUN/'lr25-prechange-entry-numeric-CPU-root-execution-20261017/root-original-entry-CPU-result-and-owned-release.json'
    entry_release_pin=full(entry_release_path)
    entry_release=base.read_json(entry_release_pin)
    entry_pin=full(entry_release['CPU_report']['path'])
    require(entry_pin==entry_release['CPU_report'],'Actual original typed entry FULLPIN differs')
    entry=base.read_json(entry_pin)
    cfg['verifier']['context']=copy.deepcopy(entry['root_job']['source_control_context'])
    cfg['helper_pins']['controller']=full(maintenance.ADAPTER,base.MAX_SOURCE)
    cfg['helper_pins']['v4']=full(adapter.V4,base.MAX_SOURCE)
    used=('live_host','metrics','identity','protection','bank_state','controller','v4','phase_script','phase_strict')
    cfg['helper_pins']={k:cfg['helper_pins'][k] for k in used}
    for value in cfg['helper_pins'].values():
        base.pin(value,base.MAX_SOURCE)
    require(cfg['helper_pins']['v4']['sha256']=='fdf7c8bfb123b494252acf83d724a51acda95bb7f00877eace28b60d0377ed18','Wrong selected V4')
    tools=Path(cfg['helper_pins']['live_host']['path']).parent
    sys.path.insert(0,str(tools))
    primitives=base.load_module(cfg['helper_pins']['live_host']['path'],'_root_healthy_case_live_host')
    for key,module in [('metrics',primitives.metrics),('identity',primitives.metrics.identity),('protection',primitives.protection)]:
        require(str(Path(module.__file__).resolve())==cfg['helper_pins'][key]['path'],'Unexpected imported helper '+key)
    dropin=Path('/run/user')/str(os.getuid())/'systemd/user'/(cfg['trainer_unit']+'.d')/'91-per-priority-phase.conf'
    class CurrentHost(primitives.LiveHost):
        def runtime_dropin(self):
            return dropin
    host=CurrentHost(cfg['trainer_unit'],cfg['fleet_unit'])
    before=host.describe()
    require(before['trainer']['MainPID']=='1626184' and before['bindings']['worker']['trainer']['starttime_ticks']==36413669,'Current healthy trainer identity changed')
    require(len(before['bindings']['actors'])==192 and len(before['bindings']['source_hashes'])==61 and len(before['bindings']['control_hashes'])==2,'Incomplete fresh ownership/source/control maps')
    unit_files={k:v for group in before['unit_files'].values() for k,v in group.items()}
    require(len(unit_files)==3 and str(dropin) not in unit_files,'Exact immutable three unit files, separate owned91 lifecycle required')
    host.metric_host.configure_logs(before['bindings']['logs'])
    row=host.capture()
    plan=dict(batch_size=4096,replay_cap=8,initial_snapshot=dict(csv=row['csv']),exposure_identity={kind:primitives.metrics.exposure_key(row['exposure'][kind]) for kind in ('optimizer','replay')})
    require(not primitives.metrics.api_issues(row,plan),'Fresh captured API/CSV guards failed')
    require(all(value['process_id']==1626184 for value in plan['exposure_identity'].values()),'Fresh exposure owner differs')
    cfg['before']=before
    cfg['baseline_csv']=copy.deepcopy(row['csv'])
    cfg['actor_masks']={str(actor['pid']):sorted(os.sched_getaffinity(actor['pid'])) for actor in before['bindings']['actors']}
    cfg['worker_mask']=host.metric_host.mask(before['bindings']['worker'])
    require(all(mask==list(range(72)) for mask in cfg['actor_masks'].values()) and cfg['worker_mask']==list(range(72)),'Original full affinity changed')
    settings=full(GAME/'models_dqn/game_settings.json')
    parsed=base.read_json(settings)
    require(parsed==seed['settings_lifecycle']['parsed_values'],'Game settings changed from held recipe')
    cfg['settings_lifecycle']=dict(initial=settings,parsed_values=parsed,policy='same_bytes_after_owned_stop_only')
    require(dropin.is_file() and not dropin.is_symlink(),'Current91 phase override required')
    dropbytes=dropin.read_bytes()
    cfg['original_dropin']=dict(path=str(dropin),content_base64=base64.b64encode(dropbytes).decode(),mode=dropin.stat().st_mode&0o777)
    require(b'9b3b839fe39044538412f0f78a8c28feae60170ea2d1c363d21efeead17d84d1' in dropbytes,'Current91 override does not identify CE9b3')
    require(not (GAME/'models_dqn/managed_save.request.json').exists(),'Foreign pending save request')
    cfg['current_completed_request']=full(GAME/'models_dqn/managed_save.request.json.completed')
    save('fresh-before.json',before)
    save('fresh-captured-main-row.json',row)
    with urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5) as stream:
        api_raw=stream.read((1<<20)+1)
    require(len(api_raw)<=1<<20,'API exceeds bounded raw snapshot')
    api=json.loads(api_raw)
    require(api['client_count']==192 and api['training_enabled'] and not api['measurement_active'] and api['lr']==2.5e-5,'Fresh actual192/.5 CE required')
    require(api['host_pipeline']['learning_exposure']['optimizer']['process_id']==1626184,'Current raw API owner changed')
    save('fresh-main-API.raw.json',api_raw)

    patch_dir=RUN/'accepted-newgame-replay-boundary-unapplied-source-preparation-20261017'
    patch_test=patch_dir/'test_handler_boundary.py'
    require(hashlib.sha256(patch_test.read_bytes()).hexdigest()=='cf116f2790bc2b901d7f70197584511cb587d1ca70e08ec0d61e986c0d6c7625','Reviewed materializer source changed')
    tree=ast.parse(patch_test.read_text())
    funcs=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in ('authenticated','candidate_source')]
    require(len(funcs)==2,'Exact in-memory patch materializer required')
    ns=dict(hashlib=hashlib,re=re,SOCKET=maintenance.SOCKET,BASE_SHA=maintenance.BEFORE_SHA,
        HERE=patch_dir,PATCH_SHA='c0ed76c79e90fbde22b80b6cb9aea5e2391fc2711141dcae0904cfe94d7b8d44',CANDIDATE_SHA=maintenance.AFTER_SHA)
    exec(compile(ast.Module(body=funcs,type_ignores=[]),str(patch_test),'exec'),ns)
    candidate=ns['candidate_source']().encode()
    compile(candidate,str(maintenance.SOCKET),'exec')
    after=save('socket_server-reviewed-4a1f6a3c.py',candidate)
    cfg['sources']=[dict(destination=str(maintenance.SOCKET),before=full(maintenance.SOCKET,base.MAX_SOURCE),after=after)]

    quality_release=full(maintenance.ACTUAL_RELEASE['path'])
    patch_guards=full(maintenance.ACTUAL_PATCH_GUARDS['path'])
    patch_manifest=full(maintenance.PATCH_MANIFEST)
    intent=dict(schema='robotron-accepted-newgame-healthy-CE-maintenance-intent-v1',owner=copy.deepcopy(maintenance.CURRENT_OWNER),running_phase=cfg['running_phase'],phase_id=cfg['phase_id'],socket_before_sha256=maintenance.BEFORE_SHA,socket_after_sha256=maintenance.AFTER_SHA,quality_release=quality_release,patch_guard_result=patch_guards,boot_newest_only=True,no_weight_or_optimizer_rollback=True,retain_original_fleet=True,target_batch_size=4096,target_lr_scale=0.5,prior_maintenance=prior_pin,original_failed_trial=prior_job['trial_result'],original_failed_return=prior_job['return_result'])
    intent_pin=save('root-maintenance-intent.json',intent)
    cfg['trial_core']=intent_pin
    static_paths=[SOURCE,PACK/'preparation-manifest.json',RUN/'accepted-newgame-healthy-CE-maintenance-independent-source-review-20261017/source-review-receipt.json',RUN/'accepted-newgame-healthy-CE-maintenance-four-guards-root-execution-20261017/root-original-four-guard-result-and-owned-release.json',RUN/'accepted-newgame-healthy-maintenance-original-four-guards-independent-saved-review-20261017/review-receipt.json',RUN/'accepted-newgame-original-seven-guards-and-partial-freeze-release-independent-saved-review-20261017/review-receipt.json',Path(quality_release['path']),Path(patch_guards['path']),Path(patch_manifest['path']),Path(intent_pin['path']),Path(entry_pin['path']),Path(entry_release_pin['path']),prior_path,Path(__file__).resolve()]
    cfg['static_pins']=[full(path,base.MAX_SOURCE) for path in static_paths]
    forbidden={str(maintenance.SOCKET),settings['path'],cfg['current_completed_request']['path'],str(dropin),str(GAME/'models_dqn/robotron_dqn_latest.pt')}
    require(not any(value['path'] in forbidden for value in cfg['static_pins']),'Mutable path must use owned lifecycle')
    job=dict(schema=maintenance.SCHEMA,activation_authorized=True,transition=cfg,entry_CPU=entry_pin,entry_CPU_release=entry_release_pin,quality_release=quality_release,patch_manifest=patch_manifest,patch_guard_result=patch_guards,maintenance_intent=intent_pin)
    maintenance.validate(job,base,adapter)
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==cfg['boot_id'],'Boot drifted during acquisition')
    require(host.describe()==before,'Fresh before changed during root acquisition')
    base.pin(settings,base.MAX_JSON)
    base.pin(cfg['current_completed_request'],base.MAX_JSON)
    require(dropin.read_bytes()==dropbytes and full(maintenance.SOCKET,base.MAX_SOURCE)==cfg['sources'][0]['before'],'Owned lifecycle/source changed during root acquisition')
    job_pin=save('root-actual-job.json',job)
    summary=save('root-actual-job-preparation.json',dict(schema='robotron-root-healthy-CE-newest-state-job-preparation-v1',prepared_unix_s=time.time(),actual_job=job_pin,source=full(SOURCE,base.MAX_SOURCE),fresh_owner=maintenance.CURRENT_OWNER,fresh_before=full(OUT/'fresh-before.json'),fresh_API=full(OUT/'fresh-main-API.raw.json'),fresh_csv=cfg['baseline_csv'],fresh_settings=settings,fresh_completed=cfg['current_completed_request'],fresh_boot_id=cfg['boot_id'],startup_tag_fresh=True,bank_geometry_prechecked=True,source_application=False,actual_maintenance=False,typed_metadata_validate='PASS',independent_fresh_job_review_pending=True))
    print(json.dumps(dict(status='ACTUAL_FRESH_JOB_VALIDATED_NOT_EXECUTED',job=job_pin,preparation=summary),allow_nan=False))

if __name__=='__main__':
    main()
