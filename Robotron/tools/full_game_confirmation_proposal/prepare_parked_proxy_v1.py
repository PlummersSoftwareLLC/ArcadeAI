"""Prepare an inert, source-bound proxy with an explicit retired-origin bound.

This does not start a listener, MAME, Torch, GPU work or a scientific study.
The original five-second active transport checks and STOP/EOF/lifecycle path
remain unchanged. The owning native must separately bind the same time limit
and keep retired origins alive until all selected full games finish.
"""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024/native-source-family-original01/full_startup_proxy_quota64_v1.py'
PARENT_SHA='af47c3dac80cc3888023e5ce8fb62b4b0934fab1df7576719adad4ef373832ca'
EDITS=(
    ('                 drain_reader,wall_ns=time.time_ns,monotonic_ns=time.monotonic_ns):',
     '                 drain_reader,parked_origin_timeout_s,wall_ns=time.time_ns,monotonic_ns=time.monotonic_ns):'),
    ('        self.drain_reader=drain_reader\n',
     "        require(type(parked_origin_timeout_s)is int and 120<=parked_origin_timeout_s<=22200,\n"
     "                'Explicit bounded retired-origin lifetime required')\n"
     '        self.parked_origin_timeout_s=parked_origin_timeout_s\n'
     '        self.drain_reader=drain_reader\n'),
    ("            require(self.stop_event.wait(120),'Owner did not intentionally close completed full-tail origin')",
     "            require(self.stop_event.wait(self.parked_origin_timeout_s),'Owner did not intentionally close completed full-tail origin')"),
    ('        an actual complete-cohort host permit can send STOP. Require peer EOF,',
     '        an actual selected-game host permit can send STOP. Require peer EOF,'),
)


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def prepared_source():
    raw=P.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=PARENT_SHA:raise ValueError('Original proxy source changed')
    source=raw.decode()
    for old,new in EDITS:
        if source.count(old)!=1:raise ValueError('Nonunique original proxy integration anchor')
        source=source.replace(old,new,1)
    reverted=source
    for old,new in reversed(EDITS):
        if reverted.count(new)!=1:raise ValueError('Nonunique prepared proxy integration anchor')
        reverted=reverted.replace(new,old,1)
    if reverted.encode()!=raw:raise ValueError('Undeclared proxy change')
    compile(source,'<prospective-parked-proxy>','exec')
    return source


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true');parser.add_argument('--directory',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    if args.directory is None:parser.error('--directory required with --execute')
    h=load('_parked_proxy_prepare_helpers',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    source=prepared_source();args.directory.mkdir(mode=0o700)
    target=args.directory/'full_startup_proxy_slot_retirement_v1.py'
    with target.open('x')as stream:
        stream.write(source);stream.flush()
    target.chmod(0o444)
    pin=h.put(args.directory/'source-preparation.json',dict(
        status='SOURCE_ONLY_UNSELECTED_NOT_NATIVE_QUALIFIED',parent=h.pin(P),source=h.pin(target),
        generator=h.pin(Path(__file__)),exact_reverse_edit_equals_original=True,
        active_peer_and_origin_timeout_s=5,post_STOP_peer_EOF_timeout_s=30,
        parked_bound_required_typed_integer_range_s=[120,22200],
        quota64_selection_or_scores_or_original_transport_guards_changed=False,
        native_owner_must_bind_matching_park_and_private_idle_limits=True,
        scientific_run_launched=False,live_controls_changed=False,promotion=False))
    print(pin)
    return 0


if __name__=='__main__':raise SystemExit(main())
