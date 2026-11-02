"""Independently rejoin one closed diagnostic's actual bytes; no scientific review."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import time
import types

GAME=Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE=Path(__file__).resolve().parent
READER=GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'

def require(value,message):
    if not value:raise ValueError(message)

def main():
    time.sleep(2)
    require(hashlib.sha256(READER.read_bytes()).hexdigest()==
        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071','Reader differs')
    spec=importlib.util.spec_from_file_location('_closed_diagnostic_reader',READER)
    r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    selection_pin=r.pin(HERE/'original-root-guard-selection.json');selection=r.read_pin(selection_pin)
    launch=r.checked_module('_closed_diagnostic_launcher',selection['launcher'])
    # A consumed output must never be passed to the fresh-execution load_plan.
    plan=launch.checked_plan(r.read_pin(selection['plan']));job=r.read_pin(plan['job'])
    modules={k:r.checked_module('_closed_diagnostic_'+k,plan['sources'][k]) for k in launch.EXPECTED if k!='reader'}
    require(all(job['sources'][k]==plan['sources'][k] for k in job['sources']),'Original source joins differ')
    root_pin=r.pin(HERE/'root-guard-execution/root-original-result-and-owned-release.json');root=r.read_pin(root_pin)
    require(root['error'] is None and root['selection']==selection_pin,'Original guard root lifecycle differs')
    root_archives=launch.verify_archives(root['original'],root['timer'],root['archives']['records'],
        lambda p,j:r.read_pin(p,as_json=j))
    require(root['outcome']==dict(exec_code=1,status=0,result='success',normal_exit=True),'Original guard did not exit0')
    require(len(root['release'])==2 and all(x['confirmed_absent'] for x in root['release']),'Guard releases incomplete')
    guarddir=Path(plan['output'])
    def single(pattern):
        matches=list(guarddir.glob(pattern));require(len(matches)==1,'Ambiguous original '+pattern)
        pin=r.pin(matches[0]);return pin,r.read_pin(pin)
    guard_pin,guard=single('*original-launch-result.json')
    _,timer=single('*original-launch-timer.json');_,archives=single('*original-terminal-archives.json')
    child_archives=launch.verify_archives(guard['original'],timer['original'],archives['records'],
        lambda p,j:r.read_pin(p,as_json=j))
    require(guard['valid'] is True and guard['error'] is None
        and guard['original_outcome']==root['outcome'],'Original private unit did not exit0')
    require(len(guard['release'])==2 and all(x['confirmed_absent'] for x in guard['release']),'Child releases incomplete')
    wd=guard['watchdog'];require(wd['valid'] is True and wd['failures']==wd['actions']==[],
        'Original watchdog coverage or signal outcome failed')
    coverage=modules['watchdog'].coverage(wd['samples'],guard['original']['start_monotonic_us']/1e6,
        int(wd['terminal_fields']['ExecMainExitTimestampMonotonic'])/1e6)
    require(coverage==wd['coverage'] and coverage['whole_unit_main_coverage'] is True,'Original whole-unit coverage differs')
    out=Path(job['output']);result_pin=r.pin(out/'result.json');result=r.read_pin(result_pin)
    launch.checked_child_result(result,modules['core'])
    inventory_pin=r.pin(out/'original-prefix-capture-inventory.json');inventory=r.read_pin(inventory_pin)
    require(inventory['errors']==[] and inventory['original_producer_modes_unchanged'] is True
        and len(inventory['retained'])==51,'Complete51 original captures required')
    caps=launch.System();caps.reader=r;caps.job=job;caps.modules=modules
    capture_proof=caps.verify_capture_inputs(result['reconciliation']['tap_provenance'])
    retained=inventory['retained'];raw={key:r.read_pin(pin,as_json=False) for key,pin in retained.items()}
    slots=range(4096,4112);sessions={int(k):v for k,v in job['sessions'].items()}
    joined=modules['tap_join'].reconcile(
        {s:raw['Lua-'+str(s)] for s in slots},raw['server'],
        {s:raw['tap-'+str(s)] for s in slots},{s:raw['console-'+str(s)] for s in slots},
        sessions,raw['ROM3'],raw['ROM10'],limit=4096)
    require(joined==result['reconciliation']['tap_provenance'],'Independent original content join differs')
    require(joined['matched_inputs']==65536 and joined['actor_slots']==16,'Full16x4096 content missing')
    process=modules['watchdog'].Processes();unit_absence=[]
    for owner,timer_owner in ((root['original'],root['timer']),(guard['original'],timer['original'])):
        require(process.start(owner['pid']) is None and not Path('/sys/fs/cgroup'+owner['cgroup']).exists(),
            'An original guard/private process or cgroup remains')
        for unit in (owner['unit'],timer_owner['unit']):
            fields=process.fields(unit);require(fields.get('Id')==unit and fields.get('LoadState')=='not-found',
                'An original unit remains loaded');unit_absence.append(unit)
    births={};events={};backend={}
    for slot in slots:
        pin=r.pin(out/f'actor-{slot}-original-birth.json');birth=r.read_pin(pin);births[str(slot)]=pin
        require(birth['parent_pid']==guard['original']['pid'] and birth['cgroup']==guard['original']['cgroup']
            and process.start(birth['pid']) is None,'Original actor birth or cleanup differs')
        text=raw['console-'+str(slot)].decode(errors='replace')
        observed=[dict(zip(('pid','fd','port','interval_us'),map(int,m))) for m in re.findall(
            r'\[robotron-socket-wait\] pid=(\d+) fd=(\d+) port=(\d+) interval_us=(\d+)',text)]
        require(len(observed)==1 and observed[0]['pid']==birth['pid']
            and observed[0]['port']==9999 and observed[0]['interval_us']==1000,'Original socket backend differs')
        backend[str(slot)]=observed
        events[slot]=[]
        for line in text.splitlines():
            if '[SOCKET ACTION TIMEOUT]' in line:
                match=re.search(r'\bunix_s=(\d+)\b',line)
                events[slot].append(dict(unix_s=int(match[1]) if match else None))
    audit=result['runtime_audit'];timing=audit['timeout_evidence']
    package=r.read_pin(job['package'])
    # Import only this standard-library evaluator helper; never import its model runtime.
    frozen=r.checked_module('_closed_diagnostic_timeout_accounting',package['file_pins']['tools/run_frozen_sidecar.py'])
    timing_rejoined=frozen.timeout_evidence({int(k):v for k,v in timing['actor_timeout_logs_before_shutdown'].items()},
        events,timing['timeout_snapshot_unix_s'])
    require(json.loads(json.dumps(timing_rejoined))==timing and sum(timing_rejoined['actor_timeout_logs'].values())==0,
        'Original runtime/cleanup timeout classification differs')
    main=r.read_pin(job['main']);baseline=modules['raw_api'].parse_wire(r.read_pin(main['baseline_API'],as_json=False))
    previous=baseline
    for sample in wd['samples']:
        evidence=sample['evidence'];api=modules['raw_api'].parse_wire(r.read_pin(evidence['raw_API'],as_json=False))
        require(evidence['main_owner']==main['owner'] and evidence['original192_actors_verified'] is True,
            'Original main sample identity differs')
        modules['main_guard'].healthy(api,baseline,main['experiment'],api['ts'])
        require(all(api[k]==baseline[k] for k in ('epsilon','expert_ratio','lr'))
            and evidence['clocks']=={k:api[k] for k in ('learner_frame_count','training_steps','optimized_samples')},
            'Original main recipe or projected clocks differ')
        require(all(api[k]>=previous[k] for k in ('frame_count','learner_frame_count','training_steps','optimized_samples')),
            'Original main counters regressed')
        for kind in ('optimizer','replay'):
            require(all(api['host_pipeline']['learning_exposure'][kind][k]==baseline['host_pipeline']['learning_exposure'][kind][k]
                for k in ('process_id','instance_monotonic_ns','epoch')),'Main optimizer/replay instance changed')
        previous=api
    modules['main_guard'].owner_and_files(main)
    monitor=modules['runtime'].System();monitor.reader=r;monitor.modules=modules;monitor.main=main
    monitor.main_hash_stats={path:monitor.stat_key(Path(path).stat()) for path in main['held_hashes']}
    monitor.package=package;monitor.baseline=baseline;monitor.previous=previous
    monitor.verify_inputs(types.SimpleNamespace(job=job))
    reviewdir=HERE/'independent-original-diagnostic-review';reviewdir.mkdir(mode=0o700)
    def put(path,data):
        with path.open('xb') as f:f.write(data);f.flush();os.fchmod(f.fileno(),0o444);os.fsync(f.fileno())
        return r.pin(path)
    current_wire={}
    def publish_api(name,data):current_wire[name]=put(reviewdir/name,data)
    monitor.health(types.SimpleNamespace(owns_output=True,publish_bytes=publish_api),force=True)
    report=dict(schema='robotron-independent-actual-original-startup-diagnostic-v1',
        status='VALID_ONE_ORIGINAL_CORRECTED_WIRE_DIAGNOSTIC_PREFIX',valid=True,
        root_closure=root_pin,guard_result=guard_pin,child_result=result_pin,selection=selection_pin,
        root_archives=root_archives,child_archives=child_archives,whole_unit_main_coverage=coverage,
        actual_all51_input_fullpins=capture_proof,inventory=inventory_pin,independent_content_join=joined,
        all_four_exact_units_absent=unit_absence,all16_original_actor_births_absent=births,
        actual_backend=backend,rejoined_timeout_evidence=timing_rejoined,
        sources_ROM_boot_checkpoint_and_main192_held195_unchanged=True,current_main_API=current_wire,
        main_clocks={k:monitor.previous[k] for k in ('learner_frame_count','training_steps','optimized_samples')},
        first_start_certified=False,admission_clock_ordering_verified=False,real_ROM_start_proven=False,
        protocol_selected=False,quality_qualified=False,learning_speed_gain_verified=False,
        prior_failed_original_preserved=True,scientific_review_rerun=False)
    pin=put(reviewdir/'review.json',(json.dumps(report,indent=2,allow_nan=False)+'\n').encode())
    print(json.dumps(dict(status=report['status'],valid=True,report=pin,matched_inputs=65536,
        quality_qualified=False,first_start_certified=False)),flush=True)

if __name__=='__main__':main()
