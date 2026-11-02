"""Bounded synthetic/temp-only tests. Never run the observer or open live API."""
import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).with_name('observe_collector.py')
SPEC = importlib.util.spec_from_file_location('collector_observer_test', SOURCE)
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)


def row(t):
    opt = dict(attempts_started=5, outcomes_recorded=5, applied=4, amp_skipped=1, unavailable=0)
    sources = dict(dqn=10, epsilon=2, expert=3, eval=0, unattributed=0)
    exposure = dict(
        optimizer=dict(schema='robotron-optimizer-exposure-v1', enabled=True, available=True,
            process_id=123, instance_monotonic_ns=4, epoch=1, epoch_reason='loaded',
            total=dict(opt), since_epoch=dict(opt), unclassified_started_total=0,
            prior_epoch_outcomes_total=0, supported_torch='2.13.0+cu130'),
        replay=dict(schema='robotron-replay-insert-exposure-v1', enabled=True, available=True,
            process_id=123, instance_monotonic_ns=6, epoch=1, epoch_reason='loaded',
            accepted_by_source_total=dict(sources), accepted_by_source_since_epoch=dict(sources),
            accepted_total=15, accepted_since_epoch=15, accepted_learner_total=12, accepted_learner_since_epoch=12))
    return dict(utc=str(t), observer_unix_s=float(t), observer_monotonic_ns=int(t*1e9),
        ts=float(t), optimized_samples=81920*t, frame_count=10240*t,
        learner_frame_count=5000*t, training_steps=20*t, measurement_frames=0,
        issues=[], notices=[], gpu1_power_w=400., gpu1_util=60.,
        train_sample_ms=10., train_transfer_ms=1., train_compute_ms=25., train_priority_ms=1.,
        train_step_ms=28., avg_inf_ms=10., client_count=192, training_enabled=True,
        measurement_active=False, epsilon=.1, expert_ratio=.1, lr=2.5e-5,
        memory_buffer_size=6000000, loss=1.4, grad_norm=.2,
        pipeline_read_error='', bank_persistence_read_error='',
        host_pipeline=dict(schema='fake-pipeline', generation=0, sample_every=20,
            latency_bucket_upper_ms=[1,2], batch_size_bucket_upper=[1,2],
            inference=dict(errors=0), actor_refresh=dict(errors=0), target_refresh=dict(errors=0),
            learner_priority=dict(errors=0), learning_exposure=exposure,
            inference_graphs=dict(ready=True,capture_count=128,validation_replay_count=640,
                validation_cpu_returns=640,postload_validations=1,runtime_capture_count=0,
                fallback_count=0,fatal_error=None),
            native_batch_update=dict(enabled=True,available=True,success_count=5,
                completed_count=5,fallback_count=0,error_count=0)),
        bank_persistence=dict(write_failures=0,last_error=None,
            output=dict(backend='stream',stream_output_enabled=True,totals={})))


class ObserverTests(unittest.TestCase):
    def test_import_and_help_are_inert(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('runtime file opened')), \
                patch.object(Path,'open',side_effect=AssertionError('runtime file opened')), \
                patch.object(observer.urllib.request,'urlopen',side_effect=AssertionError('API opened')):
            spec=importlib.util.spec_from_file_location('inert_collector',SOURCE)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with patch('builtins.print'), self.assertRaises(SystemExit) as exited:
                module.main(['--help'])
            self.assertEqual(exited.exception.code,0)

    def test_first_prospective_anchor_endpoint_not_a_cleaner_window(self):
        rows=[row(t) for t in range(220)]
        rows[191]['issues']=['retained bad endpoint']
        self.assertEqual(observer.select_window(rows,10.2,180),(11,191))
        result=observer.summary(rows,10.2,180)
        self.assertFalse(result['valid'])
        self.assertEqual(result['source_row_indexes'],[11,191])
        self.assertEqual(result['rows'],181)
        self.assertEqual(result['issues'],[dict(utc='191',issues=['retained bad endpoint'])])

    def test_bad_endpoint_missing_clocks_retains_invalid_summary(self):
        rows=[row(t) for t in range(181)]
        del rows[-1]['optimized_samples']
        rows[-1]['issues']=['API_read']
        result=observer.summary(rows,0,180)
        self.assertFalse(result['valid']);self.assertFalse(result['available'])
        self.assertIsNone(result['samples_per_s'])
        self.assertEqual(result['source_row_indexes'],[0,180])
        self.assertFalse(result['blocks30s'][-1]['available'])

    def test_counter_rates_six_blocks_tail_and_matched_gpu_energy(self):
        result=observer.summary([row(t) for t in range(181)],0,180)
        self.assertTrue(result['valid'])
        self.assertEqual(result['samples_per_s'],81920.)
        self.assertEqual(result['fleet_frames_per_s'],10240.)
        self.assertEqual(result['samples_per_nonmeasurement_fleet_frame'],8.)
        self.assertEqual(len(result['blocks30s']),6)
        self.assertEqual(result['last30s']['duration_s'],30.)
        self.assertEqual(result['energy']['integral'],72000.)
        self.assertEqual(result['energy']['covered_s'],180.)
        self.assertEqual(result['energy']['samples_per_joule'],204.8)

    def test_missing_power_does_not_silently_bridge_or_create_energy_veto(self):
        rows=[row(t) for t in range(181)];rows[90]['gpu1_power_w']=None
        result=observer.summary(rows,0,180)
        self.assertTrue(result['valid'])
        self.assertFalse(result['energy']['available'])
        self.assertEqual(result['energy']['covered_s'],178.)
        self.assertIsNone(result['energy']['samples_per_joule'])

    def test_append_initial_partial_line_boundary_and_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'append';path.write_bytes(b'old complete\npar')
            reader=observer.AppendReader(path)
            self.assertEqual(reader.initial_offset,len(b'old complete\n'))
            self.assertEqual(reader.initial_partial_prefix_bytes,3)
            self.assertEqual(reader.read(),[])
            with path.open('ab') as f:f.write(b'tial tail\nnext\n')
            self.assertEqual(reader.read(),['partial tail','next'])
            path.write_bytes(b'')
            with self.assertRaisesRegex(ValueError,'truncated'):reader.read()

    def test_manifest_types_duplicate_and_supervisor_bool_fail_closed(self):
        valid=dict(trainer_pid=123,client_count=192,actors=[dict(pid=1000+i,start_ticks=2+i,slot=i) for i in range(192)],supervisor_pids=[456])
        actors,sup=observer.manifest_identities(valid,123)
        self.assertEqual(len(actors),192);self.assertEqual(sup,[456])
        for kind in ('actor_bool','ticks_bool','supervisor_bool','duplicate'):
            broken=copy.deepcopy(valid)
            if kind=='actor_bool':broken['actors'][0]['pid']=True
            elif kind=='ticks_bool':broken['actors'][0]['start_ticks']=True
            elif kind=='supervisor_bool':broken['supervisor_pids']=[True]
            else:broken['actors'][1]=broken['actors'][0]
            with self.subTest(kind=kind),self.assertRaises(ValueError):observer.manifest_identities(broken,123)

    def test_actor_stdout_binding_uses_all_launcher_logs_without_reading_pipes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'logs').mkdir()
            tee=root/'main-fleet.log';tee.write_text('slot0\n')
            slot1=root/'logs/mame_instance_1.log';slot1.write_text('slot1\n')
            descriptors={'/proc/10/fd/1':'pipe:[1]','/proc/10/fd/2':'/dev/null',
                         '/proc/11/fd/1':str(slot1),'/proc/11/fd/2':str(slot1)}
            with patch.object(observer,'GAME',root):
                bindings=observer.actor_log_bindings([dict(pid=10,slot=0),dict(pid=11,slot=1)],root,tee,descriptors.__getitem__)
            self.assertEqual(bindings['10']['paths'],[str(tee)])
            self.assertEqual(bindings['11']['paths'],[str(slot1)])
            self.assertEqual(tee.read_text(),'slot0\n');self.assertEqual(slot1.read_text(),'slot1\n')

    def test_corrected_actual_exposure_checker_pending_and_amp_are_not_faults(self):
        check,_=observer.load_health_check()
        first=row(0);current=row(1)
        opt=current['host_pipeline']['learning_exposure']['optimizer']
        for name in ('total','since_epoch'):
            opt[name]['attempts_started']+=1
        opt['unclassified_started_total']=1;opt['available']=False
        current['grad_norm']=math.inf
        errors,notices=observer.validate_api(current,first,123,192,check)
        self.assertEqual(errors,[]);self.assertIn('nonfinite_grad_diagnostic_not_automatic_fault',notices)
        later=copy.deepcopy(current);later['grad_norm']=.2
        opt=later['host_pipeline']['learning_exposure']['optimizer']
        for name in ('total','since_epoch'):
            opt[name]['outcomes_recorded']+=1;opt[name]['amp_skipped']+=1
        opt['unclassified_started_total']=0;opt['available']=True
        errors,notices=observer.validate_api(later,current,123,192,check)
        self.assertEqual(errors,[]);self.assertIn('AMP_skip_counter_bracket_not_per_update_attribution',notices)
        self.assertEqual(observer.safe(current)['grad_norm'],'inf')

    def test_nonfinite_loss_unavailable_outcome_and_generation_change_remain_faults(self):
        check,_=observer.load_health_check();first=row(0)
        for kind in ('loss','outcome','generation','graph'):
            current=row(1)
            if kind=='loss':current['loss']=math.inf
            elif kind=='outcome':current['host_pipeline']['learning_exposure']['optimizer']['total']['unavailable']=1
            elif kind=='generation':current['host_pipeline']['generation']=1
            else:current['host_pipeline']['inference_graphs']['validation_replay_count']=639
            with self.subTest(kind=kind):
                errors,_=observer.validate_api(current,first,123,192,check)
                self.assertTrue(errors)

    def test_actual_run23_expert_float_boundary_preserves_held_recipe(self):
        check,_=observer.load_health_check();current=row(1)
        current['expert_ratio']=0.09999999999999998
        errors,_=observer.validate_api(current,row(0),123,192,check)
        self.assertEqual(errors,[])
        current['expert_ratio']=.10001
        errors,_=observer.validate_api(current,row(0),123,192,check)
        self.assertIn('held_controls',errors)

    def test_exact_always_printed_actor_transport_markers(self):
        for line in ('Socket read error: closed', 'Socket write error: broken pipe',
                     'Socket open failed: socket.127.0.0.1:9998 (refused)',
                     '[SOCKET ACTION TIMEOUT] slot=191 unix_s=1234',
                     'socket_read_error closed', 'socket_write_error closed'):
            with self.subTest(line=line):
                self.assertTrue(any(marker in line for marker in observer.ACTOR_PATTERNS))
        self.assertFalse(any(marker in 'Socket connection opened to socket.127.0.0.1:9998'
                             for marker in observer.ACTOR_PATTERNS))


if __name__=='__main__':unittest.main()
