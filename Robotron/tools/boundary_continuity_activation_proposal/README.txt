Historical maintenance wrappers and finite regression tests.

activate.py and activate_reviewed2.py are preserved failed controller revisions;
neither is a current operational entry point. Do not launch them again against
the live trainer. Their selected jobs, native outcomes and owned cleanup remain
under ignored run-26 logs.

The first revision required exactly unchanged startup clocks. The actual held
trainer performs one startup optimizer update with zero admitted actor frames.
That update was saved and retained. Reviewed2 correctly scopes four clock fields
and permits that one-update path, but its ready predicate accepted a dashboard
owner snapshot before SocketServer construction and metric initialization had
finished. Its early profile check interrupted initialization. A dashboard process
identity alone is not server readiness.

The latest saved checkpoint remained byte-identical to its passing strict phase
CPU verification. A separately recorded normal guarded startup resumed those
verified saved bytes, completed built-in phase and exact-graph checks, and
reconnected all192 original actors with the corrected source. No additional
zero-client CPU proof after the final startup is claimed. Nine live ring objects
retain their storage identity; live data writes may change timestamps/content.

Authoritative final record:
Robotron/logs/managed-learning-20261015/run-26/
  boundary-continuity-verified-bytes-forward-resume-original01-20261018/
  root-live-activation-health-PASS.json

Any future maintenance controller must wait for complete server/profile readiness
and fresh metrics before enforcing startup invariants. These pure unit tests
cover ownership and clock accounting, not a completed maintenance lifecycle.
