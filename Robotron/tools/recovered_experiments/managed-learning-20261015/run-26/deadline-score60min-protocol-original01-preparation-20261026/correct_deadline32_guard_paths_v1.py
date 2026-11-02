"""New unlaunched envelopes correcting only the prospective CPU guard filename."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
Q=Path(__file__).resolve().parent
G=Path('/home/dave/source/repos/ArcadeAI/Robotron')

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m

def prepare():
    h=load('_deadline_guard_correction_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    parent=h.pin(Q/'fixed-RCRC-deadline32-study-original01/prepared-four-legs-NOT-LAUNCH-QUALIFIED.json')
    assert parent['sha256']=='6018ccab9371d71187e71aa506e4eb273f8ef9817c0c8c38075fe3928ff2eb52'
    packet=json.loads(h.checked(parent).read_bytes());out=Q/'guard-path-correction-original01';assert not out.exists();out.mkdir(mode=0o700)
    cases=[]
    for old in packet['cases']:
        original=json.loads(h.checked(old['native_job']).read_bytes());job=copy.deepcopy(original)
        assert not Path(job['output']).exists()and not Path(old['unqualified_controller_config']['path']).parent.joinpath('execution-original01').exists()
        job['prelaunch_family_guard_closeout']=str(Path(job['output']).parent/'source-family-guards-CPU-original01/independent-deadline32-family-guards-and-CPU-closeout.json')
        assert {k for k in job if job[k]!=original[k]}=={'prelaunch_family_guard_closeout'}
        private=out/old['leg'];private.mkdir(mode=0o700);jp=h.put(private/'job.json',job)
        control=load('_deadline_guard_correction_control_'+old['leg'],h.checked(old['native_controller']))
        config=json.loads(h.checked(old['unqualified_controller_config']).read_bytes())
        config['argv'][7]=jp['path'];config['argv'][9]=jp['sha256']
        config['pins']=[p for p in config['pins']if p['path']!=old['native_job']['path']]+[control.pin(jp['path'])]
        cp=h.put(private/'controller-config-NOT-QUALIFIED.json',config)
        assert control.checked_config(cp['path'])==config
        native=load('_deadline_guard_correction_actual_native_'+old['leg'],h.checked(old['runtime']))
        native.validate_completed_context(job,h)
        case=copy.deepcopy(old);case.update(native_job=jp,unqualified_controller_config=cp,
            prelaunch_CPU_closeout=job['prelaunch_family_guard_closeout'],original_unlaunched_native_job=old['native_job'],
            original_unlaunched_config=old['unqualified_controller_config'],only_job_field_changed='prelaunch_family_guard_closeout')
        cases.append(case)
    value=copy.deepcopy(packet);value.update(cases=cases,source_preparer=h.pin(__file__),
        preserved_original_preparation=parent,guard_filename_corrected_to_actual_frozen_run_predicate=True,
        original_IDs_outputs_and_unit_names_preserved_unused=True,scientific_payload_retried=False)
    pin=h.put(out/'prepared-four-legs-NOT-LAUNCH-QUALIFIED.json',value);print(json.dumps(pin),flush=True)

if __name__=='__main__':prepare()
