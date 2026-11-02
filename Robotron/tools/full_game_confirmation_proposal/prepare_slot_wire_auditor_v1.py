"""Adapt only the independent STOP authorization join to per-slot retirement.

Keep every original global64, raw startup, wire, Lua and sparse-ledger check.
Two original selected complete rows must precede this slot's actual STOP.
The original source-bound receipt is retained; its full permit body was not
archived by native source01, so this auditor makes no body-rehash claim.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
P=G/'logs/managed-learning-20261015/run-26/future-fixed-slot64-full-game-protocol-original01-preparation-20261024/scientific-source-templates-original01/audit_quota64_wire_v2.py'
PARENT_SHA='9d6222a141252ee8b0334cd811660dc38a76d8114c84bd80317c45f991ccb654'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--directory',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    assert hashlib.sha256(P.read_bytes()).hexdigest()==PARENT_SHA
    original=P.read_text();source=original;edits=[]
    def replace(old,new):
        nonlocal source
        assert source.count(old)==1
        source=source.replace(old,new,1);edits.append((old,new))
    replace('def audit_applied_tail(wire,lifecycle,entry,subject,permit,cohort_fingerprint,policy,window):',
        'def audit_applied_tail(wire,lifecycle,entry,subject,permit,cohort_fingerprint,policy,window,*,selected_rows):')
    begin=source.index('    require(type(sequence)is int and 1200<sequence<=0xffffffff',source.index('def audit_applied_tail'))
    end=source.index("    responses=[r for r in wire",begin)
    old=source[begin:end]
    new="""    require(type(selected_rows)is list and len(selected_rows)==2
        and all(r['client_slot']==subject['slot']and r['complete']is r['eligible']is r['known_start']is True
            for r in selected_rows),'Both originally selected complete slot games required')
    ordered=sorted(selected_rows,key=lambda r:(r['start_unix_s'],r['journal_game_id']))
    ids=[r['journal_game_id']for r in ordered]
    require(len(set(ids))==2 and ids[0]==registration['journal_game_id']
        and ordered[0]['terminal_confirmation']['next_journal_game_id']==ids[1]
        and set(ids)<=set(body['started_ids']),'STOP selected pair differs from original certified first/next game')
    require(type(sequence)is int and 1200<sequence<=0xffffffff
        and receipt==entry['host_stop_receipt']and receipt['sequence']==before_stop['sequence']==sequence
        and receipt['schema']=='robotron-consumed-two-game-slot-retirement-v1'
        and type(receipt['permit_identifier'])is str and re.fullmatch('[0-9a-f]{64}',receipt['permit_identifier'])
        and receipt['selected_rows_sha256']==hashlib.sha256(canonical(ordered)).hexdigest()
        and receipt['selected_game_ids']==ids and receipt['global_completion_claim']is False
        and receipt['consumed_before_send']is True
        and all(receipt[k]==v for k,v in subject.items())and receipt['nonce']==registration['nonce']
        and type(receipt['authorized_unix_ns'])is int and type(receipt['authorized_monotonic_ns'])is int
        and receipt['authorized_monotonic_ns']>0
        and receipt['authorized_unix_ns']>=max(window['open_unix_ns'],max(int(r['end_unix_s']*1e9)for r in ordered)),
        'Original slot STOP is not source-bound to both selected completed natural games')
"""
    replace(old,new)
    anchor='        actual_Lua_STOP_application_joined=True,actual_peer_EOF_joined=True,quality_qualified=False)'
    replace(anchor,'        actual_Lua_STOP_application_joined=True,actual_peer_EOF_joined=True,\n'
        '        selected_pair_complete_before_actual_STOP=True,global64_certificate_separately_verified=True,\n'
        '        slot_permit_body_independently_rehashed=False,quality_qualified=False)')
    reverted=source
    for old,new in reversed(edits):assert reverted.count(new)==1;reverted=reverted.replace(new,old,1)
    assert reverted==original
    compile(source,'<slot-STOP-independent-wire-audit>','exec')
    args.directory.mkdir(mode=0o700)
    p=args.directory/'audit_fullgame_slot_wire_v1.py'
    with p.open('x')as f:f.write(source);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
    helper=G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py';spec=importlib.util.spec_from_file_location('_slot_wire_prepare_h',helper);h=importlib.util.module_from_spec(spec);sys.modules[spec.name]=h;spec.loader.exec_module(h)
    pin=h.put(args.directory/'source-preparation.json',dict(status='SLOT_STOP_WIRE_AUDITOR_SOURCE_ONLY',parent=h.pin(P),source=h.pin(p),generator=h.pin(Path(__file__)),
        exact_reverse_edits_equal_parent=True,edits=len(edits),all_original_startup_ROM_nonce_input_clock_checks_unchanged=True,
        original_global64_certificate_and_all_raw_STOP_Lua_EOF_ledger_checks_unchanged=True,
        only_STOP_authorization_join_adapted_to_both_selected_natural_slot_games=True,
        slot_permit_body_not_retained_in_native01_and_not_rehashed=True,scientific_or_promotion_qualification=False))
    print(json.dumps(dict(status='SLOT_STOP_WIRE_AUDITOR_SOURCE_ONLY',packet=pin)));return 0


if __name__=='__main__':raise SystemExit(main())
