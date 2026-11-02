"""Unselected read-only reviewer for one closed, source-bound R/C/R/C campaign.

All four original cohorts are checked independently. Only the two fresh
reference cohorts are pooled. No launches, signals, training changes or policy
publication occur. Selection still requires the matching launch observer and
winner protector, plus a complete integration proof.

This future-only revision independently rejoins bounded supervised main-fleet
recoveries. All195 held inputs and private full-game/ROM/score gates remain.
A recovery does not claim continuous original192 actor identities.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import time
import urllib.request

GAME = Path('/home/dave/source/repos/ArcadeAI/Robotron')
HERE = GAME/'tools/quality_capacity_proposal'
DEPENDENCIES = {
    'supervision': (HERE/'supervised_main_fleet_v1.py', '38069c081a1e693977d8aaf0389e3979f29a97185f2adc8ce960d45f01f4188d'),
    'observations': (HERE/'supervised_main_observations_v1.py', '7f7d481a3e20a239f5f1e1bc961872b47a707041743fe3f7c32363c99555988a'),
    'cohorts': (HERE/'audit_quality32_evidence_v4.py', 'f07ccdd098cbf879c7ff98ef26e92e525b7a0ea951c38641fa2b5c0571fa50e3'),
    'acquisition': (HERE/'quality32_acquisition_v4.py', '2f8ad3d84b9033c892318d069e0c462bf3f07dd3d0e9e69211008f602153ba70'),
    'runtime': (GAME/'tools/eval_capacity_proposal/review_original_pilot_raw_API_v1.py',
                '2ed5fde26fe50a23bc9572965e483ae6634b31ffbe5d4147c9f5bc338396d445'),
}
READER = GAME/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
READER_SHA = 'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071'
SLOTS = list(range(4096,4128))


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def reader_module():
    require(digest(READER) == READER_SHA, 'Exact immutable evidence reader differs')
    spec = importlib.util.spec_from_file_location('_quality32_reader_'+str(time.time_ns()), READER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_records(plan, status, summary, expected_sha):
    require(status['state'] == 'finished' and status['plan_sha256'] == summary['plan_sha256'] == expected_sha
            and status['outcome'] == summary['outcome']
            and summary['stop_signal'] is None, 'Original campaign must finish without interruption')
    records = status['legs']
    require(len(records) == 4 and [value['index'] for value in records] == [1,2,3,4]
            and [value['role'] for value in records] == ['reference','candidate','reference','candidate'],
            'All four original evaluator records required')
    previous_end = None
    pids = set()
    for record, spec in zip(records, plan['legs']):
        require(record['state'] == 'finished' and type(record['returncode']) is int
                and record['returncode'] == 0 and type(record['pid']) is int and record['pid'] > 0
                and record['pid'] not in pids
                and record['receipt_path'] == spec['receipt_path']
                and record['console_log'] == spec['console_log']
                and record['evaluator_status_path'] == spec['evaluator_status_path'],
                'Exact original successful evaluator record required; no retries')
        start, end = record['started_unix_s'], record['ended_unix_s']
        require(all(type(value) in (int,float) and math.isfinite(value) for value in (start,end))
                and 0 < start < end and (previous_end is None or start >= previous_end),
                'Original evaluator intervals overlap or are malformed')
        previous_end = end
        pids.add(record['pid'])
    return records


def validate_births(record, evaluator, actors, receipt, campaign_owner):
    require(evaluator['pid'] == record['pid'] and evaluator['parent_pid'] == campaign_owner['pid']
            and evaluator['cgroup'] == campaign_owner['cgroup']
            and type(evaluator['starttime_ticks']) is int and evaluator['starttime_ticks'] > 0
            and evaluator['observed_live'] is True, 'Original live evaluator birth differs')
    require(set(actors) == set(map(str,SLOTS)) and len({value['pid'] for value in actors.values()}) == 32,
            'All32 distinct original actor births required')
    for slot, actor in actors.items():
        require(type(actor['pid']) is int and actor['pid'] > 0
                and type(actor['starttime_ticks']) is int and actor['starttime_ticks'] > 0
                and actor['observed_live'] is True and actor['parent_pid'] == evaluator['pid']
                and actor['cgroup'] == campaign_owner['cgroup']
                and actor['pid'] == receipt['socket_wait']['actors'][slot]['pid'],
                'Original evaluator/actor/pacing identity differs')


def validate_native_command(fields, binding, config):
    campaign = binding['campaign']
    command = config['argv']
    require(command[:5] == [str(GAME.parent/'.venv-gb300/bin/python'),'-Xgil=0','-B','-u',
                str(HERE/'profile06/Robotron/tools/run_quality_campaign.py')]
            and command.count('--actors') == 1 and len(command) > command.index('--actors')+1
            and command[command.index('--actors')+1] == '32'
            and command.count('--launch') == command.count('--game-boundary-diagnostics') == 1,
            'Selected private32-slot campaign executable and explicit launch flags required')
    require(config['unit'] == campaign['native_unit'] and config['argv'] == campaign['command']
            and config['output'] == campaign['controller_output'], 'Exact original native launch config required')
    expected = ['/usr/bin/env','-u','LD_PRELOAD','-u','PYTHONPATH','CUDA_VISIBLE_DEVICES=',
        'PYTHONDONTWRITEBYTECODE=1','TMPDIR='+str(Path(config['output'])/'tmp')] + config['argv']
    match = re.fullmatch(r'\{ path=/usr/bin/env ; argv\[\]=(.*?) ; ignore_errors=no ; .* \}',fields['ExecStart'])
    require(match is not None and shlex.split(match[1]) == expected,
            'Actual original native command differs from its selected launch')


def validate_main_binding(main, binding):
    keys = ('owner','actors','held_hashes','experiment','supervision_policy')
    require(set(binding['main_holds']) == set(keys)
            and all(main[key] == binding['main_holds'][key] for key in keys)
            and main['owner'] == binding['expected_window']['owner'] and len(main['actors']) == 192
            and len(main['held_hashes']) == 195, 'Original precommitted main192/195 holds differ')


def validate_leg_scope(receipt, spec, record, binding):
    directory = Path(spec['job']['directory'])
    require(receipt['source_checkpoint_path'] == spec['job']['checkpoint']
            and receipt['checkpoint_path'] == str(directory/'checkpoint.pt')
            and Path(receipt['checkpoint_path']).stat().st_ino != Path(spec['job']['checkpoint']).stat().st_ino,
            'Each original leg requires its own canonical frozen checkpoint copy')
    actual = receipt['runtime']
    require(actual['device'] == 'cuda' and actual['cuda_visible_devices'] == spec['job']['gpu_uuid']
            and actual['gpu_name'] == 'NVIDIA RTX PRO 2000 Blackwell'
            and actual['compute_capability'] == [12,0], 'Actual physical evaluator GPU differs')
    require(type(receipt['elapsed_s']) in (int,float) and math.isfinite(receipt['elapsed_s'])
            and 0 < receipt['elapsed_s'] < 9300
            and receipt['elapsed_s'] <= record['ended_unix_s']-record['started_unix_s']+1
            and record['ended_unix_s']-record['started_unix_s'] < 9300,
            'Original leg exceeded its bounded measurement/startup/cleanup lifetime')
    if spec['role'] == 'candidate':
        require(receipt['checkpoint_sha256'] == binding['candidate']['sha256'],
                'Leg candidate differs from original acquired checkpoint')


def decision(legs):
    require([leg['index'] for leg in legs] == [1,2,3,4]
            and [leg['role'] for leg in legs] == ['reference','candidate','reference','candidate'],
            'Four independently reviewed cohorts required')
    ids = set()
    for leg in legs:
        rows = leg['rows']
        current = [row['journal_game_id'] for row in rows]
        require(len(rows) >= 50 and len(set(current)) == len(current) and not ids.intersection(current)
                and all(isinstance(value,str) and value for value in current)
                and {row['client_slot'] for row in rows} == set(SLOTS)
                and all(type(row['score']) is int and row['score'] >= 0 for row in rows),
                'Distinct full games, all32 slots and integer scores required in every leg')
        ids.update(current)
    references = [row['score'] for leg in legs if leg['role'] == 'reference' for row in leg['rows']]
    count, total = len(references), sum(references)
    require(total > 0, 'Fresh pooled reference mean must be positive')
    def median_twice(scores):
        ordered = sorted(scores)
        return ordered[(len(ordered)-1)//2] + ordered[len(ordered)//2]
    median2 = median_twice(references)
    checks = []
    for leg in legs:
        if leg['role'] == 'reference':
            continue
        scores = [row['score'] for row in leg['rows']]
        left, right = sum(scores)*count*20, total*len(scores)*21
        checks.append(dict(index=leg['index'], count=len(scores), mean=sum(scores)/len(scores),
            median=median_twice(scores)/2, mean_integer_left=left, mean_integer_right=right,
            mean_pass=left >= right, median_pass=median_twice(scores) >= median2))
    qualified = all(value['mean_pass'] and value['median_pass'] for value in checks)
    return dict(outcome='qualified_improvement' if qualified else 'not_improved',
        qualified_improvement=qualified, pooled_reference=dict(count=count, score_sum=total,
            mean=total/count, median=median2/2), individual_candidate_checks=checks,
        candidates_pooled_for_qualification=False)


def review(job, job_pin, reader):
    # The closed context must exist before any output or runtime query.
    context_pin = reader.pin(job['closed_context_path'])
    context = reader.read_pin(context_pin)
    require(context['schema'] == 'robotron-closed-quality32-campaign-context-v1'
            and context['binding'] == job['binding'], 'Exact closed original context required')
    output = Path(job['output'])
    require(output.is_absolute() and not output.exists(), 'One new original review output; never retry')
    output.mkdir(mode=0o700)
    hashes, artifacts, payloads = {}, {}, {}
    def read(entry, as_json=True):
        value = reader.read_pin(entry, as_json=as_json)
        hashes[entry['path']] = entry['sha256']
        return value
    def capture(path):
        path = Path(path)
        before = reader.pin(path)
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == before['sha256'], 'Closed evidence read race')
        if str(path) in payloads:
            require(raw == payloads[str(path)], 'Closed evidence changed between reads')
            return raw
        target = output/f'{len(artifacts):04d}-{path.name}'
        with target.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fchmod(stream.fileno(),0o444); os.fsync(stream.fileno())
        artifacts[str(path)] = dict(copy=target.name, sha256=before['sha256'])
        hashes[str(path)] = before['sha256']; payloads[str(path)] = raw
        return raw
    report = dict(schema='robotron-closed-quality32-independent-review-v1', valid=False,
        root_job=job_pin, closed_context=context_pin, artifacts=artifacts, evidence_sha256=hashes,
        quality_qualified=False, promotion=False, learning_speed_gain_verified=False,
        actual_runtime_changed=False)
    try:
        read(job_pin); read(context_pin); capture(__file__)
        modules = {}
        for name,(path,expected) in DEPENDENCIES.items():
            require(digest(path) == expected, 'Exact tested reviewer dependency changed')
            modules[name] = reader.checked_module('_closed32_'+name+'_'+str(time.time_ns()),reader.pin(path))
        for path,expected in DEPENDENCIES.values(): hashes[str(path)] = expected
        cohorts, acquisition, runtime = (modules[key] for key in ('cohorts','acquisition','runtime'))
        binding = read(job['binding'])
        acquired = acquisition.review_acquisition(binding, read, runtime.archived_closure)
        owner = read(context['native_owner']); closure = read(context['native_closure'])
        require(owner['unit'] == binding['campaign']['native_unit']
                and context['native_owner']['path'] == binding['campaign']['native_owner_path'],
                'Only the original selected campaign owner file and named service')
        fields = runtime.archived_closure(closure, owner, read, exit_zero=True)
        validate_native_command(fields,binding,read(context['native_controller_config']))
        start = int(fields['ExecMainStartTimestampMonotonic'])/1e6
        end = int(fields['ExecMainExitTimestampMonotonic'])/1e6
        require(0 < start < end <= time.monotonic() and end-start <= 36600
                and runtime.duration_seconds(fields['RuntimeMaxUSec']) == 36600
                and fields['MemoryMax'] == str(12<<30)
                and runtime.duration_seconds(fields['CPUQuotaPerSecUSec']) == 12
                and fields['Restart'] == 'no' and fields['SendSIGKILL'] == 'no',
                'Original campaign runtime/resources/restart policy differs')
        directory = Path(binding['campaign']['output_directory'])
        plan_raw = capture(directory/'plan.json'); plan_sha = hashlib.sha256(plan_raw).hexdigest()
        require(plan_sha == binding['campaign']['plan_sha256'], 'Original native plan hash differs')
        plan = json.loads(plan_raw)
        game, backend, helpers, auditor = cohorts.dependencies()
        cohorts.validate_plan(plan, dict(binding['campaign'], checkpoints=plan['checkpoints']), game)
        for role in ('reference','candidate'):
            require(plan['checkpoints'][role] == dict(source=binding[role]['path'],
                snapshot=str(directory/'checkpoints'/(role+'.pt')), sha256=binding[role]['sha256']),
                'Plan role checkpoint differs from verified acquisition')
            require(digest(plan['checkpoints'][role]['snapshot']) == binding[role]['sha256'],
                    'Original role checkpoint copy changed')
            require(Path(plan['checkpoints'][role]['snapshot']).stat().st_ino != Path(binding[role]['path']).stat().st_ino,
                    'Original role checkpoint must be an independent copy')
        status_raw, summary_raw = capture(directory/'status.json'), capture(directory/'summary.json')
        require(status_raw == read(context['status_final'],False)
                and summary_raw == read(context['summary_final'],False), 'Original terminal authority copies differ')
        status, summary = json.loads(status_raw), json.loads(summary_raw)
        records = validate_records(plan,status,summary,plan_sha)
        main = read(context['main_binding'])
        validate_main_binding(main,binding)
        window = reader.checked_module('_closed32_main_'+str(time.time_ns()), job['main_guard_source'])
        hashes[job['main_guard_source']['path']] = job['main_guard_source']['sha256']
        require(job['main_guard_source']['sha256'] == 'f44f392188bcc6924baab87b2762d6a80879331078f76495bb4c00686b8b65f3',
                'Exact main hold predicate required')
        main['baseline_API_value'] = read(main['baseline_API'])
        manifest = read(context['main_observations'])
        samples = runtime.validate_raw_API_samples(manifest,[read(entry) for entry in manifest['samples']],read)
        supervision, observations = modules['supervision'], modules['observations']
        policy = read(main['supervision_policy'])
        supervision_state, supervision_summary = observations.review(
            main,policy,manifest,samples,start,end,read,runtime,window,supervision)
        births = read(context['leg_evaluator_births']); actors = read(context['leg_actor_identities'])
        require(set(births) == set(actors) == {'1','2','3','4'}, 'Four original evaluator/actor registries required')
        package = read(binding['evidence']['source_package'])
        for relative,expected in package['files'].items():
            require(digest(game/relative) == expected, 'Private source changed during closed review')
            hashes[str(game/relative)] = expected
        prefix = backend.__package__
        campaign = __import__(prefix+'.run_quality_campaign',fromlist=['load_leg'])
        boot = __import__(prefix+'.sidecar_boot',fromlist=['load_snapshot'])
        lease = Path(job['lease_path']); info = lease.lstat()
        require(str(lease) == '/dev/shm/robotron-snapshot-smoke-gpu0.lock'
                and lease.resolve(strict=True) == lease and info.st_uid == os.getuid() and info.st_nlink == 1
                and dict(device=info.st_dev,inode=info.st_ino) == job['lease_identity'],
                'Original canonical private GPU lease differs')
        reviewed, row_legs = [], []
        signature = None
        for spec,record in zip(plan['legs'],records):
            legdir = Path(spec['job']['directory'])
            receipt_raw = capture(legdir/'receipt.json')
            receipt, validated, receipt_sha = campaign.load_leg(spec,plan)
            require(receipt == json.loads(receipt_raw), 'Receipt changed before original readback')
            validate_leg_scope(receipt,spec,record,binding)
            if spec['index'] == 1:
                require(max(job['binding']['identity']['ctime_ns'],job['binding']['identity']['mtime_ns'])/1e9
                        <= receipt['start_ts']
                        and max(main['supervision_policy']['identity']['ctime_ns'],main['supervision_policy']['identity']['mtime_ns'])/1e9
                        <= receipt['start_ts']
                        and max(context['main_binding']['identity']['ctime_ns'],context['main_binding']['identity']['mtime_ns'])/1e9
                        <= receipt['start_ts'] and plan['created_unix_s'] <= record['started_unix_s'],
                        'Root/main bindings, supervision policy and native plan must predate the first measurement')
            current_signature = dict(job={key:receipt['job'][key] for key in backend.JOB_FIELDS},
                numeric_policy=receipt['numeric_policy'],runtime=receipt['runtime'],
                source_hashes=receipt['source_hashes'],protocol=validated['protocol'],
                boot_identity=receipt['boot_assets']['identity'],wire_binary=receipt['socket_wait']['sha256'])
            require(signature is None or signature == current_signature,
                    'Actual backend/numeric/source/game protocol differs across legs')
            signature = current_signature
            require(summary['legs'][spec['index']-1]['valid'] is True
                    and summary['legs'][spec['index']-1]['receipt_sha256'] == receipt_sha
                    and set(summary['legs'][spec['index']-1]['included_game_ids']) ==
                        {row['journal_game_id'] for row in receipt['rows']},
                    'Original native summary does not cover this complete receipt')
            validate_births(record,births[str(spec['index'])],actors[str(spec['index'])],receipt,owner)
            require(record['started_unix_s'] <= receipt['start_ts'] < receipt['close_ts']
                    <= receipt['timeout_snapshot_unix_s'] <= receipt['ended_unix_s'] <= record['ended_unix_s']
                    and math.isclose(receipt['close_ts']-receipt['start_ts'],5400,abs_tol=1e-6),
                    'Fixed admission/full tail falls outside original evaluator lifetime')
            require(json.loads(capture(legdir/'plan.json')) == dict(spec['job'],
                    checkpoint_sha256=binding[spec['role']]['sha256']), 'Original per-leg plan differs')
            if spec['role'] == 'candidate':
                require(all(receipt['checkpoint_metadata'][key] == acquired['clocks'][key]
                    for key in ('training_steps','optimized_samples','learner_frame_count')),
                    'Candidate receipt clocks differ from actual CPU acquisition')
            for name in ('games.jsonl','measurement_starts.jsonl','lives.jsonl'):
                capture(legdir/'journal'/name)
            for slot in SLOTS: capture(legdir/'actors'/str(slot)/'console.log')
            cohort = cohorts.completed_cohort(receipt,legdir,backend,helpers,auditor)
            boot_manifest = boot.load_snapshot(Path(spec['job']['boot_assets']))
            require(receipt['boot_assets'] == plan['boot_assets'] == boot_manifest,
                    'Original boot snapshot differs from precommit')
            for slot in SLOTS:
                restore = receipt['boot_restores'][str(slot)]
                require(restore['manifest_sha256'] == digest(Path(spec['job']['boot_assets'])/'manifest.json')
                        and restore['restored_paths'] == {name:str(legdir/'actors'/str(slot)/name)
                            for name in boot_manifest['files']}, 'Original per-slot boot restore differs')
            require(digest(receipt['socket_wait']['library']) == receipt['socket_wait']['sha256'],
                    'Original private pacing binary changed')
            capture(receipt['socket_wait']['library'])
            console = capture(spec['console_log']).decode(errors='replace')
            classified = helpers.console_lines(console,receipt,game,auditor,unused_expert_proof_validated=True)
            runtime.verify_cleanup(owner,actors[str(spec['index'])],spec['job']['gpu_uuid'],Path(job['lease_path']))
            reviewed.append(dict(index=spec['index'],role=spec['role'],receipt_sha256=receipt_sha,
                cohort=cohort,classified_console_lines=classified))
            row_legs.append(dict(index=spec['index'],role=spec['role'],rows=receipt['rows']))
        result = decision(row_legs)
        require(summary['qualified_improvement'] is result['qualified_improvement']
                and summary['outcome'] == result['outcome'], 'Native and independent individual decisions differ')
        current_census = supervision.collect(policy,supervision_state)
        observations.validate_current(main,policy,current_census,supervision_state,supervision,window)
        current = json.load(urllib.request.urlopen('http://127.0.0.1:8771/api/now',timeout=5))
        window.healthy(current,main['baseline_API_value'],main['experiment'],time.time())
        require(all(digest(path) == expected for path,expected in hashes.items()),
                'Original source/evidence changed during closed review')
        require('torch' not in sys.modules, 'Independent review imported numerical runtime')
        report.update(valid=True,status='VALID_CLOSED_FOUR_LEG_QUALITY32_REVIEW',legs=reviewed,
            acquisition=acquired,decision=result,quality_qualified=result['qualified_improvement'],
            full_original_tails_and_ROM_verified=True,original_native_exit0_and_cleanup_verified=True,
            main192_continuous_holds_verified=supervision_summary['recoveries']==0,
            main_supervised_runtime_verified=True,main_supervision_summary=supervision_summary)
    except Exception as error:
        report.update(status='REJECTED_OR_NEEDS_REVIEW',error=repr(error))
    with (output/'review.json').open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False); stream.write('\n')
        stream.flush(); os.fchmod(stream.fileno(),0o444); os.fsync(stream.fileno())
    fd=os.open(output,os.O_DIRECTORY); os.fsync(fd); os.close(fd)
    return report


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--execute' not in argv:
        print('PLAN_ONLY: no reads, queries, outputs, launches or promotion')
        return 0
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true'); parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--job-sha256',required=True); parser.add_argument('--source-sha256',required=True)
    args=parser.parse_args(argv)
    require(digest(__file__) == args.source_sha256,'Exact original root reviewer source required')
    reader=reader_module(); pin=reader.pin(args.job)
    require(pin['sha256'] == args.job_sha256,'Root job SHA differs')
    job=reader.read_pin(pin)
    require(job['schema'] == 'robotron-closed-quality32-root-review-job-v1','Exact future root job schema required')
    result=review(job,pin,reader)
    print(json.dumps(dict(valid=result['valid'],quality_qualified=result['quality_qualified'],promotion=False)))
    return 0 if result['valid'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
