"""Synthetic closed-receipt/protected-copy guards; no scientific main is called."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import shlex
import statistics
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

B = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/startup_policy_journal_proposal')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


p = load('_new_certified_quality_protection', Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-protected1741-vs-currentLR125-quota64Protocol-firstSave-original01-preparation-20261024/winner-protection-quota64Protocol-future-original01/held-launch-symlink-correction-original01/protect_quota64Protocol3045_owned_winner_v2.py'))
reader = p.reader_module()
assessor = load('_protection_guard_score_assessor', Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024/scientific-protocol-interface-correction-original01/assess_quality32_quota64_selected_original01_v2.py'))


class Fixture:
    """Synthetic six archived descriptors; never launch or impersonate a real unit."""
    def __init__(self, root, damage=None):
        self.root = root
        self.game = root/'Robotron'
        self.directory = self.game/'logs/managed-learning-20261015/run-26/synthetic-campaign'
        self.directory.mkdir(parents=True)
        self.destination = root/'protected'
        self.destination.mkdir()
        self.counter = 0
        def put(path, value):
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode()
            with path.open('xb') as stream:
                stream.write(raw)
                stream.flush()
                os.fchmod(stream.fileno(), 0o444)
                os.fsync(stream.fileno())
            return reader.pin(path)
        self.put = put
        reference = put(root/'reference.pt', b'synthetic reference policy')
        candidate = put(root/'candidate.pt', b'synthetic candidate policy')
        self.pair = put(self.directory/'pair.json', dict(reference=dict(policy=reference),
            candidate=dict(policy=candidate, saved_clocks=copy.deepcopy(p.CANDIDATE_CLOCKS))))
        source = reader.pin(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024/scientific-protocol-interface-correction-original01/assess_quality32_quota64_selected_original01_v2.py'))
        input_path = root/'synthetic-held-launch-input'
        with input_path.open('xb') as stream:
            stream.write(b'explicit synthetic held launch input; never executed')
            stream.flush(); os.fchmod(stream.fileno(), 0o775); os.fsync(stream.fileno())
        if damage == 'held_symlink':
            real_input = root/'synthetic-held-real-target'
            input_path.rename(real_input)
            input_path.symlink_to(real_input.name)
        self.held_input = reader.pin(input_path)
        self.held_ABI = dict(path=self.held_input['path'],sha256=self.held_input['sha256'],bytes=self.held_input['bytes'],
            identity={key:self.held_input['identity'][key] for key in ('device','inode','mode','uid','nlink')})
        held_inputs=[] if damage=='input_not_held' else [source,self.held_input]
        self.readiness = put(self.directory/'readiness.json', dict(campaign_assessor=source, quality_pair=self.pair,inputs=held_inputs))
        root_job = dict(schema='robotron-original-certified-quality32-campaign-assessment-job-v1',
            campaign_directory=str(self.directory), output=str(self.directory/'independent-campaign-assessment-original01'),
            pair=self.pair, launch_readiness_precommit=self.readiness)
        job_pin = put(self.directory/'campaign-assessment-job-original01.json', root_job)
        argv = ['/usr/bin/python3.12', '-I', '-B', str(Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024/scientific-protocol-interface-correction-original01/assess_quality32_quota64_selected_original01_v2.py')), '--execute',
            '--job', job_pin['path'], '--job-sha256', job_pin['sha256'], '--source-sha256', p.ASSESSOR_SHA]
        unit = 'robotron-quality32-synthetic-protection-original01.service'
        config = dict(unit=unit, output=str(self.directory/'campaign-assessment-execution-original01'), argv=argv,
            properties=['CPUQuota=200%', 'MemoryMax=4G', 'MemorySwapMax=0', 'RuntimeMaxSec=660',
                'TasksMax=128', 'TimeoutStopSec=5', 'SendSIGKILL=no'], pins=[source,self.held_ABI], observation_s=720)
        config_pin = put(self.directory/'campaign-assessment-controller-config-original01.json', config)
        owner = dict(pid=99999999, starttime_ticks=123456789, observed_live=True, unit=unit,
            timer=unit.replace('.service', '.timer'), invocation_id='a'*32, timer_invocation_id='b'*32)
        owner_pin = put(Path(config['output'])/'root-original-identity.json', owner)
        wrapper = ['/usr/bin/env', '-u', 'LD_PRELOAD', '-u', 'PYTHONPATH', 'CUDA_VISIBLE_DEVICES=',
            'PYTHONDONTWRITEBYTECODE=1', 'TMPDIR='+str(Path(config['output'])/'tmp')]+argv
        fields = dict(Id=unit, InvocationID=owner['invocation_id'], MainPID='0', ExecMainPID=str(owner['pid']),
            ExecMainCode='1', ExecMainStatus='0', NRestarts='0', Result='success', CPUQuotaPerSecUSec='2s',
            MemoryMax=str(4 << 30), MemorySwapMax='0', RuntimeMaxUSec='11min', TasksMax='128',
            TimeoutStopUSec='5s', SendSIGKILL='no', Restart='no',
            ExecStart='{ path=/usr/bin/env ; argv[]='+shlex.join(wrapper)+' ; ignore_errors=no ; fake=yes }')
        if damage == 'argv':
            fields['ExecStart'] = fields['ExecStart'].replace('--execute', '--unbound-command')
        if damage == 'resources':
            fields['MemoryMax'] = str(5 << 30)
        if damage == 'native_exit':
            fields.update(ExecMainStatus='17', Result='exit-code')
        archives = []
        for index, kind in enumerate(['show', 'cat', 'journal', 'show', 'cat', 'journal']):
            target = unit if index < 3 else owner['timer']
            command = ['journalctl', '--user', '--unit', target, '--no-pager'] if kind == 'journal' else [
                'systemctl', '--user', kind, target]
            value = '\n'.join(k+'='+v for k, v in fields.items()) if index == 0 else (
                'Id='+owner['timer']+'\nLoadState=not-found\n' if index == 3 else 'synthetic descriptor\n')
            archives.append(dict(argv=command, exit=1 if index == 4 else 0, timed_out=False,
                stdout=put(root/f'archive-{index}-stdout.txt', value.encode()),
                stderr=put(root/f'archive-{index}-stderr.txt', b'')))
        if damage == 'missing_descriptor':
            archives.pop()
        closure = dict(original_exit=17 if damage == 'native_exit' else 0, original=owner, lifecycle_complete=True,
            unit_released=True, original_archived_before_release=True, payload_retried=False, native_archives=archives,
            owned_release=[dict(unit=u, confirmed_absent=True) for u in [unit, owner['timer']]])
        closure_pin = put(Path(config['output'])/'root-original-result-and-owned-release.json', closure)
        result_pin = put(self.directory/'campaign-assessment-controller-original-result.json',
            dict(actual_exit=17 if damage == 'controller_exit' else 0, original_attempt=1, no_retry=True,
                live_registration_errors=[], closure=closure_pin))
        legs = []
        reviews = []
        artifacts = []
        for index, (role, folder) in enumerate(zip(p.ORDER, p.FOLDERS)):
            policy = reference if role.startswith('R') else candidate
            scores = [100]*64 if role.startswith('R') else [105]*64
            if role == 'C1' and damage == 'pooled_rescue':
                scores = [104]*64
            if role == 'C2' and damage == 'pooled_rescue':
                scores = [200]*64
            if role == 'C1' and damage == 'median':
                scores = [90]*33+[200]*31
            if role == 'C1' and damage == 'zero':
                scores = [106]*63+[0]
            ids = [role+':synthetic:'+str(i) for i in range(len(scores))]
            rows = [dict(journal_game_id=jid, client_slot=4096+i%32, score=score, complete=True,
                eligible=True, known_start=True, excluded_reason='') for i, (jid, score) in enumerate(zip(ids, scores))]
            cohort = dict(closed=True, complete=True, valid=True, pending=0, abandoned=0, pending_ids=[],
                abandoned_ids=[], count=len(rows), started=len(rows), rows=rows, started_ids=ids,
                started_actor_slots=list(range(4096, 4128)), mean=statistics.mean(scores),
                median=statistics.median(scores), sd=statistics.stdev(scores), se=statistics.stdev(scores)/len(scores)**.5)
            cohort.update(closed_by='slot_quota',slot_admitted_counts={str(slot):2 for slot in range(4096,4128)})
            decision_cohort=copy.deepcopy(cohort)
            if role=='C1':
                if damage=='fifty_not_sixty_four':
                    cohort['rows']=cohort['rows'][:50];cohort['started_ids']=cohort['started_ids'][:50]
                    cohort.update(count=50,started=50)
                elif damage=='one_and_three':cohort['rows'][0]['client_slot']=4097
                elif damage=='unfinished_tail':cohort.update(complete=False,pending=1)
                elif damage=='abandoned_tail':cohort['abandoned']=1
            root = self.directory/folder
            njob = put(root/'job.json', dict(quality_leg=role, quality_pair_precommit=self.pair))
            native = put(root/'diagnostic-output-original01/result.json', dict(before_intentional_stop=cohort,
                policy_before={'checkpoint_sha256': policy['sha256']}))
            no = dict(pid=88888880+index, starttime_ticks=200+index, invocation_id=str(index+1)*32)
            ro = dict(pid=88888890+index, starttime_ticks=300+index, invocation_id=str(index+5)*32)
            no_pin = put(root/'execution-original01/root-original-identity.json', no)
            ro_pin = put(root/'independent-review-execution-original01/root-original-identity.json', ro)
            reviewed = dict(schema='robotron-original-quota64-independent-cohort-review-v1', valid=True,
                full_game_score_verified=True, quality_qualified=False, promotion=False, quality_leg=role,
                quality_pair_precommit=self.pair, original_native_job=njob, original_result=native, original_owner=no_pin,
                expected_selected_games=64,minimum_quality_complete_games=50,outer_start_horizon_s=21540,
                cohort_selection=copy.deepcopy(assessor.COHORT_SELECTION))
            if role=='C1' and damage=='changed_descriptor':reviewed['cohort_selection']['expected_games']=63
            review_pin = put(root/'independent-quality-leg-review-original01/review.json', reviewed)
            reviews.append(review_pin)
            artifacts.extend([njob, native, no_pin, ro_pin, review_pin])
            legs.append(dict(role=role, policy_sha256=policy['sha256'], cohort=decision_cohort, cohort_selection=copy.deepcopy(assessor.COHORT_SELECTION), evidence_verified=True,
                original_attempt=1, no_retry=True, native_identity=[no['pid'], no['starttime_ticks'], no['invocation_id']],
                review_identity=[ro['pid'], ro['starttime_ticks'], ro['invocation_id']]))
        decision = assessor.assess_validated_cohorts(legs, reference['sha256'], candidate['sha256'])
        report = dict(schema='robotron-original-certified-quality32-campaign-assessment-v1', valid=True,
            quality_qualified=True, status='ORIGINAL_FOUR_LEG_QUALITY_ASSESSMENT_COMPLETE', promotion=False,
            main_runtime_changed=False, learning_speed_gain_verified=False, job=job_pin,
            all_original_runtime_and_review_scopes_verified=True, fixed_input_pair=self.pair,
            artifacts=artifacts, original_leg_reviews=reviews, decision=decision)
        if damage == 'invalid':
            report['valid'] = False
        if damage == 'forged_decision':
            report['decision'] = copy.deepcopy(decision)
            report['decision']['fixed_fresh_reference']['mean'] += 1
        report_pin = put(Path(root_job['output'])/'assessment.json', report)
        self.job = dict(schema='robotron-certified-quota64-winner-protection-job-v1', assessor_source=source,
            assessment_report=report_pin, assessment_job=job_pin, assessment_controller_config=config_pin,
            assessment_controller_result=result_pin, assessment_owner=owner_pin,
            label='synthetic-confirmed', destination=str(self.destination))
        self.job_pin = put(root/'protection-job.json', self.job)
        self.source = candidate
        if damage=='launch_input_drift':
            with input_path.open('ab') as stream:stream.write(b'changed');stream.flush();os.fsync(stream.fileno())
        elif damage=='launch_input_mode':os.chmod(input_path,0o755)

    def context(self, test):
        test.enterContext(patch.object(p, 'GAME', self.game))
        test.enterContext(patch.object(p, 'PAIR_SHA', self.pair['sha256']))
        test.enterContext(patch.object(p, 'CANDIDATE_SHA', self.source['sha256']))
        test.enterContext(patch.object(p, 'READINESS_SHA', self.readiness['sha256']))


class CertifiedQualityProtectionV2(unittest.TestCase):
    def fixture(self, damage=None):
        temporary = tempfile.TemporaryDirectory(prefix='certified-quality-protection-guards-')
        self.addCleanup(temporary.cleanup)
        fixture = Fixture(Path(temporary.name), damage)
        fixture.context(self)
        return fixture

    def test_valid_closed_receipts_publish_exact_independent_readonly_copy_and_preserve_prior_policy(self):
        f = self.fixture()
        prior = f.put(f.destination/'previous-incumbent.pt', b'older protected original')
        before = p.verify(f.job, f.job_pin, reader)
        self.assertTrue(before['assessment']['all_candidate_gates_passed'])
        result = p.publish(f.job, f.job_pin, reader)
        final = reader.pin(result['protected_checkpoint'])
        self.assertEqual(final['sha256'], f.source['sha256'])
        self.assertEqual(final['identity']['mode'], '0o444')
        self.assertEqual(final['identity']['nlink'], 1)
        self.assertNotEqual(final['identity']['inode'], f.source['identity']['inode'])
        self.assertEqual(reader.pin(prior['path']), prior)
        metadata = reader.read_pin(reader.pin(str(result['protected_checkpoint'])+'.json'))
        self.assertEqual(metadata['assessment'], before['assessment'])
        self.assertFalse(metadata['managed_incumbent_updated'])
        self.assertFalse(metadata['live_learner_restored'])
        with self.assertRaises(ValueError):
            p.publish(f.job, f.job_pin, reader)
        self.assertEqual(reader.pin(result['protected_checkpoint']), final)

    def test_original_failed_scope_incomplete_descriptors_wrong_argv_resources_and_invalid_review_reject(self):
        for damage in ['controller_exit', 'native_exit', 'missing_descriptor', 'argv', 'resources', 'invalid']:
            with self.subTest(damage=damage):
                f = self.fixture(damage)
                with self.assertRaises(ValueError):
                    p.publish(f.job, f.job_pin, reader)
                self.assertEqual(list(f.destination.iterdir()), [])

    def test_pooled_rescue_median_regression_zero_and_forged_statistics_cannot_publish(self):
        for damage in ['pooled_rescue', 'median', 'zero', 'forged_decision']:
            with self.subTest(damage=damage):
                f = self.fixture(damage)
                with self.assertRaises(ValueError):
                    p.publish(f.job, f.job_pin, reader)
                self.assertEqual(list(f.destination.iterdir()), [])

    def test_evidence_drift_while_copying_prevents_publication_and_removes_only_new_partials(self):
        f = self.fixture()
        verified = p.verify(f.job, f.job_pin, reader)
        with patch.object(p, 'verify', side_effect=[verified, ValueError('synthetic changed receipt')]):
            with self.assertRaises(ValueError):
                p.publish(f.job, f.job_pin, reader)
        self.assertEqual(list(f.destination.iterdir()), [])
        self.assertEqual(reader.pin(f.source['path']), f.source)

    def test_missing_original_assessment_never_creates_a_protected_copy(self):
        f = self.fixture()
        altered = copy.deepcopy(f.job)
        altered['assessment_report']['path'] = str(f.root/'missing-original-assessment.json')
        with self.assertRaises(FileNotFoundError):
            p.publish(altered, f.job_pin, reader)
        self.assertEqual(list(f.destination.iterdir()), [])

    def test_all64_two_per_slot_full_tails_and_exact_selection_are_required(self):
        for damage in ['fifty_not_sixty_four','one_and_three','unfinished_tail','abandoned_tail','changed_descriptor']:
            with self.subTest(damage=damage):
                f=self.fixture(damage)
                with self.assertRaises(ValueError):p.publish(f.job,f.job_pin,reader)
                self.assertEqual(list(f.destination.iterdir()),[])

    def test_non_archive_launch_inputs_require_full_original_readiness_identity(self):
        for damage in ['input_not_held','launch_input_drift','launch_input_mode']:
            with self.subTest(damage=damage):
                f=self.fixture(damage)
                with self.assertRaises(ValueError):p.publish(f.job,f.job_pin,reader)
                self.assertEqual(list(f.destination.iterdir()),[])

    def test_full_publication_accepts_only_exact_originally_held_symlink(self):
        f = self.fixture('held_symlink')
        self.assertTrue(Path(f.held_input['path']).is_symlink())
        previous = load('_previous_symlink_rejection_regression', Path('/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/quality32-protected1741-vs-currentLR125-quota64Protocol-firstSave-original01-preparation-20261024/winner-protection-quota64Protocol-future-original01/protect_quota64Protocol3045_owned_winner_v1.py'))
        held_controller = load('_guard_actual_held_controller', p.CONTROLLER)
        with self.assertRaises(ValueError):
            previous.verify_held_launch_pin(f.held_ABI, reader.read_pin(f.readiness), held_controller, reader)
        result = p.publish(f.job, f.job_pin, reader)
        self.assertEqual(reader.pin(result['protected_checkpoint'])['sha256'], f.source['sha256'])
        self.assertEqual(reader.pin(f.held_input['path']), f.held_input)

    def test_symlink_retarget_with_identical_bytes_rejects_original_identity_drift(self):
        f = self.fixture('held_symlink')
        alias = Path(f.held_input['path'])
        target = alias.resolve(strict=True)
        replacement = f.root/'same-bytes-different-inode'
        replacement.write_bytes(target.read_bytes())
        replacement.chmod(0o775)
        alias.unlink()
        alias.symlink_to(replacement.name)
        self.assertEqual(reader.pin(alias)['sha256'], f.held_input['sha256'])
        self.assertNotEqual(reader.pin(alias)['identity']['inode'], f.held_input['identity']['inode'])
        with self.assertRaises(ValueError):
            p.publish(f.job, f.job_pin, reader)
        self.assertEqual(list(f.destination.iterdir()), [])

    def test_unheld_symlink_alias_to_same_target_rejects(self):
        f = self.fixture('held_symlink')
        held_controller = load('_guard_unheld_alias_controller', p.CONTROLLER)
        alias = f.root/'unheld-alias'
        alias.symlink_to(Path(f.held_input['path']).resolve(strict=True).name)
        entry = held_controller.pin(alias)
        with self.assertRaises(ValueError):
            p.verify_held_launch_pin(entry, reader.read_pin(f.readiness), held_controller, reader)
        self.assertEqual(list(f.destination.iterdir()), [])

    def test_changed_held_symlink_target_bytes_rejects(self):
        f = self.fixture('held_symlink')
        with Path(f.held_input['path']).resolve(strict=True).open('ab') as stream:
            stream.write(b'changed target bytes')
            stream.flush()
            os.fsync(stream.fileno())
        with self.assertRaises(ValueError):
            p.publish(f.job, f.job_pin, reader)
        self.assertEqual(list(f.destination.iterdir()), [])

    def test_original_publication_implementation_retained_default_inert_and_no_scientific_main_called(self):
        def functions(path):
            return {n.name: ast.dump(n, include_attributes=False)
                for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}
        previous = functions(B.parent/'quality_capacity_proposal/protect_quality32_winner_v7.py')
        current = functions(Path(p.__file__))
        for name in ['publish', 'fsync_directory']:
            self.assertEqual(previous[name], current[name])
        result = subprocess.run(['/usr/bin/python3.12', '-I', '-B', p.__file__],
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(result.stdout.startswith('PLAN_ONLY'))
        self.assertEqual(result.stderr, '')
        self.assertNotIn('torch', sys.modules)
        calls = [node for node in ast.walk(ast.parse(Path(p.__file__).read_text())) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(node.func, ast.Attribute) and node.func.attr in ['execute', 'main', 'run'] for node in calls))


if __name__ == '__main__':
    unittest.main(verbosity=2)
