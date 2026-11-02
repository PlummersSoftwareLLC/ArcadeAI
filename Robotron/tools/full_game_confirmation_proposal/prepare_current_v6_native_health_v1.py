"""Prepare a still-UNBOUND native using the CPU/live-probed current-v6 guard.

This integrates the new health scope without borrowing old197/192 history.
Fresh policy/source/prebody/controller and finite MAME engineering qualification
are still required before a scientific launch. The all64 full-game rules stay.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')


def require(value,message):
    if not value:raise ValueError(message)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--parent-packet',type=Path);parser.add_argument('--health-review',type=Path);parser.add_argument('--directory',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    h=load('_prepare_v6_native_health_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    parent=json.loads(args.parent_packet.read_text());review=json.loads(args.health_review.read_text())
    require(parent['status']=='UNBOUND_NATIVE_SOURCE_ONLY_NOT_LAUNCHABLE'
        and review['status']=='PASS_CPU10_AND_FIVE_ACTUAL_BOUNDED_PHYSICAL_SAMPLES','Exact source-only native and current guard engineering required')
    original=h.checked(parent['native']).read_text();source=original
    health=h.checked(review['source']);health_pin=h.pin(health);review_pin=h.pin(args.health_review)
    edits=[]
    def replace(old,new):
        nonlocal source
        require(source.count(old)==1,'Nonunique current-v6 integration anchor: '+old[:80])
        source=source.replace(old,new,1);edits.append((old,new))
    begin="    require(all(type(job.get(key))is dict and set(job[key])=={'path','sha256','bytes','identity'}\n"
    end="    require(job.get('quality_leg')in ROLES"
    old=source[source.index(begin):source.index(end)]
    replace(old,"    require(job.get('current_v6_health_source',{}).get('sha256')=="+repr(health_pin['sha256'])+"\n"
        "        and job.get('current_v6_health_qualification',{}).get('sha256')=="+repr(review_pin['sha256'])+"\n"
        "        and all(type(job.get(k))is dict for k in ('current_main','current_fleet','source_family_manifest')),\n"
        "        'Exact prospective current-v6 health source/engineering/fresh current owner binding required')\n")
    begin="    expected=dict(supervision=";end="    require(job['lease']['path']==str(LEASE)"
    old=source[source.index(begin):source.index(end)]
    replace(old,"    require(job['current_main']['owner']['pid']==job['current_fleet']['trainer']['pid']\n"
        "        and job['current_main']['owner']['starttime_ticks']==job['current_fleet']['trainer']['birth'],\n"
        "        'Current Main owner and actual v6 fleet must agree')\n")
    begin="        supervision=load('_compiled32_main_supervision'";end="        sidecar=load('_compiled32_profile06_sidecar'"
    old=source[source.index(begin):source.index(end)]
    new="""        h.checked(job['current_v6_health_qualification'])
        current_health=load('_fullgame_current_v6_main_health',h.checked(job['current_v6_health_source']))
        main_guard=current_health.CurrentV6MainHealth(job,output,h);main_guard.start()
        def collect_main():
            record=main_guard.observe()
            require(len(main_samples)<20000,'Original current-v6 observation ceiling exceeded; no truncation')
            main_samples.append(record);return record
        def check_main(require_closed=False):
            while True:
                with main_lock:record=collect_main()
                if not require_closed or not record['phase']['overlap_pending']:return record
                require(time.monotonic()<deadline and not stopped.is_set(),'No late current-v6 health rescue')
                time.sleep(.2)
        initial_ready=check_main(require_closed=True)
        main_initial_readiness=h.put(output/'original-initial-current-v6-main-readiness.json',initial_ready)
        def watch_main():
            while not health_stop.wait(5):
                try:
                    with main_lock:
                        if health_stop.is_set():return
                        collect_main()
                except Exception as error:
                    errors.append('Original current-v6 physical Main watch: '+repr(error));stopped.set();return
        health_worker=threading.Thread(target=watch_main,name='fullgame-current-v6-physical-Main',daemon=True)
        health_worker.start()
"""
    replace(old,new)
    begin="        if main_guard is not None and main_finalizer is not None:\n";end="        owned_threads.append(health_worker)\n"
    old=source[source.index(begin):source.index(end)]
    new="""        if main_guard is not None:
            try:
                if not errors:check_main(require_closed=True)
            except Exception as error:errors.append('Original final current-v6 Main observation: '+repr(error))
        health_stop.set()
        if health_worker is not None:health_worker.join(timeout=20)
        if main_guard is not None:
            try:main_guard_report=main_guard.finish(health_worker)
            except Exception as error:
                errors.append('Original current-v6 Main close: '+repr(error))
                main_guard_failure=h.put(output/'original-current-v6-Main-close-failure.json',dict(error=repr(error)))
"""
    replace(old,new)
    replace("        main_health_protocol=job['main_health_protocol'],source_family_manifest=job['source_family_manifest'],",
        "        main_health_protocol=None,source_family_manifest=job['source_family_manifest'],\n"
        "        current_main=job['current_main'],current_fleet=job['current_fleet'],\n"
        "        current_v6_health_source=job['current_v6_health_source'],\n"
        "        current_v6_health_qualification=job['current_v6_health_qualification'],")
    replace("        complete=complete,errors=errors,original_attempt=1,no_retry=True,original_slots=actual_slots,",
        "        complete=complete,errors=errors,original_job=jp,original_attempt=1,no_retry=True,original_slots=actual_slots,")
    restored=source
    for old,new in reversed(edits):
        require(restored.count(new)==1,'Nonunique current-v6 reverse edit');restored=restored.replace(new,old,1)
    require(restored==original,'Undeclared current-v6 native change')
    compile(source,'<unbound-fullgame-current-v6-native>','exec')
    left=ast.parse(original);right=ast.parse(source);unchanged=[]
    for item in left.body:
        if isinstance(item,(ast.ClassDef,ast.FunctionDef))and item.name not in('run','validate_job'):
            other=next(x for x in right.body if getattr(x,'name',None)==item.name)
            require(ast.dump(item)==ast.dump(other),'Unrelated native kernel changed: '+item.name);unchanged.append(item.name)
    require(args.directory.is_absolute()and not args.directory.exists(),'Fresh absolute preparation directory required')
    args.directory.mkdir(mode=0o700)
    target=args.directory/'run_quality32_current_v6_retirement_UNBOUND_v1.py'
    with target.open('x')as f:f.write(source);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
    result=h.put(args.directory/'source-preparation.json',dict(status='CURRENT_V6_NATIVE_UNBOUND_SOURCE_ONLY',
        parent_packet=h.pin(args.parent_packet),parent_native=parent['native'],native=h.pin(target),generator=h.pin(Path(__file__)),
        current_health_source=health_pin,current_health_engineering_review=review_pin,
        exact_reverse_edits_equal_parent=True,unchanged_AST_kernels=unchanged,declared_edits=len(edits),
        old_historical_physical_Main_health_not_borrowed=True,current_scope='Declared bounded current-v6 physical/TCP plus original owner/API/exposure samples; <=10s unaccepted overlaps and <=15s observation gap.',
        frozen_pair_still_deliberately_UNBOUND=True,
        remaining_before_launch=['Fresh exact policy/CPU/pair/source/resource/controller prebody qualification.',
            'Finite real-MAME engineering integration of startup, per-slot two-game retirement, global64 and current-v6 health, with original-process positive closeout.',
            'Independent raw game/ROM/START/STOP/score/life/current-health and final separate full-game C1/C2 promotion review.'],
        actual_native_MAME_GPU_or_scientific_job_launched=False,live_controls_changed=False,promotion=False))
    print(json.dumps(dict(status='CURRENT_V6_NATIVE_UNBOUND_SOURCE_ONLY',report=result)));return 0


if __name__=='__main__':raise SystemExit(main())
