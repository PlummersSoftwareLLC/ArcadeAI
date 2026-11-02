"""Tiny fake/temp-only reference tests; never inspect a new private cohort/model."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import statistics
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('quality1200_fixture',HERE/'quality1200_reference.py')
helper=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(helper)


def stats(rows,labels=None):
    values=[float(row['score']) for row in rows]
    sd=statistics.stdev(values) if len(values)>1 else 0.
    return dict(count=len(values),mean=statistics.mean(values),median=statistics.median(values),sd=sd,se=sd/len(values)**.5)


def fixture():
    saved=dict(training_steps=100,optimized_samples=409600,learner_frame_count=200,frame_count=400)
    job=dict(device='cuda',gpu_uuid='fakeGPU0',actors=16,actor_slots=helper.SLOTS,port=9999,
        cohort_s=1200.,timeout_s=2400.,wait_us=1000,inference_backend='inductor')
    plan=dict(schema='robotron-quality1200-plan-v1',fixed_labels={'192M_reference':list(helper.LABELS)},
        reference=dict(required_valid_legs=2,checkpoint=dict(path='/FAKE/protected192.pt',sha256='a'*64,stat={}),saved_metadata=saved),
        history=dict(path='/FAKE/history.json',sha256='h'*64,expected_receipts=26,expected_unique_games=2613),
        publication=dict(reference_output=str(helper.RUN/'quality1200-reference-final.json')),
        backend=dict(job=job,numeric_policy={'weights':'float32'},runtime={'torch':'fake'},source_hashes={'12':'fake'},
                     boot_identity='boot',boot_files={'fake':'seed'},socket_wait_sha256='s'*64),root_design={})
    design=dict(root_adopted_design=True,fixed_labels=copy.deepcopy(plan['fixed_labels']),reference_checkpoint_sha256='a'*64)
    plan['validity']=dict(official_min_games=50,precision_only_N_below=64,operational_replacement_authorized=False)
    rows=[dict(journal_game_id='new:'+str(i),client_slot=4096+i%16,score=0.,boundary_reason='wire_lives_exhausted',end_unix_s=1301.+i/100.) for i in range(64)]
    boundary=dict(clients=16,expected=16,acknowledged=16,generation=1,requested_generation=1,actor_slots=helper.SLOTS)
    receipt=dict(label=helper.LABELS[0],phase='finished',reason=None,receipt_validator='passed',
        checkpoint_sha256='a'*64,source_checkpoint_path=plan['reference']['checkpoint']['path'],
        checkpoint_path='/FAKE/privatecopy.pt',job={**copy.deepcopy(job),'checkpoint':plan['reference']['checkpoint']['path']},
        numeric_policy=plan['backend']['numeric_policy'],runtime=plan['backend']['runtime'],source_hashes=plan['backend']['source_hashes'],
        boot_assets=dict(identity='boot',files={'fake':'seed'}),socket_wait=dict(sha256='s'*64,actors={str(i):dict(activation_count=1) for i in helper.SLOTS}),
        checkpoint_metadata={**saved,'defaulted_metadata_fields':[]},clocks=dict(saved),boundary=boundary,generation=1,
        ended_unix_s=1400.,started=64,count=64,**{k:v for k,v in stats(rows).items() if k!='count'},_rows=rows)
    def validate_backend(document,verify_checkpoint):
        if verify_checkpoint is not False:raise AssertionError('Unexpected model hash/load delegated')
        if document.get('_official_invalid'):raise ValueError('official full-tail validation failed')
        return dict(label=document['label'],rows=document['_rows'],start_ts=100.,close_ts=1300.,
            clocks={**saved,'learner_frames':saved['learner_frame_count']},expected_actor_slots=helper.SLOTS)
    tools=SimpleNamespace(JOB_FIELDS=list(job),validate_backend=Mock(side_effect=validate_backend),summarize=stats)
    shared=SimpleNamespace(META_KEYS=list(saved),CORE_CLOCKS=list(saved),summarize=stats)
    return plan,design,receipt,tools,shared


class Evidence:
    def __init__(self,documents=None):self.documents=documents or {};self.files={};self.rechecks=0;self.pins=[]
    def file(self,path,expected=None):self.pins.append((str(path),expected));return Path(path)
    def json(self,path,expected=None):
        key=str(Path(path).absolute());self.files[key]='b'*64
        return self.documents[key]
    def recheck(self):self.rechecks+=1
    def snapshot(self):return {'fake':True}


class ReferenceTests(unittest.TestCase):
    def test_import_help_and_default_never_read_evidence(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('Evidence read')),patch.object(Path,'open',side_effect=AssertionError('Evidence open')):
            spec=importlib.util.spec_from_file_location('inert_reference1200',HERE/'quality1200_reference.py')
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with patch('builtins.print'):self.assertEqual(module.main([]),0)
            with self.assertRaises(SystemExit) as exited:module.main(['--help'])
            self.assertEqual(exited.exception.code,0)

    def test_exact_fixed_plan_windows_labels_and_no_replacement(self):
        plan,design,*_=fixture();helper.check_plan(plan,design)
        for kind in ('window','timeout','labels','cardinality','replacement','floor'):
            broken=copy.deepcopy(plan)
            if kind=='window':broken['backend']['job']['cohort_s']=600
            elif kind=='timeout':broken['backend']['job']['timeout_s']=1200
            elif kind=='labels':broken['fixed_labels']['192M_reference'].reverse()
            elif kind=='cardinality':broken['reference']['required_valid_legs']=1
            elif kind=='replacement':broken['validity']['operational_replacement_authorized']=True
            else:broken['validity']['official_min_games']=64
            with self.subTest(kind=kind),self.assertRaises(ValueError):helper.check_plan(broken,design)

    def test_cardinality_rejected_before_context_or_future_receipt(self):
        for labels in ([helper.LABELS[0]],list(reversed(helper.LABELS)),[*helper.LABELS,'third'],[helper.LABELS[0]]*2):
            with self.subTest(labels=labels),patch.object(helper,'context',side_effect=AssertionError('future opened')),self.assertRaises(ValueError):
                helper.build(labels,[],[])

    def test_exact_positive_audit_sha_and_ownedcleanup_required(self):
        valid=dict(pass_=True)
        valid={'pass':True,'checks':dict(private_owned_processes_listener_released=True,private_GPU0_context_released=True,loaded_sources_unchanged=True),'receipt_sha256':'b'*64,'checkpoint_sha256':'a'*64}
        helper.positive_audit(valid,'b'*64,'a'*64)
        for kind in ('receipt','policy','cleanup','othercheck'):
            broken=copy.deepcopy(valid)
            if kind=='receipt':broken['receipt_sha256']='x'*64
            elif kind=='policy':broken['checkpoint_sha256']='x'*64
            elif kind=='cleanup':broken['checks']['private_GPU0_context_released']=False
            else:broken['checks']['new_error']=False
            with self.subTest(kind=kind),self.assertRaises(ValueError):helper.positive_audit(broken,'b'*64,'a'*64)

    def test_whole_valid_reference_can_score_zero_no_quality_selection(self):
        plan,_,receipt,tools,shared=fixture();evidence=Evidence()
        leg=helper.validate_reference_leg(receipt,helper.LABELS[0],plan,evidence,tools,shared)
        self.assertEqual(len(leg['rows']),64);self.assertEqual(stats(leg['rows'])['mean'],0.)
        tools.validate_backend.assert_called_once_with(receipt,verify_checkpoint=False)
        self.assertIn(('/FAKE/privatecopy.pt','a'*64),evidence.pins)

    def test_backend_savedclock_slots_boot_and_natural_tails_fail_closed(self):
        plan,_,receipt,tools,shared=fixture()
        for kind in ('window','numeric','boot','source','clock','slot','tail','summary','official'):
            broken=copy.deepcopy(receipt)
            if kind=='window':broken['job']['cohort_s']=600
            elif kind=='numeric':broken['numeric_policy']={'weights':'float16'}
            elif kind=='boot':broken['boot_assets']['identity']='other'
            elif kind=='source':broken['source_checkpoint_path']='/other.pt'
            elif kind=='clock':broken['clocks']['training_steps']+=1
            elif kind=='slot':broken['boundary']['acknowledged']=15
            elif kind=='tail':broken['_rows'][0]['end_unix_s']=1500.
            elif kind=='summary':broken['mean']=1.
            else:broken['_official_invalid']=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):helper.validate_reference_leg(broken,helper.LABELS[0],plan,Evidence(),tools,shared)

    def fake_build(self,*,single=False,overlap=False,second_score=1.):
        plan,_,first,tools,shared=fixture();second=copy.deepcopy(first);second['label']=helper.LABELS[1]
        second['_rows']=[{**row,'journal_game_id':'second:'+str(i),'score':second_score} for i,row in enumerate(second['_rows'])]
        second.update({k:v for k,v in stats(second['_rows']).items() if k!='count'})
        if overlap:second['_rows'][0]['journal_game_id']=first['_rows'][0]['journal_game_id']
        labels=[helper.LABELS[0]] if single else list(helper.LABELS)
        documents={str((helper.CAMPAIGN/label/'receipt.json').absolute()):receipt for label,receipt in zip(helper.LABELS,(first,second))}
        audits=[Path('/FAKE/audit'+str(i)+'.json') for i in range(len(labels))]
        for path in audits:documents[str(path)]={'pass':True,'checks':dict(private_owned_processes_listener_released=True,private_GPU0_context_released=True,loaded_sources_unchanged=True),'receipt_sha256':'b'*64,'checkpoint_sha256':'a'*64}
        evidence=Evidence(documents);seen={'historical:'+str(i):'old' for i in range(2613)}
        with patch.object(helper,'context',return_value=(shared,evidence,tools,plan,{},seen)),patch.object(helper,'full_stat',return_value={}):
            result,_=helper.build(labels,audits,['c'*64]*len(labels),single=single)
        return result,evidence

    def test_two_fixed_poor_legs_pool_allrows_without_choosing_reference(self):
        result,evidence=self.fake_build(second_score=1.)
        self.assertTrue(result['reference_final']);self.assertTrue(result['usable_as_new_reference'])
        self.assertEqual([row['label'] for row in result['sources']],list(helper.LABELS))
        self.assertEqual(result['original_row_pool']['count'],128)
        self.assertEqual(result['original_row_pool']['mean'],.5)
        self.assertEqual(result['global_ids'],dict(receipts=28,games=2741,overlaps=0))
        self.assertEqual(len(result['original_rows']),128)
        self.assertFalse(result['promotion']);self.assertFalse(result['state_or_control_changes'])
        self.assertTrue(result['no_score_threshold_or_reference_selection']);self.assertGreater(evidence.rechecks,0)

    def test_single_leg_is_not_usable_reference_and_overlap_is_never_dropped(self):
        single,_=self.fake_build(single=True)
        self.assertFalse(single['reference_final']);self.assertFalse(single['usable_as_new_reference'])
        self.assertIsNone(single['original_rows'])
        with self.assertRaisesRegex(ValueError,'overlap'):self.fake_build(overlap=True)

    def test_completed_history_binds_all26_and2613_unique_ids(self):
        plan,*_=fixture();sources=[];documents={};historical_labels=['historical-'+str(i) for i in range(24)]+['sidecar-gpu0-192M-screen-01','sidecar-gpu0-192M-confirm-01']
        for i,label in enumerate(historical_labels):
            count=100 if i<23 else 200 if i==23 else 52 if i==24 else 61
            path='/FAKE/history-'+str(i)+'.json';sources.append(dict(label=label,path=path,sha256='b'*64))
            documents[path]=dict(label=label,rows=[dict(journal_game_id=str(i)+':'+str(j)) for j in range(count)])
        history=dict(schema='robotron-quality1200-completed-history-v1',complete=True,sources=sources,expected_receipts=26,expected_unique_games=2613,
            final192_analysis=dict(path='/FAKE/analysis.json',sha256='c'*64),published192_campaign=dict(path='/FAKE/published.json',sha256='d'*64),root192_promotion=dict(path='/FAKE/promoted.json',sha256='e'*64))
        documents.update({'/FAKE/history.json':history,'/FAKE/analysis.json':dict(global_ids=dict(receipts=26,games=2613,overlaps=0),sources=sources),
            '/FAKE/published.json':dict(sources=sources[-2:]),'/FAKE/promoted.json':dict(root_promoted=True,new_model_root_sha256='a'*64)})
        evidence=Evidence(documents);tools=SimpleNamespace(validate_receipt=lambda r:dict(label=r['label'],rows=r['rows']))
        _,seen=helper.history_registry(plan,evidence,tools);self.assertEqual(len(seen),2613)
        documents[sources[-1]['path']]['rows'][0]['journal_game_id']='0:0'
        with self.assertRaisesRegex(ValueError,'overlap'):helper.history_registry(plan,evidence,tools)

    def test_publication_is_new_readonly_json_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(helper,'RUN',Path(directory)):
            path=Path(directory)/'quality1200-fixture.json';evidence=Evidence()
            helper.publish(dict(fake=True),evidence,path)
            self.assertEqual(path.stat().st_mode&0o777,0o444);before=path.read_bytes()
            with self.assertRaises(ValueError):helper.publish(dict(fake=False),evidence,path)
            self.assertEqual(path.read_bytes(),before)

    def test_reused_actual_byte_snapshot_validator_rejects_changed_temp_evidence(self):
        # Import the already-pinned pure validator only; no context/dependencies/data.
        shared=helper.shared_module()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fake-receipt.json';path.write_text('{"fake":1}')
            evidence=shared.Evidence();expected=helper.sha(path.read_bytes())
            self.assertEqual(evidence.json(path,expected),dict(fake=1))
            evidence.recheck()
            path.write_text('{"fake":2}')
            # Parsed values and reported hash remain bound to the first snapshot.
            self.assertEqual(evidence.json(path,expected),dict(fake=1))
            with self.assertRaisesRegex(ValueError,'Evidence changed'):evidence.recheck()


if __name__=='__main__':unittest.main()
