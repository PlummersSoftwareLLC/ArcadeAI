from pathlib import Path
import importlib.util
import json
import os
import sys
import time

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'logs/managed-learning-20261015/run-26'
F = B / 'quality32-protectedb231-vs-distinct8dae-fullgame-original01-20261101'
STATE = B.parent / 'state.json'
DELL = G / 'DELL_SETUP.md'
PUBLIC = G / 'html/next-policy-evaluation.json'
spec = importlib.util.spec_from_file_location('_recordFull8Header', B / 'fleet-cleanup-queue8192-fullstate-maintenance-original01-20261101/sources/prepare_current_continuous_preservation_header_v3.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
phase = sys.argv[1]
number = {'prepared': 188, 'running': 189}[phase]
old, db, ub = STATE.read_bytes(), DELL.read_bytes(), PUBLIC.read_bytes()
state = json.loads(old)
goal = state['optimization_goal']
prior = state['current_optimization_recovery_index']
if phase == 'prepared':
    assert prior['sha256'] == '4edbc1f5d6066bbd3556f7c396e1c7797229ee5891be0047cfdf462c531ae656'
else:
    assert 'original188.json' in prior['path']
small = lambda pin: {key: pin[key] for key in ['path', 'sha256', 'bytes']}
preimages = {label: h.put(F / (f'{label}-before-index{number}.exact' + suffix), raw)
             for label, suffix, raw in [('canonical', '.json', old), ('DELL', '.md', db), ('public', '.json', ub)]}
prepared = h.metadata(F / 'prepared-campaign.json')[0]
job = h.metadata(F / 'original-sequence-job.json')[0]
cpu = h.metadata(F / 'preflight-CPU-original01.json')[0]
physical = h.metadata(F / 'preflight-physical-source-ABI-original01.json')[0]
assert json.loads(Path(cpu['path']).read_text())['checks_total'] == 31
assert json.loads(Path(physical['path']).read_text())['checks_total'] == 36
owner = None
wait = None
if phase == 'running':
    owner = json.loads((F / 'original-sequence-owner.json').read_text())
    birth = lambda pid: int(Path('/proc', str(pid), 'stat').read_text().rsplit(')', 1)[1].split()[19])
    assert birth(owner['pid']) == owner['birth']
    wait = dict(kind='ORIGINAL_FRESH_FULLGAME_B231_VS_DISTINCT8DAE', tool_session=int(sys.argv[2]),
                outer_pid=owner['pid'], outer_birth=owner['birth'], current_leg='R1',
                directory=str(F), original_attempt=1, no_retry=True)
    native_path = F / '01-reference/execution-original01/root-original-identity.json'
    if native_path.exists() and native_path.stat().st_mode & 0o777 == 0o444:
        native = json.loads(native_path.read_text())
        assert birth(native['pid']) == native['starttime_ticks']
        wait.update(native_pid=native['pid'], native_birth=native['starttime_ticks'], native_invocation_id=native['invocation_id'])
summary = ('Fresh b231-vs-distinct8dae natural-fullgame campaign ' + phase + '. '
           'All4 jobs,256 distinct transport identities and predeclared R1/C1/R2/C2 rule bound before first score; '
           '31CPU and36actual physical/source/port/GPU preflight checks passed. '
           '64natural games perleg,2per all32/fulltails/min50floor; fresh pooled128R1/R2 reference only, '
           'C1 andC2 separately mean>=1.05reference and median preserved; no pooling/retry/censored rescue. '
           'C2 can be skipped only after reviewed R1/C1/R2 show exact C1 gate failure. '
           'Native functions unchanged except pendingwait0.2s vs5s; reviewer/assessor onlypair/case constants; '
           'controller/sequence/score/health/closure/decision kernels exact. No pendingbranch liveclaim. '
           'Original77f9R1 staysinvalid; completed8dae shortscreen valid15min-0.61percent but nofullranking/promotion. '
           'Main155TRAIN/remainingEVAL continues unchanged; research savedfloor5309060592 requires rebind to this fullpair before acquisition.')
index = h.put(F / f'fresh-distinct8dae-fullgame-{phase}-index-original{number}.json', dict(
    schema='robotron-current-optimization-recovery-index-v1', status='FRESH_DISTINCT8DAE_FULLGAME_' + phase.upper(),
    observed_unix_s=time.time(), prior_index=prior, preimages=preimages,
    prepared=small(prepared), original_sequence_job=small(job), CPU31=small(cpu), actual_live36=small(physical),
    original_owner=owner, actual_running_wait=wait, main_training_running=True,
    scientific_job_running=phase == 'running', next_action=summary, promotion=False))
active = dict(directory=str(F), preparation=small(prepared), sequence_job=small(job), state=phase,
              original_attempt=1, no_retry=True, ordered_legs=['R1', 'C1', 'R2', 'C2'])
for target in [state, goal]:
    target.update(current_optimization_recovery_index=small(index), actual_running_wait=wait,
                  main_training_running=True, scientific_job_running=phase == 'running',
                  engineering_job_running=False, active_screen_job=None, active_quality_job=active)
goal.update(next_action=summary, current_campaign=str(F), current_campaign_phase='FRESH_FULLGAME_' + phase.upper(),
            pending_fullgame_comparison=small(prepared), updated_unix_s=time.time(),
            latest_goal_turn_classification=dict(classification='progress',
                evidence='Prepared new distinct8dae natural-fullgame source family, reverified original CPU scope, passed31CPU gate/source tests and36actual physical/ABI/source/port/GPU preflight checks.'))
state['updated_unix_s'] = time.time()
raw = (json.dumps(state, separators=(',', ':'), allow_nan=False) + '\n').encode()
assert len(raw) < 1 << 20
public = json.loads(ub)
public.update(study_directory=str(F), state='running' if phase == 'running' else 'prepared',
              stage='fullgame_' + phase, current_leg=None, screen_only=False, mode='manual',
              legs=[dict(index=index + 1, role=role, state='pending') for index, role in enumerate(['reference', 'candidate', 'reference', 'candidate'])],
              quality_qualified=False, promotion=False, updated_unix_s=time.time(), observation_unix_s=time.time())
public['next_work'].update(
    state='fullgame_' + phase, current_stage='Fresh full-game reference cohort ready' if phase == 'prepared' else 'Starting fresh full-game reference cohort',
    detail='Compare the protected champion and the later saved candidate with64 natural complete games per cohort. Each candidate confirmation must separately pass the5% mean and median gates. Training continues.',
    waiting_for='Original reference launch' if phase == 'prepared' else 'Original reference games and full tails',
    next_stage='Candidate cohort after independent reference review',
    eta='Natural games have no fixed completion time; each cohort has a six-hour safety limit. Unfinished games do not count as complete.',
    updated_unix_s=time.time(), observation_unix_s=time.time())

def cas(path, before, after):
    assert path.read_bytes() == before
    temporary = path.with_name(path.name + f'.index{number}.tmp')
    with temporary.open('xb') as stream:
        stream.write(after)
        stream.flush()
        os.fsync(stream.fileno())
    assert path.read_bytes() == before
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    os.fsync(fd)
    os.close(fd)

cas(STATE, old, raw)
cas(DELL, db, f'Robotron recovery index{number}: {index["path"]}\n{summary}\n\n'.encode() + db)
if phase == 'prepared':
    cas(PUBLIC, ub, (json.dumps(public, indent=2, allow_nan=False) + '\n').encode())
print(json.dumps(dict(index=small(index), phase=phase, actual_running_wait=wait, state_bytes=len(raw))))
