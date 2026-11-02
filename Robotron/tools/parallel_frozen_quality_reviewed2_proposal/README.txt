Unselected revision of the parallel frozen-quality prototype.

The parent now validates fresh API and pipeline timestamps, all four typed zero
pipeline error counters, pipeline availability/generation, read errors, learning
clocks and original enabled optimizer/replay identities. The real runtime_guard
calls this pure health contract. A normal in-flight optimizer availability flag
is admitted. Seven added test methods include the actual runtime_guard using
finite fake host adapters; the original eight metadata methods remain.

The original proposal and every running campaign/trainer source remain unchanged.
Member behavior, scoring gates, timeout and ownership logic are byte-preserved.
No parallel campaign, capacity run, A/A, deployment or publication is selected.

The original CPU placement restriction remains: a private CPU mask must exclude
the held main inference-worker mask. With the current main mask covering CPUs
0..71, no such private mask exists on this host. Do not select a live run until
after the current campaign closes and its freeze is released, a measured CPU
placement or revised isolation design is accepted, and dedicated carrier/FD
inheritance/failure cleanup plus full A/A latency and capacity are validated.

Metadata-test evidence is recorded separately under ignored run-26 logs. Source
preparation metadata records its state when prepared and is never rewritten to
represent a later execution result. These tests do not prove runtime capacity,
FD inheritance, cleanup under real faults, policy quality or learning speed.
