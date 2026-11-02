"""Tiny synthetic checks only: no real phase/model/proc/API/Torch/GPU access."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import startup_common as common
import startup_cpu_readonly as cpu
import startup_observe_readonly as observe


class Tensor:
    def __init__(self, shape=(), value=0, dtype="torch.float32", device="cpu", finite=True):
        self.shape = tuple(shape)
        self.value, self.dtype = value, dtype
        self.device = types.SimpleNamespace(type=device)
        self.finite = finite

    def numel(self):
        result = 1
        for value in self.shape:
            result *= value
        return result

    def item(self):
        return self.value


TORCH = types.SimpleNamespace(is_tensor=lambda value: isinstance(value, Tensor),
    isfinite=lambda value: types.SimpleNamespace(all=lambda: value.finite))


def checkpoint():
    metadata = dict(training_steps=1000, total_training_steps=1000, optimized_samples=4096000,
        learner_frame_count=2000000, frame_count=10000000, measurement_frame_count=7550388,
        last_target_update_samples=4000000, baseline_batch_size=512)
    networks = {kind: {"support": Tensor((51,)), **{f"p{i}": Tensor((i + 1,)) for i in range(99)}}
        for kind in ("online_state_dict", "target_state_dict")}
    group = dict(params=list(range(99)), lr=.000025, betas=(.9, .999), eps=.00015,
        weight_decay=0, amsgrad=False, maximize=False, foreach=False, capturable=False,
        differentiable=False, fused=True, decoupled_weight_decay=False)
    optimizer = dict(state={i: dict(step=Tensor(value=997), exp_avg=Tensor((i + 1,)),
        exp_avg_sq=Tensor((i + 1,))) for i in range(81)}, param_groups=[group])
    scaler = dict(scale=65536.0, growth_factor=2.0, backoff_factor=.5,
        growth_interval=2000, _growth_tracker=1)
    saved = dict(metadata, **networks, optimizer_state_dict=optimizer,
        epsilon=.1, expert_ratio=.1, lr_gear="climb", lr_anchor_step=0., grad_scaler_state_dict=scaler)
    signatures = {kind: {name:dict(shape=list(t.shape), dtype=t.dtype) for name,t in values.items()}
        for kind,values in networks.items()}
    recorded_group = json.loads(json.dumps({k:v for k,v in group.items() if k != "params"}))
    recorded_group["parameter_count"] = 99
    reference = dict(state_dict_signatures=signatures, optimizer=dict(groups=[recorded_group]))
    manifest = dict(saved_metadata=metadata, optimizer_state_count=81, optimizer_parameter_steps=[997.])
    return saved, manifest, reference


def exposure(applied=True):
    total = dict(attempts_started=1, outcomes_recorded=1, applied=int(applied),
        amp_skipped=int(not applied), unavailable=0)
    sources = dict(dqn=0, epsilon=0, expert=0, eval=0, unattributed=0)
    return dict(optimizer=dict(enabled=True, process_id=777, instance_monotonic_ns=111, epoch=1, epoch_reason="optimizer_restore_begin",
        total=total, since_epoch=dict(total), unclassified_started_total=0,
        prior_epoch_outcomes_total=0, available=True, last_reason="single_cuda_found_inf"),
        replay=dict(enabled=True, available=True, process_id=777, instance_monotonic_ns=222, epoch=1, epoch_reason="directory_adopt_begin",
            accepted_total=0, accepted_learner_total=0, accepted_since_epoch=0,
            accepted_learner_since_epoch=0, accepted_by_source_total=sources,
            accepted_by_source_since_epoch=dict(sources)))


def prefleet(applied=True):
    _, manifest, _ = checkpoint()
    saved = manifest["saved_metadata"]
    graph = dict(requested=True, ready=True, capture_count=128, validation_replay_count=640,
        validation_cpu_returns=640, postload_validations=1, covered_shapes=list(range(1,129)),
        private_pool_per_shape=True, padding=False, runtime_capture_count=0, fallback_count=0,
        fatal_error=None, graph_owned_reserved_bytes=1000, budget_bytes=16000,
        numeric_policy=dict(weights_inputs="float32", grad_context="no_grad", autocast=False,
            dynamic_compiled=True, compile_internal_cudagraphs=False, matmul_precision="high",
            cuda_matmul_allow_tf32=True, cudnn_allow_tf32=True))
    bank = dict(capture_attempts=0, writes=0, write_failures=0, last_error=None, writer_active=False,
        revision=dict(hof=1,ephof=1), saved_revision=dict(hof=1,ephof=1), dirty=dict(hof=False,ephof=False),
        output=dict(available=True, stream_output_enabled=True, backend="stream", active=None,
            totals={name:dict(errors=0) for name in ("write","file_fsync")}))
    api = dict(client_count=0, training_enabled=True, measurement_active=False,
        frame_count=saved["frame_count"], learner_frame_count=saved["learner_frame_count"],
        measurement_frames=saved["measurement_frame_count"], training_steps=saved["training_steps"]+1,
        optimized_samples=saved["optimized_samples"]+4096, memory_buffer_size=6000000,
        bank_persistence=bank, pipeline_read_error=None, bank_persistence_read_error=None,
        lr=.000025, epsilon=.1, expert_ratio=.1, ts=1234.5, loss=.1, grad_norm=float("inf"),
        host_pipeline=dict(inference_graphs=graph, learning_exposure=exposure(applied),
            native_batch_update=dict(enabled=True, available=True, completed_count=1, success_count=1,
                fallback_count=0, error_count=0)))
    return api, saved, dict(banks={name:dict(match=True) for name in ("hof","ephof")}), dict(
        environment=dict(DQN_EXACT_GRAPH_BUDGET_BYTES="16000"))


class StartupTests(unittest.TestCase):
    def test_import_default_and_help_are_inert(self):
        for path in ("startup_common.py", "startup_cpu_readonly.py", "startup_observe_readonly.py"):
            spec=importlib.util.spec_from_file_location("inert_"+path[:-3], HERE/path)
            module=importlib.util.module_from_spec(spec)
            with patch.object(Path,"read_bytes",side_effect=AssertionError("evidence read")), \
                 patch.object(Path,"read_text",side_effect=AssertionError("evidence read")):
                spec.loader.exec_module(module)
        for module in (cpu,observe):
            with patch.object(module,"execute",side_effect=AssertionError("runtime execute")), \
                 patch.object(common,"baseline",side_effect=AssertionError("baseline read")), \
                 patch.object(sys,"argv",["fixture"]),contextlib.redirect_stdout(io.StringIO()) as output:
                module.main()
                self.assertEqual(json.loads(output.getvalue())["mode"],"PLAN_ONLY_NO_RUNTIME_READS")
            with patch.object(sys,"argv",["fixture","--help"]),contextlib.redirect_stdout(io.StringIO()), \
                 self.assertRaises(SystemExit) as result:
                module.main()
            self.assertEqual(result.exception.code,0)
        self.assertNotIn("torch",sys.modules)

    def test_full_virtual443_tensor_Adam81_scaler_state_is_preserved(self):
        saved,manifest,reference=checkpoint()
        before=copy.deepcopy(manifest)
        facts=cpu.validate_checkpoint(saved,manifest,reference,TORCH)
        self.assertEqual(facts["finite_tensor_count"],443)
        self.assertEqual(facts["optimizer_parameter_steps"],[997.])
        self.assertEqual(facts["grad_scaler_state_dict"],saved["grad_scaler_state_dict"])
        self.assertEqual(manifest,before)

    def test_cpu_finite_inventory_order_and_missing_clock_fail_closed(self):
        for change in (lambda s:s["target_state_dict"].pop("p98"),
                       lambda s:setattr(s["online_state_dict"]["p2"],"device",types.SimpleNamespace(type="cuda")),
                       lambda s:setattr(s["online_state_dict"]["p2"],"finite",False),
                       lambda s:s.pop("optimized_samples"),
                       lambda s:s["online_state_dict"].update(support=s["online_state_dict"].pop("support"))):
            saved,manifest,reference=checkpoint();change(saved)
            with self.assertRaises((ValueError,KeyError)):
                cpu.validate_checkpoint(saved,manifest,reference,TORCH)

    def test_ordered99_Adam_moments_and_exactint_owners(self):
        for change in (lambda s:s["optimizer_state_dict"]["state"][0].update(exp_avg=Tensor((2,)),exp_avg_sq=Tensor((2,))),
                       lambda s:setattr(s["optimizer_state_dict"]["state"][0]["exp_avg"],"dtype","torch.float64"),
                       lambda s:s["optimizer_state_dict"]["param_groups"][0]["params"].__setitem__(0,False),
                       lambda s:s["optimizer_state_dict"]["state"].update({False:s["optimizer_state_dict"]["state"].pop(0)}),
                       lambda s:s["optimizer_state_dict"]["param_groups"][0].update(lr=.00005)):
            saved,manifest,reference=checkpoint();change(saved)
            with self.assertRaises(ValueError):cpu.validate_checkpoint(saved,manifest,reference,TORCH)

    def test_scaler_controls_and_Adam_clock_failures(self):
        for change in (lambda s:s.pop("grad_scaler_state_dict"),
                       lambda s:s["grad_scaler_state_dict"].update(scale=float("inf")),
                       lambda s:s["grad_scaler_state_dict"].update(_growth_tracker=2000),
                       lambda s:s.update(lr_anchor_step=True),
                       lambda s:s["optimizer_state_dict"]["state"][0].update(step=Tensor(value=996)),
                       lambda s:s["optimizer_state_dict"]["state"][0].update(step=Tensor(value=True))):
            saved,manifest,reference=checkpoint();change(saved)
            with self.assertRaises((ValueError,KeyError)):cpu.validate_checkpoint(saved,manifest,reference,TORCH)

    def test_saved4096_deltas_separate_known_Adam_skip(self):
        _,manifest,_=checkpoint();old=copy.deepcopy(manifest)
        old["saved_metadata"].update(training_steps=990,total_training_steps=990,optimized_samples=4096000-40960,
            learner_frame_count=1999000,frame_count=9998000,last_target_update_samples=3999000)
        old["optimizer_parameter_steps"]=[988.]
        result=cpu.clock_delta(manifest["saved_metadata"],old,[997.])
        self.assertEqual(result["logical_updates"],10)
        self.assertEqual(result["optimized_samples"],40960)
        self.assertEqual(result["Adam_parameter_steps"],9)
        self.assertEqual(result["logical_minus_Adam_delta"],1)
        changed=copy.deepcopy(manifest["saved_metadata"]);changed["optimized_samples"]+=1
        with self.assertRaises(ValueError):cpu.clock_delta(changed,old,[997.])
        with self.assertRaises(ValueError):cpu.clock_delta(manifest["saved_metadata"],old,[999.])

    def test_environment_only_runpath_and_wait_both_directions(self):
        baseline=dict(ROBOTRON_RUN_DIR="/fake/run-23",DQN_INFERENCE_BATCH_WAIT_MS="1",
            DQN_BATCH_SIZE="4096",CUDA_VISIBLE_DEVICES="pinned-GB300")
        contract=dict(environment=baseline)
        for old_wait,new_wait in (("1","0.5"),("0.5","1")):
            prior=dict(baseline,ROBOTRON_RUN_DIR="/fake/run-24",DQN_INFERENCE_BATCH_WAIT_MS=old_wait)
            current=dict(baseline,ROBOTRON_RUN_DIR="/fake/run-25",DQN_INFERENCE_BATCH_WAIT_MS=new_wait)
            selected,changes=common.check_environment(current,current,prior,contract,Path("/fake/run-25"),float(new_wait))
            self.assertEqual(selected,current);self.assertEqual(set(changes),{"ROBOTRON_RUN_DIR","DQN_INFERENCE_BATCH_WAIT_MS"})
            for change in (dict(current,DQN_BATCH_SIZE="2048"),dict(current,LD_PRELOAD="unexpected"),
                           dict(current,DQN_INFERENCE_BATCH_WAIT_MS="2")):
                with self.assertRaises(ValueError):common.check_environment(change,current,prior,contract,Path("/fake/run-25"),float(new_wait))

    def test_config_only_collector_and_older_omitted_field(self):
        baseline=dict(batch_size=4096,compile_full_loss=True,use_torch_compile=True,inference_batch_wait_ms=1.)
        current=dict(baseline,inference_batch_wait_ms=.5)
        self.assertEqual(common.check_config(current,baseline,dict(config=baseline),.5),dict(inference_batch_wait_ms=[1.,.5]))
        omitted={k:v for k,v in baseline.items() if k!="inference_batch_wait_ms"}
        common.check_config(omitted,baseline,dict(config=baseline),.5)
        for change in (dict(current,batch_size=2048),dict(current,inference_batch_wait_ms=1.)):
            with self.assertRaises(ValueError):common.check_config(change,baseline,dict(config=baseline),.5)

    def test_known_applied_or_skipped_first_outcome_not_unavailable_or_imported(self):
        for applied in (True,False):
            value=exposure(applied);result=common.outcome_checks(value,777)
            self.assertEqual(result["optimizer"]["total"]["amp_skipped"],int(not applied))
        for change in (lambda x:x["optimizer"].update(available=False),
                       lambda x:x["replay"].update(available=False),
                       lambda x:x["optimizer"].update(instance_monotonic_ns=0),
                       lambda x:x["optimizer"]["total"].update(unavailable=1,applied=0),
                       lambda x:x["optimizer"].update(unclassified_started_total=1),
                       lambda x:x["optimizer"].update(process_id=888),
                       lambda x:x["replay"].update(epoch=2),
                       lambda x:x["replay"].update(accepted_total=6000000),
                       lambda x:x["replay"]["accepted_by_source_total"].update(eval=1),
                       lambda x:x["replay"]["accepted_by_source_since_epoch"].pop("eval")):
            value=exposure();change(value)
            with self.assertRaises(ValueError):common.outcome_checks(value,777)

    def test_prefleet_exact_one4096_graph640_and_knownskip(self):
        for applied in (True,False):
            api,saved,facts,contract=prefleet(applied)
            self.assertTrue(all(observe.validate_prefleet(api,saved,facts,777,contract).values()))
        changes=(lambda a:a.update(training_steps=a["training_steps"]+1),
            lambda a:a.update(loss=float("nan")),
            lambda a:a.update(optimized_samples=a["optimized_samples"]+1),
            lambda a:a.update(client_count=1),
            lambda a:a["host_pipeline"]["inference_graphs"].update(validation_cpu_returns=639),
            lambda a:a["host_pipeline"]["inference_graphs"].update(graph_owned_reserved_bytes=16001),
            lambda a:a["host_pipeline"]["inference_graphs"].update(runtime_capture_count=1),
            lambda a:a["host_pipeline"]["native_batch_update"].update(fallback_count=1),
            lambda a:a["bank_persistence"]["output"].update(stream_output_enabled=False))
        for change in changes:
            api,saved,facts,contract=prefleet();change(api)
            self.assertFalse(all(observe.validate_prefleet(api,saved,facts,777,contract).values()))

    def test_exclusive_readonly_publication_and_raw_NaN_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"new.json"
            common.publish(path,dict(pass_=True,value=1))
            self.assertEqual(path.stat().st_mode&0o777,0o444)
            with self.assertRaises(FileExistsError):common.publish(path,dict(value=2))
            with self.assertRaises(ValueError):common.publish(Path(directory)/"bad.json",dict(value=float("nan")))
            raw=b'{"gradient":Infinity,"other":"retained"}\n'
            rawpath=Path(directory)/"api.json"
            common.publish_raw(rawpath,raw)
            self.assertEqual(rawpath.read_bytes(),raw)
            self.assertEqual(rawpath.stat().st_mode&0o777,0o444)


if __name__ == "__main__":
    unittest.main()
