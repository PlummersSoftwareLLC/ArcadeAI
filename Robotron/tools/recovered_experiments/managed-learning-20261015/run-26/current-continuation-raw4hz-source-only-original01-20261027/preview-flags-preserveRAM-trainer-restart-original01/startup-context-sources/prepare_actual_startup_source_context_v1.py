"""Default inert. Archive bounded actual startup source/control/unit metadata only."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
CASE = GAME/'logs/managed-learning-20261015/run-26/current-continuation-raw4hz-source-only-original01-20261027/preview-flags-preserveRAM-trainer-restart-original01'
LIVE = CASE/'live-original01'
OUTPUT = LIVE/'startup-source-context-original01'
UNIT = 'robotron-managed-run-26-previewflags-preserveRAM-original01-20261027-trainer.service'
VERIFIER_SHA = '08c165ed917b8633ab658a8efbc915f81e37adff21c1330cd5806cd3148f4051'
SOURCES = ('__init__.py','model.py','config.py','learning_control.py','agent.py','training.py','loss_kernel.py','priority_phase.py')
MODEL_SOURCES = {'__init__.py','model.py','config.py','learning_control.py'}


def require(value, message):
    if not value: raise ValueError(message)


def identity(s):
    return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns,mode=oct(stat.S_IMODE(s.st_mode)),uid=s.st_uid,nlink=s.st_nlink)


def read_bytes(pin):
    require(type(pin) is dict and set(pin) == {'path','sha256','bytes','identity'}, 'Full pin required')
    path = Path(pin['path']); before = path.lstat()
    require(path.is_absolute() and path.resolve(strict=True) == path and stat.S_ISREG(before.st_mode)
            and before.st_nlink == 1 and 0 < before.st_size <= 2_000_000
            and identity(before) == pin['identity'] and pin['bytes'] == before.st_size,
            'Only exact bounded regular source/metadata may be opened')
    with path.open('rb') as stream:
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Source changed before open')
        raw = stream.read(2_000_001)
        require(identity(os.fstat(stream.fileno())) == identity(before), 'Source changed during read')
    require(identity(path.lstat()) == identity(before) and len(raw) == pin['bytes']
            and hashlib.sha256(raw).hexdigest() == pin['sha256'], 'Source bytes changed')
    return raw


def fingerprint(path):
    path = Path(path); s = path.lstat()
    require(path.resolve(strict=True) == path and stat.S_ISREG(s.st_mode)
            and s.st_nlink == 1 and 0 < s.st_size <= 2_000_000, 'Bounded canonical metadata/source required')
    result = dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=s.st_size,identity=identity(s))
    read_bytes(result); return result


def read(pin):
    require(pin['identity']['mode'] == '0o444' and pin['identity']['uid'] == os.getuid(), 'Owned immutable JSON required')
    raw = read_bytes(pin); value = json.loads(raw); require(read_bytes(pin) == raw, 'JSON changed'); return value


def publish(path, value):
    raw = value if isinstance(value,bytes) else (json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(),0o444); os.fsync(stream.fileno())
    return fingerprint(path)


def archive(pin, destination):
    raw = read_bytes(pin); archived = publish(destination,raw)
    require(read_bytes(pin) == raw and archived['sha256'] == pin['sha256']
            and (archived['identity']['device'],archived['identity']['inode']) !=
                (pin['identity']['device'],pin['identity']['inode']), 'Independent archive changed or aliases source')
    return archived


def observe_owner(owner, phase):
    require(type(owner) is dict and set(owner) == {'pid','starttime_ticks','unit','invocation_id','cgroup'}
            and type(owner['pid']) is int and owner['pid'] > 0
            and type(owner['starttime_ticks']) is int and owner['starttime_ticks'] > 0
            and owner['unit'] == UNIT and re.fullmatch('[0-9a-f]{32}',owner['invocation_id'])
            and owner['cgroup'] == '/user.slice/user-'+str(os.getuid())+'.slice/user@'+str(os.getuid())+'.service/app.slice/'+UNIT,
            'Actual next named owner required; future facts cannot be unfilled')
    query = subprocess.run(['systemctl','--user','show',UNIT],capture_output=True,text=True,timeout=10)
    require(query.returncode == 0 and query.stderr == '', 'Actual named-unit observation failed')
    fields = dict(line.split('=',1) for line in query.stdout.splitlines() if '=' in line)
    require(fields.get('MainPID') == str(owner['pid']) and fields.get('InvocationID') == owner['invocation_id']
            and fields.get('ControlGroup') == owner['cgroup'] and fields.get('NRestarts') == '0'
            and fields.get('ActiveState') == 'active' and fields.get('SubState') == 'running', 'Actual new owner changed')
    process = Path('/proc',str(owner['pid'])); raw = (process/'stat').read_text()
    require(int(raw[raw.rfind(')')+2:].split()[19]) == owner['starttime_ticks']
            and (process/'cgroup').read_text().strip() == '0::'+owner['cgroup']
            and [x.decode() for x in (process/'cmdline').read_bytes().rstrip(b'\0').split(b'\0')] ==
                [str(GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','Scripts/run_dqn.py'],
            'Actual process birth/cgroup/literal trainer argv differs')
    uid_line = next(line for line in (process/'status').read_text().splitlines() if line.startswith('Uid:'))
    require(list(map(int,uid_line.split()[1:])) == [os.getuid()]*4, 'Owner UID differs')
    environment = dict(item.split(b'=',1) for item in (process/'environ').read_bytes().split(b'\0') if b'=' in item)
    get = lambda key: environment.get(key.encode(),b'').decode()
    require(get('ROBOTRON_RUN_DIR') == str(LIVE) and get('DQN_PRIORITY_PHASE_RECORD') == phase['path']
            and get('DQN_PRIORITY_PHASE_RECORD_SHA256') == phase['sha256'] and get('PYTHONUNBUFFERED') == '1'
            and get('DQN_BATCH_SIZE') == '4096' and get('DQN_N_STEP') == '3'
            and get('DQN_MAX_SAMPLES_PER_FRAME') == '8'
            and get('CUDA_VISIBLE_DEVICES') == 'GPU-c0c5d295-6f07-aab5-bbde-b592ea426ec1'
            and get('CUDA_DEVICE_ORDER') == 'PCI_BUS_ID', 'Actual same-state recipe/phase/GPU environment differs')
    again = (process/'stat').read_text()
    require(int(again[again.rfind(')')+2:].split()[19]) == owner['starttime_ticks'], 'Owner changed during observation')
    return {key:fields[key] for key in ('MainPID','NRestarts','ControlGroup','ActiveState','SubState','InvocationID')}


def build_context(template, pairs, archived_control, archived_unit, provenance):
    require(set(pairs) == set(SOURCES) and set(template['source_control_context']['model_package']) == MODEL_SOURCES,
            'Exact existing source/context ABI required')
    context = copy.deepcopy(template['source_control_context'])
    context.update(model_package={name:pairs[name]['current'] for name in MODEL_SOURCES},
        archived_control=archived_control,archived_trainer_unit=archived_unit,provenance=provenance)
    require(context['held_recipe_context'] == template['source_control_context']['held_recipe_context'],
            'Held recipe context must remain data-equivalent')
    return context


def prepare(selection_pin):
    spec = read(selection_pin)
    require(set(spec) == {'schema','actual_new_owner','CPU_template','actual_resume_phase_record',
            'actual_stop_result','source_install_receipt','actual_installed_sources','actual_control','provenance'}
            and spec['schema'] == 'robotron-root-actual-preserveRAM-startup-source-context-selection-v1'
            and all(value is not None for value in spec.values()), 'Explicit actual ROOT selection required')
    owner = read(spec['actual_new_owner']); template = read(spec['CPU_template'])
    phase = read(spec['actual_resume_phase_record']); stop = read(spec['actual_stop_result'])
    read(spec['source_install_receipt'])
    require(template['verifier_sha256'] == VERIFIER_SHA and set(template['phase_snapshot']['sources']) == set(SOURCES)
            and set(template['source_control_context']['model_package']) == MODEL_SOURCES,
            'Exact existing08c eight-source template shape required')
    recipe = template['source_control_context']['held_recipe_context']
    require(recipe['batch_size'] == 4096 and recipe['baseline_batch_size'] == 512
            and recipe['n_step'] == 3 and recipe['max_samples_per_frame'] == 8
            and recipe['learning_control_lr_scale'] == .125 and recipe['optimizer_lr'] == 6.25e-6,
            'Only unchanged current LR.125 recipe context permitted')
    require(stop['status'] == 'CURRENT_TRAINER_STOPPED_AND_FULL_STATE_HOT_REPLAY_PRESERVED'
            and stop['trainer_stopped'] is True and stop['replacement_started'] is False
            and stop['saved']['strict_phase_verified'] is True
            and stop['saved']['replay_bank_consistency_verified'] is True
            and phase['schema'] == 'robotron-priority-metric-start-v1' and phase['action'] == 'resume'
            and phase['metric'] == 'ce'
            and phase['checkpoint'] == {k:stop['saved']['checkpoint'][k] for k in ('path','sha256','bytes')},
            'Actual stopped same-state checkpoint and NEW resume phase required')
    saved_report = read(stop['saved']['report']); founder = saved_report['saved_priority_metric_phase']
    require(saved_report['status'] == 'PASS' and saved_report['phase_metadata_verified'] is True
            and saved_report['sha256'] == stop['saved']['checkpoint']['sha256']
            and founder['valid'] is True and founder['metric'] == 'ce'
            and phase['phase_id'] == founder['phase_id']
            and phase['root_precommit_sha256'] == founder['root_precommit_sha256'],
            'NEW resume record must preserve actual verified CE founder identity')
    require(spec['actual_resume_phase_record']['path'] == str(LIVE/'resume-phase-record.json')
            and spec['actual_control']['path'] == str(GAME/'models_dqn/learning_control.json'), 'Exact current phase/control paths required')
    control = json.loads(read_bytes(spec['actual_control'])); require(control['lr_scale'] == .125, 'Current control recipe changed')
    require(type(spec['actual_installed_sources']) is dict and type(spec['provenance']) is list
            and len(spec['provenance']) <= 12, 'Bounded actual install/provenance source map required')
    socket_path = str(GAME/'Scripts/dqn/socket_server.py')
    require(socket_path in spec['actual_installed_sources'], 'Actual installed host-only socket source must be selected')
    for path,value in spec['actual_installed_sources'].items():
        require(value['path'] == path, 'Installed-source map path differs'); read_bytes(value)
    for value in spec['provenance']: read_bytes(value)
    actual = {name:fingerprint(GAME/'Scripts/dqn'/name) for name in SOURCES}
    for name,value in actual.items():
        parent = template['phase_snapshot']['sources'][name]['current']
        require(parent['path'] == value['path'] and parent['sha256'] == value['sha256'] and parent['bytes'] == value['bytes'],
                'Host-only continuation must preserve each reviewed numerical source: '+name)
    before = observe_owner(owner,spec['actual_resume_phase_record'])
    unit = subprocess.run(['systemctl','--user','cat',UNIT],capture_output=True,timeout=15)
    require(unit.returncode == 0 and unit.stderr == b'' and 0 < len(unit.stdout) <= 2_000_000
            and spec['actual_resume_phase_record']['sha256'].encode() in unit.stdout,
            'Actual new-unit source must explicitly bind NEW resume phase')
    require(not OUTPUT.exists() and OUTPUT.parent.is_dir(), 'Fresh actual startup context output required')
    OUTPUT.mkdir(mode=0o700); (OUTPUT/'source-archives').mkdir()
    pairs = {name:dict(current=value,archive=archive(value,OUTPUT/'source-archives'/name)) for name,value in actual.items()}
    archived_control = archive(spec['actual_control'],OUTPUT/'actual-current-learning-control.json')
    archived_unit = publish(OUTPUT/'actual-new-trainer-unit.txt',unit.stdout)
    context = build_context(template,pairs,archived_control,archived_unit,
        [selection_pin,spec['actual_stop_result'],spec['source_install_receipt'],
         spec['actual_resume_phase_record'],spec['actual_new_owner'],*spec['provenance']])
    require(context['held_recipe_context'] == recipe, 'Held recipe context must remain byte-for-byte data-equivalent')
    pairs_pin = publish(OUTPUT/'actual-eight-phase-source-pairs.json',pairs)
    context_pin = publish(OUTPUT/'actual-source-control-context.json',context)
    after = observe_owner(owner,spec['actual_resume_phase_record'])
    require(before == after and all(fingerprint(value['path']) == value for value in actual.values())
            and read_bytes(spec['actual_control']) == read_bytes(archived_control), 'Owner/control/source bracket changed')
    return publish(OUTPUT/'prepared-actual-installed-source-context-for-startup-CPU.json',dict(
        schema='robotron-actual-startup-source-context-readonly-preparation-v1',owner=owner,
        owner_pin=spec['actual_new_owner'],before=before,after=after,actual_phase_source_pairs=pairs_pin,
        actual_source_control_context=context_pin,actual_new_trainer_unit=archived_unit,
        source_install_receipt=spec['source_install_receipt'],selection=selection_pin,
        acquisition=None,model_source=None,verification_copy=None,model_body_reads=0,control_or_process_actions=0))


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--selection'); parser.add_argument('--selection-sha256'); parser.add_argument('--expected-source-sha256')
    args = parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY: no owner/source/model reads, archives, API queries or controls'); return
    own = fingerprint(__file__); require(own['sha256'] == args.expected_source_sha256
            and own['identity']['mode'] == '0o444', 'Frozen selected context generator required')
    selection = fingerprint(args.selection); require(selection['sha256'] == args.selection_sha256, 'Exact ROOT selection SHA required')
    print(json.dumps(prepare(selection),indent=2))


if __name__ == '__main__':
    main()
