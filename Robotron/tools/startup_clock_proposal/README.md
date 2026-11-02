# Prospective startup host-clock bracket

The completed 1741M quality comparison is valid, protected and adopted. Its
closed source hold has been released. This new component is a first step toward
recovering excluded initial-game evaluation time through a prospective startup
certificate. It changes no running trainer, actor, inference, journal or evaluator.

The next experiment exercises the actual host send/receive ordering over a
socket pair. In particular the peer can act before the send callback returns.
The lower bound must precede that send; the upper bound follows receipt of the
joined snapshot. Both endpoints must lie inside the original fixed admission
interval. The attempt binds session, connection, slot, epoch, exchange, frame,
policy hash, generation and a fresh one-use nonce. Send failure, reconnect,
duplicate consumption, late snapshots, bad joins, debug bypass and already-held
START inputs must reject permanently. Nine new guard methods cover those cases.

This is a transport clock primitive, not a completed game-start certificate.
The test acknowledgement producer is simulated. A nonce join does not authenticate
a malicious peer or prove loaded policy, local input application, accepted ROM
START1, initialization before play, or full-game eligibility. The real private
Lua/server adapter and independent ROM trace remain to be built and validated.
Their records must join to this interval. Existing v2 actions carry motion/fire
and curriculum flags; they do not carry the START1 button. Lua's current local
START can still apply after socket failure, so a future gated path must explicitly
suppress it on failure or debug bypass. No live source is changed here.

The eventual journal handoff must preserve the unknown preplay attachment as
excluded/incomplete, create a distinct authenticated first-start record, and
never relabel an old attachment or manufacture its terminal. Any future quality
comparison still needs fresh R1/R2 and separate C1/C2 confirmation, full tails,
all-slot coverage and original runtime/ROM validity. No efficiency gain is claimed
until a new real bounded experiment measures useful eligible-game yield and cost.
