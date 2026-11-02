Review-only CE versus KL priorities

The production trainer, configuration, objective, controls and GPU were untouched.
optional-kl-priorities.patch is unapplied. DQN_PER_PRIORITY_METRIC defaults to ce;
the proposed kl option changes detached replay priorities while preserving the CE
objective, CE slice diagnostics and optimizer/sample clocks. Run metadata already
records the new config field and DQN_* environment. Both eager and compiled paths
are covered; the original four-output TrainingLoss API remains the default.

The bounded CPU probe used 256 copied rows: 86 ring, 85 HOF and 85 EpHOF. It pinned
CURRENT.json bank generations and saved the copied rows. On the ring, mean CE was
2.210232 = target entropy 2.199731 + KL 0.010501; CE/entropy Pearson correlation was
0.997996. CE and KL top-decile overlap was 44.4%. CE ranking therefore mostly tracks
target distribution breadth in this sample, rather than divergence from the target.

The counterpoint is substantial: at beta1 the sampled-pool normalized-IS-weight
proxy fell from 0.498054 for CE to 0.042961 for KL. The proposed switch can strongly
reduce PER's effective gradient scale and, through mean-PER bank weighting, bank
scale too. These are counterfactual weights on a small uniform sample, not actual
live-tree weights or the quota mixture. They establish neither a gameplay benefit
nor a reason to change the currently improving recipe. New-row priority hints/caps
also retain reward-based scales. Any future KL trial needs a separate precommitment,
actual normalized-weight diagnostics and a sufficient replay turnover/improvement
horizon; it should follow the existing learning-knob plan rather than bypass it.

Artifacts are under:
  Robotron/logs/managed-learning-20261015/run-26/priority-analysis/
This contains offline-diagnostic.json, sample256.npz, proposal-manifest.json,
test-results.txt and staged/ source copies. The saved model SHA in the diagnostic
is authoritative; robotron_dqn_latest.pt may advance after this analysis. The exact
weights also match managed-checkpoints/recovery-227M-20261016.pt (SHA904e622b...).

Regenerate the review-only patch and source copies from the current source:
  python Robotron/tools/priority_metric_proposal/build_proposal.py
  git apply --check Robotron/tools/priority_metric_proposal/optional-kl-priorities.patch

Run the meaningful CPU tests (after generating source copies):
  CUDA_VISIBLE_DEVICES='' .venv-gb300/bin/python -m unittest Robotron.tools.priority_metric_proposal.test_analyze_replay_priorities Robotron.tools.priority_metric_proposal.test_priority_kernel -v > Robotron/logs/managed-learning-20261015/run-26/priority-analysis/test-results.txt 2>&1

Recompute forward metrics on exactly the saved rows (the checkpoint SHA must match
for exact reproduction; a different checkpoint is a new comparison):
  CUDA_VISIBLE_DEVICES='' .venv-gb300/bin/python Robotron/tools/priority_metric_proposal/analyze_replay_priorities.py Robotron/models_dqn/managed-checkpoints/recovery-227M-20261016.pt --runtime-metadata Robotron/logs/managed-learning-20261015/run-25/metadata.json --sample-file Robotron/logs/managed-learning-20261015/run-26/priority-analysis/sample256.npz > Robotron/logs/managed-learning-20261015/run-26/priority-analysis/recomputed-diagnostic.json

New bounded read-only sampling, if independently requested:
  CUDA_VISIBLE_DEVICES='' .venv-gb300/bin/python Robotron/tools/priority_metric_proposal/analyze_replay_priorities.py Robotron/models_dqn/robotron_dqn_latest.pt --runtime-metadata Robotron/logs/managed-learning-20261015/run-25/metadata.json --ring-size 6000000 --samples 256 --save-sample Robotron/logs/managed-learning-20261015/run-26/priority-analysis/new-sample256.npz > Robotron/logs/managed-learning-20261015/run-26/priority-analysis/new-diagnostic.json

The older probe helper's saved-size interpretation has now also been corrected by
the parent: replay _meta.npy stores [data_ptr, valid_size, max_priority]. This
analyzer independently reads valid_size. Explicit verified --ring-size 6000000
was used in the recorded probe, so the historical bug did not affect its rows.
Live-ring columns are copied without acquiring trainer locks and can race writes;
saved bank contents can lag current banks. This remains an offline diagnostic.
