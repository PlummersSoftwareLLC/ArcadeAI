"""New5400/min50 composed quality scope with actual journals and synthetic peers.

Only non-test fixture helpers are reused. No old test/scientific main, real
emulator, neural model, GPU context, production write or policy gate is run.
"""
import ast
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

B=Path(__file__).resolve().parent
sys.path.insert(0,str(B))

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

games=load('_quality_composed_game_audit',B/'audit_quality32_games_v1.py')
wire=load('_quality_composed_wire_audit',B/'audit_quality32_wire_v1.py');wire.dependencies()
runtime=load('_quality_composed_runtime',B/'run_compiled_full_tail32_quality2259_v1.py')
control=load('_quality_composed_control',B/'control_compiled_full_tail32_quality2259_v1.py')
review=load('_quality_composed_review',B/'read_compiled_quality32_2259_original_v1.py')
jdefs=load('_consumed_journal_fixture_helpers_only',B/'test_audit_full_tail_games_v1.py')
wdefs=load('_consumed_wire_fixture_helpers_only',B/'test_audit_full_tail_wire_v1.py')
metadata=load('_consumed_metadata_fixture_helpers_only',B/'test_full_tail_final_scope_v1.py')
host=jdefs.defs

class QualityHostFixture(host.Fixture):
    """New fixture admission; original primary classes/functions are unchanged."""
    def __init__(self,role='reference'):
        self.temp=tempfile.TemporaryDirectory(prefix='robotron-quality54-min50-fixture-')
        self.wall=1_000_000_000_000;self.mono=50_000_000_000
        selected=runtime.POLICIES[role];clocks=selected['clocks']
        self.agent=host.SyntheticAgent();self.agent.training_steps=clocks['training_steps']
        self.agent.optimized_samples=clocks['optimized_samples']
        self.metrics=SimpleNamespace(lock=threading.Lock(),training_enabled=False,
            learner_frame_count=clocks['learner_frame_count'],total_training_steps=self.agent.training_steps,
            total_optimized_samples=self.agent.optimized_samples,measurement_active=False,
            measurement_generation=0,measurement_label='',ratchet_frozen=False)
        self.journal=host.journal_module.GameJournal(self.temp.name,clock=lambda:self.wall/1e9,
            completion_policy='confirmed_reset_reserves_v1')
        self.controller=host.controller_module.ManagedMeasurement(self.agent,self.metrics,self.journal,
            clock=lambda:self.wall/1e9,boundary_status=lambda generation:
                dict(ready=True,generation=generation,actor_slots=host.SLOTS))
        self.controller.enter('new-quality54-min50-'+role,cohort_s=5400,timeout_s=9000)
        self.controller.tick()
        self.policy=dict(checkpoint_sha256=selected['sha256'],policy_load_id='b'*64,
            measurement_active=True,measurement_generation=1,experiment=self.controller.label,
            training_enabled=False,replay_enabled=False,epsilon=0.,expert_ratio=0.,
            learner_frame_count=clocks['learner_frame_count'],training_steps=clocks['training_steps'],
            optimized_samples=clocks['optimized_samples'])
        self.window=dict(open_unix_ns=int(self.controller.start_ts*1e9),
            close_unix_ns=int(self.controller.close_ts*1e9),generation=1,experiment=self.controller.label)
        self.context=dict(experiment=self.controller.label,measurement_active=True,measurement_generation=1,
            epsilon=0.,expert_ratio=0.,difficulty=5,learner_frames=clocks['learner_frame_count'],
            training_steps=clocks['training_steps'],optimized_samples=clocks['optimized_samples'])
        self.subjects=[dict(slot=s,session=f'{s:032x}',connection=f'{s+10000:032x}')for s in host.SLOTS]
        self.gate=host.drain.CohortDrain(self.journal,self.controller,subjects=self.subjects,
            policy_reader=lambda:self.policy,admission_reader=lambda:self.window,
            wall_ns=lambda:self.wall,monotonic_ns=lambda:self.mono)
        self.states={};self.bindings={};self.advance(1_000_000)
        for subject in self.subjects:self.certify(subject)

class QualityFleetWithoutFirst(QualityHostFixture):
    def certify(self,subject):
        if subject['slot']!=4096:super().certify(subject)

class QualityGamesFixture(jdefs.Fixture):
    def __init__(self,extra=18,role='reference'):
        self.f=QualityHostFixture(role);self.certified={}
        f=self.f;unknown={r['client_slot']:r for r in f.journal.completed}
        for slot,binding in f.bindings.items():
            game=f.journal.measurement_games[binding['journal_game_id']]
            self.certified[slot]=dict(binding,previous_journal_game_id=unknown[slot]['journal_game_id'],
                game_uid=game['game_uid'])
        extras=set(host.SLOTS[:extra])
        for slot in sorted(extras):
            self.finish(slot);f.advance(100_000)
            f.journal.observe(slot-4000,host.frame(player_alive=True,game_score=9_000_000),f.states[slot],
                context=lambda:f.context)
        f.closed()
        for slot in host.SLOTS:self.finish(slot,score=9_000_000 if slot in extras else None,
            next_wave=1 if slot==4096 else 7)
        f.controller.tick();self.cohort=copy.deepcopy(f.controller.status()['cohort'])
        assert self.cohort['complete']and self.cohort['valid']
        for slot in host.SLOTS:f.journal.disconnect(slot-4000,lambda:f.context)
        self.payloads={name:(Path(f.temp.name)/name).read_bytes()for name in
            ('games.jsonl','measurement_starts.jsonl','lives.jsonl')}

class QualityCombinedScopeV1(unittest.TestCase):
    def fixture(self,extra=18,role='reference'):
        value=QualityGamesFixture(extra,role);self.addCleanup(value.close);return value

    def test_primary_journal_genuine50_games_all32_slots_zero_extras_and_saved_policy_contexts_join(self):
        for role in ('reference','candidate'):
            with self.subTest(role=role):
                f=self.fixture(role=role);result=games.review(**f.args())
                self.assertEqual(result['statistics']['count'],50)
                self.assertEqual(len(result['admitted_ids']),50)
                self.assertEqual(len(result['terminal_links']),50);self.assertEqual(len(result['rom_links']),50)
                self.assertEqual(sum(row['verified_lives']for row in result['life_links']),50)
                self.assertEqual(result['certified_initial_games'],32)
                self.assertEqual(result['statistics']['score_sum'],sum(row['score']for row in f.cohort['rows']))
                self.assertTrue(any(row['score']==0 for row in f.cohort['rows']))
                self.assertGreaterEqual(len(result['retained_outside_cohort_ids']),32)
                self.assertFalse(result['full_game_score_verified']);self.assertFalse(result['quality_qualified'])
        self.assertNotIn('torch',sys.modules)

    def test_minimum49_and_engineering32_reject_while_extra51_and_all_original_zeros_remain_counted(self):
        for extra in (0,17):
            f=self.fixture(extra=extra)
            with self.assertRaises(ValueError):games.review(**f.args())
        f=self.fixture(extra=19);result=games.review(**f.args())
        self.assertEqual(result['statistics']['count'],51)
        self.assertEqual(result['statistics']['score_sum'],sum(row['score']for row in f.cohort['rows']))
        with self.assertRaises(ValueError):jdefs.audit.review(**f.args())

    def test_changed_window_missing_life_start_terminal_clocks_and_forged_statistics_reject(self):
        f=self.fixture()
        for damage in ('window','life','start','terminal','clock','statistics','unknown'):
            with self.subTest(damage=damage):
                args=f.args();row=args['cohort']['rows'][1];jid=row['journal_game_id']
                if damage=='window':args['window']['close_unix_ns']+=1
                elif damage in ('life','start'):
                    name='lives.jsonl'if damage=='life'else'measurement_starts.jsonl'
                    args['payloads'][name]=b''.join(games.canonical(r)+b'\n'for r in games.lines(args['payloads'][name])
                        if r['journal_game_id']!=jid)
                elif damage=='terminal':
                    row['terminal_confirmation']['previous_raw_reserves']=1
                    jdefs.update_row(args['payloads'],'games.jsonl',jid,lambda value:value.update(row))
                elif damage=='clock':
                    jdefs.update_row(args['payloads'],'lives.jsonl',jid,
                        lambda value:value['context'].update(learner_frames=f.f.policy['learner_frame_count']+1))
                elif damage=='statistics':args['cohort']['mean']+=1
                else:
                    prior=args['certified'][4096]['previous_journal_game_id']
                    jdefs.update_row(args['payloads'],'games.jsonl',prior,lambda value:value.update(known_start=True))
                with self.assertRaises(ValueError):games.review(**args)

    def test_new5400_wire_prefix_recomputes_original_bytes_and_job_binding_without_90s_reader(self):
        # Patch the consumed fixture factory only; primary runtime classes and
        # source bodies are untouched and create genuinely new5400 certificates.
        with patch.object(wdefs.defs,'FleetWithoutFirst',QualityFleetWithoutFirst):f=wdefs.Fixture()
        self.addCleanup(f.close)
        result=wire.audit_slot_prefix(4096,f.entry,f.job,f.result,f.starts,f.games,f.read,wdefs.h.pin,
            expected_job_sha256=wdefs.audit.JOB_SHA)
        self.assertEqual(result['original_exchanges'],1200)
        self.assertTrue(result['prefix_ledger']['raw_prefix_ledger_recomputed'])
        self.assertEqual(result['session'],f.subject['session'])
        with self.assertRaises(ValueError):wire.audit_slot_prefix(4096,f.entry,f.job,f.result,f.starts,
            f.games,f.read,wdefs.h.pin,expected_job_sha256='f'*64)
        tail=wire.audit_applied_tail(**f.tail_args())
        self.assertTrue(tail['actual_Lua_STOP_application_joined'])
        self.assertFalse(tail['raw_tail_ledger_recomputed'])

    def test_each_fixed_role_native_and_review_scope_joins_min50_actual_journal_and_owned_exit_fields(self):
        helper=metadata.FinalFullTailScope();self.addCleanup(helper.doCleanups)
        for leg in ('R1','C1','R2','C2'):
            with self.subTest(leg=leg):
                directory,job,jp,cfg,scope=helper.documents();selected=runtime.POLICIES[runtime.ROLES[leg]]
                job.update(schema='robotron-compiled-full-tail32-quality-original-v1',quality_leg=leg,
                    quality_pair_precommit={'sha256':runtime.PAIR_SHA},minimum_completed_games=50,
                    expected_policy_clocks=copy.deepcopy(selected['clocks']),admission_s=5400,
                    runtime=metadata.h.pin(B/'run_compiled_full_tail32_quality2259_v1.py'))
                job['checkpoint']['sha256']=selected['sha256'];cfg['argv'][4]=job['runtime']['path']
                cfg['argv'][11]=job['runtime']['sha256'];cfg['pins'][1]={'path':job['runtime']['path'],'sha256':job['runtime']['sha256']}
                scope.update(schema='robotron-original-all32-compiled-quality32-acceptance-v1',fixed_admission_s=5400,
                    minimum_quality_completed_games=50);scope.pop('minimum_engineering_completed_games')
                review.validate_scope(job,jp,scope,cfg);runtime.validate_job(job)
                path=directory/'quality-controller.json';path.write_text(json.dumps(cfg));control.checked_config(path)
                f=self.fixture(role=runtime.ROLES[leg]);original=helper.result()
                policy=copy.deepcopy(f.f.policy);policy['numeric_policy']=original['policy_before']['numeric_policy']
                original.update(schema='robotron-compiled-full-tail32-quality-original-result-v1',
                    status='PASS_ALL32_COMMON_COMPILED_CERTIFIED_QUALITY_COHORT_AND_HOST_DRAIN',
                    quality_leg=leg,quality_pair_precommit=job['quality_pair_precommit'],
                    expected_policy_clocks=job['expected_policy_clocks'],minimum_completed_games=50,
                    policy_before=policy,policy_after=copy.deepcopy(policy),before_intentional_stop=f.cohort,
                    after_intentional_stop=copy.deepcopy(f.cohort))
                original['controller_exit']['cohort']=copy.deepcopy(f.cohort)
                _,cohort=review.validate_runtime_result(original,job)
                self.assertEqual(cohort['count'],50);games.review(**f.args())
                for damage in ('exit','policy','missing_tail','unsealed','minimum','role'):
                    bad=copy.deepcopy(original)
                    if damage=='exit':bad['original_slots']['4096']['actual_exit']=None
                    elif damage=='policy':bad['policy_after']['training_steps']+=1
                    elif damage=='missing_tail':bad['before_intentional_stop']['rows'].pop()
                    elif damage=='unsealed':bad['all_original_threads_stopped']=False
                    elif damage=='minimum':bad['minimum_completed_games']=49
                    else:bad['quality_leg']='C3'
                    with self.assertRaises(ValueError):review.validate_runtime_result(bad,job)

    def test_terminal_ROM_life_transport_cleanup_and_main_health_predicate_bodies_stay_unchanged(self):
        def definitions(path):return {n.name:ast.dump(n,include_attributes=False)
            for n in ast.parse(path.read_text()).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
        for before,after,changed in [(B/'audit_full_tail_games_v1.py',Path(games.__file__),['review']),
                (B/'audit_full_tail_wire_v2.py',Path(wire.__file__),['dependencies','audit_slot_prefix'])]:
            a,b=definitions(before),definitions(after)
            self.assertEqual([name for name in a if a[name]!=b[name]],changed)
        self.assertNotIn('torch',sys.modules)

if __name__=='__main__':unittest.main(verbosity=2)
