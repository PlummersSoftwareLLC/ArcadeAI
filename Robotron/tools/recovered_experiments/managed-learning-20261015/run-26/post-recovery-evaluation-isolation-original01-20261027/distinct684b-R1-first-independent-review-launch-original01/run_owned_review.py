"""Own the first precommitted R1 independent review controller through reap."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path('/home/dave/source/repos/ArcadeAI/Robotron')
OUT=Path(__file__).resolve().parent
LEG=OUT.parent/'distinct684b-buffered-family8-study-original01/R1'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


h=load('_first_review_owned_helpers',ROOT/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
assert h.pin(Path(h.__file__))['sha256']=='2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1'
helperpath=ROOT/'tools/startup_policy_journal_proposal/sequence_quality32_2259_prospective197_v1.py'
assert h.pin(helperpath)['sha256']=='b462dbb6562e08ef6efca66bc10f6b0c94273daceb12ac9f86f4a68eb972d6e4'
helper=load('_first_review_owned_controller',helperpath)
preparedpin=h.pin(LEG/'independent-review-prepared-original01.json')
prepared=json.loads(h.checked(preparedpin).read_bytes())
assert prepared['leg']=='R1' and prepared['no_retry']is True
assert not (LEG/'independent-review-controller-original-launch.json').exists()
h.put(OUT/'original-wrapper-intent.json',dict(prepared=preparedpin,source=h.pin(Path(__file__).resolve()),
    wrapper_pid=os.getpid(),wrapper_birth=helper.birth(os.getpid()),created_unix_s=time.time(),first_original_review=True,no_retry=True))


def on_live(owner,controller):
    pin=h.put(OUT/'actual-original-review-owner.json',dict(owner=owner,controller=controller,prepared=preparedpin,
        wrapper_pid=os.getpid(),wrapper_birth=helper.birth(os.getpid()),observed_unix_s=time.time()))
    print(json.dumps(dict(event='FIRST_ORIGINAL_R1_REVIEW_LIVE',owner=pin)),flush=True)


pin=helper.invoke_controller_once(LEG,'independent-review-',prepared['controller'],prepared['review_config'],h,on_live)
result=json.loads(h.checked(pin).read_bytes())
print(json.dumps(dict(first_original_review_result=pin,actual_controller_exit=result['actual_exit'])),flush=True)
sys.exit(result['actual_exit'])
