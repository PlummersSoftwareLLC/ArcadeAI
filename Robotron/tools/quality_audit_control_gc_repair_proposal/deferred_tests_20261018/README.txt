DEFERRED / SOURCE ONLY / NOT IMPORTED OR EXECUTED

Root may run this suite only AFTER the current campaign/source freeze release
and explicit source review/selection. No current selected control or waiter was
changed. No tests, imports, default execution, runtime/unit/API/process/model
operations were performed by the author. Only source read/hash/AST inspection.

Target: ../control_audit_reviewed2.py, exact SHA256
3c600a37d6502de5b82a1ab04c12901ee6e693c1c5272e0a92b46af87e8f452d.
The suite checks this SHA before compiling the target into a fresh namespace.
It imports no application/proposal module. At a future test run, the target's
stdlib-only definitions are executed, then all target subprocess.run, time and
Path/proc interfaces are replaced BEFORE launch/observe/main are called.

Nineteen authored methods drive the actual target launch -> observe in the SAME
module/process. ScriptedIO has no real subprocess fallback: it requires exact
argv, keyword flags and order. An unplanned operation is recorded and causes
cleanup failure even if target.observe catches its first AssertionError. /proc
is a synthetic object supporting only the fake auditor stat read. Filesystem
operations through the target are confined to private temporary fixtures and
the exact target source; no model/current campaign/unit/process file is read.
Only private temporary filesystem writes/fsyncs/chmods are real in a future run.

Cases cover audit0/full-six success; audit2+timer-GC [0,0,0,0,1,0] without invented
stop0; both allowed exact stop5 reason forms vs arbitrary/foreign/invalid text
and still-present timer; foreign timer/service refusal; missing/changed launch
proof/config/PIN; missed live identity; bounded fake-clock deadline; partial
archive timeout/raw bytes/null exit; failed archive vs payload0; failed reset
with partial release; repeated launch/observe refusal; scheduling timeout once.
Payload exit and lifecycle completeness are asserted separately. Missing proof
or preflight refusal grants no fabricated final success; launch failure retains
its separate genuine error receipt. Queue calls represent synthetic observations,
never a real payload or host release.

Future root command (NOT RUN):
  /usr/bin/python3 -B -m unittest discover -s <this directory> -p test_control_gc.py -v
Expected method count is19; there is no claimed result/pass/skip count. Root
must retain the actual future runner exit/streams and decide scope/resources.
No new runner/service/orchestration layer is included.

Limits: scripted metadata cases prove branch and receipt logic only. They do
not establish real systemd timing, startup latency, kernel PID correctness,
invocation/name atomicity, stderr behavior on this host, or exclusive ownership.
In particular systemctl stop remains name-based without invocation CAS; root's
exclusive exact-name ownership remains necessary for any later real execution.
Source immutability is checked at launch; no per-poll source freeze is invented.
