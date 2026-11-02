# Isolated greedy-inference CUDA graph prototype

`benchmark_cuda_graph_inference.py` is a new-file experiment. It does not change
the agent, configuration, model, server, launcher, training state, or sidecar.
Default invocation prints a plan without importing Torch/NumPy or creating files.
Only `--execute` permits CUDA. Physical GPU0 UUID is fixed in the helper; the
GB300 is hidden. Torch/OMP/BLAS/Inductor use two CPU threads, private compiler
caches and private control/model output paths. An idle-compute-owner check runs
before numerical imports and after the experiment. Use an external 240-second
timeout. Never run alongside a private GPU0 quality evaluation.

```
timeout --kill-after=5s 240s env -u LD_PRELOAD \
  CUDA_VISIBLE_DEVICES=GPU-b549355c-78bb-53d8-04a6-da34d45e1dd0 \
  OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  TORCHINDUCTOR_COMPILE_THREADS=2 PYTHONDONTWRITEBYTECODE=1 \
  .venv-gb300/bin/python -u Robotron/tools/benchmark_cuda_graph_inference.py \
  --directory /absolute/path/to/new-output-directory --execute
```

The checkpoint is SHA-pinned protected 32M. A separately pinned compatible 16M
checkpoint tests refresh and restoration, without replacing either disk file.
The immutable 128-row sample contains real normalized stacked HOF/EpHOF states
(64 each); its payload must match archived provenance. These are test inputs,
never reintroduced into learning. Empty states supplement the real states.

The prototype matches the main agent's `torch.no_grad()`, FP32 inputs/weights,
TF32 settings, disabled autocast, eval mode, and parameter `requires_grad=True`.
It compiles and warms dynamic and static callables, with internal Inductor
CUDA graphs disabled. It then enables recompile errors and serially captures
32/64/128-row graphs before serving. Each graph retains its own input/output
tensors and private memory pool. Runtime requests never capture or recompile.

One RLock covers replay, input-buffer reuse, in-place weight refresh, and
blocking CPU readback. CPU callers receive fresh independent allocations.
GPU diagnostic callers use the original compiled callable plus stream
dependencies and ownership recording, rather than captured output buffers.
Unknown exact shapes use the prewarmed compiled route. Explicit experimental
padding clears all unused rows without RNG. Runtime failures latch; the helper
does not silently retry a failed graph with a successful fallback.

Refresh follows the existing source-ready event, inference-stream copy,
copy-done event, source-stream dependency sequence. `load_state_dict(assign=False)`
must retain every `state_dict` tensor's pointer, shape, stride, dtype and device.
Every captured bucket is checked at 32M, after installing 16M, and after restoring
32M, without recapture. Nonpersistent buffers are not changed by this refresh;
their addresses are not separately recorded by this prototype's signature.

PyTorch requires non-default-stream warmup/capture, stable addresses and shapes,
and no CPU/GPU synchronization or unrelated CUDA work during capture within
the same process. Its graph context performs device synchronization and cache
cleanup on entry, which makes runtime capture inappropriate here. The helper
checked the installed Torch 2.13 CUDA graph implementation and the
[official CUDA graph constraints](https://docs.pytorch.org/docs/2.14/notes/cuda.html#cuda-graphs)
and [compiler options](https://docs.pytorch.org/docs/2.14/generated/torch.compile.html).
Stable web documentation currently redirects to 2.14; the artifact records the
installed 2.13 source path and hash.

## First GPU0 result

`logs/managed-learning-20261015/run-09/cuda-graph-gpu0-prototype-01/result.json`
records PID 809337, 2026-10-16 05:48:47–05:50:13 UTC. Warmup took 37.77 seconds
dynamic and 42.91 seconds static. Six graph captures took 0.083 seconds combined.
The process exited normally and released its GPU0 context. No GB300 context was
created by the helper.

Real-state median CPU-return **host service** times (12 alternating route-order
measurements per cell):

| Exact rows | Existing dynamic compiled | Dynamic compiled + graph | Speed ratio |
|---:|---:|---:|---:|
| 32 | 2.671 ms | 1.140 ms | 2.34× |
| 64 | 2.759 ms | 1.802 ms | 1.53× |
| 128 | 3.648 ms | 3.296 ms | 1.11× |

Service starts at input transfer and ends after CPU readback. It excludes
socket/replay/epsilon processing, action decoding, lock acquisition and guard
overhead. Dispatch measures host enqueue time, not GPU kernel time. Graph
dispatch was about 0.015 ms, with device execution waiting moving into readback;
the service improvement is smaller than the dispatch improvement. No GPU event
kernel timings were collected. These isolated GPU0 numbers do not establish
GB300 speed, training overlap, FPS improvement, or whole-game quality.

Dynamic exact graphs were bit-identical to the existing dynamic compiled Q
values at each tested shape, including the 16M refresh and restoration. All
joint and all nine held-fire action choices matched. Retained CPU outputs,
GPU diagnostic outputs, cross-bucket reuse, and a delayed consumer with a second
caller passed. Compiler counters stayed at five graphs with no graph breaks.
Final weights exactly matched the protected 32M model. Peak reserved memory was
1.21 GB for both compile variants and all six graphs together.

**Reject padding.** Real-state 50→64 padding changed 2/450 held-fire choices;
96→128 changed 1/96 greedy choices and 2/864 held-fire choices. The 31→32 and
65→128 probes also changed held-fire choices. Current row-independent model
semantics do not make floating-point effective-shape changes action invariant.
Padding timings are single-call diagnostics, not benchmark estimates. Static
compilation introduced small Q differences versus dynamic compilation without
a material speed benefit, so it has no advantage for this proposed path.

Only exact dynamic graphs merit a later bounded pilot. Cover observed exact
sizes (including 50) at startup, or retain the existing compiled path for shapes
not captured; do not silently pad or capture during serving. A production pilot
would need startup ordering before any CUDA worker, all parameter/buffer address
guards, a strict greedy/CPU-return eligibility check, the existing refresh lock
and event order, and measurements on GB300 with the learner active. Changes to
the evaluator's inference backend, loaded sources, numeric settings or protocol
require a fresh same-backend whole-game reference. Main-agent-only optimization
does not change the private GPU0 evaluator or invalidate its protected 32M reference.
No production integration is authorized by the presence of this result file.

## Exact 1–128 coverage extension

`benchmark_cuda_graph_coverage.py` is another default-plan-only helper, with the
same isolation and immutable inputs. Root authorized a separate run:
`run-09/cuda-graph-gpu0-prototype-02/result.json`. It retains all 128 exact graphs
and separate pools simultaneously, uses only the existing dynamic compiled
callable, and never pads. The allocator has a hard 10 GiB per-process budget;
per-capture evidence also records global free memory and reserved/peak bytes.
A 285-second internal and 300-second external limit bound the run. Any failure
records `incomplete.json` with completed capture sizes and does no retry.

PID 824092 ran 05:57:40–05:58:38 UTC on 2026-10-16 and released its GPU0 context.
All 128 shapes passed real and empty state checks at 32M, after a 16M refresh,
and after restoring 32M: 768 shape/policy/input comparisons, 4,012,416 identical
Q-value elements, 49,536 greedy choices and 445,824 held-fire choices. Every
refresh changed policy output and every restoration recovered the original
bytes, without recapture. This extension signs all named parameters and buffers,
including nonpersistent buffers. Their storage was preserved, as were final
weights, all retained CPU outputs, diagnostic GPU outputs, arbitrary shape-order
reuse, and a delayed consumer with a second serialized caller. Compiler counters
stayed at two graphs with no breaks.

Cold warmup took 43.28 seconds; capturing all 128 graphs took 2.45 seconds.
Their private pools reserved 8.06 GiB, and allocator peak reservation was
9.27 GiB (peak live allocation 0.70 GiB), within the 10 GiB budget. Reservation
and allocation are different allocator measures; the small live-allocation number
does not remove the private-pool reservation cost.

| Exact rows | Compiled full call | Graph full call | Speed ratio |
|---:|---:|---:|---:|
| 32 | 2.467 ms | 1.210 ms | 2.04× |
| 50 | 2.492 ms | 1.569 ms | 1.59× |
| 64 | 2.521 ms | 1.889 ms | 1.33× |
| 128 | 3.741 ms | 3.416 ms | 1.10× |

These 12 alternating-order measurements include the helper's Python lock,
context, transfer, dispatch, CPU readback and guard work. Socket/replay/epsilon
processing and action decoding remain excluded. At 50 rows the corresponding
transfer-through-readback service medians were 2.423→1.508 ms. These are host
elapsed times on isolated GPU0, not kernel times or a GB300 performance claim.
The coverage result supports a separate smoke test of staged production wiring;
it does not authorize a live enable. The executed helper sources are preserved
beside each result, and each run's `analysis.json` checks source integrity.

## Actual default-off agent/helper smoke

After independent CPU/source reviews, `smoke_agent_cuda_graphs.py` exercised the
applied production candidate (`agent.py` SHA `6fe6c5b4…e71eefb8`, helper SHA
`222d5b8b…ae8145db`) on GPU0. Full agent, replay, prefetcher and optimizer
constructors were explicitly patched to raise. A `RainbowAgent.__new__` instance
owned only isolated online/inference networks, locks, a dedicated stream and
events. No trainer, replay, MAME process or GB300 context existed in this smoke.

PID 849451 completed 2026-10-16 06:13:13–06:14:16 UTC in 62.56 seconds. Results,
analysis and exact executed source copies are in
`run-09/agent-exact-graphs-gpu0-smoke-01/`. All 12 acceptance flags passed:

- All 128 exact real/empty input sizes matched compiled Q bytes, joint actions
  and every held-fire choice through the actual agent CPU-return methods.
- Capture happened on initialized weights before the real checkpoint copy.
  Actual `_sync_inference(force=True)` made loaded 32M and then 16M effective;
  `install_inference_policy` restored 32M without changing online weights or sync
  markers. Final online and inference tensors were restored to protected 32M.
- CPU/CUDA/Python/NumPy RNG states were unchanged across setup, post-load
  validation, serving and refresh. Clocks, callable identity and every parameter
  and buffer's storage were preserved.
- Retained CPU outputs, arbitrary shape order, a delayed second caller and
  original-path GPU diagnostic outputs retained correct ownership. A guarded
  graph call succeeded with intermediate CPU `Tensor.to` forbidden, verifying
  the new direct static-input copy route.
- A deliberate replay exception escaped with its exact message and zero
  compiled/eager fallback calls. Capture count remained 128, runtime captures
  zero, compiler count two, and fallback count zero.

The production helper's pool-plus-static-input reservation was 8.40 GiB; peak
process allocator reservation was 9.32 GiB. The isolated 50-row graph agent method
took 1.833 ms median versus 2.437 ms for the compiled `_run_inference` control
(1.33×). The compiled control omits some ordinary public-method overhead such as
`net.eval`, so these are conservative wiring timings, not a direct live
before/after measurement. Both paths include transfer and completed CPU readback;
they exclude socket/replay/epsilon processing and action decoding. No GB300 or
learning-concurrency benefit is established. Default-off source passing this
smoke permits a root-reviewed pilot decision; it does not enable a live run.

An additional cross-process hash check found different initial 32M Q bytes at
123/128 sizes between this smoke's compiled control and prototype02's compiled
control. Each run independently had exact graph/control parity. Process,
warmup, allocation and kernel-selection conditions can differ; their contribution
was not isolated. Prototype02 saved hashes and gap summaries rather than full
Q/action arrays, so the cross-run numerical/action difference is unquantified.
No cross-process or cross-architecture byte-identity claim is made. This
main-agent change is not loaded by the separate GPU0 sidecar; its existing
protected 32M whole-game reference remains applicable while its backend, loaded
sources, configuration and boot protocol remain unchanged.

The eight CPU routing/ownership/failure tests can run with CUDA hidden:

```
env CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 \
  .venv-gb300/bin/python -m unittest discover -s Robotron/tools \
  -p test_cuda_graph_inference_prototype.py -v
```
