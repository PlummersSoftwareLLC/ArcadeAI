"""Focused synthetic assessment fixtures; no actual reference/future/model data."""
import copy
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

helper = load('assessment1200_under_test', 'assess_quality1200.py')
reference = load('reference1200_for_fixtures', 'quality1200_reference.py')
# Reuse only the pinned, pure decisions/Evidence source; never call its context.
shared = reference.shared_module()
SHA = dict(receipt='b'*64, audit='c'*64, lineage='f'*64, reference='1'*64, guard='2'*64)

class Evidence:
    def __init__(self):
        self.docs, self.files, self.pins, self.stat_pins = {}, {}, [], []
        self.rechecks = 0
    def put(self, path, value, sha=None):
        self.docs[str(Path(path).absolute())] = (value, sha or SHA['receipt'])
    def json(self, path, expected=None):
        key = str(Path(path).absolute())
        result, actual = self.docs[key]
        if expected is not None and expected != actual:
            raise ValueError('Pinned fake JSON SHA differs')
        self.files[key] = actual
        self.pins.append((key, expected))
        return result
    def file(self, path, expected=None):
        self.pins.append((str(path), expected))
        return Path(path)
    def bind_stat(self, path, expected):
        self.stat_pins.append((path, expected))
    def recheck(self): self.rechecks += 1
    def snapshot(self): return {'synthetic': True}


def rows(label, values):
    return [dict(journal_game_id=label+':'+str(i), client_slot=4096+i%16,
                 score=value, boundary_reason='wire_lives_exhausted', end_unix_s=1301+i/100)
            for i, value in enumerate(values)]


def audit(policy_sha, receipt_sha=SHA['receipt']):
    return {'pass':True, 'receipt_sha256':receipt_sha, 'checkpoint_sha256':policy_sha,
        'checks':dict(private_owned_processes_listener_released=True,
            private_GPU0_context_released=True, loaded_sources_unchanged=True)}


class Fixture:
    def __init__(self):
        self.evidence = Evidence()
        saved = dict(training_steps=100, optimized_samples=409600, learner_frame_count=1000,
            frame_count=2000, measurement_frame_count=10, total_training_steps=100,
            last_target_update_samples=400000, baseline_batch_size=512, engine_version=28,
            state_size=11128, single_frame_state_size=2782, frame_stack=4, epsilon=.1,
            expert_ratio=.1, lr_gear=0, lr_anchor_step=0.)
        optimizer = dict(state_count=81, all_tensors_CPU=True, tensor_count=243,
            step_values=[99.], groups=[dict(params=list(range(99)), lr=2.5e-5, betas=[.9,.999])])
        job = dict(device='cuda', gpu_uuid='FAKE_GPU0', actors=16, actor_slots=helper.SLOTS,
            port=9999, cohort_s=1200., timeout_s=2400., wait_us=1000, inference_backend='inductor')
        self.base = dict(reference=dict(checkpoint=dict(path='/FAKE/protected192.pt', sha256='a'*64),
            saved_metadata=saved, optimizer=optimizer), backend=dict(job=job,
                numeric_policy=dict(weights='float32'), runtime=dict(torch='fake'),
                source_hashes=dict(private12='fake'), boot_identity='seed', boot_files=dict(seed='fake'),
                socket_wait_sha256='0'*64))
        self.plan = dict(reference_publication=dict(path='/FAKE/final-reference.json'),
            roles={}, collector_resume_chronology=[],lineage_verifier=dict(sha256='5'*64),lineage_precommit=dict(sha256='6'*64))
        for role, target in [('224M',3000), ('256M',5000)]:
            self.plan['roles'][role] = dict(checkpoint='/FAKE/'+role+'.pt', target=target,
                lineage_schema='robotron-'+role+'-checkpoint-lineage-v1',
                gate_path='/FAKE/'+role+'-gate.json', output='/FAKE/'+role+'-analysis.json')
        for i in (1,2):
            anchor = dict(path='/FAKE/anchor'+str(i)+'.json', sha256='4'*64,
                saved_metadata=dict(training_steps=100+i))
            self.plan['collector_resume_chronology'].append(anchor)
            self.evidence.put(anchor['path'], dict(saved_metadata=anchor['saved_metadata']), anchor['sha256'])
        def official(document, verify_checkpoint):
            if verify_checkpoint is not False: raise AssertionError('Unexpected model body hash')
            if document.get('_official_invalid'): raise ValueError('Official runtime/full-tail failure')
            if len(document['_rows']) < 50: raise ValueError('Official minimum50')
            clocks = dict(document['clocks'])
            clocks['learner_frames'] = clocks['learner_frame_count']
            return dict(rows=document['_rows'], start_ts=100., close_ts=1300., clocks=clocks,
                expected_actor_slots=helper.SLOTS, protocol=document.get('_protocol',dict(wire_version=6,frame_stack=4)))
        self.tools = SimpleNamespace(JOB_FIELDS=list(job), validate_backend=Mock(side_effect=official),
            summarize=lambda r, labels=None:shared.summarize(r),
            analyze_rows=lambda r,c,*args:dict(reference_count=len(r), candidate_count=len(c)))
        self.seen = {'history:'+str(i):'old' for i in range(2613)}
        reference_rows, sources, audits = [], [], []
        for label in reference.LABELS:
            receipt = self.receipt(label, self.ref_identity(), [100.]*64)
            path, audit_path = '/FAKE/'+label+'.json', '/FAKE/'+label+'-audit.json'
            self.evidence.put(path, receipt)
            self.evidence.put(audit_path, audit('a'*64), SHA['audit'])
            sources.append(dict(label=label,path=path,sha256=SHA['receipt']))
            audits.append(dict(label=label,path=audit_path,sha256=SHA['audit']))
            reference_rows.extend(receipt['_rows'])
        self.reference_report = dict(schema='robotron-quality1200-192M-reference-v1',
            reference_final=True, usable_as_new_reference=True, plan_sha256=reference.PLAN_SHA,
            sources=sources, protected_policy=copy.deepcopy(self.base['reference']),
            backend=copy.deepcopy(self.base['backend']), no_score_threshold_or_reference_selection=True,
            all_original_fulltails_retained=True, no_fabricated_measurement_receipt=True, promotion=False, protection=False, state_or_control_changes=False,
            final_isolation_audits=audits, original_rows=reference_rows,
            original_row_pool=shared.summarize(reference_rows),
            global_ids=dict(receipts=28,games=2613+len(reference_rows),overlaps=0))
        self.evidence.put(self.plan['reference_publication']['path'], self.reference_report, SHA['reference'])
        self.identities = {}
        for role, steps, policy_sha in [('224M',200,'d'*64),('256M',400,'e'*64)]:
            meta = {**saved, 'training_steps':steps, 'total_training_steps':steps,
                'optimized_samples':steps*4096,'learner_frame_count':self.plan['roles'][role]['target'],
                'frame_count':self.plan['roles'][role]['target']*2,
                'last_target_update_samples':steps*4096-10}
            opt = {**copy.deepcopy(optimizer), 'step_values':[float(steps-1)]}
            identity = dict(path=self.plan['roles'][role]['checkpoint'], sha256=policy_sha,
                metadata=meta, optimizer=opt)
            self.identities[role] = identity
            gate_record = dict(tag='fresh3-'+role, target=self.plan['roles'][role]['target'],
                checkpoint=identity['path'], experiment=helper.EXPERIMENT)
            self.evidence.put(self.plan['roles'][role]['gate_path'],gate_record,'3'*64)
            lineage = dict(schema=self.plan['roles'][role]['lineage_schema'],proposal_only=False,PASS=True,
                checks=dict(synthetic=True),root_verification=dict(status='PASS',CUDA_initialized=False,
                    verifier_sha256='5'*64,precommit_sha256='6'*64,model_body_reads=1,model_CPU_loads=1,CUDA_VISIBLE_DEVICES=''),
                candidate=dict(path=identity['path'],sha256=policy_sha,stat=dict(fake=True),
                    all_network_optimizer_tensors_finite=True,saved_metadata=meta,optimizer=opt),
                trigger_gate=dict(path=self.plan['roles'][role]['gate_path'],sha256='3'*64,record=gate_record),
                branch_provenance=dict(experiment=helper.EXPERIMENT,compile_mode='default',exposure_counters_enabled=True,
                    held_recipe=dict(batch_size=4096,n_step=3,max_samples_per_frame=8,lr_scale=.5,epsilon=.1,expert_ratio=.1),
                    collector_resume_chronology=copy.deepcopy(self.plan['collector_resume_chronology'])),
                actual_recorded_batch_exposure=dict(since192M=dict(recorded_batch_size=4096,
                    logical_updates_delta=steps-100,optimized_samples_delta=(steps-100)*4096,
                    learner_frames_delta=meta['learner_frame_count']-1000)),counter_exposure_evidence=dict(available=False))
            self.evidence.put('/FAKE/'+role+'-lineage.json',lineage,SHA['lineage'])
            for label in helper.LABELS[role]:
                self.evidence.put(helper.CAMPAIGN/label/'receipt.json',self.receipt(label,identity,[110.]*64))
                self.evidence.put('/FAKE/'+label+'-audit.json',audit(policy_sha),SHA['audit'])
    def ref_identity(self):
        return dict(path=self.base['reference']['checkpoint']['path'],
            sha256=self.base['reference']['checkpoint']['sha256'],metadata=self.base['reference']['saved_metadata'])
    def receipt(self,label,identity,values):
        data = dict(label=label,phase='finished',reason=None,receipt_validator='passed',
            checkpoint_sha256=identity['sha256'],source_checkpoint_path=identity['path'],
            checkpoint_path='/FAKE/'+label+'-private-copy.pt',job={**copy.deepcopy(self.base['backend']['job']),'checkpoint':identity['path']},
            checkpoint_metadata={**identity['metadata'],'defaulted_metadata_fields':[]},clocks=dict(identity['metadata']),
            numeric_policy=copy.deepcopy(self.base['backend']['numeric_policy']),runtime=copy.deepcopy(self.base['backend']['runtime']),
            source_hashes=copy.deepcopy(self.base['backend']['source_hashes']),boot_assets=dict(identity='seed',files=dict(seed='fake')),
            socket_wait=dict(sha256='0'*64,actors={str(slot):dict(activation_count=1) for slot in helper.SLOTS}),
            boundary=dict(clients=16,expected=16,acknowledged=16,generation=1,requested_generation=1,actor_slots=helper.SLOTS),
            generation=1,ended_unix_s=1400.,_rows=rows(label,values))
        data.update(shared.summarize(data['_rows']))
        return data
    def context(self):
        return reference,shared,self.evidence,self.tools,self.base,self.plan,self.seen
    def build(self, role='224M', labels=None, guard_sha=None):
        labels = list(helper.LABELS[role]) if labels is None else labels
        with patch.object(helper,'context',side_effect=self.context):
            return helper.build(role,labels,SHA['reference'],'/FAKE/'+role+'-lineage.json',SHA['lineage'],
                ['/FAKE/'+label+'-audit.json' for label in labels],[SHA['audit']]*len(labels),guard_sha)
    def put_completed_guard(self):
        report,_ = self.build('224M')
        # Each analysis is a new context, not a shared mutable ID registry.
        self.seen = {'history:'+str(i):'old' for i in range(2613)}
        self.evidence.put(self.plan['roles']['224M']['output'],report,SHA['guard'])
        return report


class AssessmentTests(unittest.TestCase):
    def test_import_default_help_are_inert(self):
        with patch.object(Path,'read_bytes',side_effect=AssertionError('Evidence read')),patch.object(Path,'open',side_effect=AssertionError('Evidence open')):
            module=load('inert_assessment1200','assess_quality1200.py')
            with patch('sys.stdout',new=io.StringIO()):self.assertEqual(module.main([]),0)
            with patch('sys.stdout',new=io.StringIO()),self.assertRaises(SystemExit) as exited:module.main(['--help'])
            self.assertEqual(exited.exception.code,0)

    def test_bad_cardinality_and_sha_fail_before_context(self):
        cases=[('224M',[]),('224M',list(helper.LABELS['224M'])*2),('256M',list(reversed(helper.LABELS['256M']))),
               ('256M',[helper.LABELS['256M'][1]]),('256M',[*helper.LABELS['256M'],'third'])]
        with patch.object(helper,'context',side_effect=AssertionError('Future evidence opened')):
            for role,labels in cases:
                with self.subTest(role=role,labels=labels),self.assertRaises(ValueError):
                    helper.build(role,labels,SHA['reference'],'/FAKE/lineage',SHA['lineage'],['audit']*len(labels),[SHA['audit']]*len(labels),SHA['guard'])
            with self.assertRaises(ValueError):helper.build('224M',list(helper.LABELS['224M']),None,'/FAKE/lineage',SHA['lineage'],['audit'],[SHA['audit']])
            with self.assertRaises(ValueError):helper.build('256M',list(helper.LABELS['256M']),SHA['reference'],'/FAKE/lineage',SHA['lineage'],['a','b'],[SHA['audit']]*2,None)

    def test_actual_prospective_plan_matches_role_formula_and_targets(self):
        plan=json.loads((HERE/'quality1200-assessment-plan.json').read_bytes())
        self.assertEqual(plan['roles']['224M']['target'],228629023)
        self.assertEqual(plan['roles']['256M']['target'],260629023)
        self.assertEqual(plan['roles']['224M']['required_valid_legs'],1)
        self.assertFalse(plan['roles']['224M']['extra_N_trigger_leg'])
        self.assertEqual(plan['roles']['256M']['required_valid_legs'],2)
        self.assertEqual(plan['roles']['256M']['each_mean_fraction'],1.05)
        self.assertEqual(plan['roles']['256M']['each_median_fraction'],1.)
        self.assertEqual(plan['reference_publication']['exact_source_labels'],list(reference.LABELS))
        for role in helper.LABELS:self.assertEqual(plan['roles'][role]['labels'],list(helper.LABELS[role]))

    def test_valid_build_keeps_all_new_original_rows_and_new_copy_only(self):
        f=Fixture();report,evidence=f.build()
        self.assertEqual(report['reference_original_denominator'],128)
        self.assertEqual(report['original_full_denominators'],{helper.LABELS['224M'][0]:64})
        self.assertEqual(report['global_ids'],dict(receipts=29,games=2805,overlaps=0))
        self.assertFalse(report['promotion']);self.assertFalse(report['management']['additional_valid_guard_authorized'])
        copies=[p for p,sha in evidence.pins if p.endswith('-private-copy.pt')]
        self.assertEqual(copies,['/FAKE/'+helper.LABELS['224M'][0]+'-private-copy.pt'])
        self.assertEqual(evidence.rechecks,1)

    def test_partial_wrong_reference_and_omitted_reweighted_originals_reject(self):
        for kind in ('partial','single','policy','backend','omitted','reweighted','count'):
            f=Fixture();r=f.reference_report
            if kind=='partial':r['reference_final']=False
            elif kind=='single':r['sources'].pop()
            elif kind=='policy':r['protected_policy']['checkpoint']['sha256']='9'*64
            elif kind=='backend':r['backend']['numeric_policy']['weights']='float16'
            elif kind=='omitted':r['original_rows']=r['original_rows'][:-1]
            elif kind=='reweighted':r['original_rows']=[r['original_rows'][0]]*len(r['original_rows'])
            else:r['global_ids']['games']-=1
            with self.subTest(kind=kind),self.assertRaises(ValueError):f.build()

    def test_sha_pinned_reference_lineage_audit_and_receipt_identity(self):
        for kind in ('reference','lineage','audit','receipt'):
            f=Fixture()
            if kind=='reference':f.evidence.put(f.plan['reference_publication']['path'],f.reference_report,'9'*64)
            elif kind=='lineage':
                key='/FAKE/224M-lineage.json';f.evidence.docs[key]=(f.evidence.docs[key][0],'9'*64)
            elif kind=='audit':
                key='/FAKE/'+helper.LABELS['224M'][0]+'-audit.json';f.evidence.docs[key]=(f.evidence.docs[key][0],'9'*64)
            else:
                key='/FAKE/'+helper.LABELS['224M'][0]+'-audit.json';f.evidence.docs[key][0]['receipt_sha256']='9'*64
            with self.subTest(kind=kind),self.assertRaises(ValueError):f.build()

    def test_protocol_numeric_boot_activation_clock_slots_tails_official_reject(self):
        for kind in ('window','timeout','numeric','source','boot','activation','metadata','clock','slot','tail','boundary','arithmetic','official','wire'):
            f=Fixture();label=helper.LABELS['224M'][0];r=f.evidence.docs[str(helper.CAMPAIGN/label/'receipt.json')][0]
            if kind=='window':r['job']['cohort_s']=600
            elif kind=='timeout':r['job']['timeout_s']=1200
            elif kind=='numeric':r['numeric_policy']['weights']='float16'
            elif kind=='source':r['source_hashes']['private12']='changed'
            elif kind=='boot':r['boot_assets']['identity']='other'
            elif kind=='activation':next(iter(r['socket_wait']['actors'].values()))['activation_count']=2
            elif kind=='metadata':r['checkpoint_metadata']['defaulted_metadata_fields']=['frame_count']
            elif kind=='clock':r['clocks']['training_steps']+=1
            elif kind=='slot':r['boundary']['actor_slots']=[0]*16
            elif kind=='tail':r['_rows'][0]['end_unix_s']=r['ended_unix_s']+1
            elif kind=='boundary':r['_rows'][0]['boundary_reason']='score_reset'
            elif kind=='arithmetic':r['mean']+=1
            elif kind=='wire':r['_protocol']=dict(wire_version=5,frame_stack=4)
            else:r['_official_invalid']=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):f.build()

    def test_reference_legs_and_old_guard_must_match_official_wire_protocol(self):
        f=Fixture();second=f.reference_report['sources'][1]
        f.evidence.docs[second['path']][0]['_protocol']=dict(wire_version=6,frame_stack=1)
        with self.assertRaisesRegex(ValueError,'protocol'):f.build()
        g=Fixture();g.put_completed_guard();label=helper.LABELS['224M'][0]
        g.evidence.docs[str(helper.CAMPAIGN/label/'receipt.json')][0]['_protocol']=dict(wire_version=5,frame_stack=4)
        with self.assertRaisesRegex(ValueError,'protocol'):g.build('256M',guard_sha=SHA['guard'])

    def test_global_ids_never_deduplicate_or_drop_overlap(self):
        for origin in ('history','reference','candidate'):
            f=Fixture();label=helper.LABELS['224M'][0];r=f.evidence.docs[str(helper.CAMPAIGN/label/'receipt.json')][0]
            r['_rows'][0]['journal_game_id']=('history:0' if origin=='history' else
                f.reference_report['original_rows'][0]['journal_game_id'] if origin=='reference' else r['_rows'][1]['journal_game_id'])
            with self.subTest(origin=origin),self.assertRaisesRegex(ValueError,'overlap'):f.build()

    def test224_one_low_N_never_requests_extra_guard(self):
        for score,mean_alarm,median_alarm,severe in [(90,False,False,False),(80,True,True,False),(79.9,True,True,True),(110,False,False,False)]:
            result=helper.decisions('224M',rows('ref',[100]*64),{'guard':rows('guard',[score]*50)},shared)
            self.assertEqual((result['each_leg'][0]['mean_alarm'],result['each_leg'][0]['median_alarm'],result['each_leg'][0]['severe_alert']),(mean_alarm,median_alarm,severe))
            self.assertTrue(result['each_leg'][0]['low_N']);self.assertTrue(result['maximum_valid_legs_reached'])
            for key in ('confirmation_still_needed','additional_valid_guard_authorized','promotion','reference_rebased','automatic_action'):
                self.assertFalse(result[key])
        self.assertFalse(helper.decisions('224M',rows('ref',[100]*64),{'guard':rows('guard',[100]*64)},shared)['each_leg'][0]['low_N'])

    def test256_exact_boundaries_independent_legs_no_pooled_rescue(self):
        reference_rows=rows('ref',[100]*64)
        equal=helper.decisions('256M',reference_rows,{'one':rows('one',[105]*64),'two':rows('two',[105]*64)},shared)
        self.assertTrue(equal['promotion_eligible'])
        # The pooled mean clears105, but the weaker original leg must still fail.
        bad=helper.decisions('256M',reference_rows,{'one':rows('one',[104]*64),'two':rows('two',[200]*64)},shared)
        self.assertFalse(bad['promotion_eligible']);self.assertFalse(bad['each_leg'][0]['mean_gate'])
        # A large high tail cannot rescue a leg whose median is below reference.
        bad_median=helper.decisions('256M',reference_rows,{'one':rows('one',[99]*48+[500]*16),'two':rows('two',[110]*64)},shared)
        self.assertTrue(bad_median['each_leg'][0]['mean_gate']);self.assertFalse(bad_median['each_leg'][0]['median_gate']);self.assertFalse(bad_median['promotion_eligible'])
        first=helper.decisions('256M',reference_rows,{'one':rows('one',[500]*64)},shared)
        self.assertTrue(first['confirmation_still_needed']);self.assertFalse(first['promotion_eligible'])

    def test256_same_criterion_crossed_alarms_do_not_confirm_regression(self):
        # Mean-only first: 3*100+0 ->75, median100. Median-only second: 3*80+200 ->110, median80.
        result=helper.decisions('256M',rows('ref',[100]*64),{'one':rows('one',[100]*48+[0]*16),'two':rows('two',[80]*48+[200]*16)},shared)
        self.assertTrue(result['each_leg'][0]['mean_alarm']);self.assertFalse(result['each_leg'][0]['median_alarm'])
        self.assertFalse(result['each_leg'][1]['mean_alarm']);self.assertTrue(result['each_leg'][1]['median_alarm'])
        self.assertFalse(result['repeated_same_criterion_alarm'])
        both=helper.decisions('256M',rows('ref',[100]*64),{'one':rows('one',[80]*64),'two':rows('two',[89]*64)},shared)
        self.assertTrue(both['repeated_mean_alarm']);self.assertTrue(both['repeated_median_alarm'])
        equality=helper.decisions('256M',rows('ref',[100]*64),{'one':rows('one',[90]*64),'two':rows('two',[90]*64)},shared)
        self.assertFalse(equality['repeated_same_criterion_alarm']);self.assertFalse(equality['third_valid_cohort_authorized'])

    def test256_requires_completed_unpromoted224_history_without_pooling(self):
        f=Fixture();guard=f.put_completed_guard();report,_=f.build('256M',guard_sha=SHA['guard'])
        self.assertEqual(report['reference_original_denominator'],128)
        self.assertEqual(report['global_ids'],dict(receipts=31,games=2933,overlaps=0))
        self.assertFalse(report['completed224_guard_history']['pooled_into_reference']);self.assertTrue(report['management']['promotion_eligible'])
        for kind in ('promoted','rebase','wrongref','wrongrole','overlap'):
            g=Fixture();old=g.put_completed_guard()
            if kind=='promoted':old['management']['promotion']=True
            elif kind=='rebase':old['management']['reference_rebased']=True
            elif kind=='wrongref':old['reference_publication']['sha256']='9'*64
            elif kind=='wrongrole':old['role']='256M'
            else:
                label=helper.LABELS['256M'][0]
                r=g.evidence.docs[str(helper.CAMPAIGN/label/'receipt.json')][0]
                r['_rows'][0]['journal_game_id']=helper.LABELS['224M'][0]+':0'
            with self.subTest(kind=kind),self.assertRaises(ValueError):g.build('256M',guard_sha=SHA['guard'])

    def test_lineage_gate_branch_chronology_4096_and_counter_scope_reject(self):
        for kind in ('proposal','CPU','verifier','precommit','loadcount','CUDAenv','clockbool','geometry','Adam','gate','compiler','recipe','chronology','exposure','counter'):
            f=Fixture();r=f.evidence.docs['/FAKE/224M-lineage.json'][0]
            if kind=='proposal':r['proposal_only']=True
            elif kind=='CPU':r['root_verification']['CUDA_initialized']=True
            elif kind=='verifier':r['root_verification']['verifier_sha256']='9'*64
            elif kind=='precommit':r['root_verification']['precommit_sha256']='9'*64
            elif kind=='loadcount':r['root_verification']['model_CPU_loads']=2
            elif kind=='CUDAenv':r['root_verification']['CUDA_VISIBLE_DEVICES']='0'
            elif kind=='clockbool':r['candidate']['saved_metadata']['training_steps']=True
            elif kind=='geometry':r['candidate']['optimizer']['groups'][0]['betas']=[.8,.99]
            elif kind=='Adam':r['candidate']['optimizer']['step_values']=[True]
            elif kind=='gate':r['trigger_gate']['record']['target']-=1
            elif kind=='compiler':r['branch_provenance']['compile_mode']='max-autotune-no-cudagraphs'
            elif kind=='recipe':r['branch_provenance']['held_recipe']['batch_size']=2048
            elif kind=='chronology':r['branch_provenance']['collector_resume_chronology'].reverse()
            elif kind=='exposure':r['actual_recorded_batch_exposure']['since192M']['optimized_samples_delta']+=1
            else:r['counter_exposure_evidence']['available']=True
            with self.subTest(kind=kind),self.assertRaises(ValueError):f.build()

    def test_actual_reused_Evidence_keeps_one_snapshot_and_rechecks_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fake-reference.json';path.write_text('{"fake":1}')
            evidence=shared.Evidence();sha=reference.sha(path.read_bytes())
            self.assertEqual(evidence.json(path,sha),dict(fake=1));evidence.recheck()
            path.write_text('{"fake":2}')
            self.assertEqual(evidence.json(path,sha),dict(fake=1))
            with self.assertRaisesRegex(ValueError,'Evidence changed'):evidence.recheck()

if __name__ == '__main__':unittest.main()
