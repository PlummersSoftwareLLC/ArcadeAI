"""New independent wire-auditor contract over synthetic original peers.

Only fixture definitions from consumed modules are used. No old test methods,
real MAME, Torch/GPU, original scientific reader or live mutation occurs. Lua
application rows and nonexistent actor PIDs here are explicitly synthetic.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


audit=load('_new_original_independent_wire_auditor',HERE/'audit_full_tail_wire_v1.py');audit.dependencies()
defs=load('_consumed_full_tail_proxy_fixture_definitions_only',HERE/'test_full_tail_proxy_v4.py')
h=load('_wire_audit_test_pin_helpers',HERE/'run_full_policy_startup_v3.py')


class Fixture:
    def __init__(self):
        self.f=defs.Fixture();f=self.f;f.prefix();f.step(planned_start=1,planned_coin=1);f.step()
        f.fleet.complete_all();permit=f.fleet.gate.try_issue();f.served_request();f.proxy.serve(f.peer,f.origin)
        self.permit=dict(identifier=permit.identifier,**json.loads(permit.payload))
        self.cohort=copy.deepcopy(f.fleet.controller.status()['cohort'])
        self.fingerprint=hashlib.sha256(audit.canonical(dict(
            started_ids=sorted(self.cohort['started_ids']),rows=self.cohort['rows']))).hexdigest()
        self.wire=[dict(row,proxy_event=i)for i,row in enumerate(f.logs,1)]
        self.producer=audit.games_audit.lines(f.path.read_bytes())
        self.subject=f.subject
        self.rom_sha=hashlib.sha256(defs.defs.ROM).hexdigest()
        proxy=f.proxy
        self.entry=dict(pid=999999999,birth=42,actual_exit=0,frames=proxy.sequence,handoff=proxy.handoff,
            footer=copy.deepcopy(self.producer[-1]),prefix_summary=copy.deepcopy(proxy.prefix_summary),
            host_stop_receipt=copy.deepcopy(proxy.stop_receipt),peer_EOF=True,final_ledger=copy.deepcopy(proxy.final_ledger))
        decoded=defs.codec.decode_response(proxy.last_response)
        common=dict(schema='robotron-full-tail-lifecycle-v2',**self.subject)
        values=[dict(kind='header',sequence=0,continuation_enabled=True,trace_frame_limit=1200),
            dict(kind='prefix_closed',sequence=1200,trace_events=len(self.producer),failed=False,
                machine_exit_requested=False,**{k:self.entry['footer'][k]for k in
                    ('initialized_sequence','latched_sequence','first_play_sequence')}),
            dict(kind='stop_response',sequence=proxy.sequence,response_hex=proxy.last_response.hex(),nonce=decoded['nonce']),
            dict(kind='stop_applied',sequence=proxy.sequence,response_hex=proxy.last_response.hex(),nonce=decoded['nonce'],
                socket_ok=True,apply_ok=True,debug_bypass=False,held_start_before_response=False,
                start=decoded['start'],coin=decoded['coin']),
            dict(kind='exit_requested',sequence=proxy.sequence,response_hex=proxy.last_response.hex(),apply_ok=True),
            dict(kind='closed',sequence=proxy.sequence,reason='drained_shutdown',failed=False,stop_received=True)]
        self.lifecycle=[dict(common,event=i,**row)for i,row in enumerate(values,1)]
        root=Path(f.fleet.temp.name);actor_dir=root/'actors/4096';actor_dir.mkdir(parents=True)
        actor=h.put(actor_dir/'original-actor.json',dict(pid=self.entry['pid'],starttime_ticks=self.entry['birth'],
            proxy_port=20000,original_job=dict(sha256=audit.JOB_SHA),**self.subject))
        self.actor=actor
        self.entry['files']={}
        for name,raw,path in [('producer.jsonl',f.path.read_bytes(),f.path),
            ('proxy.jsonl',b''.join(audit.canonical(r)+b'\n'for r in self.wire),root/'proxy-final-capture.jsonl')]:
            if path!=f.path:
                with path.open('xb')as stream:stream.write(raw)
            path.chmod(0o444);self.entry['files'][name]=h.pin(path)
        self.job=dict(output=str(root),sessions={'4096':self.subject['session']},
            connections={'4096':self.subject['connection']},proxy_ports={'4096':20000},loaded_rom_sha256=self.rom_sha)
        self.result=dict(policy_before=copy.deepcopy(f.fleet.policy),_admission=copy.deepcopy(f.fleet.window))
        self.starts=audit.games_audit.indexed(audit.games_audit.lines(f.fleet.journal.measurement_starts_path.read_bytes()),'fixture starts')
        self.games=audit.games_audit.indexed(audit.games_audit.lines(f.fleet.journal.games_path.read_bytes()),'fixture games')

    def read(self,entry,as_json=True):
        assert h.pin(entry['path'])==entry
        raw=Path(entry['path']).read_bytes()
        return json.loads(raw)if as_json else raw

    def tail_args(self):return copy.deepcopy(dict(wire=self.wire,lifecycle=self.lifecycle,entry=self.entry,
        subject=self.subject,permit=self.permit,cohort_fingerprint=self.fingerprint,
        policy=self.result['policy_before'],window=self.result['_admission']))

    def close(self):self.f.close()


class OriginalIndependentWireAudit(unittest.TestCase):
    def fixture(self):
        f=Fixture();self.addCleanup(f.close);return f

    def test_original_v2_prefix_certification_recomputed_ledger_and_applied_STOP_join(self):
        f=self.fixture()
        prefix=audit.audit_slot_prefix(4096,f.entry,f.job,f.result,f.starts,f.games,f.read,h.pin)
        self.assertEqual(prefix['journal_game_id'],f.entry['handoff']['journal_game_id'])
        self.assertEqual(prefix['original_exchanges'],1200)
        self.assertTrue(prefix['prefix_ledger']['raw_prefix_ledger_recomputed'])
        tail=audit.audit_applied_tail(**f.tail_args())
        self.assertEqual(tail['final_ledger']['exchange_count'],1203)
        self.assertTrue(tail['actual_Lua_STOP_application_joined'])
        self.assertFalse(tail['raw_tail_ledger_recomputed'])
        self.assertFalse(tail['postprefix_raw_reconstructable'])
        self.assertFalse(tail['quality_qualified']);self.assertNotIn('torch',sys.modules)

    def test_original_prefix_payload_metadata_response_and_anchor_corruption_are_rejected(self):
        f=self.fixture()
        for damage in ('payload','metadata','response','anchor'):
            with self.subTest(damage=damage):
                wire=copy.deepcopy(f.wire)
                if damage in ('payload','metadata'):
                    exchange=next(r for r in wire if r['kind']=='origin_exchange'and r['sequence']==100)
                    if damage=='payload':
                        raw=bytes.fromhex(exchange['original_payload_hex']);exchange['original_payload_hex']=(raw[:100]+b'\1'+raw[101:]).hex()
                    else:exchange['metadata']['last_apply_ok']=False
                elif damage=='response':
                    row=next(r for r in wire if r['kind']=='before_wrapped_response'and r['sequence']==100)
                    raw=bytes.fromhex(row['response_hex']);row['response_hex']=(raw[:-1]+b'\x84').hex()
                else:next(r for r in wire if r['kind']=='tail_ledger_checkpoint')['chain_sha256']='f'*64
                with self.assertRaises(ValueError):audit.audit_prefix_ledger(wire,f.producer,f.subject,f.rom_sha,f.entry)

    def test_foreign_permit_early_consumption_missing_STOP_and_applied_lifecycle_damage_fail(self):
        f=self.fixture()
        for damage in ('permit','early','missing','nonce','apply','fault','extra'):
            with self.subTest(damage=damage):
                args=f.tail_args()
                if damage=='permit':args['permit']['cohort_sha256']='0'*64
                elif damage=='early':
                    row=next(r for r in args['wire']if r['kind']=='before_original_host_drained_STOP')
                    row['receipt']['authorized_unix_ns']=args['window']['close_unix_ns']-1
                elif damage=='missing':args['wire']=[r for r in args['wire']if r['kind']!='before_original_host_drained_STOP']
                elif damage=='nonce':args['lifecycle'][3]['nonce']='f'*64
                elif damage=='apply':args['lifecycle'][3]['apply_ok']=False
                elif damage=='fault':args['lifecycle'][-1]['failed']=True
                else:args['lifecycle'].append(dict(args['lifecycle'][-1],event=7))
                with self.assertRaises(ValueError):audit.audit_applied_tail(**args)

    def test_sparse_tail_counter_checkpoint_EOF_and_witness_event_corruption_fail(self):
        f=self.fixture()
        for damage in ('counter','checkpoint','EOF','chain','event','unknown'):
            with self.subTest(damage=damage):
                args=f.tail_args()
                if damage=='counter':
                    rows=[r for r in args['wire']if r['kind']=='tail_ledger_checkpoint'];rows[-1]['accepted']-=1
                elif damage=='checkpoint':
                    args['wire']=[r for r in args['wire']if not(r['kind']=='tail_ledger_checkpoint'and r['reason']=='drained_peer_EOF')]
                elif damage=='EOF':args['entry']['peer_EOF']=False
                elif damage=='chain':
                    next(r for r in args['wire']if r['kind']=='tail_ledger_checkpoint')['chain_sha256']='short'
                elif damage=='event':args['wire'][2]['proxy_event']=9999
                else:args['wire'][2]['kind']='original_proxy_failure'
                raw=b''.join(audit.canonical(row)+b'\n'for row in args['wire'])
                with self.assertRaises(ValueError):
                    args['wire']=audit.wire_rows(raw);audit.audit_applied_tail(**args)


if __name__=='__main__':unittest.main(verbosity=2)
