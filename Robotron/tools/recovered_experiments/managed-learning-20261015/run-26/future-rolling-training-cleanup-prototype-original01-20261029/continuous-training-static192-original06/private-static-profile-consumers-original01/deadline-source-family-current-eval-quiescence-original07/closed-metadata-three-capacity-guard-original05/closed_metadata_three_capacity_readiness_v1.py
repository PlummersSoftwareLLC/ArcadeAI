"""Capacity-only derivation of three new jobs from closed M9 semantic subjects.

No work on import; original G12/M9 facts retain their original identities. Each
new exact subject repeats every accepted/rejected/verifier/registry integrity
check after proving the complete explicit metadata-only capacity derivation.
"""
import copy
import importlib.util
import json
from pathlib import Path

PARENT_SHIM = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/closed-metadata-current-profile-guard-original04/closed_metadata_readiness_reuse_current_profile_v8.py', 'sha256': '235aafdb90a1ea5d776b92191f2b7f077bf9bc585ddf76dc03cb502f7b80c3e5', 'bytes': 27770, 'identity': {'device': 2304, 'inode': 85459692, 'bytes': 27770, 'mtime_ns': 1793317172827728702, 'ctime_ns': 1793317172827728702, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
PARENT_CPU_JOB = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/actual-closed-metadata-current-profile-guard-original04/job.json', 'sha256': '84ef03c6c13c0b804a2f8271db0ac41855c4b5e62bb0a14861b8952d216a3313', 'bytes': 437179, 'identity': {'device': 2304, 'inode': 85459711, 'bytes': 437179, 'mtime_ns': 1793317228426664765, 'ctime_ns': 1793317228426664765, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
AMENDMENT_PRODUCER = {'path': '/home/dave/source/repos/ArcadeAI/Robotron/logs/managed-learning-20261015/run-26/future-rolling-training-cleanup-prototype-original01-20261029/continuous-training-static192-original06/private-static-profile-consumers-original01/deadline-source-family-current-eval-quiescence-original07/remaining-three-main-journal128-amendment-original01/prepare_remaining_three_main_journal128_amendment_v1.py', 'sha256': '6ecf2d7ac03b58a514bcf3ea15c0297b2d4161e3595c3a17f7c19078337bd96a', 'bytes': 18465, 'identity': {'device': 2304, 'inode': 87556186, 'bytes': 18465, 'mtime_ns': 1793326293883632414, 'ctime_ns': 1793326483693411855, 'mode': '0o444', 'uid': 1001, 'nlink': 1}}
FUTURE = ('C1','R2','C2')


def require(value, reason):
    if not value:
        raise ValueError(reason)


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class ClosedMetadataReadiness:
    def __init__(self,cpu_job,h,phase):
        self.h,self.phase,self.cpu_job=h,phase,cpu_job
        require(AMENDMENT_PRODUCER is not None,'Final immutable amendment producer is required')
        require(cpu_job['parent_guard_CPU_job']==PARENT_CPU_JOB
                and cpu_job['parent_readiness_reuse_shim']==PARENT_SHIM
                and cpu_job['amendment_producer']==AMENDMENT_PRODUCER,
                'Exact historical proof and new metadata derivation sources required')
        parent_job=self.read(PARENT_CPU_JOB)
        require(cpu_job['closed_metadata_readiness_authority']==parent_job['closed_metadata_readiness_authority']
                and cpu_job['closed_metadata_readiness_source_contract']==parent_job['closed_metadata_readiness_source_contract'],
                'Historical closed M9 semantic authority changed')
        parent_module=load('_original_G12_closed_M9_predicates',h.checked(PARENT_SHIM))
        self.base=parent_module.ClosedMetadataReadiness(parent_job,h,phase)
        self.counts=self.base.counts
        self.producer=load('_exact_three_capacity_metadata_producer',h.checked(AMENDMENT_PRODUCER))
        self.prepared=self.read(cpu_job['prepared_amendment'])
        self.mixed=self.read(cpu_job['prepared_manifest'])
        require(self.prepared['schema']=='robotron-prepared-unused-three-leg-main-journal128-amendment-v1'
                and self.prepared['source']==AMENDMENT_PRODUCER
                and self.prepared['mixed_manifest']==cpu_job['prepared_manifest']
                and [v['leg']for v in self.prepared['subjects']]==list(FUTURE),
                'Exact new ordered unused-three metadata preparation required')
        self.selection_pin=self.prepared['selected_amendment']
        self.selection=self.read(self.selection_pin)
        require(self.selection['schema']=='robotron-root-original-study-unused-three-leg-capacity-amendment-v1'
                and self.selection['source']==AMENDMENT_PRODUCER
                and self.selection['original_manifest']==self.base.a['native_prepared']
                and self.selection['future_legs']==list(FUTURE)
                and self.selection['original_main_case_inventory_profiles_and_R1_unchanged']is True
                and self.selection['scientific_fields_unchanged']is True
                and self.selection['main_or_journal_changed']is False,
                'Only the selected capacity-only three unused subjects may derive authority')
        self.original=self.read(self.base.a['native_prepared'])
        require(self.mixed['original_manifest']==self.base.a['native_prepared']
                and self.mixed['capacity_amendment']==self.selection_pin
                and self.mixed['capacity_amendment_source']==AMENDMENT_PRODUCER
                and self.mixed['cases'][0]==self.original['cases'][0]
                and self.mixed['study_precommit']==self.original['study_precommit']
                and self.mixed['original_R1_already_qualified']is True
                and self.mixed['any_capacity_amended_payload_launched']is False
                and [r['leg']for r in self.mixed['cases']]==['R1',*FUTURE],
                'Original R1/common study must stay exact and future capacity jobs unused')
        fixed=self.producer.FIXED
        require(fixed['original_manifest']==self.base.a['native_prepared']
                and fixed['R1_qualification']==self.selection['original_R1_qualification']
                and fixed['original_review_precommit']==self.selection['original_review_precommit']
                and fixed['original_guards']==self.selection['original_CPU_guards']
                and fixed['capacity_packet']==self.selection['capacity_packet']
                and fixed['contract']==self.selection['selected_contract']
                and fixed['runtime']==self.selection['selected_runtime']
                and fixed['reviewer']==self.selection['selected_private_reviewer']
                and fixed['controller']==self.selection['selected_native_controller'],
                'New derivation must retain its exact original and selected source graph')
        self.capacity=self.read(fixed['capacity_packet'])
        self.mapping=self.read(self.capacity['observer_source_map'])
        self.old_reviews=self.read(fixed['original_review_precommit'])
        self.old_guards=self.read(fixed['original_guards'])
        q=self.read(fixed['R1_qualification'])
        require(q['status']=='INDEPENDENT_DEADLINE32_QUALIFIED'and q['leg']=='R1'
                and q['precommit']==fixed['original_review_precommit']
                and q['actual_review_tool_terminal_exit']==0,
                'Existing R1 remains an original qualification, never a new guard subject')
        self.subjects=[]
        for record,row,parent_row,old_review,old_guard in zip(self.prepared['subjects'],self.mixed['cases'][1:],
                self.original['cases'][1:],self.old_reviews['cases'][1:],self.old_guards['guards'][1:]):
            require(record['leg']==row['leg']==parent_row['leg']==old_review['leg']
                    and record['native_job']==row['native_job']
                    and record['original_native_job']==parent_row['native_job']
                    and record['original_CPU_guard']==old_guard,
                    'Exact ordered new/parent job and historical guard metadata join differs')
            self.validate_subject(row,parent_row,old_review,old_guard,record)
            self.subjects.append((row['leg'],self.read(row['native_job'])))
        require(len(self.subjects)==3,'Exactly three new unused subjects required')

    def read(self,value):
        return json.loads(self.h.checked(value).read_bytes())

    def validate_subject(self,row,parent_row,old_review,old_guard,record):
        h,fixed=self.h,self.producer.FIXED
        old=self.read(parent_row['native_job']);new=self.read(row['native_job'])
        parent=Path(parent_row['native_job']['path']).parent
        branch=parent/'main-journal128-amendment-original01'
        require(Path(row['native_job']['path'])==parent/'job-main-journal128-original01.json'
                and row['runtime']==fixed['runtime']and row['native_controller']==fixed['controller']
                and row['unqualified_controller_config']==record['unqualified_controller_config']
                and Path(row['unqualified_controller_config']['path'])==parent/'controller-config-main-journal128-NOT-QUALIFIED-original01.json'
                and Path(row['source_family']['path'])==branch/'source-family-main-journal128.json'
                and row['prospective_qualified_config_path']==record['qualified_config_path']
                    ==str(parent/'controller-config-main-journal128-CPU-QUALIFIED-original01.json')
                and record['future_CPU_guard_path']==str(branch/'source-family-guards-CPU-original01/independent-deadline32-family-guards-and-CPU-closeout.json'),
                'Only the exact new filename/runtime/controller/guard path may be selected')
        family=copy.deepcopy(self.read(old['source_family_manifest']))
        family.update(runtime=fixed['runtime'],reviewer=fixed['reviewer'],main_observer=self.mapping['observer_sources'],
            round_observer_reviewer=self.mapping['observer_reviewer'],
            main_domain_readiness_reviewer=self.capacity['parents']['observer_reviewer'],
            main_journal_capacity_overlay=fixed['capacity_packet'])
        require(self.read(row['source_family'])==family and new['source_family_manifest']==row['source_family'],
                'Only the explicit capacity source-family edits are authorized')
        expected=copy.deepcopy(old)
        expected.update(runtime=fixed['runtime'],output=str(branch/'deadline-output-original01'),
            observer_sources=self.mapping['observer_sources'],source_family_manifest=row['source_family'],
            prelaunch_family_guard_closeout=record['future_CPU_guard_path'],
            main_journal_capacity_amendment=self.selection_pin)
        additions=[self.selection_pin,AMENDMENT_PRODUCER,*fixed.values(),self.capacity['observer_source_map'],
            self.capacity['parent_source_map'],self.capacity['derivation'],*self.capacity['sources'].values(),
            *self.capacity['parents'].values(),row['source_family'],parent_row['native_job'],
            old['source_family_manifest'],old_review['native_config'],old_guard]
        expected['inputs']=list({v['path']:v for v in [*old['inputs'],*additions]}.values())
        require(new==expected,'A new job differs beyond the exact selected capacity/output/input derivation')
        require(new['main_binding']==old['main_binding']and new['main_health_protocol']==old['main_health_protocol'],
                'Original case390 and physical protocol must remain exact')
        original_subject=next(subject for leg,subject in self.base.subjects if leg==row['leg'])
        require(old==original_subject,'New subject parent was not one of the actual closed M9 semantic jobs')
        old_cfg=self.read(old_review['native_config']);cfg=self.read(row['unqualified_controller_config'])
        control=load('_three_capacity_controller',h.checked(fixed['controller']))
        expected_cfg=copy.deepcopy(old_cfg)
        expected_cfg['argv']=[*old_cfg['argv'][:4],fixed['runtime']['path'],'--execute','--job',row['native_job']['path'],
            '--job-sha256',row['native_job']['sha256'],'--source-sha256',fixed['runtime']['sha256']]
        pins={v['path']:v for v in old_cfg['pins']}
        for value in [row['native_job'],*additions]:pins[value['path']]=control.pin(value['path'])
        expected_cfg['pins']=list(pins.values())
        require(cfg==expected_cfg and control.checked_config(row['unqualified_controller_config']['path'])==cfg,
                'Actual new serialized controller differs beyond exact metadata source/job pins')

    def validate_launch(self,job,context,h):
        require(h is self.h and any(job==subject for _,subject in self.subjects),
                'Capacity proof reuse only for one exact new C1/R2/C2 subject')
        leg=job['leg'];row=next(r for r in self.mixed['cases']if r['leg']==leg)
        family=self.read(job['source_family_manifest'])
        require(context['family']==family and context['main_binding']==self.read(job['main_binding'])
                and family['native_launch_qualified']is True,
                'Exact new source family/main case and scientific launch flag required')
        contract=load('_three_capacity_selected_contract',h.checked(self.selection['selected_contract']))
        parent_sources,parent_reviewer=contract.capacity_overlay(family,h)
        oldjob=next(subject for oldleg,subject in self.base.subjects if oldleg==leg)
        oldfamily=self.read(oldjob['source_family_manifest'])
        require(oldfamily['main_observer']==parent_sources and oldfamily['round_observer_reviewer']==parent_reviewer,
                'Historical readiness may only be replayed under its original source identities')
        original_context=dict(context,family=oldfamily)
        verified=self.base.validate_launch(oldjob,original_context,h)
        return dict(verified,main_journal_capacity_overlay_verified=True,selected_main_journal_capacity_bytes=128<<20,
            original_engineering_source_map_preserved=True,new_capacity_sources_claimed_to_have_run_original_engineering=False,
            original_exact_job_parent_semantics_used=True,new_capacity_subject=next(r['native_job']for r in self.mixed['cases']if r['leg']==leg))

    def bind(self,contract):
        require(self.h.pin(Path(contract.__file__).resolve())==self.selection['selected_contract'],
                'Only exact selected capacity contract may receive bounded historical semantic reuse')
        contract.validate_launch=self.validate_launch
        return contract
