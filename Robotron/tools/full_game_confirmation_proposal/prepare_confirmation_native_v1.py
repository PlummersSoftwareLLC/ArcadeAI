"""Bind the qualified full-game native and owned controller to the fixed pair.

No launch occurs. Runtime selection, fresh four-role jobs and independent
reviewer/campaign preparation must still be completed and CPU checked.
"""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
B=G/'logs/managed-learning-20261015/run-26'
C=B/'post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
F=B/'quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m


def write(path,text):
    with path.open('x')as f:f.write(text);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');args=p.parse_args()
    if not args.execute:p.print_help();return 0
    h=load('_confirmation_native_prepare_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    pair_pin=h.pin(F/'fixed-pair-precommit.json');pair=json.loads(h.checked(pair_pin).read_text())
    prep_path=C/'fullgame-evaluator-live-engineering-original01-20261101/slot-permit-archival-source-original02/native-scientific-archival-UNBOUND-original01/source-preparation-and-CPU-unbound-proof.json'
    prep=json.loads(prep_path.read_text());parent=h.checked(prep['native']);original=parent.read_text();source=original;edits=[]
    def replace(old,new):
        nonlocal source
        assert source.count(old)==1;source=source.replace(old,new,1);edits.append((old,new))
    start=source.index("PAIR_SHA='");end=source.index('\n',start)
    replace(source[start:end],'PAIR_SHA='+repr(pair_pin['sha256']))
    start=source.index('POLICIES=');end=source.index('\n',start)
    policies={role:dict(sha256=entry['policy']['sha256'],clocks=entry['saved_clocks'])for role,entry in pair['roles'].items()}
    replace(source[start:end],'POLICIES='+repr(policies))
    marker='def run(job,jp,h):\n';assert source.count(marker)==1
    validate="""def validate_selected_family(job,h):
    family=json.loads(h.checked(job['source_family_manifest']).read_text())
    require(family['schema']=='robotron-current-v6-fullgame-confirmation-source-family-v1'
        and family['pair']==job['quality_pair_precommit']
        and family['native']==job['runtime']
        and family['source_package']==job['source_package']
        and family['current_Main_health']==job['current_v6_health_source']
        and family['slot_closeout']==job['quota64_source_pins']['slot_closeout']
        and family['finite_engineering']==job['quota64_validation']['finite_current_v6_retirement_engineering']
        and family['archival_CPU']==job['quota64_validation']['full_slot_permit_archival_CPU'],
        'Actual selected scientific source family differs from this original job')
    for key in ('native','native_controller','leg_reviewer','campaign_assessor','wire_auditor','games_auditor',
                'current_Main_health','slot_closeout','source_package','finite_engineering','archival_CPU'):
        h.checked(family[key])
    return family


"""
    replace(marker,validate+marker)
    replace('    output=validate_job(job)\n','    output=validate_job(job)\n    validate_selected_family(job,h)\n')
    reverted=source
    for old,new in reversed(edits):assert reverted.count(new)==1;reverted=reverted.replace(new,old,1)
    assert reverted==original
    compile(source,'<fixed-fullgame-native>','exec')
    left=ast.parse(original);right=ast.parse(source);stable=[]
    for item in left.body:
        if isinstance(item,(ast.FunctionDef,ast.ClassDef))and item.name not in('run',):
            other=next(n for n in right.body if getattr(n,'name',None)==item.name)
            assert ast.dump(item)==ast.dump(other);stable.append(item.name)
    target=F/'selected-source/run_fixed_b231_vs_1c_fullgame_v1.py';write(target,source)
    CPU=B/'future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/handoff-preservation-original01/state-sources/control_stopped_fullstate600_CPU_v1.py'
    old=CPU.read_text();controller=old
    changes=[("props.get('CPUQuota')=='200%'","props.get('CPUQuota')=='1200%'"),
        ("props.get('MemoryMax')=='4G'","props.get('MemoryMax')=='24G'"),
        ("props.get('TasksMax','128')=='128'","props.get('TasksMax','512')=='512'"),
        ("props.get('RuntimeMaxSec')=='600'","props.get('RuntimeMaxSec')=='22260'"),
        ("c['observation_s']==660","c['observation_s']==22320")]
    for a,b in changes:assert controller.count(a)==1;controller=controller.replace(a,b,1)
    back=controller
    for a,b in reversed(changes):assert back.count(b)==1;back=back.replace(b,a,1)
    assert back==old
    ctl_target=F/'selected-source/control_fixed_fullgame22260_v1.py';write(ctl_target,controller)
    result=h.put(F/'selected-source/native-controller-preparation.json',dict(status='FIXED_NATIVE_AND_CONTROLLER_BOUND_NOT_JOB_QUALIFIED_OR_LAUNCHED',
        pair=pair_pin,parent_native=prep['native'],parent_native_preparation=h.pin(prep_path),native=h.pin(target),
        native_controller=h.pin(ctl_target),parent_controller=h.pin(CPU),generator=h.pin(Path(__file__)),
        native_exact_declared_reverse_edits=True,unchanged_AST_kernels=stable,
        controller_exact_five_resource_limit_changes=True,work_wall_s=22200,cohort_timeout_s=21600,resource_runtime_s=22260,
        all_selected_games_per_leg=64,games_per_each32_slot=2,scientific_job_launched=False,promotion=False))
    print(json.dumps(dict(status='FIXED_NATIVE_AND_CONTROLLER_BOUND_NOT_JOB_QUALIFIED_OR_LAUNCHED',packet=result)));return 0


if __name__=='__main__':raise SystemExit(main())
