"""Actual raw chain replay and explicitly synthetic sequential-spawn fixtures."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from . import round_admission_proof_v1 as a
from . import round_health_transport_v6 as health

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'logs/managed-learning-20261015/run-26'


def rewrite(record,value):
    raw=(json.dumps(value,indent=2)+'\n').encode()
    record['raw']=raw.decode();record['sha256']=hashlib.sha256(raw).hexdigest()
    record['identity']['bytes']=len(raw)


def transport(sample):
    uid=os.getuid();lines=['header'];owners=dict(trainer=['101']);namespace='net:[ENGINEERING]'
    def row(index,local,remote,state,inode):
        return f'{index}: {local} {remote} {state} 00000000:00000000 00:00000000 00000000 {uid} 0 {inode}'
    lines.append(row(0,'00000000:270E','00000000:0000','0A','101'))
    connected={str(row['client_slot'])for row in sample['api']['client_rows']}
    for slot in sample['actors']:
        owners[slot]=[]
        if slot not in connected:continue
        index=int(slot);port=f'{40000+index:04X}';server=str(2000+index);client=str(3000+index)
        owners['trainer'].append(server);owners[slot].append(client)
        lines.append(row(2*index+1,'0100007F:270E','0100007F:'+port,'01',server))
        lines.append(row(2*index+2,'0100007F:'+port,'0100007F:270E','01',client))
    sample['transport']=dict(raw_tables=dict(tcp='\n'.join(lines)+'\n',tcp6='header\n'),
        socket_inodes=owners,namespaces={key:namespace for key in owners},collector_namespace=namespace)


class RoundAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_case=None
        # This actual snapshot is supplied by the original bounded CPU driver.
        directory=Path(os.environ['ROBOTRON_ADMISSION_ENGINEERING_FIXTURES'])
        cls.original_case=json.loads((directory/'declared-original-round-case.json').read_bytes())
        cls.actual=json.loads((directory/'actual-initial.raw.json').read_bytes())
        cls.actual_next=json.loads((directory/'actual-next.raw.json').read_bytes())

    def fixture(self,spawned=3,connected=1):
        """Synthetic phase, anchored to actual closed-round bytes and sources."""
        sample=copy.deepcopy(self.actual);case=copy.deepcopy(self.original_case)
        closed=copy.deepcopy(sample['round_admission']['closed_chain'][-1]);old=closed['round'];number=old+1
        case['initial_round']=old;case.pop('baseline_snapshot',None)
        now=sample['unix_s'];summary=json.loads(closed['summary']['raw']);summary['updated_unix_s']=now-.3
        rewrite(closed['summary'],summary)
        prior=copy.deepcopy(sample);prior.pop('round_admission',None)
        prior.update(actors={},results={slot:json.loads(value['raw'])for slot,value in closed['receipts'].items()},
            receipt_hashes={slot:value['sha256']for slot,value in closed['receipts'].items()},
            status=copy.deepcopy(summary),started=json.loads(closed['started']['raw']),previous_complete=None,
            unix_s=now-.3,monotonic_s=sample['monotonic_s']-.3)
        prior['api'].update(client_count=0,client_rows=[],ts=now-.3)
        prior['observed_counts']=health.base().observed_counts(prior);transport(prior)
        started=a.capture(Path(case['round_root'])/('round-%06d'%number)/'started.json')
        start=json.loads(started['raw']);start['started_unix_s']=now-.2;rewrite(started,start)
        model=copy.deepcopy(next(iter(sample['actors'].values())))
        actors={}
        for slot in range(spawned):
            actor=copy.deepcopy(model);actor.update(pid=20_000_000+slot,starttime_ticks=30_000_000+slot,state='S')
            actor['environment'].update(ROBOTRON_CLIENT_SLOT=str(slot),ROBOTRON_ACTOR_ROUND=str(number),
                ROBOTRON_EVAL_MODE='1'if case['slot_eval'][str(slot)]else'2',
                ROBOTRON_PREVIEW_CLIENT='1'if slot==0 else'0')
            actors[str(slot)]=actor
        sample.update(actors=actors,status=copy.deepcopy(prior['status']),results=copy.deepcopy(prior['results']),
            receipt_hashes=copy.deepcopy(prior['receipt_hashes']),started=copy.deepcopy(prior['started']),previous_complete=None)
        rows=[dict(client_slot=slot,client_id=9000+slot,eval=case['slot_eval'][str(slot)],connected_seconds=.04)
            for slot in range(connected)]
        sample['api'].update(client_count=len(rows),client_rows=rows,ts=now-.1)
        proof=copy.deepcopy(sample['round_admission'])
        proof.update(effective_round=number,published_round=old,bootstrap=True,chain_start=old,
            closed_chain=[closed],current=dict(round=number,started=started,receipts={}),
            pending=list(map(str,range(spawned,192))),registering=list(map(str,range(connected,spawned))))
        identifiers={outer['result']['journal_game_id']for outer in prior['results'].values()}
        proof['committed_journal_lines']={key:value for key,value in proof['committed_journal_lines'].items()if key in identifiers}
        sample['round_admission']=proof
        sample['observed_counts']=health.base().observed_counts(sample);transport(sample)
        return case,prior,sample

    def test_actual_initial_jump_replays_every_intervening_closed_round(self):
        health.check_inputs(self.original_case,full=True)
        health.validate(self.original_case,self.actual)
        proof=self.actual['round_admission']
        self.assertEqual([x['round']for x in proof['closed_chain']],list(range(self.original_case['initial_round'],self.actual['status']['round'])))
        self.assertGreater(len(proof['closed_chain']),0)

    def test_actual_next_snapshot_keeps_ordinary_path_and_learning_lineage(self):
        self.assertNotIn('round_admission',self.actual_next)
        health.validate(self.original_case,self.actual_next,previous=self.actual)

    def test_synthetic_original_bootstrap_accepts_only_accounted_spawn_prefix(self):
        for spawned in (0,1,64,191,192):
            with self.subTest(spawned=spawned):
                case,prior,sample=self.fixture(spawned,spawned//2)
                health.validate(case,prior)
                health.validate(case,sample,previous=prior)

    def test_synthetic_bootstrap_can_advance_and_publish_without_clock_or_birth_reset(self):
        case,prior,first=self.fixture(3,1);health.validate(case,first,previous=prior)
        _,_,second=self.fixture(64,32)
        second['unix_s']+=.1;second['monotonic_s']+=.1;second['api']['ts']+=.1
        health.validate(case,second,previous=first)
        _,_,published=self.fixture(192,64)
        p=published['round_admission'];p.update(published_round=p['effective_round'],chain_start=p['effective_round'],closed_chain=[],committed_journal_lines={})
        published.update(status=dict(round=p['effective_round'],total=192,completed=0,retired=0,active=192,
            complete=False,updated_unix_s=published['unix_s']),started=json.loads(p['current']['started']['raw']),results={},receipt_hashes={})
        published['unix_s']+=.2;published['monotonic_s']+=.2;published['api']['ts']+=.2
        published['observed_counts']=health.base().observed_counts(published)
        health.validate(case,published,previous=second)
        normal=copy.deepcopy(published);normal.pop('round_admission');normal['unix_s']+=.1;normal['monotonic_s']+=.1
        normal['api'].update(client_count=192,client_rows=[dict(client_slot=slot,client_id=9000+slot,
            eval=case['slot_eval'][str(slot)],connected_seconds=.1)for slot in range(192)],ts=normal['unix_s'])
        transport(normal);health.validate(case,normal,previous=published)

    def test_missing_changed_or_noncommitted_original_barriers_rejected(self):
        for fault in ('missing_score','journal_uncommitted','journal_wrong_score','retired191','wrong_mean','wrong_csv','raw_hash','early_start','wrong_source'):
            case,prior,sample=self.fixture();proof=sample['round_admission'];closed=proof['closed_chain'][0]
            if fault=='missing_score':closed['receipts'].pop('0')
            elif fault=='journal_uncommitted':
                key=next(iter(proof['committed_journal_lines']));proof['committed_journal_lines'][key]=proof['committed_journal_lines'][key].rstrip('\n')
            elif fault=='journal_wrong_score':
                key=next(iter(proof['committed_journal_lines']));row=json.loads(proof['committed_journal_lines'][key]);row['score']+=1
                proof['committed_journal_lines'][key]=json.dumps(row)+'\n'
            elif fault in ('retired191','wrong_mean'):
                row=json.loads(closed['summary']['raw']);row['retired'if fault=='retired191'else'mean']+=1;rewrite(closed['summary'],row)
            elif fault=='wrong_csv':closed['scores_csv']['raw']=closed['scores_csv']['raw'].replace('slot,score','slot,wrong',1)
            elif fault=='raw_hash':closed['started']['sha256']='f'*64
            elif fault=='early_start':
                row=json.loads(proof['current']['started']['raw']);row['started_unix_s']=sample['unix_s']-1;rewrite(proof['current']['started'],row)
            else:case['inputs'][str(a.FLEET)]['sha256']='f'*64
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):
                health.validate(case,sample,previous=prior)

    def test_old_actor_pending_disappearance_stale_bootstrap_and_API_rejected(self):
        for fault in ('old_pid','not_suffix','bootstrap_expired','API_stale','old_API_row','unknown_API_slot','wrong_role','changed_owner','changed_epoch'):
            case,prior,sample=self.fixture();proof=sample['round_admission']
            if fault=='old_pid':sample['actors']['0']['pid']=prior['results']['0']['pid']
            elif fault=='not_suffix':proof['pending']=proof['pending'][:-1]
            elif fault=='bootstrap_expired':sample['unix_s']+=5.001
            elif fault=='API_stale':sample['api']['ts']=sample['unix_s']-.501
            elif fault=='old_API_row':sample['api']['client_rows'][0]['connected_seconds']=1
            elif fault=='unknown_API_slot':sample['api']['client_rows'][0]['client_slot']=191
            elif fault=='wrong_role':sample['actors']['0']['environment']['ROBOTRON_EVAL_MODE']='3'
            elif fault=='changed_owner':sample['owners']['trainer']['process']['pid']+=1
            else:sample['api']['host_pipeline']['learning_exposure']['replay']['epoch']+=1
            with self.subTest(fault=fault),self.assertRaises((ValueError,KeyError)):
                health.validate(case,sample,previous=prior)

    def test_spawned_actor_cannot_disappear_into_pending_or_be_replaced(self):
        case,prior,first=self.fixture(64,32);health.validate(case,first,previous=prior)
        _,_,smaller=self.fixture(3,1)
        with self.assertRaises(ValueError):health.validate(case,smaller,previous=first)
        larger=copy.deepcopy(first);larger['actors']['0']['starttime_ticks']+=1
        with self.assertRaises(ValueError):health.validate(case,larger,previous=first)

    def test_unknown_physical_client_rejected_by_unchanged_TCP_predicates(self):
        case,prior,sample=self.fixture()
        raw=sample['transport']['raw_tables']['tcp'];sample['transport']['raw_tables']['tcp']=raw+raw.splitlines()[2]+'\n'
        with self.assertRaises(ValueError):health.validate(case,sample,previous=prior)

    def test_missing_chain_round_or_changed_original_receipt_rejected(self):
        for fault in ('hole','changed_receipt'):
            sample=copy.deepcopy(self.actual);case=copy.deepcopy(self.original_case)
            if fault=='hole':sample['round_admission']['closed_chain'].pop(0)
            else:
                row=sample['round_admission']['closed_chain'][0]['receipts']['0'];row['sha256']='f'*64
            with self.subTest(fault=fault),self.assertRaises(ValueError):health.validate(case,sample)

    def test_raw_API_and_status_bytes_are_not_rewritten_during_verification(self):
        case,prior,sample=self.fixture();before=copy.deepcopy(sample)
        health.validate(case,sample,previous=prior);self.assertEqual(sample,before)

    def test_actual_unchanged_fleet_publishes_start_before_spawn_and_reaps_before_next_round(self):
        spec=importlib.util.spec_from_file_location('_admission_test_actual_fleet',a.FLEET)
        fleet=importlib.util.module_from_spec(spec);spec.loader.exec_module(fleet)
        with tempfile.TemporaryDirectory(prefix='robotron-original-fleet-ENGINEERING-')as directory:
            root=Path(directory);journal=root/'journal.jsonl';journal.write_text('')
            output=root/'rounds';output.mkdir();(output/'round-000006').mkdir()
            fleet.publish(output/'status.json',dict(round=6,complete=True,retired=192))
            run=fleet.RoundFleet(dict(slot_eval={str(slot):False for slot in range(192)}),journal,output)
            born=[];reaped=[];phases=[]
            class Child:
                def __init__(self,slot):self.slot=slot;self.pid=20_000_000+slot
                def poll(self):return 0
                def wait(self,timeout=None):reaped.append(self.slot);return 0
                def send_signal(self,*args):raise AssertionError('Synthetic exited child cannot be signalled')
                def terminate(self):raise AssertionError('Synthetic exited child cannot be terminated')
                def kill(self):raise AssertionError('Synthetic exited child cannot be killed')
            def spawn(slot,directory,number):
                self.assertEqual(json.loads((directory/'started.json').read_bytes())['round'],7)
                self.assertEqual(json.loads((output/'status.json').read_bytes())['round'],6)
                self.assertEqual(born,list(range(slot)))
                phases.append(dict(spawned=len(born),pending=list(range(slot,192))))
                born.append(slot);return dict(process=Child(slot),started_unix_s=time.time(),frozen=False)
            class Journal:
                def poll(self):
                    now=time.time()
                    return [dict(client_slot=slot,journal_game_id='ENGINEERING-'+str(slot),complete=True,
                        eligible=True,known_start=True,boundary_reason='score_reset',score=slot,
                        max_level=1,duration_s=1,start_unix_s=now)for slot in range(192)]
            run.spawn=spawn;run.journal=Journal();run.wait_ready=lambda:None
            original_round=run.run_round;next_round=[]
            def one_then_observe(number):
                if number==7:return original_round(number)
                self.assertEqual(number,8);self.assertEqual(reaped,list(range(192)))
                closed=json.loads((output/'round-000007/summary.json').read_bytes())
                self.assertTrue(closed['all_final_scores_durable']);self.assertEqual(closed['retired'],192)
                next_round.append(number);return False
            run.run_round=one_then_observe
            with patch.object(fleet.subprocess,'Popen',side_effect=AssertionError('No real process launch allowed')):
                run.run()
            self.assertEqual(len(phases),192);self.assertEqual(next_round,[8])
