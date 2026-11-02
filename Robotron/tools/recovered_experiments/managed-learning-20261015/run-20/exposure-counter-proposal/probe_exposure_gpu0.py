#!/usr/bin/env python3
"""Root-run tiny fused-Adam/GradScaler parity probe. Default is plan only.

No checkpoints, replay, sockets, MAME, production imports, compile or driver
settings. Inspection copies below belong to this test, not the proposal's hot
path. The proposed path retains an existing found_inf and appends it to the
already-required packed CPU readback exactly once.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
GPU_UUID = "GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0"


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_uuid(value):
    return str(value).lower().removeprefix("gpu-").replace("-", "")


def source_contract():
    helper = HERE / "proposed/learning_exposure.py"
    training = HERE / "proposed/training.py"
    tree = ast.parse(helper.read_text())
    capture = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name == "capture_amp_found_inf")
    forbidden = {"item", "cpu", "to", "clone", "detach", "sum", "get_scale", "synchronize"}
    assert not any(isinstance(n, ast.Attribute) and n.attr in forbidden for n in ast.walk(capture))
    assert training.read_text().count("packed.cpu().numpy()") == 1
    return {str(p.relative_to(HERE)): sha(p) for p in [helper, training, Path(__file__).resolve()]}


def execute(output, expected_helper_sha):
    if os.environ.get("CUDA_VISIBLE_DEVICES") != GPU_UUID:
        raise RuntimeError("CUDA_VISIBLE_DEVICES must contain exactly the designated GPU0 UUID")
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        if os.environ.get(name) != "2":
            raise RuntimeError(f"{name}=2 is required before importing Torch")
    identities = source_contract()
    if identities["proposed/learning_exposure.py"] != expected_helper_sha:
        raise RuntimeError("Proposed helper SHA does not match root's explicit reviewed pin")
    if output.exists():
        raise FileExistsError(output)
    output.mkdir(parents=True)
    started = utc()
    result = dict(schema="robotron-tiny-exposure-gpu0-probe-v1", status="running",
                  utc_start=started, pid=os.getpid(), sources=identities,
                  scope="Constructed tiny tensors only; no model/replay/checkpoint imports or loads")

    def timeout(signum, frame):
        raise TimeoutError("Tiny probe exceeded its internal 105-second budget")

    signal.signal(signal.SIGALRM, timeout)
    signal.alarm(105)
    try:
        apps = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid,gpu_uuid",
                                       "--format=csv,noheader,nounits"], text=True, timeout=5)
        if any(GPU_UUID in line for line in apps.splitlines()):
            raise RuntimeError("GPU0 already has a compute owner; root must coordinate an idle interval")
        import numpy as np
        import torch
        torch.set_num_threads(2)
        torch.set_num_interop_threads(1)
        assert torch.cuda.device_count() == 1
        props = torch.cuda.get_device_properties(0)
        assert canonical_uuid(props.uuid) == canonical_uuid(GPU_UUID)
        assert str(torch.__version__) == "2.13.0+cu130"
        device = torch.device("cuda:0")
        spec = importlib.util.spec_from_file_location("exposure_gpu0_proposed", HERE / "proposed/learning_exposure.py")
        helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = helper
        spec.loader.exec_module(helper)

        def rng():
            return (torch.get_rng_state().clone(), torch.cuda.get_rng_state(0).clone(),
                    random.getstate(), np.random.get_state())

        def same_rng(a, b):
            return (torch.equal(a[0], b[0]) and torch.equal(a[1], b[1]) and a[2] == b[2]
                    and a[3][0] == b[3][0] and np.array_equal(a[3][1], b[3][1])
                    and a[3][2:] == b[3][2:])

        def cpu_bits(value):
            if torch.is_tensor(value):
                array = value.detach().cpu().contiguous().numpy()
                return dict(dtype=str(array.dtype), shape=list(array.shape), bytes=array.tobytes().hex())
            if isinstance(value, dict):
                return {str(k): cpu_bits(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [cpu_bits(v) for v in value]
            return value

        def run_case(mode, amp=True):
            # Explicit values avoid consuming RNG even during construction.
            weight = torch.nn.Parameter(torch.tensor([[.1, -.2, .3], [.4, .5, -.6]], device=device))
            bias = torch.nn.Parameter(torch.tensor([.05, -.05], device=device))
            params = [weight, bias]
            optimizer = torch.optim.Adam(params, lr=.001, eps=1.5e-4, fused=True)
            scaler = torch.amp.GradScaler("cuda", enabled=amp, init_scale=128., growth_interval=2)
            counter = helper.OptimizerExposure() if mode != "baseline" else None
            x = torch.tensor([[1., 0., .25], [0., .5, 1.], [.25, 1., 0.], [1., .5, .25]], device=device)
            y = torch.tensor([[.2, .4], [.3, .1], [.5, .6], [.1, .2]], device=device)
            rows, logical, samples = [], 0, 0
            initial_rng = rng()
            for step in range(4):
                optimizer.zero_grad(set_to_none=True)
                with torch.autocast("cuda", dtype=torch.float16, enabled=amp):
                    ce_loss = (x @ weight.T + bias - y).square().mean(dim=1)
                    loss = ce_loss.mean()
                if amp:
                    scaler.scale(loss).backward()
                    if step == 1:
                        # Finite loss but nonfinite gradients reaches the same
                        # overflow path as real AMP; the loss guard is not bypassed.
                        weight.grad.fill_(float("inf"))
                    scaler.unscale_(optimizer)
                else:
                    loss.backward()
                found, outcome_mode = None, "unscaled"
                registry = scaler._per_optimizer_states if amp else None
                original_found = None
                if counter is not None and amp:
                    if mode == "missing":
                        scaler._per_optimizer_states = {}
                    elif mode == "malformed":
                        state = registry[id(optimizer)]
                        original_found = state["found_inf_per_device"]
                        state["found_inf_per_device"] = {device: torch.zeros(1, device=device)}
                    try:
                        found, outcome_mode = helper.capture_amp_found_inf(
                            scaler, optimizer, device, is_tensor=torch.is_tensor,
                            adam_type=torch.optim.Adam, scaler_type=torch.amp.GradScaler,
                            torch_version=str(torch.__version__))
                    finally:
                        scaler._per_optimizer_states = registry
                        if original_found is not None:
                            registry[id(optimizer)]["found_inf_per_device"] = original_found
                    if mode == "enabled":
                        assert found is registry[id(optimizer)]["found_inf_per_device"][device]
                grad_norm = torch.nn.utils.clip_grad_norm_(params, 10.)
                ticket = counter.begin() if counter is not None else None
                if amp:
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    optimizer.step()
                # Exactly the proposed append position: after all optional
                # diagnostics, before the existing SINGLE packed readback.
                with torch.no_grad():
                    scalars = [loss.detach().float(), grad_norm.detach().float(), loss.detach().float() * 0]
                    if step % 2 == 0:
                        scalars.extend([loss.detach().float() + j for j in range(12)])
                    index = len(ce_loss) + len(scalars) if found is not None else None
                    if found is not None:
                        scalars.append(found)
                    packed = torch.cat((ce_loss.detach().float(), torch.stack(scalars)))
                host = packed.cpu().numpy()
                if counter is not None:
                    counter.finish(ticket, outcome_mode, host[index] if index is not None else None)
                logical += 1
                samples += len(ce_loss)
                optimizer_bits = cpu_bits(optimizer.state_dict())
                adam_steps = [float(np.frombuffer(bytes.fromhex(state["step"]["bytes"]),
                                                 dtype=state["step"]["dtype"])[0])
                              for state in optimizer_bits["state"].values()]
                rows.append(dict(step=step, mode=outcome_mode,
                                 found_inf=None if index is None else float(host[index]),
                                 packed_prefix_bits=host[:index if index is not None else len(host)].tobytes().hex(),
                                 parameters=cpu_bits(params), optimizer=optimizer_bits, adam_steps=adam_steps,
                                 scaler=scaler.state_dict(), logical=logical, samples=samples,
                                 counter=None if counter is None else counter.snapshot()))
            assert same_rng(initial_rng, rng())
            return dict(rows=rows, rng_unchanged=True,
                        counter=None if counter is None else counter.snapshot())

        cases = {"baseline": run_case("baseline"), "enabled": run_case("enabled"),
                 "missing": run_case("missing"), "malformed": run_case("malformed"),
                 "amp_off_baseline": run_case("baseline", False),
                 "amp_off_enabled": run_case("enabled", False)}
        for name in ("enabled", "missing", "malformed"):
            for control, row in zip(cases["baseline"]["rows"], cases[name]["rows"]):
                for field in ("parameters", "optimizer", "scaler", "logical", "samples", "packed_prefix_bits"):
                    assert control[field] == row[field], (name, row["step"], field)
        for control, row in zip(cases["amp_off_baseline"]["rows"], cases["amp_off_enabled"]["rows"]):
            for field in ("parameters", "optimizer", "scaler", "logical", "samples", "packed_prefix_bits"):
                assert control[field] == row[field], ("amp_off", row["step"], field)
        assert [r["found_inf"] for r in cases["enabled"]["rows"]] == [0., 1., 0., 0.]
        assert [r["adam_steps"] for r in cases["enabled"]["rows"]] == [[1., 1.], [1., 1.], [2., 2.], [3., 3.]]
        assert [r["adam_steps"] for r in cases["amp_off_enabled"]["rows"]] == [[1., 1.], [2., 2.], [3., 3.], [4., 4.]]
        assert cases["enabled"]["counter"]["total"] == dict(attempts_started=4, outcomes_recorded=4, applied=3, amp_skipped=1, unavailable=0)
        for name in ("missing", "malformed"):
            assert cases[name]["counter"]["total"]["unavailable"] == 4
        assert cases["amp_off_enabled"]["counter"]["total"]["applied"] == 4
        assert not helper.exposure_enabled({})
        assert identities == source_contract(), "Candidate sources changed during probe"
        result.update(status="PASS", cases=cases, gpu=dict(uuid=str(props.uuid), name=props.name),
                      torch_version=str(torch.__version__), cuda_visible_devices=os.environ["CUDA_VISIBLE_DEVICES"],
                      peak_allocated_bytes=torch.cuda.max_memory_allocated(0),
                      peak_reserved_bytes=torch.cuda.max_memory_reserved(0),
                      acceptance=dict(all_parity=True, overflow_observed=True, unavailable_explicit=True,
                                      amp_disabled_applied=True, rng_unchanged=True, source_contract=True),
                      caveats=["Within one tiny GPU0 process; no live/GB300 overhead claim.",
                               "State/weight/scaler inspection copies are probe-only.",
                               "Applied means scaler allowed the call, not every parameter changed."])
    except BaseException as error:
        result.update(status="FAIL", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        signal.alarm(0)
        result["utc_end"] = utc()
        with (output / "result.json").open("x") as handle:
            json.dump(result, handle, indent=2, allow_nan=False)
            handle.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Execute only after root coordinates GPU0")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--expected-helper-sha")
    args = parser.parse_args()
    if not args.run:
        print(json.dumps(dict(mode="plan_only", gpu_uuid=GPU_UUID, source_hashes=source_contract(),
                              external_timeout_s=120, internal_timeout_s=105), indent=2))
        return
    if args.output_dir is None or not args.expected_helper_sha:
        parser.error("--run requires --output-dir and --expected-helper-sha")
    execute(args.output_dir.resolve(), args.expected_helper_sha)


if __name__ == "__main__":
    main()
