"""Passive five-minute birth/stream/raw-health observation; no payload controls."""
import importlib.util
import json
import os
from pathlib import Path
import time

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
OUT=Path(__file__).resolve().parent
ISOLATION=OUT.parent
STUDY=ISOLATION/'distinct684b-buffered-family8-study-original01'
NATIVE=STUDY/'R1/deadline-output-original01'
OWNERS={3723189:10638068,3723190:10638074,3723416:10638423,3723887:10647119,
        3756376:10798772,3757415:10803740,3723722:10644206}


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module);return module


def birth(pid):
    try:return int(Path('/proc',str(pid),'stat').read_text().rsplit(')',1)[1].split()[19])
    except FileNotFoundError:return None


def read(path):return json.loads(path.read_bytes())


def main():
    h=load('_passive_original_wait_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    reader=load('_passive_original_wait_immutable',ROOT/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py')
    source=h.pin(Path(__file__).resolve())
    owner=h.put(OUT/'original-watcher-owner.json',dict(pid=os.getpid(),birth=birth(os.getpid()),source=source,
        observed_live=True,no_process_controls=True,scientific_qualification=False))
    observer_job=read(NATIVE/'main-health-scope/job.json')
    control=Path(observer_job['live_control_path'])/'live.json'
    observations=[];warnings=[];started=time.monotonic();first_snapshot=last_snapshot=None
    for index in range(31):
        due=started+index*10
        if time.monotonic()<due:time.sleep(due-time.monotonic())
        now=time.monotonic()
        if (STUDY/'R1/controller-original-result.json').exists():
            warnings.append(dict(kind='ORIGINAL_TERMINAL_REQUIRES_REVIEW',monotonic_s=now));break
        try:
            assert all(birth(pid)==expected for pid,expected in OWNERS.items()),'Original owner birth changed'
            status=read(NATIVE/'status.json');live=read(control)
            assert status['phase']=='active_deadline'and status['errors']==[]
            slots=status['slots'];assert len(slots)==32 and all(birth(row['pid'])==row['birth']and row['prefix_verified']is True for row in slots.values())
            assert live['state']=='running'and 0<=time.monotonic()-live['updated_monotonic_s']<=.5
            entry=live['latest_sample'];pin=h.pin(Path(entry['path']))
            assert pin['sha256']==entry['sha256']and pin['bytes']==entry['bytes']
            raw=reader.read_pin(pin);assert raw['index']==entry['index']
            if first_snapshot is None:first_snapshot=pin
            last_snapshot=pin
            row=dict(index=index,observed_monotonic_s=now,observed_unix_s=time.time(),
                accepted_health_samples=live['observed_samples'],health_age_s=time.monotonic()-live['updated_monotonic_s'],
                minimum_wire_sequence=min(value['sequence']for value in slots.values()),
                wire_sequences={key:value['sequence']for key,value in slots.items()},
                raw_main_snapshot=pin,all32_original_births_and_prefixes_verified=True,
                original_controller_native_observer_wrapper_sequence_and_projectors_alive=True)
            if observations:
                before=observations[-1]
                assert row['accepted_health_samples']>before['accepted_health_samples']
                assert all(row['wire_sequences'][key]>value for key,value in before['wire_sequences'].items())
            observations.append(row)
            print(json.dumps(dict(event='ORIGINAL_VERIFIED_WAIT',index=index,health=row['accepted_health_samples'],minimum_wire=row['minimum_wire_sequence'])),flush=True)
        except (AssertionError,ValueError,OSError,KeyError)as error:
            # An outer observation failure never restarts or invalidates payload.
            warnings.append(dict(index=index,error=repr(error),monotonic_s=now))
            print(json.dumps(dict(event='PASSIVE_OBSERVATION_REQUIRES_REPOLL',index=index,error=repr(error))),flush=True)
    h.checked(source)
    result=h.put(OUT/'original-five-minute-observation.json',dict(schema='robotron-passive-original-five-minute-observation-v1',
        status='VERIFIED_WAIT'if len(observations)==31 and not warnings else'OBSERVATION_REQUIRES_REVIEW',
        original_watcher=owner,source=source,started_monotonic_s=started,ended_monotonic_s=time.monotonic(),
        observations=observations,warnings=warnings,first_main_snapshot=first_snapshot,last_main_snapshot=last_snapshot,
        payload_controls_used=False,source_or_recipe_changed=False,quality_qualified=False,promotion=False))
    print(json.dumps(dict(result=result,observations=len(observations),warnings=warnings)),flush=True)
    return 0 if len(observations)==31 and not warnings else 1


if __name__=='__main__':raise SystemExit(main())
