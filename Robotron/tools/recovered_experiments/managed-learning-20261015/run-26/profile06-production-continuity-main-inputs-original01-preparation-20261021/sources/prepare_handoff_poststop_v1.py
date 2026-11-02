"""Prepare source/phase inputs only; never select or execute a live handoff."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace


GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
RUN = GAME/'logs/managed-learning-20261015/run-26'
PREPARED = RUN/'profile06-production-continuity-main-inputs-original01-preparation-20261021/prepared-inputs.json'
PREPARED_SHA = 'ac0f2ff0bd79e0fc6c780585fd8899f8ba1cfeb0c16fd001b7ad024af55e2a5a'


def load(path,name):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(output, *, case='scorecarry-profile06-main-original01-20261021'):
    here = Path(__file__).parent
    import re
    if re.fullmatch(r'scorecarry-profile06-main-original[0-9]{2}-20261021',case) is None:
        raise ValueError('One explicit bounded original handoff case required')
    l = load(here/'handoff_linux_v1.py','_prepare_handoff_linux')
    prepared_pin = l.full_pin(PREPARED)
    l.require(prepared_pin['sha256'] == PREPARED_SHA,'The original handoff proposal changed')
    prepared = json.loads(l.checked(prepared_pin))
    for name in ('original_main','original_fleet','original_listener','installed_before','proposed_socket'):
        l.checked(prepared[name])
    main = json.loads(l.checked(prepared['original_main']))
    guard_pin = l.full_pin(RUN/'capacity-original-full-reviewer-CPU-original01-preparation-20261019/immutable-main-hold-guard.py')
    guard = l.module(guard_pin,'_prepare_handoff_guard')
    guard.owner_and_files(main)
    l.require(output.is_absolute() and output.parent == PREPARED.parent and not output.exists(),
              'One new preparation directory under the original proposal is required')
    output.mkdir(mode=0o700)
    (output/'numerical-source-archives').mkdir()
    p = load(here/'handoff_poststop_v1.py','_prepare_handoff_poststop')
    original_job = json.loads((RUN/'boundary-continuity-forward-recovery-original01-root-preparation-20261018/job.json').read_bytes())
    template = json.loads((RUN/'boundary-continuity-forward-recovery-original01-20261018/newest_stopped/CPU-job.json').read_bytes())
    for name in template['phase_snapshot']['sources']:
        current = l.full_pin(GAME/'Scripts/dqn'/name)
        archive = p.archive(l,current['path'],output/'numerical-source-archives'/name)
        template['phase_snapshot']['sources'][name] = dict(current=current,archive=archive)
        if name in template['source_control_context']['model_package']:
            template['source_control_context']['model_package'][name] = current
    phase_path = Path(prepared['current_boot_phase_record']['path'])
    phase_pin = l.full_pin(phase_path)
    l.require(phase_pin == prepared['current_boot_phase_record'],
              'Current original boot phase record changed')
    phase = json.loads(l.checked(phase_pin))
    boot_pin = l.full_pin(Path(prepared['current_boot_CPU']['path']))
    l.require(boot_pin == prepared['current_boot_CPU'],'Exact current owner boot CPU proof changed')
    boot = json.loads(l.checked(boot_pin))
    template['phase_snapshot'].update(owner=main['owner'],phase_record=phase_pin,
        boot_checkpoint=phase['checkpoint'],boot_verification=boot_pin,expected_phase=p.expected_phase(boot,phase_pin))
    control = p.archive(l,l.CONTROL,output/'original-learning-control.json')
    settings = p.archive(l,l.MODEL/'game_settings.json',output/'original-game-settings.json')
    unit = subprocess.run(['systemctl','--user','cat',main['owner']['unit']],capture_output=True,timeout=15)
    l.require(unit.returncode == 0,'Original trainer unit archive failed')
    unit_pin = l.publish(output/'original-trainer-unit.txt',unit.stdout)
    template['experiment'] = main['experiment']
    template['source_control_context'].update(archived_control=control,archived_trainer_unit=unit_pin,
                                            provenance=[prepared_pin,boot_pin,phase_pin])
    template_pin = l.publish(output/'current-original-phase-CPU-template.json',template)
    config = dict(schema='robotron-score-carry-poststop-inputs-v1',case=case,
        created_unix_s=time.time(),original_owner=main['owner'],cpu_template=template_pin,
        boot_CPU_report=boot_pin,boot_checkpoint=phase['checkpoint'],original_phase_record=phase_pin,
        boot_replay_snapshot=prepared['current_boot_replay_snapshot'],
        settings_archive=settings,python='/home/dave/source/repos/ArcadeAI/.venv-gb300/bin/python',
        phase_dropin=l.full_pin(Path('/run/user/1001/systemd/user')/(main['owner']['unit']+'.d/91-per-priority-phase.conf')),
        verifier=l.full_pin(GAME/'tools/live_lr_recipe_continuation_proposal/verify_recipe_phase_snapshot.py'),
        cpu_controller=l.full_pin(GAME/'tools/quality_capacity_proposal/control_quality32_review_v1.py'),
        bank_helper=l.full_pin(original_job['bank_helper']['path']),bank_spec=original_job['bank_spec'],
        archive_checker=l.full_pin(GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py'),pins=[])
    config['pins'] = [config[k] for k in ('cpu_template','boot_CPU_report','original_phase_record','settings_archive',
        'phase_dropin','verifier','cpu_controller','bank_helper','archive_checker','boot_replay_snapshot')]
    config_pin = l.publish(output/'poststop-inputs.json',config)
    backend = SimpleNamespace(job=dict(backend_source=l.full_pin(here/'handoff_linux_v1.py'),
        poststop_inputs=config_pin,prepared=prepared_pin,case=config['case']),owner=main['owner'])
    adapter = p.prepare(backend)
    guard.owner_and_files(main)
    return l.publish(output/'preparation-result.json',dict(status='POSTSTOP_ADAPTER_CONSTRUCTED_INPUTS_VERIFIED',
        poststop_inputs=config_pin,base_control_archive=control,base_control_sha256=control['sha256'],
        prepared=prepared_pin,source_pins={path.name:l.full_pin(path) for path in here.glob('handoff_*_v1.py')},
        current_original_owner=main['owner'],expected_original_phase=adapter.expected,
        full195_holds_and_original192_verified=True,production_changed=False,
        live_job_selected=False,actual_newest_stopped_CPU_run=False,actual_replacement_started=False,
        deployment_ready=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--output',type=Path)
    parser.add_argument('--case',default='scorecarry-profile06-main-original01-20261021')
    args = parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY: no reads, outputs, queries or runtime actions')
        return 0
    if args.output is None:
        raise ValueError('One new explicit preparation directory required')
    print(json.dumps(prepare(args.output,case=args.case)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
