"""Collect actual current4096 inputs only. No arming, stop, source edit or start."""
from pathlib import Path
import base64
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

ROOT = Path('/home/dave/source/repos/ArcadeAI')
GAME = ROOT/'Robotron'
RUN = GAME/'logs/managed-learning-20261015/run-26'
OUT = RUN/'CE2048-trial01-final-root-preparation-20261017'
SOURCE = GAME/'tools/kl_priority_mixture_proposal/raw_kl_sequential_trial_proposal/batch2048_one_trial_execution_release_proposal/run_CE_batch_transition.py'
manifest = json.loads((SOURCE.parent/'preparation-manifest.json').read_text())
entry = next(item for item in manifest['files'] if item['path'] == str(SOURCE))
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == entry['sha256']
spec = importlib.util.spec_from_file_location('root_CE2048_current_adapter',SOURCE)
adapter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = adapter
spec.loader.exec_module(adapter)
base = adapter.load_v4()
old = json.loads((RUN/'rawKL-trial02-final-root-preparation-20261017/activation-job-FINAL.json').read_text())
sys.path.insert(0,str(GAME/'tools'))
primitives = base.load_module(old['helper_pins']['live_host']['path'],'root_CE2048_current_host')

class Host(primitives.LiveHost):
    def runtime_dropin(self):
        return Path(old['original_dropin']['path'])

host = Host(old['trainer_unit'],old['fleet_unit'])
before = host.describe()
assert before['trainer']['MainPID'] == '620749'
proc = Path('/proc/620749/stat').read_text()
assert int(proc[proc.rfind(')')+2:].split()[19]) == 33475842
show = subprocess.run(['systemctl','--user','show',old['trainer_unit'],'--all'],capture_output=True,text=True,timeout=15)
fields = dict(line.split('=',1) for line in show.stdout.splitlines() if '=' in line)
assert show.returncode == 0 and fields['MainPID'] == '620749' and fields['InvocationID'] == '3e0b59be7ec5484d9cc8d33265e74d77'
host.adopt_initial(before)
host.metric_host.configure_logs(before['bindings']['logs'])
row = host.capture()
plan = dict(batch_size=4096,replay_cap=8,initial_snapshot=dict(csv=row['csv']),
    exposure_identity={name:primitives.metrics.exposure_key(row['exposure'][name]) for name in ('optimizer','replay')})
issues = primitives.metrics.api_issues(row,plan)
assert not issues, issues
assert row['client_count'] == len(before['bindings']['actors']) == 192
actors = {str(actor['pid']):sorted(os.sched_getaffinity(actor['pid'])) for actor in before['bindings']['actors']}
worker = host.metric_host.mask(before['bindings']['worker'])
assert all(value == list(range(72)) for value in actors.values()) and worker == list(range(72))
dropin = Path(old['original_dropin']['path'])
dropin_bytes = dropin.read_bytes()
assert b'3475a048151c08bbc4fdc58a9b4336c7df67cb7e6668779523239d3a35274308' in dropin_bytes
OUT.mkdir()

def save(path,value,*,allow_nan=False):
    with path.open('x') as stream:
        json.dump(value,stream,indent=2,allow_nan=allow_nan)
        stream.write('\n');stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    return base.fingerprint(path,8<<20)

before_pin = save(OUT/'actual-before-current620749-main192.json',before)
save(OUT/'actual-baseline-API-and-CSV.json',row,allow_nan=True)
save(OUT/'actual-current-trainer-unit-show.json',dict(argv=show.args,returncode=show.returncode,stdout=show.stdout,stderr=show.stderr))
save(OUT/'actual-original192-and-worker-masks.json',dict(actors=actors,worker=worker))
save(OUT/'actual-original-phase-dropin.json',dict(path=str(dropin),content_base64=base64.b64encode(dropin_bytes).decode(),mode=dropin.stat().st_mode&0o777))
settings = Path(old['settings_lifecycle']['initial']['path'])
save(OUT/'actual-settings-lifecycle.json',dict(initial=base.fingerprint(settings,base.MAX_JSON),parsed_values=json.loads(settings.read_text()),policy='same_bytes_after_owned_stop_only'))
save(OUT/'actual-current-completed-request.json',base.fingerprint(GAME/'models_dqn/managed_save.request.json.completed',base.MAX_JSON))
banks = base.load_module(old['helper_pins']['bank_state']['path'],'root_CE2048_current_banks')
bank_spec = old['bank_spec']
save(OUT/'actual-live-storage-asof-descriptors.json',dict(scope='Live as-of descriptor inventory only; no stopped/memory-equality claim',
    ring_directory=banks.directory_identity(bank_spec['ring']),
    banks={name:banks.bank_state(name,Path(bank_spec['model_dir'])/('robotron_dqn_latest_replay_'+name),bank_spec['bank_strides'][name],bank_spec['state_size'],bank_spec['episode_capacity']) for name in ('hof','ephof')},
    stopped_no_writer_descriptors=None,actual_startup_mmaps=None))
save(OUT/'root-actual-readonly-preparation.json',dict(status='ACTUAL_CURRENT4096_MAIN192_CAPTURED_NOT_ARMED_OR_EXECUTED',before=before_pin,
    source_manifest=base.fingerprint(SOURCE.parent/'preparation-manifest.json',base.MAX_JSON),source=entry,
    initial_root_import_failure='First inline precheck omitted tools sys.path; helper import failed before runtime capture/output. Corrected here; no numerical or trial process was started.',
    actual_future_owner=None,actual_future_checkpoint=None,only_readonly_runtime_inspection_and_new_log_files=True,live_batch2048_activated=False))
print(json.dumps(dict(status='PASS_ACTUAL_READONLY_PREPARATION',directory=str(OUT),before=before_pin,baseline_csv=row['csv'])))
