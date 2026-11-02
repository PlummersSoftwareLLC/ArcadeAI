"""Add full slot-permit archival and replay to future sources only.

Never synthesize missing bodies for a closed run. Original runtime actions,
quota64 guards, raw startup and wire/Lua/ledger checks remain. New pure checks
bind actual retained permit bodies to their immutable commitments and receipts.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
C=G/'logs/managed-learning-20261015/run-26/post-reboot-LR625-vs-frozenS2-fixedcutoff-screen-original01-20261031'

ARCHIVE_CHECKS="""            slot_permit=drain._permits[slot]
            slot_body=json.loads(slot_permit.payload)
            require(slot_permit.used is True
                and hashlib.sha256(slot_permit.payload).hexdigest()==slot_permit.identifier
                    ==drain._commitments[slot]==receipt['permit_identifier']
                and slot_body['schema']=='robotron-fixed-slot-two-full-games-retirement-v1'
                and slot_body['slot']==slot and slot_body['required_complete_games_this_slot']==2
                and slot_body['global_expected_games']==64 and slot_body['global_completion_claim']is False
                and slot_body['quality_qualified']is False
                and slot_body['selected_game_ids']==ids
                and slot_body['selected_rows_sha256']==receipt['selected_rows_sha256']
                and slot_body['registration']==original.registrations[slot]
                and slot_body['policy']==original.policy and slot_body['admission']==original.window
                and original.window['open_unix_ns']<=slot_body['issued_unix_ns']<=receipt['authorized_unix_ns']
                and slot_body['issued_unix_ns']>=max(int(r['end_unix_s']*1e9)for r in rows)
                and slot_body['issued_monotonic_ns']<=receipt['authorized_monotonic_ns']
                and type(slot_body['global_completed_at_issue'])is int and 2<=slot_body['global_completed_at_issue']<=64,
                'Actual retained slot permit body differs from its original commitment or consumed STOP')
"""

REPLAY_CHECKS="""    require(type(slot_permit_record)is dict and set(slot_permit_record)=={'identifier','body'},
        'Actual archived complete slot permit required; missing bodies cannot be synthesized')
    slot_body=slot_permit_record['body']
    require(hashlib.sha256(canonical(slot_body)).hexdigest()==slot_permit_record['identifier']==receipt['permit_identifier']
        and slot_body['schema']=='robotron-fixed-slot-two-full-games-retirement-v1'
        and slot_body['slot']==subject['slot']and slot_body['required_complete_games_this_slot']==2
        and slot_body['global_expected_games']==64 and slot_body['global_completion_claim']is False
        and slot_body['quality_qualified']is False
        and slot_body['selected_game_ids']==ids and slot_body['selected_rows_sha256']==receipt['selected_rows_sha256']
        and slot_body['registration']==registration and slot_body['policy']==policy and slot_body['admission']==window
        and type(slot_body['global_completed_at_issue'])is int and 2<=slot_body['global_completed_at_issue']<=64
        and window['open_unix_ns']<=slot_body['issued_unix_ns']<=receipt['authorized_unix_ns']
        and slot_body['issued_unix_ns']>=max(int(r['end_unix_s']*1e9)for r in ordered)
        and slot_body['issued_monotonic_ns']<=receipt['authorized_monotonic_ns'],
        'Actual full slot permit body/commitment/policy/pair/timing differs')
"""


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true');parser.add_argument('--directory',type=Path)
    args=parser.parse_args()
    if not args.execute:parser.print_help();return 0
    spec=importlib.util.spec_from_file_location('_slot_archival_prepare_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    h=importlib.util.module_from_spec(spec);sys.modules[spec.name]=h;spec.loader.exec_module(h)
    parent=C/'full-game-retirement-source-only-original01-20261101/native-retirement-source-original01/slot_retirement_closeout_v1.py'
    wire=C/'fullgame-evaluator-live-engineering-original01-20261101/slot-wire-audit-source-original01/audit_fullgame_slot_wire_v1.py'
    assert hashlib.sha256(parent.read_bytes()).hexdigest()=='0b41660911a55522cac315a9451e3b5700ae1d59edd3aaffd3c3fd5faf176f26'
    original=parent.read_text();source=original
    marker='            selected_ids.extend(ids)\n';assert source.count(marker)==1;source=source.replace(marker,ARCHIVE_CHECKS+marker,1)
    old='                original_actual_exit=actual_exit,original_ledger_sequence=ledger.sequence))'
    new='                original_actual_exit=actual_exit,original_ledger_sequence=ledger.sequence,\n                full_slot_permit=dict(identifier=slot_permit.identifier,body=slot_body)))'
    assert source.count(old)==1;source=source.replace(old,new,1)
    assert source.replace(new,old,1).replace(ARCHIVE_CHECKS,'',1)==original
    wire_original=wire.read_text();wire_source=wire_original
    signature='*,selected_rows):';assert wire_source.count(signature)==1
    wire_source=wire_source.replace(signature,'*,selected_rows,slot_permit_record):',1)
    anchor="    responses=[r for r in wire if r['kind']=='before_wrapped_response'and r['sequence']>1200]\n"
    assert wire_source.count(anchor)==1;wire_source=wire_source.replace(anchor,REPLAY_CHECKS+anchor,1)
    wire_source=wire_source.replace('slot_permit_body_independently_rehashed=False','slot_permit_body_independently_rehashed=True',1)
    assert wire_source.replace('*,selected_rows,slot_permit_record):',signature,1).replace(REPLAY_CHECKS,'',1).replace('slot_permit_body_independently_rehashed=True','slot_permit_body_independently_rehashed=False',1)==wire_original
    args.directory.mkdir(mode=0o700)
    targets={}
    for name,text in [('slot_retirement_closeout_v2.py',source),('audit_fullgame_slot_wire_v2.py',wire_source)]:
        compile(text,name,'exec');p=args.directory/name
        with p.open('x')as f:f.write(text);f.flush();os.fsync(f.fileno());os.fchmod(f.fileno(),0o444)
        targets[name]=h.pin(p)
    packet=h.put(args.directory/'source-preparation.json',dict(status='FUTURE_SLOT_PERMIT_ARCHIVAL_AND_REPLAY_SOURCE_ONLY',
        original_closeout=h.pin(parent),original_wire_audit=h.pin(wire),sources=targets,generator=h.pin(Path(__file__)),
        exact_declared_additions_revert_to_both_parents=True,
        original_all64_and_slot_STOP_normal0_EOF_ledger_guards_preserved=True,
        all_original_raw_ROM_START_clock_wire_Lua_and_sparse_ledger_checks_preserved=True,
        permit_body_source='Actual retained permit.payload; no reconstruction or historical backfill.',
        no_runtime_actions_added=True,closed_engineering_or_scientific_results_modified=False,
        actual_native_or_scientific_selection_qualified=False,promotion=False))
    print(json.dumps(dict(status='FUTURE_SLOT_PERMIT_ARCHIVAL_AND_REPLAY_SOURCE_ONLY',packet=packet)));return 0


if __name__=='__main__':raise SystemExit(main())
