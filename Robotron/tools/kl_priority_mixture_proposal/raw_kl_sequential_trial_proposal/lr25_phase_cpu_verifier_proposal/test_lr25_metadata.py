"""Unexecuted stdlib source/metadata guards; all PASS/owner/model fixtures are synthetic."""
import ast
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('_lr25_metadata_guards', HERE/'verify_phase_snapshot_lr25.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def pin(name):
    return dict(path='/fixture/'+name, sha256=hashlib.sha256(name.encode()).hexdigest(), bytes=20,
                identity=dict(device=1, inode=20, bytes=20, mtime_ns=1, ctime_ns=1,
                              mode='0o444', uid=os.getuid(), nlink=1))


def recipe():
    return dict(batch_size=4096, baseline_batch_size=512, epsilon=.1, expert_ratio=.1,
        n_step=3, max_samples_per_frame=8, c51_target_smoothing=0, learning_control_lr_scale=.25,
        lr_gear='climb', lr_anchor_step=0., optimizer_lr=1.25e-5, optimizer_eps=1.5e-4,
        fused=True, gamma=.995, num_atoms=51, v_min=-10., v_max=50.)


def fixture():
    owner=dict(pid=101, starttime_ticks=102, unit='fixture.service', invocation_id='a'*32,
               cgroup='/fixture.service')
    phase=dict(record=pin('phase.json'), boot_checkpoint=dict(path='/fixture/original-boot.pt', sha256='b'*64, bytes=100),
        boot_verification=pin('boot-CPU.json'), expected=dict(metric='ce', valid=True,
            phase_id='fixture', founder_phase_record_sha256=v.FOUNDER_SHA256,
            last_resume_record_sha256=None, root_precommit_sha256='c'*64,
            started_from=dict(path='/fixture/original-boot.pt', sha256='b'*64, bytes=100,
                              clocks=dict.fromkeys(v.CLOCKS, 10))))
    spec=dict(purpose='candidate', observed_clients=192, owner=owner, phase_record=phase['record'],
        boot_checkpoint=phase['boot_checkpoint'], boot_verification=phase['boot_verification'],
        expected_phase=phase['expected'])
    entry_source=dict(path='/fixture/managed-checkpoints/pre-change-entry.pt', sha256='d'*64, bytes=100)
    entry_job=dict(source=entry_source, phase_snapshot=copy.deepcopy(spec),
        source_control_context=dict(held_recipe_context=dict(recipe(), learning_control_lr_scale=.5, optimizer_lr=2.5e-5)))
    entry=dict(schema='robotron-phase-snapshot-checkpoint-CPU-result-v1', status='PASS',
        phase_metadata_verified=True, script=dict(sha256=v.ENTRY_PHASE_SHA256),
        strict_phase_base=dict(sha256=v.ENTRY_STRICT_SHA256), root_job=entry_job,
        saved_priority_metric_phase=dict(metric='ce', valid=True, phase_record_sha256=v.FOUNDER_SHA256),
        sha256=entry_source['sha256'], bytes=100, clocks=dict.fromkeys(v.CLOCKS, 20))
    pp, ep, rp = pin('future-root-precommit.json'), pin('future-entry-CPU.json'), pin('future-quality-release.json')
    pre=dict(schema='robotron-live-CE-lr25-hot-change-precommit-v1',
        status='ROOT_PRECOMMITTED_AFTER_QUALITY_CLOSURE_AND_FREEZE_RELEASE', experiment='fixture-lr25',
        owner=copy.deepcopy(owner), current_phase=copy.deepcopy(phase), entry_checkpoint=copy.deepcopy(entry_source),
        entry_CPU=ep, source_freeze_release=rp, quality_closed=True, lr_scale_before=.5, lr_scale_after=.25,
        optimizer_lr_before=2.5e-5, optimizer_lr_after=1.25e-5, no_weight_or_optimizer_reset=True, no_replay_clear=True)
    store={pp['path']:pre, ep['path']:entry, rp['path']:dict(source_freeze_released=True)}
    job=dict(experiment='fixture-lr25', phase_snapshot=spec, clock_floor=dict.fromkeys(v.CLOCKS, 21),
        lr25_context=dict(schema='robotron-live-CE-lr25-hot-control-context-v1', precommit=pp, entry_CPU=ep))
    evidence=dict(bound_files={})
    def read(p, ev, label):
        ev['bound_files'][label]=dict(mode='0o444', uid=os.getuid(), nlink=1)
        return store[p['path']]
    base=NS(HELD_RECIPE_CONTEXT=recipe(), pinned_json=read)
    return job, base, evidence, store, pre, entry


class LR25MetadataContracts(unittest.TestCase):
    def test_genuine_shape_hot_context_preserves_original_boot_and_entry(self):
        job, base, ev, store, pre, entry=fixture()
        v.check_lr25_context(job, base, ev)
        self.assertTrue(ev['lr25_hot_context_verified'])
        self.assertEqual(ev['lr25_entry_clocks'], entry['clocks'])
        self.assertNotEqual(pre['entry_checkpoint'], pre['current_phase']['boot_checkpoint'])
        self.assertEqual(len(ev['bound_files']), 3)

    def test_missing_wrong_context_and_false_or_coerced_declarations_refuse(self):
        for kind in ('missing', 'schema', 'status', 'closed', 'reset', 'replay', 'scale', 'bool'):
            job, base, ev, store, pre, entry=fixture()
            if kind=='missing': del job['lr25_context']
            elif kind=='schema': job['lr25_context']['schema']='legacy-insurance'
            elif kind=='status': pre['status']='PLAN'
            elif kind=='closed': pre['quality_closed']=False
            elif kind=='reset': pre['no_weight_or_optimizer_reset']=False
            elif kind=='replay': pre['no_replay_clear']=False
            elif kind=='scale': pre['lr_scale_after']=.5
            else: pre['lr_scale_before']=True
            with self.subTest(kind=kind), self.assertRaises((RuntimeError, KeyError)):
                v.check_lr25_context(job, base, ev)

    def test_current_owner_founder_boot_and_startup_alias_refuse(self):
        for kind in ('owner', 'founder', 'boot', 'phase', 'startup'):
            job, base, ev, store, pre, entry=fixture()
            if kind=='owner': pre['owner']['pid']=999
            elif kind=='founder': pre['current_phase']['expected']['founder_phase_record_sha256']='0'*64
            elif kind=='boot': pre['current_phase']['boot_checkpoint']['sha256']='0'*64
            elif kind=='phase': pre['current_phase']['expected']['metric']='kl'
            else: job['phase_snapshot']['purpose']='startup'
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                v.check_lr25_context(job, base, ev)

    def test_entry_requires_original_4096_half_scale_CE192_CPU(self):
        for kind in ('verifier', 'role', 'clients', 'owner', 'lr', 'legacy', 'source'):
            job, base, ev, store, pre, entry=fixture()
            if kind=='verifier': entry['script']['sha256']='0'*64
            elif kind=='role': entry['root_job']['phase_snapshot']['purpose']='startup'
            elif kind=='clients': entry['root_job']['phase_snapshot']['observed_clients']=0
            elif kind=='owner': entry['root_job']['phase_snapshot']['owner']['pid']=999
            elif kind=='lr': entry['root_job']['source_control_context']['held_recipe_context']['optimizer_lr']=1.25e-5
            elif kind=='legacy': entry['schema']='robotron-live8-maintenance-checkpoint-CPU-result-v1'
            else: pre['entry_checkpoint']['sha256']='0'*64
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                v.check_lr25_context(job, base, ev)

    def test_entry_floor_release_and_live_candidate192_are_required(self):
        for kind in ('floor', 'release', 'candidate0'):
            job, base, ev, store, pre, entry=fixture()
            if kind=='floor': job['clock_floor']['optimized_samples']=19
            elif kind=='release': store[pre['source_freeze_release']['path']]['source_freeze_released']=False
            else: job['phase_snapshot']['observed_clients']=0
            with self.subTest(kind=kind), self.assertRaises(RuntimeError):
                v.check_lr25_context(job, base, ev)

    def test_new_job_schema_requires_context_and_exact_source_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);out=root/'future-output';p=root/'root-job.json'
            def fp(path):
                return dict(sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(), mode='0o444',
                            uid=os.getuid(), nlink=1)
            base=NS(fingerprint=fp, canonical=lambda value, exists=True:Path(value).resolve(strict=exists), MAX_JOB=1<<20)
            job=dict(schema=v.SCHEMA, verifier_sha256=fp(v.__file__)['sha256'], strict_phase_base_sha256=v.STRICT_SHA256,
                original_strict_base_sha256=v.ORIGINAL_SHA256, experiment='fixture-lr25', source=None, verification_copy=None,
                clock_floor=dict.fromkeys(v.CLOCKS, 10), source_control_context=None, output_directory=str(out),
                phase_snapshot=None, lr25_context=None)
            p.write_text(json.dumps(job));p.chmod(0o444)
            args=NS(job=p, expected_job_sha256=fp(p)['sha256'], expected_verifier_sha256=job['verifier_sha256'])
            self.assertEqual(v.read_job(args, base)[0], job)
            del job['lr25_context'];p.chmod(0o644);p.write_text(json.dumps(job));p.chmod(0o444)
            args.expected_job_sha256=fp(p)['sha256']
            with self.assertRaises(RuntimeError):v.read_job(args, base)

    def test_base_finite_delta_reverse_and_numeric_body_exact(self):
        prior=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/phase_snapshot_cpu_verifier_proposal/strict_phase_base.py').read_bytes()
        data=(HERE/'strict_phase_base_lr25.py').read_bytes()
        self.assertEqual(hashlib.sha256(prior).hexdigest(), v.ENTRY_STRICT_SHA256)
        self.assertEqual(hashlib.sha256(data).hexdigest(), v.STRICT_SHA256)
        reverse=data
        for before, after in v.BASE_REPLACEMENTS:
            self.assertEqual(reverse.count(after), 1);reverse=reverse.replace(after, before)
        self.assertEqual(reverse.count(v.BASE_CLI_REFUSAL), 1)
        self.assertEqual(reverse.replace(v.BASE_CLI_REFUSAL, b''), prior)
        def functions(raw):
            text=raw.decode();return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
        self.assertEqual(functions(data)['validate_checkpoint'], functions(prior)['validate_checkpoint'])

    def test_phase_lineage_callbacks_exact_and_default_read_free(self):
        old=Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/phase_snapshot_cpu_verifier_proposal/verify_phase_snapshot.py').read_text()
        new=(HERE/'verify_phase_snapshot_lr25.py').read_text()
        def functions(text):
            return {n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
        for name in ('check_acquisition','verify_phase','immutable','historical_archive'):
            self.assertEqual(functions(old)[name], functions(new)[name])
        main=functions(new)['main']
        self.assertLess(main.index('check_acquisition('), main.index('check_lr25_context('))
        self.assertLess(main.index('check_lr25_context('), main.index('base.validate_checkpoint('))
        with mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('read')), mock.patch.object(v, 'load_base', side_effect=AssertionError('load')), mock.patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(v.main([]), 0)


if __name__=='__main__':
    unittest.main()
