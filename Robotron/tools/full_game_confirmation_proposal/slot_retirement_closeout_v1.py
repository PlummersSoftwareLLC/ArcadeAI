"""Join32 actual per-slot STOP receipts to the unchanged global64 certificate.

Called by a source-bound future native before common origin shutdown. The
caller still owns independent raw Lua/ROM, original process and scope review.
This helper does not perform I/O or signal, start, adopt or replace a process.
"""
import hashlib
import inspect
import json
from pathlib import Path

AUTHORITY_SHA='78c1ed55490690d2fb18268fe2d8616251031a4692c1a8fb08a5cb22f54820e6'
SLOTS=tuple(range(4096,4128))


def require(value,message):
    if not value:raise ValueError(message)


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def validate(drain,cohort,actors,*,drain_payload,drain_identifier):
    require(type(drain).__name__=='SlotQuotaRetirement'
        and hashlib.sha256(Path(inspect.getsourcefile(type(drain))).read_bytes()).hexdigest()==AUTHORITY_SHA,
        'Exact selected per-slot retirement authority required')
    require(type(actors)is dict and set(actors)==set(SLOTS),'All32 original actor handles required')
    with drain.lock:
        now,mono,status=drain._live();original=drain.original
        actual=original._cohort(now)
        require(actual==cohort and status['complete']is status['valid']is True
            and status['phase']=='complete','Actual complete64 cohort/controller required')
        fingerprint=original._complete_rows(actual)
        permit=drain.permit
        require(permit is not None and permit.used_slots==set()
            and hashlib.sha256(permit.payload).hexdigest()==permit.identifier==drain_identifier
            and json.loads(permit.payload)==drain_payload
            and drain_payload['cohort_sha256']==fingerprint
            and drain_payload['count']==drain_payload['started']==64
            and set(drain_payload['started_ids'])==set(cohort['started_ids']),
            'Unchanged original global64 certificate required; its STOP history must not be fabricated')
        receipts=drain.slot_stop_receipts
        require(set(receipts)==set(SLOTS),'All32 genuine slot STOP consumptions required')
        selected_ids=[];joined=[]
        for slot in SLOTS:
            row=actors[slot];proxy=row['proxy'];receipt=receipts[slot]
            actual_exit=row['child'].poll()
            require(type(actual_exit)is int and actual_exit==0
                and proxy.stop_receipt==receipt and proxy.stop_sent.is_set()and proxy.peer_eof.is_set()
                and proxy.prefix_verified.is_set()and proxy.sent_complete.is_set()
                and proxy.error is None and proxy.sequence==receipt['sequence']>1200,
                'Original normal0 STOP/EOF/prefix/sequence witness missing')
            require(proxy.subject=={k:receipt[k]for k in ('slot','session','connection')}
                and receipt['slot']==slot and receipt['nonce']==proxy.issuer.nonce
                and receipt['schema']=='robotron-consumed-two-game-slot-retirement-v1'
                and receipt['consumed_before_send']is True and receipt['global_completion_claim']is False,
                'Actual original slot STOP receipt differs')
            ledger=proxy.ledger
            require(ledger.closed is True and ledger.sequence==proxy.sequence
                and ledger.subject==proxy.subject and ledger.stop_receipt==canonical(receipt)
                and proxy.final_ledger==ledger.summary(),
                'Actual closed original tail ledger differs')
            rows=drain._slot_rows(actual,slot)
            ids=[game['journal_game_id']for game in rows]
            require(len(ids)==2 and ids==receipt['selected_game_ids']
                and hashlib.sha256(canonical(rows)).hexdigest()==receipt['selected_rows_sha256'],
                'Retired slot must retain both originally selected complete games')
            selected_ids.extend(ids)
            joined.append(dict(slot=slot,selected_game_ids=ids,STOP_receipt=receipt,
                original_actual_exit=actual_exit,original_ledger_sequence=ledger.sequence))
        require(len(selected_ids)==len(set(selected_ids))==64
            and set(selected_ids)==set(cohort['started_ids']),
            'Slot retirements must partition all64 original selected games')
        return dict(schema='robotron-slot-retirement-global64-partition-v1',complete=True,
            global_certificate_identifier=drain_identifier,global_cohort_sha256=fingerprint,
            global_used_slots_intentionally_empty=True,slots=joined,
            selected_games=64,slot_retirements=32,raw_Lua_and_process_scope_review_still_required=True,
            quality_qualified=False,promotion=False)
