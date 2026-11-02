"""Synthetic closed32-slot artifacts; no pilot, GPU, model or policy claim."""
import copy
import hashlib
import json
from pathlib import Path
import statistics
import tempfile
import unittest

import audit_pilot_evidence as review
import audit_confirmed_completed_leg_reviewed3 as auditor
from Robotron.tools import compare_sidecar_measurements as backend
from Robotron.tools.test_eval_capacity import receipt32
from Robotron.tools.test_compare_sidecar_measurements import write_terminal_fixture


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.data=receipt32('synthetic-pilot32')
        checkpoint=self.root/'frozen.pt';checkpoint.write_bytes(b'synthetic frozen bytes\n')
        self.data.update(checkpoint_path=str(checkpoint),checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            checkpoint_metadata=copy.deepcopy(self.data['clocks']),timeout_snapshot_unix_s=200,
            server_error=None,inference_error=None,cleanup_errors=[])
        self.data['job'].update(directory=str(self.root),host='127.0.0.1')
        self.data['source_hashes']={'Scripts/dqn/socket_server.py':review.HANDLER_SHA}
        self.data['ended_source_hashes']=dict(self.data['source_hashes'])
        self.data['boundary'].update(expected=32,acknowledged=32,acknowledged_client_ids=list(range(32)))
        for index,row in enumerate(self.data['rows']):
            row.update(client_id=index%32,start_utc=f'synthetic-start-{index}')
            diagnostic=copy.deepcopy(row['terminal_confirmation']['ingest_boundary_inputs'])
            diagnostic.update(recent_start=True,last_start_frame_before=4,last_start_frame_after=4)
            diagnostic['previous_accepted_wire']['player_alive']=False
            diagnostic['current_wire']['player_alive']=False
            row['terminal_confirmation']['ingest_boundary_inputs']=copy.deepcopy(diagnostic)
            diagnostic['journal_start_reason']=row['start_reason']
            row['start_context']['game_boundary_diagnostics']=copy.deepcopy(diagnostic)
            self.data['terminal_successors'][row['journal_game_id']]['client_id']=row['client_id']
        scores=[row['score'] for row in self.data['rows']]
        stats=dict(count=50,started=50,mean=statistics.mean(scores),median=statistics.median(scores),
            sd=statistics.stdev(scores),se=statistics.stdev(scores)/(50**.5))
        self.data.update(stats)
        self.data['cohort']=dict(stats,started_ids=[r['journal_game_id'] for r in self.data['rows']],
            started_actor_slots=list(review.SLOTS),complete=True,valid=True,closed=True)
        for key in ('actor_timeout_logs_before_shutdown','actor_timeout_logs_after_shutdown'):
            self.data[key]={str(slot):0 for slot in review.SLOTS}
        for slot in review.SLOTS:
            self.data['socket_wait']['actors'][str(slot)]['pid']=80000+slot
            path=self.root/'actors'/str(slot)/'console.log';path.parent.mkdir(parents=True)
            path.write_text('Lua startup\nALSA lib seq_hw.c:528:(snd_seq_hw_open) open /dev/snd/seq failed: Permission denied\n'
                'MAME interface initialized.\nSocket connection opened to socket.127.0.0.1:9999\n'
                f'[robotron-socket-wait] pid={80000+slot} fd=8 port=9999 interval_us=1000\n')
        self.write_originals()

    def write_originals(self):
        for row in self.data['rows']:
            self.data['terminal_successors'][row['journal_game_id']]['context']['game_boundary_diagnostics']=copy.deepcopy(
                row['terminal_confirmation']['ingest_boundary_inputs'])
        write_terminal_fixture(self.data,self.root)
        path=self.root/'journal/measurement_starts.jsonl';starts=[json.loads(line) for line in path.read_bytes().splitlines()]
        rows={row['journal_game_id']:row for row in self.data['rows']}
        for entry in starts:
            if entry['journal_game_id'] in rows:
                row=rows[entry['journal_game_id']]
                for key in ('start_utc','experiment','measurement_active','measurement_generation'):
                    entry[key]=copy.deepcopy(row[key])
        path.write_bytes(b''.join((json.dumps(entry)+'\n').encode() for entry in starts))
        self.rehash('measurement_starts.jsonl')

    def rehash(self,name):
        self.data['terminal_journal_sha256'][name]=hashlib.sha256((self.root/'journal'/name).read_bytes()).hexdigest()

    def games(self):return review.original_games(self.data,self.root,backend,auditor)
    def logs(self):return review.actor_logs(self.data,self.root,auditor)
    def console(self,text,validated=True):
        return review.console_lines(text,self.data,Path('/synthetic/private/game'),auditor,
            unused_expert_proof_validated=validated)

    def test_all50_originals_and_ROM_proofs_cover32_slots_without_mutation(self):
        before=copy.deepcopy(self.data);result=self.games()
        self.assertEqual(self.data,before);self.assertEqual(result['statistics']['count'],50)
        self.assertEqual(result['original_terminal_readback']['verified_games'],50)
        self.assertEqual(result['rom_game_over_evidence']['verified_games'],50)
        self.assertGreater(self.data['rows'][-1]['end_unix_s'],self.data['close_ts'])
        self.assertFalse(result['quality_qualified']);self.assertFalse(result['promotion'])

    def test_pending_abandoned_invalid_or_under50_are_rejected(self):
        original=copy.deepcopy(self.data)
        for field,value in (('pending',1),('abandoned',1),('complete',False),('valid',False)):
            self.data=copy.deepcopy(original);self.data[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):self.games()
        self.data=copy.deepcopy(original);self.data['rows'].pop()
        with self.assertRaises(ValueError):self.games()

    def test_both_original_journals_are_mandatory_and_unchanged(self):
        for name in ('games.jsonl','measurement_starts.jsonl'):
            path=self.root/'journal'/name;raw=path.read_bytes();path.write_bytes(raw+b'\n')
            with self.subTest(name=name),self.assertRaises(ValueError):self.games()
            path.unlink()
            with self.assertRaises(FileNotFoundError):self.games()
            path.write_bytes(raw)

    def test_checkpoint_bytes_are_actually_read_back(self):
        Path(self.data['checkpoint_path']).write_bytes(b'different bytes')
        with self.assertRaises(ValueError):self.games()

    def test_any_additional_original_admission_without_a_full_tail_fails(self):
        path=self.root/'journal/measurement_starts.jsonl';entry=json.loads(path.read_bytes().splitlines()[0])
        entry['journal_game_id']='synthetic-additional-admitted-game'
        with path.open('ab') as stream:stream.write((json.dumps(entry)+'\n').encode())
        self.rehash('measurement_starts.jsonl')
        with self.assertRaises(ValueError):self.games()

    def test_32_slots_cannot_share16_client_identities(self):
        for index,row in enumerate(self.data['rows']):
            row['client_id']=index%16
            self.data['terminal_successors'][row['journal_game_id']]['client_id']=row['client_id']
        self.write_originals()
        with self.assertRaisesRegex(ValueError,'mapping'):self.games()

    def test_ROM_proof_requires_exhausted_reserves_inactive_player_and_restart(self):
        original=copy.deepcopy(self.data)
        for key in ('reserve','alive','restart'):
            self.data=copy.deepcopy(original);row=self.data['rows'][0];confirmation=row['terminal_confirmation']
            if key=='reserve':confirmation['previous_raw_reserves']=1
            elif key=='restart':confirmation['ingest_boundary_inputs']['recent_start']=False
            else:
                confirmation['ingest_boundary_inputs']['previous_accepted_wire']['player_alive']=True
                confirmation['ingest_boundary_inputs']['current_wire']['player_alive']=True
            self.write_originals()
            with self.subTest(key=key),self.assertRaises(ValueError):self.games()

    def test_saved_statistics_metadata_or_registry_cannot_diverge(self):
        original=copy.deepcopy(self.data)
        for change in ('mean','median','checkpoint_clock','registry'):
            self.data=copy.deepcopy(original)
            if change in ('mean','median'):self.data[change]+=1
            elif change=='checkpoint_clock':self.data['checkpoint_metadata']['training_steps']+=1
            else:self.data['cohort']['started_ids'][0]='foreign'
            with self.subTest(change=change),self.assertRaises(ValueError):self.games()

    def test_every32_actor_log_including_highest_slot_is_required(self):
        result=self.logs();self.assertEqual(set(result['slots']),{str(s) for s in review.SLOTS})
        (self.root/'actors/4127/console.log').unlink()
        with self.assertRaises(FileNotFoundError):self.logs()

    def test_actual_runtime_and_missing_time_timeouts_are_rejected(self):
        path=self.root/'actors/4127/console.log';original=path.read_text()
        self.data['actor_timeout_logs_after_shutdown']['4127']=1;self.data['actor_cleanup_timeout_logs']['4127']=1
        for event in ('[SOCKET ACTION TIMEOUT] unix_s=200','[SOCKET ACTION TIMEOUT]'):
            path.write_text(original+event+'\n')
            with self.subTest(event=event),self.assertRaises(ValueError):self.logs()

    def test_proven_later_cleanup_timeout_keeps_original_diagnostic(self):
        path=self.root/'actors/4127/console.log'
        with path.open('a') as f:f.write('[SOCKET ACTION TIMEOUT] unix_s=201\nSocket open failed: socket.127.0.0.1:9999 (Connection refused)\n')
        self.data['actor_timeout_logs_after_shutdown']['4127']=1;self.data['actor_cleanup_timeout_logs']['4127']=1
        result=self.logs()['slots']['4127'];self.assertEqual((result['runtime'],result['cleanup']),(0,1))
        self.assertTrue(result['allowed_lines'])

    def test_unknown_actor_error_wrong_activation_or_accounting_fails(self):
        path=self.root/'actors/4127/console.log';original=path.read_text()
        for text in (original+'RuntimeError: wrong state\n',original.replace('pid=84127','pid=1')):
            path.write_text(text)
            with self.assertRaises(ValueError):self.logs()
        path.write_text(original);self.data['actor_timeout_logs_after_shutdown']['4127']=1
        with self.assertRaises(ValueError):self.logs()

    def test_cutoff_before_any_full_tail_forbids_shutdown_classification(self):
        self.data['timeout_snapshot_unix_s']=168
        with self.assertRaises(ValueError):self.logs()
        with self.assertRaises(ValueError):self.console('Client 7 disconnected: EOF')

    def test_same_source_unused_expert_warning_requires_exact_proof_and32_greedy_controls(self):
        text='Startup\n'+auditor.OPTIONAL_EXPERT_WARNING
        self.assertEqual(len(self.console(text)),1)
        self.assertFalse(auditor.optional_expert_warning(2,auditor.OPTIONAL_EXPERT_WARNING,
            self.data['job'],self.data['rows'],True)) # Existing16-slot auditor is unchanged.
        with self.assertRaises(ValueError):self.console(text,False)
        self.data['source_hashes']['Scripts/dqn/socket_server.py']='0'*64
        with self.assertRaises(ValueError):self.console(text)

    def test_other_warnings_exploration_and_foreign_tracebacks_still_fail(self):
        for text in ('Startup\n[WARN] other expert unavailable','Traceback (most recent call last):\n  File "foreign.py", line 1, in infer\nRuntimeError: Inference batcher is stopped'):
            with self.subTest(text=text),self.assertRaises(ValueError):self.console(text)
        self.data['job']['expert_ratio']=.1
        with self.assertRaises(ValueError):self.console('Startup\n'+auditor.OPTIONAL_EXPERT_WARNING)

    def test_exact_closed_batcher_cleanup_trace_is_classified(self):
        text='Traceback (most recent call last):\n  File "/synthetic/private/game/Scripts/dqn/socket_server.py", line 1, in handle_client\n    action = infer()\n  File "/synthetic/private/game/Scripts/dqn/socket_server.py", line 2, in infer\n    raise stopped\nRuntimeError: Inference batcher is stopped\nClient 7 disconnected: EOF'
        self.assertTrue(self.console(text))


if __name__=='__main__':unittest.main()
