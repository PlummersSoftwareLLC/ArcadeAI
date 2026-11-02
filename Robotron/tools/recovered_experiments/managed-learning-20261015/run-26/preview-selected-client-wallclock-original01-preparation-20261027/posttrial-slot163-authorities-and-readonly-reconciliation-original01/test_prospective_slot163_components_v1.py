"""New pure future-metadata and fake-exec checks; no current binding/actor action.

Historical192 records seed CPU fixtures. New PID/CID/inodes below are explicitly
synthetic and are never published as actual state. Old8/9 suites are not run.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
P = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = load('_new_reconciliation', HERE / 'prepare_slot163_readonly_reconciliation_v1.py')
        cls.out = load('_new_output_authority', HERE / 'posttrial_slot163_output_authority_v1.py')
        cls.selected = load('_new_selected_collector', HERE / 'supervised_main_fleet_slot163_preview_v3.py')
        game = Path('/home/dave/source/repos/ArcadeAI/Robotron')
        cls.base = load('_old_collector', game / 'tools/quality_capacity_proposal/supervised_main_fleet_v2.py')
        cls.window = load('_old_window', game / 'tools/lr125_survival_trial_proposal_20261023/window_observer.py')
        cls.counter = load('_old_counter', game / 'tools/live_lr_recipe_continuation_proposal/observer.py')
        cls.execbase = load('_old_exec_base', P / 'role-bound-wrapper-trial-original01/exec_role_bound_mame_v1.py')
        cls.census = json.loads((P / 'owned-actor-rollout-options-original01/read-only-original192-census-and-actual-role-map.json').read_bytes())
        cls.old = json.loads(Path(cls.census['binding']['path']).read_bytes())
        cls.policy = json.loads(Path(cls.old['supervision_policy']['path']).read_bytes())
        cls.manifest = json.loads((P / 'role-bound-wrapper-trial-original01/prospective-slot163-manifest.json').read_bytes())

    def api(self, timestamp):
        roles = self.census['actual192_role_map']
        optimizer = dict(schema='robotron-optimizer-exposure-v1', enabled=True, available=True,
            process_id=self.old['owner']['pid'], instance_monotonic_ns=101, epoch=1, epoch_reason='CPUfixture',
            total=dict(attempts_started=6, outcomes_recorded=6, applied=6, amp_skipped=0, unavailable=0),
            since_epoch=dict(attempts_started=6, outcomes_recorded=6, applied=6, amp_skipped=0, unavailable=0),
            unclassified_started_total=0)
        replay = dict(schema='robotron-replay-insert-exposure-v1', enabled=True, available=True,
            process_id=self.old['owner']['pid'], instance_monotonic_ns=102, epoch=1, epoch_reason='CPUfixture',
            accepted_total=15, accepted_learner_total=15,
            accepted_by_source_total=dict(dqn=12, epsilon=3, expert=0, eval=0, unattributed=0))
        pipeline = dict(schema='robotron-host-pipeline-v1', available=True, generation=10,
            learning_exposure=dict(optimizer=optimizer, replay=replay))
        for key in ('inference', 'actor_refresh', 'target_refresh', 'learner_priority'):
            pipeline[key] = dict(errors=0)
        return dict(client_count=192, client_rows=[dict(client_slot=r['slot'], client_id=r['connection_id'],
            eval=r['eval']) for r in roles], training_enabled=True, measurement_active=False,
            managed_experiment=self.old['experiment'], lr=6.25e-6,
            pipeline_read_error='', bank_persistence_read_error='', ts=timestamp,
            pipeline_snapshot_age_s=.1, host_pipeline=pipeline, bank_persistence=dict(write_failures=0),
            frame_count=100, learner_frame_count=40, training_steps=6, optimized_samples=24576)

    def fixture(self):
        before = copy.deepcopy(self.census['actual_snapshot'])
        before.update(collection_started_unix_s=2999.9, collection_started_monotonic_s=2999.9,
                      unix_s=3000., monotonic_s=3000.)
        after = copy.deepcopy(before)
        after.update(collection_started_unix_s=3000.9, collection_started_monotonic_s=3000.9,
                     unix_s=3001., monotonic_s=3001.)
        target = after['actors']['163']
        target['pid'] = 99_999_999; target['starttime_ticks'] += 20_000
        target['command'][target['command'].index('-autoboot_script') + 1] = self.manifest['target_lua']['path']
        target['environment']['ROBOTRON_EVAL_MODE'] = '1'
        after['previous_birth_probes']['163'] = None
        ready = copy.deepcopy(after)
        ready['previous_birth_probes']['163'] = target['starttime_ticks']
        first = self.api(3000.)
        last = self.api(3001.)
        next(r for r in last['client_rows'] if r['client_slot'] == 163)['client_id'] = 999_999
        values = dict(prior_binding=self.old, before_snapshot=before,
            after_old_birth_probe_snapshot=after, new_registry_snapshot=ready,
            before_API=first, after_API=last)
        pins = {key: dict(path='/CPUfixture/' + key, sha256='a' * 64, bytes=10, identity={})
                for key in self.rec.REQUIRED_EXTRA}
        pins['target_lua'] = self.manifest['target_lua']
        pins['installed_wrapper']['path'] = '/home/dave/source/repos/ArcadeAI/Robotron/tools/mame_with_socket_wait.sh'
        pins['launcher']['path'] = '/home/dave/source/repos/ArcadeAI/Robotron/startmame.sh'
        claim = dict(schema='robotron-slot163-exec-reservation-consumed-v1',
            status='CONSUMED_RESERVATION_NOT_PROOF_OF_SUCCESSFUL_EXEC',
            claimant_pid=target['pid'], claimant_birth=target['starttime_ticks'], command=target['command'],
            observed_parent=dict(pid=self.policy['fleet']['pid'],
                starttime_ticks=self.policy['fleet']['starttime_ticks'], prior_actor_birth_absent=True),
            original_permit=pins['single_use_permit'], manifest=pins['launch_input_manifest'])
        values['trial_claim'] = claim
        facts = {key: dict(path='/CPUfixture/fact-' + key) for key in self.rec.FACTS}
        release = dict(schema='robotron-root-fixed03-preview-freeze-release-v1',
            all_four_legs_qualified=True, all_owned_scopes_closed=True, trial_wrapper_source_sha256='a' * 64)
        plan = dict(schema='robotron-slot163-prospective-reconciliation-plan-v1',
            root_freeze_release=dict(path='/CPUfixture/release'), max_handoff_s=45,
            selected_was_historical_original_actor=True, facts=facts, extra_pins=pins)
        def read(pin, as_json=True):
            if not as_json: return b'CPUfixture authenticated small source'
            if pin == plan['root_freeze_release']: return copy.deepcopy(release)
            if pin == self.old['supervision_policy']: return copy.deepcopy(self.policy)
            if pin == self.old['baseline_API']: return self.api(3000.)
            for key, entry in facts.items():
                if pin == entry: return copy.deepcopy(values[key])
            raise ValueError('Unexpected CPUfixture read')
        return plan, read, values

    def prepare(self, plan, read):
        return self.rec.prepare(plan, read, self.base, self.selected, self.counter.normalise, self.window)

    def test_exact_collector_delta_and_old_policy_negative(self):
        path = Path(self.base.__file__); original = path.read_bytes()
        selected = Path(self.selected.__file__).read_bytes()
        old = b"and actor['environment']['ROBOTRON_EVAL_MODE'] == '0',"
        new = b"and actor['environment']['ROBOTRON_EVAL_MODE'] == ('1' if slot == '163' else '0'),"
        self.assertEqual(original.count(old), 1)
        self.assertEqual(selected.replace(new, old), original)
        plan, read, _ = self.fixture(); prepared = self.prepare(plan, read)
        with self.assertRaises(ValueError): self.base.validate_policy(prepared['policy'])
        self.selected.validate_policy(prepared['policy'])

    def test_future_facts_produce_only_pending_binding_and_explicit_extra_holds(self):
        plan, read, values = self.fixture(); prepared = self.prepare(plan, read)
        binding = prepared['binding_requiring_actual_policy_and_transition_pins']
        self.assertIsNone(binding['supervision_policy']); self.assertIsNone(binding['preview_slot163_transition'])
        self.assertEqual(binding['owner'], self.old['owner'])
        self.assertTrue(all(binding['held_hashes'][k] == v for k, v in self.old['held_hashes'].items()))
        self.assertGreater(len(binding['held_hashes']), len(self.old['held_hashes']))
        self.assertEqual(binding['preview_actual_roles']['163'], dict(connection_id=999_999, eval=True))
        self.assertEqual(binding['historical_original_actor_survivors'], 188)
        self.assertEqual(binding['verified_between_study_replacement_count'], 4)
        for actor in binding['actors']:
            if actor['slot'] != 163:
                self.assertEqual(actor, next(x for x in self.old['actors'] if x['slot'] == actor['slot']))
        self.assertTrue(prepared['transition']['weights_continue_evolving_under_training'])

    def test_unfilled_actuals_and_unrelated_changes_fail(self):
        for change in ('unfilled', 'otherPID', 'otherCID', 'otherRole', 'selectedRole', 'selectedArgs', 'oldBirthLives'):
            plan, read, values = self.fixture()
            if change == 'unfilled': plan['facts']['new_registry_snapshot'] = None
            if change == 'otherPID': values['after_old_birth_probe_snapshot']['actors']['10']['pid'] += 1
            if change == 'otherCID': values['after_API']['client_rows'][10]['client_id'] = 777_777
            if change == 'otherRole': values['after_API']['client_rows'][10]['eval'] = not values['after_API']['client_rows'][10]['eval']
            if change == 'selectedRole': next(x for x in values['after_API']['client_rows'] if x['client_slot'] == 163)['eval'] = False
            if change == 'selectedArgs': values['after_old_birth_probe_snapshot']['actors']['163']['command'] += ['--different']
            if change == 'oldBirthLives': values['after_old_birth_probe_snapshot']['previous_birth_probes']['163'] = self.policy['baseline_actors']['163']['starttime_ticks']
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                self.prepare(plan, read)

    def test_replay_optimizer_identity_cannot_reset_and_old_holds_cannot_change(self):
        plan, read, values = self.fixture()
        values['after_API']['host_pipeline']['learning_exposure']['replay']['epoch'] += 1
        with self.assertRaises(ValueError): self.prepare(plan, read)
        plan, read, _ = self.fixture()
        plan['extra_pins']['target_lua'] = dict(plan['extra_pins']['target_lua'], sha256='0' * 64)
        with self.assertRaises(ValueError): self.prepare(plan, read)

    def test_persistent_and_rollback_output_keep_original_INPUT_and_explicit_eval(self):
        row = self.manifest['slots']['163']; environment = dict(row['expected_environment'])
        for mode, source in ((self.out.ACCEPT, self.manifest['target_lua']),
                             (self.out.ROLLBACK, self.manifest['original_lua'])):
            authority = dict(mode=mode, output_lua=source)
            command, output = self.out.prepare_output(authority, self.manifest,
                    row['expected_args'], environment, self.execbase)
            self.assertEqual(command[command.index('-autoboot_script') + 1], source['path'])
            self.assertEqual(output['ROBOTRON_EVAL_MODE'], '1')
            expected = dict(environment); expected['ROBOTRON_EVAL_MODE'] = '1'
            self.assertEqual(output, expected)
            with self.assertRaises(ValueError):
                self.out.prepare_output(authority, self.manifest, command[1:], output, self.execbase)
        wrong = dict(mode=self.out.ROLLBACK, output_lua=self.manifest['target_lua'])
        with self.assertRaises(ValueError):
            self.out.prepare_output(wrong, self.manifest, row['expected_args'], environment, self.execbase)

    def test_new_output_modes_reach_only_temporary_fake_with_correct_Lua_and_role(self):
        with tempfile.TemporaryDirectory(prefix='posttrial literal $ ') as directory:
            root = Path(directory); fake = root / 'fake MAME only.py'
            fake.write_text('#!/usr/bin/python3.12\nimport json,os,sys\n'
                'print(json.dumps(dict(argv=sys.argv,eval=os.environ["ROBOTRON_EVAL_MODE"],literal=os.environ["LITERAL"])))\n')
            fake.chmod(0o555)
            row = self.manifest['slots']['163']; environment = dict(row['expected_environment'], LITERAL="spaces $ ; ` ' preserved")
            for mode, source in ((self.out.ACCEPT, self.manifest['target_lua']),
                                 (self.out.ROLLBACK, self.manifest['original_lua'])):
                command, output = self.out.prepare_output(dict(mode=mode, output_lua=source), self.manifest,
                    row['expected_args'], environment, self.execbase)
                self.assertEqual(command[0], '/usr/games/mame')
                # Test-harness substitution only; never execute actual MAME.
                # Waitenv equality is checked above; avoid loading its shim into the Python fake here.
                output = dict(output); output.pop('LD_PRELOAD')
                result = subprocess.run([str(fake), *command[1:]], env=output,
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                recorded = json.loads(result.stdout)
                self.assertEqual(recorded['eval'], '1')
                self.assertEqual(recorded['literal'], environment['LITERAL'])
                self.assertEqual(recorded['argv'][recorded['argv'].index('-autoboot_script') + 1], source['path'])

    def test_complete_future_authority_requires_actual_adopted_binding_or_explicit_rollback(self):
        plan, old_read, values = self.fixture(); prepared = self.prepare(plan, old_read)
        policy_pin = dict(path='/CPUfixture/published-policy')
        transition_pin = dict(path='/CPUfixture/published-transition')
        binding_pin = dict(path='/CPUfixture/published-binding')
        selection_pin = dict(path='/CPUfixture/ROOT-selection')
        fresh_pin = dict(path='/CPUfixture/fresh-parent')
        outcome_pin = dict(path='/CPUfixture/closed-trial')
        table = {policy_pin['path']: prepared['policy'], transition_pin['path']: prepared['transition'],
                 fresh_pin['path']: values['before_snapshot']}
        def read(entry, as_json=True):
            if entry['path'] in table: return copy.deepcopy(table[entry['path']])
            return old_read(entry, as_json)
        binding = self.rec.finalize(prepared, policy_pin, transition_pin, read)
        table[binding_pin['path']] = copy.deepcopy(binding)
        prior = values['after_old_birth_probe_snapshot']['actors']['163']
        manifest_pin = dict(self.original_manifest_pin())
        authority = dict(schema='robotron-slot163-posttrial-output-authority-v1', mode=self.out.ACCEPT,
            root_selection=selection_pin, fresh_parent_snapshot=fresh_pin,
            supervisor_owner=self.policy['fleet'],
            supervisor_process=values['before_snapshot']['owners']['fleet']['process'],
            prior_actor=prior, base_manifest=manifest_pin, output_lua=self.manifest['target_lua'],
            claim_directory=None)
        selection = dict(schema='robotron-root-slot163-output-selection-v1', mode=authority['mode'],
            base_manifest=manifest_pin, output_lua=authority['output_lua'], fresh_parent_snapshot=fresh_pin,
            prior_actor=prior, root_freeze_release=plan['root_freeze_release'],
            accepted_output_binding=binding_pin, operational_benchmark_accepted=True)
        table[selection_pin['path']] = selection
        self.assertEqual(self.out.validate_authority(authority, read, self.execbase), self.manifest)
        table[binding_pin['path']]['supervision_policy'] = None
        with self.assertRaises(ValueError): self.out.validate_authority(authority, read, self.execbase)
        table[binding_pin['path']] = binding
        authority.update(mode=self.out.ROLLBACK, output_lua=self.manifest['original_lua'],
                         claim_directory=dict(path='/CPUfixture/NEW-rollback-claim-directory',
                                              identity=dict(device=1, inode=2)))
        selection.update(mode=self.out.ROLLBACK, output_lua=self.manifest['original_lua'],
                         closed_trial_outcome=outcome_pin, explicit_rollback_selected=True)
        claim_pin = dict(path='/CPUfixture/original-trial-claim')
        permit_pin = dict(path='/CPUfixture/original-trial-permit')
        table[claim_pin['path']] = dict(schema='robotron-slot163-exec-reservation-consumed-v1',
            original_permit=permit_pin, manifest=manifest_pin,
            claimant_pid=prior['pid'], claimant_birth=prior['starttime_ticks'])
        table[permit_pin['path']] = dict(claim_directory=dict(path='/CPUfixture/OLD-trial-directory',
                                                            identity=dict(device=1, inode=1)))
        table[outcome_pin['path']] = dict(schema='robotron-root-closed-slot163-preview-trial-outcome-v1',
            prior_owned_process=prior, original_trial_permit_retained=True, actual_outcome_preserved=True,
            original_trial_claim=claim_pin, original_trial_permit=permit_pin)
        self.assertEqual(self.out.validate_authority(authority, read, self.execbase), self.manifest)
        table[claim_pin['path']]['claimant_pid'] = self.policy['baseline_actors']['163']['pid']
        with self.assertRaisesRegex(ValueError, 'OUTPUT claimant'):
            self.out.validate_authority(authority, read, self.execbase)
        table[claim_pin['path']]['claimant_pid'] = prior['pid']
        authority['output_lua'] = self.manifest['target_lua']
        with self.assertRaises(ValueError): self.out.validate_authority(authority, read, self.execbase)
        authority['root_selection'] = None
        with self.assertRaises(ValueError): self.out.validate_authority(authority, read, self.execbase)

    def original_manifest_pin(self):
        path = P / 'role-bound-wrapper-trial-original01/prospective-slot163-manifest.json'
        s = path.lstat(); raw = path.read_bytes()
        return dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
            identity=dict(device=s.st_dev, inode=s.st_ino, bytes=s.st_size, mtime_ns=s.st_mtime_ns,
                          ctime_ns=s.st_ctime_ns, mode=oct(s.st_mode & 0o777), uid=s.st_uid, nlink=s.st_nlink))

    def test_actual_entry_is_default_inert_and_unfilled_execute_refuses_before_MAME(self):
        source = HERE / 'posttrial_slot163_output_authority_v1.py'
        default = subprocess.run(['/usr/bin/python3.12', '-I', '-B', str(source)],
                                 capture_output=True, text=True, timeout=10)
        self.assertEqual(default.returncode, 0)
        self.assertIn('PLAN_ONLY', default.stdout)
        with tempfile.TemporaryDirectory(prefix='unfilled output authority ') as directory:
            root = Path(directory); helper = root / 'exact helper.py'; helper.write_bytes(source.read_bytes()); helper.chmod(0o444)
            authority = dict(schema='robotron-slot163-posttrial-output-authority-v1', mode=self.out.ROLLBACK,
                root_selection=None, fresh_parent_snapshot=None, supervisor_owner=None,
                supervisor_process=None, prior_actor=None, base_manifest=None, output_lua=None, claim_directory=None)
            path = root / 'unfilled authority.json'; path.write_text(json.dumps(authority)); path.chmod(0o444)
            game = Path('/home/dave/source/repos/ArcadeAI/Robotron')
            command = ['/usr/bin/python3.12', '-I', '-B', str(helper), '--execute',
                '--base-helper', self.execbase.__file__, '--fuse-helper',
                str(P / 'role-bound-wrapper-trial-original02-single-use/exec_role_bound_mame_once_v2.py'),
                '--collector-source', str(game / 'tools/quality_capacity_proposal/supervised_main_fleet_v2.py'),
                '--authority', str(path), '--authority-sha256', hashlib.sha256(path.read_bytes()).hexdigest(),
                '--expected-source-sha256', hashlib.sha256(helper.read_bytes()).hexdigest(), '--',
                *self.manifest['slots']['163']['expected_args']]
            rejected = subprocess.run(command, capture_output=True, text=True, timeout=10)
            self.assertEqual(rejected.returncode, 2)
            self.assertIn('Future actual authority/parent/registry facts are unfilled', rejected.stderr)


if __name__ == '__main__':
    unittest.main()
