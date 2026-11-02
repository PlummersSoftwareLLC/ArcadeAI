"""Freeze prospective10/15/30/60-minute private evaluator sources; default inert.

No models, GPU, MAME, units, training controls or live outputs are opened.
Every changed file is a derived copy with an exact reversible parent patch.
"""
import argparse
import ast
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
C=G/'logs/managed-learning-20261015/run-26/post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'
HORIZONS='(600_000_000_000, 900_000_000_000, 1_800_000_000_000, 3_600_000_000_000)'


def replace_once(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new)


def execute(output):
    assert output.is_absolute() and output.parent.resolve(strict=True)==output.parent and not output.exists()
    hp=G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py'
    assert hashlib.sha256(hp.read_bytes()).hexdigest()=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
    spec=importlib.util.spec_from_file_location('_profile_source_helper',hp)
    h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
    prepared=json.loads((C/'prepared.json').read_text())
    job=json.loads(h.checked(prepared['jobs']['R1']['job']).read_text())
    output.mkdir(mode=0o700)
    derived={};deltas=[]

    def save(role,parent,text):
        original=h.checked(parent).read_text();ast.parse(text)
        target=output/(role+'.py')
        with target.open('x')as stream:
            stream.write(text);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
        pin=h.pin(target);derived[role]=pin
        deltas.append(dict(role=role,parent=parent,selected=pin,
            patch=''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True)))))
        return pin

    parent=job['components']['recorder'];text=h.checked(parent).read_text()
    text=replace_once(text,'HORIZON_NS = 3_600_000_000_000',
        'HORIZON_NS = 3_600_000_000_000\nSUPPORTED_HORIZONS_NS = '+HORIZONS+
        '\nCHECKPOINT_OFFSETS_NS = (300_000_000_000, 600_000_000_000, 900_000_000_000, 1_200_000_000_000, 1_800_000_000_000)')
    text=replace_once(text,'def __init__(self, *, clock_ns=time.monotonic_ns):',
        'def __init__(self, *, clock_ns=time.monotonic_ns, horizon_ns=HORIZON_NS, checkpoint_offsets_ns=()):')
    text=replace_once(text,'        self._clock = clock_ns',
        "        require(type(horizon_ns) is int and horizon_ns in SUPPORTED_HORIZONS_NS, 'Explicit supported horizon required')\n"
        "        require(type(checkpoint_offsets_ns) in (list, tuple) and all(type(v) is int for v in checkpoint_offsets_ns)\n"
        "                and tuple(checkpoint_offsets_ns) == tuple(sorted(set(checkpoint_offsets_ns)))\n"
        "                and all(v in CHECKPOINT_OFFSETS_NS and v < horizon_ns for v in checkpoint_offsets_ns),\n"
        "                'Sorted unique predeclared intermediate horizons required')\n"
        '        self.horizon_ns = horizon_ns\n'
        '        self._checkpoint_rows = {offset: {} for offset in checkpoint_offsets_ns}\n'
        '        self._checkpoints_emitted = set()\n'
        '        self._clock = clock_ns')
    text=replace_once(text,'now, now + HORIZON_NS, deepcopy(readiness)',
        'now, now + self.horizon_ns, deepcopy(readiness)')
    text=replace_once(text,'horizon_ns=HORIZON_NS, members=32','horizon_ns=self.horizon_ns, members=32')
    text=replace_once(text,'horizon_ns=HORIZON_NS, anchor_monotonic_ns=',
        'horizon_ns=self.horizon_ns, anchor_monotonic_ns=')
    text=replace_once(text,'                self._anchor_packets[slot] = deepcopy(self._last_packets[slot])\n            return True',
        '                self._anchor_packets[slot] = deepcopy(self._last_packets[slot])\n'
        '            self._capture_checkpoint_crossings(slot, stamp, previous_score, previous_packet)\n            return True')
    text+='\n'+Path(__file__).with_name('checkpoint_methods_v1.txt').read_text()
    recorder=save('recorder',parent,text)

    parent=job['components']['report'];text=h.checked(parent).read_text()
    text=replace_once(text,"ORDER = ('R1', 'C1', 'R2', 'C2')","ORDER = ('R1', 'C1', 'R2', 'C2')\nSUPPORTED_HORIZONS_NS = "+HORIZONS)
    text=replace_once(text,"seal['horizon_ns'] == 3_600_000_000_000",
        "type(seal['horizon_ns']) is int and seal['horizon_ns'] in SUPPORTED_HORIZONS_NS")
    text=text.replace('Explicit selected deadline32/60-minute metric required','Explicit supported selected deadline32 metric required')
    text=replace_once(text,"'FIRST-GAME SCORE AT THE 60-MINUTE DEADLINE'",
        "f\"FIRST-GAME SCORE AT THE {seal['horizon_ns']//60_000_000_000}-MINUTE DEADLINE\"")
    text=replace_once(text,"    scores = {name: validate(seals[name]) for name in ORDER}",
        "    scores = {name: validate(seals[name]) for name in ORDER}\n"
        "    require(len({seals[name]['horizon_ns'] for name in ORDER}) == 1, 'Mixed metric horizons cannot be compared')")
    text=replace_once(text,'metric_schema=SCHEMA, horizon_ns=3_600_000_000_000,',
        "metric_schema=SCHEMA, horizon_ns=seals['R1']['horizon_ns'],")
    report=save('report',parent,text)

    parent=job['components']['score_auditor'];text=h.checked(parent).read_text()
    text=replace_once(text,'HORIZON=3_600_000_000_000','SUPPORTED_HORIZONS_NS='+HORIZONS)
    text=replace_once(text,"    require(seal['schema']=='robotron-first-game-deadline-score32-v2' and seal['horizon_ns']==HORIZON,",
        "    horizon=integer(job['horizon_ns'],'selected horizon')\n"
        "    require(horizon in SUPPORTED_HORIZONS_NS,'Unsupported selected horizon')\n"
        "    require(seal['schema']=='robotron-first-game-deadline-score32-v2' and seal['horizon_ns']==horizon,")
    text=replace_once(text,'d-a==HORIZON and anchor[','d-a==horizon and anchor[')
    text=replace_once(text,'horizon_ns=HORIZON,members=32','horizon_ns=horizon,members=32')
    text=text.replace('Selected new32/60-minute schema required','Selected supported32/horizon schema required')
    text=replace_once(text,"row['activity_age_ns']==d-activity_stamp<=BOUND and",
        "row['activity_age_ns']==d-activity_stamp and (d-activity_stamp<=BOUND or row['status']=='completed') and")
    text=replace_once(text,"        if done:\n            terminal=row['completed_row'];confirmation=terminal['terminal_confirmation']",
        "        if done:\n            validate_completed_retirement(row,job,result,seal)\n            terminal=row['completed_row'];confirmation=terminal['terminal_confirmation']")
    text+='\n'+Path(__file__).with_name('completed_retirement_audit_v1.txt').read_text()
    auditor=save('score_auditor',parent,text)

    parent=prepared['selected_sources']['native'];text=h.checked(parent).read_text()
    text=replace_once(text,"SLOTS=tuple(range(4096,4128))",
        'SUPPORTED_HORIZONS_NS='+HORIZONS+'\n'
        'DURATION_COMPONENTS='+repr({k:derived[k]['sha256']for k in ('recorder','report','score_auditor')})+'\n'
        'SLOTS=tuple(range(4096,4128))')
    text=replace_once(text,"job['horizon_ns']==3_600_000_000_000", "job['horizon_ns'] in SUPPORTED_HORIZONS_NS")
    text=replace_once(text,"    require(set(job['components'])==COMPONENT_KEYS,'Exact actual deadline source chain required')",
        "    require(set(job['components'])==COMPONENT_KEYS,'Exact actual deadline source chain required')\n"
        "    require(all(job['components'][key]['sha256']==sha for key,sha in DURATION_COMPONENTS.items()),\n"
        "        'Selected recorder/report/auditor horizon source chain differs')\n"
        "    require(type(job['checkpoint_offsets_ns']) is list and all(type(v) is int for v in job['checkpoint_offsets_ns']) and job['checkpoint_offsets_ns']==\n"
        "        [v for v in (300_000_000_000,600_000_000_000,900_000_000_000,1_200_000_000_000,1_800_000_000_000) if v<job['horizon_ns']],\n"
        "        'Exact predeclared intermediate horizon schedule required')")
    text=replace_once(text,"    policy=selected['reference'if job['leg']=='R1'else'candidate']",
        "    require(type(selected['screen_horizon_ns']) is int and selected['screen_horizon_ns']==job['horizon_ns']\n"
        "        and type(selected['checkpoint_offsets_ns']) is list and all(type(v) is int for v in selected['checkpoint_offsets_ns']) and selected['checkpoint_offsets_ns']==job['checkpoint_offsets_ns']\n"
        "        and selected['short_screen_is_promotion_evidence'] is False,\n"
        "        'Both arms must select the same horizon/checkpoints and screening-only scope')\n"
        "    policy=selected['reference'if job['leg']=='R1'else'candidate']")
    text=replace_once(text,'recorder=modules[\'recorder\'].DeadlineScoreRecorder()',
        "recorder=modules['recorder'].DeadlineScoreRecorder(horizon_ns=job['horizon_ns'],checkpoint_offsets_ns=job['checkpoint_offsets_ns'])")
    text=replace_once(text,'all_threads_stopped=False;child_reap=None;source_unchanged=False;private_score_stall_override_applied=False',
        'all_threads_stopped=False;child_reap=None;source_unchanged=False;private_score_stall_override_applied=False;checkpoint_pins={}')
    text=replace_once(text,"    output.mkdir(mode=0o700);(output/'actors').mkdir(mode=0o700);(output/'status-samples').mkdir(mode=0o700)",
        "    output.mkdir(mode=0o700);(output/'actors').mkdir(mode=0o700);(output/'status-samples').mkdir(mode=0o700);(output/'score-checkpoints').mkdir(mode=0o700)")
    text=replace_once(text,"            if time.monotonic()-last_status>=5:",
        "            if anchor is not None:\n"
        "                for checkpoint in recorder.take_checkpoints(time.monotonic_ns()):\n"
        "                    checkpoint_pins[str(checkpoint['horizon_offset_ns'])]=h.put(output/'score-checkpoints'/(str(checkpoint['horizon_offset_ns']//1_000_000_000)+'.json'),checkpoint)\n"
        "            if time.monotonic()-last_status>=5:")
    text=replace_once(text,'complete=bool(not errors and seal_pin is not None',
        "complete=bool(set(checkpoint_pins)=={str(value)for value in job['checkpoint_offsets_ns']} and not errors and seal_pin is not None")
    text=replace_once(text,'main_runtime_changed=False,promotion_gates_changed=False,screen_only=True,promotion=False,',
        "predeclared_horizon_checkpoints=checkpoint_pins,selected_horizon_ns=job['horizon_ns'],checkpoint_offsets_ns=job['checkpoint_offsets_ns'],\n"
        '        main_runtime_changed=False,promotion_gates_changed=False,screen_only=True,promotion=False,')
    text=text.replace('Exact selected32/60-minute/native bounds required','Exact selected32/horizon/native bounds required')
    native=save('native',parent,text)

    parent=prepared['selected_sources']['controller'];text=h.checked(parent).read_text()
    text=replace_once(text,'robotron-post-reboot-LR625-S2-fixedcutoff-score-','robotron-duration-profile-S2-screen-')
    text=replace_once(text,prepared['selected_sources']['native']['path'],native['path'])
    controller=save('controller',parent,text)

    parent=prepared['selected_sources']['outer'];text=h.checked(parent).read_text()
    text=replace_once(text,"seal['horizon_ns'] == 3_600_000_000_000", "seal['horizon_ns'] == job['horizon_ns']")
    text=replace_once(text,"    reference=selection['reference'];candidate=selection['candidate']",
        "    reference=selection['reference'];candidate=selection['candidate']\n"
        "    horizon=selection['screen_horizon_ns']\n"
        "    if type(horizon) is not int or horizon not in "+HORIZONS+":\n"
        "        raise ValueError('Explicit supported display horizon required')\n"
        "    minutes=horizon//60_000_000_000")
    text=replace_once(text,"' using the same one-hour cutoff. Protected incumbent b231 remains unchanged; no automatic promotion.'",
        "f' using the same {minutes}-minute cutoff. Protected incumbent b231 remains unchanged; no automatic promotion.'")
    text=replace_once(text,"policy_scope='Selected frozen candidate versus selected frozen reference; exploratory one-hour screen only, no automatic promotion'",
        "policy_scope=f'Selected frozen candidate versus selected frozen reference; exploratory {minutes}-minute screen only, no automatic promotion',screen_minutes=minutes")
    text=text.replace("'No confirmed start time yet; each admitted arm runs for one hour.'",
        "f\"No confirmed start time yet; each admitted arm runs for {display['screen_minutes']} minutes.\"")
    text=text.replace('fixed one-hour cutoff','fixed selected cutoff')
    text=text.replace('one-hour clock','selected horizon clock')
    outer=save('outer',parent,text)
    manifest=h.put(output/'source-only-duration-profile.json',dict(
        status='SOURCE_ONLY_NOT_CPU_TESTED_OR_SELECTED_OR_LAUNCHED',sources=derived,
        unchanged_Lua=prepared['selected_sources']['lua'],parent_prepared=h.pin(C/'prepared.json'),
        components={k:derived.get(k,v)for k,v in job['components'].items()},
        supported_horizons_s=[600,900,1800,3600],one_hour_resource_caps_preserved=True,
        exact_intermediate_observations_are_not_independent_samples=True,
        automated_early_rejection_rule=None,statistical_error_control_qualified=False,
        current_runtime_or_controls_changed=False,promotion=False))
    h.put(output/'exact-parent-derivations.json',dict(source_builder=h.pin(Path(__file__)),
        checkpoint_method_source=h.pin(Path(__file__).with_name('checkpoint_methods_v1.txt')),deltas=deltas))
    print(json.dumps(dict(manifest=manifest,sources=list(derived))))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    parser.add_argument('--output',type=Path);args=parser.parse_args()
    if args.execute:
        assert args.output
        execute(args.output)
    else:parser.print_help()
