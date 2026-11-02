"""CPU-only real64-subject codec/proxy/authority/certificate/journal guards."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
N=Path(__file__).resolve().parent
F=N/'future-capacity64-shared-slot-domain-UNSELECTED-original01'
E=N/'evaluator-count-active600-counterbalanced-engineering-original01'


def load(name,path,digest=None):
    if digest:assert hashlib.sha256(path.read_bytes()).hexdigest()==digest
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s)
    sys.modules[name]=m;s.loader.exec_module(m);return m


h=load('_domain_guard_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py',
       '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
manifest=h.pin(F/'source-derivation-UNSELECTED.json')
assert manifest['sha256']=='cf2f32233078b77376660a6e47de6d55e33c96ad561f798fcb6ac6be50b414e1'
derivation=json.loads(h.checked(manifest).read_bytes())
pins={r['component']:r['derived']for r in derivation['derivations']}
codec=load('wire_codec_v2',h.checked(pins['codec']),pins['codec']['sha256'])
authority=load('startup_handoff_v2',h.checked(pins['authority']),pins['authority']['sha256'])
load('boot_readiness_v3',h.checked(pins['boot_readiness']),pins['boot_readiness']['sha256'])
load('tail_ledger_v1',h.checked(pins['tail_ledger']),pins['tail_ledger']['sha256'])
bridge=load('_domain_actual_startup_proxy',h.checked(pins['bridge']),pins['bridge']['sha256'])
old_codec=load('_domain_original32_codec',G/'tools/startup_policy_journal_proposal/wire_codec_v2.py',
               '94e95bc1f6fb8c2063393e57512f43acba57611da9d6e33ba94c857d967ca0f3')
journal_module=load('_domain_real_game_journal',G/'tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/game_journal.py',
                    '96864c78df67f46bc58b1c4af4ce1bceb3791a8842fdcf02871385a1013d1e0f')
A1=E/'01-A1-control/diagnostic-output-original01'
starts=[json.loads(line)for line in (A1/'journal/measurement_starts.jsonl').read_bytes().splitlines()]
original=starts[0]['context']['startup_certificate']
original_rows=[json.loads(line)for line in (A1/'actors/4096/producer.jsonl').read_bytes().splitlines()]
rom=b''.join(bytes.fromhex(r['data_hex'])for r in original_rows if r['kind']=='raw_ROM_chunk')
assert len(rom)==102400 and hashlib.sha256(rom).hexdigest()==original['loaded_rom_sha256']
wire_rows=[json.loads(line)for line in (A1/'actors/4096/proxy.jsonl').read_bytes().splitlines()]
metadata_template=next(r['metadata']for r in wire_rows if r['kind']=='origin_exchange')
POLICY=json.loads((E/'02-B1-capacity64/diagnostic-output-original01/original-loaded-policy.json').read_text())['policy']
POLICY['experiment']='CPU-synthetic-shared-slot64-domain'
WINDOW=dict(open_unix_ns=100,close_unix_ns=1000000,generation=POLICY['measurement_generation'],experiment=POLICY['experiment'])
CONTEXT=dict(measurement_active=True,measurement_generation=POLICY['measurement_generation'],experiment=POLICY['experiment'],
             epsilon=0,expert_ratio=0,difficulty=5,learner_frames=POLICY['learner_frame_count'],
             training_steps=POLICY['training_steps'],optimized_samples=POLICY['optimized_samples'])
FRAME=SimpleNamespace(game_score=0,level_number=1,player_alive=False,num_lasers=2,lives=3,start_pressed=False,done=False)
RESULTS=[]


def subject(slot):
    return dict(slot=slot,session=f'{slot:032x}',connection=f'{slot+100000:032x}')


def issuer(journal,slot,cid):
    return authority.StartupHandoff(journal,client_id=cid,**subject(slot),expected_rom_sha256=original['loaded_rom_sha256'],
        policy_reader=lambda:copy.deepcopy(POLICY),admission_reader=lambda:copy.deepcopy(WINDOW),wall_ns=lambda:200,monotonic_ns=lambda:300)


def authorization_and_evidence(auth,cid):
    auth.loaded_rom(rom)
    action=bytes.fromhex(original['evidence']['application']['response_hex'])[-6:]
    sent=[];response=auth.authorize(original['evidence']['application']['sequence'],action,lambda data:sent.append(data))
    assert sent==[response]
    evidence=copy.deepcopy(original['evidence'])
    for key in ('application','gate','setup','initialization'):
        evidence[key].update(**subject(auth.slot),nonce=auth.nonce)
    evidence['application']['response_hex']=response.hex()
    evidence['origin_acceptance'].update(client_id=cid,client_slot=auth.slot)
    return evidence


class SharedDomainGuards(unittest.TestCase):
    def test_01_all64_exact_handshakes_and_metadata(self):
        identities=[]
        for slot in range(4096,4160):
            s=subject(slot);identities += [s['session'],s['connection']]
            self.assertEqual(codec.decode_handshake(codec.encode_handshake(**s)),s)
            meta=copy.deepcopy(metadata_template);meta.update(s)
            self.assertEqual(codec.metadata(meta),meta)
        self.assertEqual(len(set(identities)),128)

    def test_02_exact_outside_domain_and_identity_width_refusals(self):
        for slot in (4095,4160,8191,True,4096.0):
            with self.subTest(slot=slot),self.assertRaises(ValueError):codec.encode_handshake(slot,'1'*32,'2'*32)
        for field,value in [('slot',4160),('session','1'*64),('nonce','1'*32)]:
            meta=copy.deepcopy(metadata_template);meta[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):codec.metadata(meta)

    def test_03_lower32_byte_and_metadata_parity(self):
        for slot in range(4096,4128):
            s=subject(slot)
            self.assertEqual(codec.encode_handshake(**s),old_codec.encode_handshake(**s))
            meta=copy.deepcopy(metadata_template);meta.update(s)
            self.assertEqual(codec.metadata(copy.deepcopy(meta)),old_codec.metadata(copy.deepcopy(meta)))

    def test_04_real64_proxy_and_authority_constructors(self):
        with tempfile.TemporaryDirectory()as tmp:
            journal=journal_module.GameJournal(Path(tmp)/'journal',clock=lambda:2e-7,completion_policy='confirmed_reset_reserves_v1')
            with patch.object(bridge.socket,'socket',side_effect=AssertionError('network forbidden'))as sock, \
                 patch.object(threading.Thread,'start',side_effect=AssertionError('thread forbidden'))as thread:
                for cid,slot in enumerate(range(4096,4160)):
                    p=Path(tmp)/str(slot);p.touch(mode=0o600);stat=p.stat()
                    identity=dict(device=stat.st_dev,inode=stat.st_ino,mode=oct(stat.st_mode&0o777),uid=stat.st_uid,nlink=stat.st_nlink)
                    events=[]
                    proxy=bridge.StartupProxy(object(),**subject(slot),trace_path=p,trace_identity=identity,
                        rom_sha256=original['loaded_rom_sha256'],policy_reader=lambda:copy.deepcopy(POLICY),
                        admission_reader=lambda:copy.deepcopy(WINDOW),frame_parser=lambda _:None,emit=events.append,
                        stop_event=threading.Event(),drain_reader=lambda:None)
                    auth=issuer(journal,slot,cid)
                    self.assertEqual(proxy.subject,subject(slot));self.assertEqual(auth.slot,slot)
                    self.assertEqual(events[0]['subject'],subject(slot))
                sock.assert_not_called();thread.assert_not_called()

    def test_05_real64_certificate_issue_and_confirmed_journal_handoff(self):
        with tempfile.TemporaryDirectory()as tmp:
            journal=journal_module.GameJournal(Path(tmp)/'journal',clock=lambda:2e-7,completion_policy='confirmed_reset_reserves_v1')
            for cid,slot in enumerate(range(4096,4160)):
                auth=issuer(journal,slot,cid);evidence=authorization_and_evidence(auth,cid)
                permit=auth.issue(lambda:copy.deepcopy(evidence))
                origin=evidence['origin_acceptance']
                cs=dict(client_slot=slot,frames=origin['accepted_frames'],game_uid=origin['game_uid'],eval_only=True)
                journal.observe(cid,FRAME,cs,context=lambda:copy.deepcopy(CONTEXT))
                auth.handoff(permit,FRAME,cs,lambda:copy.deepcopy(CONTEXT))
                self.assertTrue(journal.active[cid]['known_start'])
                self.assertEqual(journal.active[cid]['start']['startup_certificate']['identifier'],permit.identifier)
                RESULTS.append(dict(slot=slot,certificate_identifier=permit.identifier,journal_game_id=journal.active[cid]['journal_game_id']))
            rows=[json.loads(line)for line in journal.measurement_starts_path.read_bytes().splitlines()]
            self.assertEqual(len(rows),64);self.assertEqual({r['client_slot']for r in rows},set(range(4096,4160)))
            with self.assertRaises(ValueError):auth.handoff(permit,FRAME,cs,lambda:copy.deepcopy(CONTEXT))
            self.assertEqual(len(journal.measurement_starts_path.read_bytes().splitlines()),64)

    def test_06_foreign_subject_or_tampered_certificate_refused(self):
        with tempfile.TemporaryDirectory()as tmp:
            journal=journal_module.GameJournal(Path(tmp)/'journal',completion_policy='confirmed_reset_reserves_v1')
            with self.assertRaises(ValueError):issuer(journal,4160,0)
            for field,value in [('slot',4160),('connection','f'*32),('nonce','f'*64)]:
                auth=issuer(journal,4159,0);e=authorization_and_evidence(auth,0);e['application'][field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):auth.issue(lambda:copy.deepcopy(e))

    def test_07_all_fork_bodies_inverse_exact_and_public_imports_isolated(self):
        for row in derivation['derivations']:
            text=h.checked(row['derived']).read_text()
            for before,after in reversed(row['exact_changes']):
                self.assertEqual(text.count(after),1);text=text.replace(after,before)
            self.assertEqual(text,h.checked(row['parent']).read_text())
        self.assertIs(bridge.codec,codec);self.assertIs(bridge.authority,authority)
        self.assertEqual(Path(codec.__file__).parent,F);self.assertEqual(Path(authority.__file__).parent,F)
        self.assertNotIn('torch',sys.modules)


def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SharedDomainGuards))
    report=dict(schema='robotron-capacity64-shared-domain-actual-constructor-certificate-CPU-guards-v1',
        source=h.pin(__file__),source_derivation=manifest,tests_run=r.testsRun,passed=r.wasSuccessful(),
        failures=len(r.failures),errors=len(r.errors),actual64_synthetic_subject_certificates_and_journal_handoffs=RESULTS,
        real_codec_proxy_authority_and_confirmed_GameJournal_used=True,historical_ROM_and_evidence_only_fixture=True,
        actual64_live_MAME_startup_verified=False,native_launch_ready=False,quality_qualified=False,
        original_failed_B1_retried=False,main_or_held_original_sources_changed=False)
    print(json.dumps(dict(report=h.put(F/'CPU-shared-domain-guards-original01/actual-CPU-shared-domain-guard-results.json',report),
                          tests_run=r.testsRun,passed=r.wasSuccessful())),flush=True)
    time.sleep(8);return 0 if r.wasSuccessful()else 1


if __name__=='__main__':raise SystemExit(main())
