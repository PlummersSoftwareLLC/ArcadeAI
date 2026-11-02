"""UNBOUND template: one fresh quota64 R1/C1/R2/C2 sequence.

Default is inert. Every leg is prepared and launched exactly once by this
sequence. Existing R1 jobs and prior sequencers are never adopted or restarted.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
B = G / 'tools/startup_policy_journal_proposal'
PAIR_SHA='95092f4aaaf7384a6bebfeb72a5b8743bb01159dd9fbe5a374f49b0716493f25'
BASE_SHA = 'b462dbb6562e08ef6efca66bc10f6b0c94273daceb12ac9f86f4a68eb972d6e4'


def checked_module(name, path, sha):
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise ValueError('Source changed: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sequence_type(base):
    class FreshSequence(base.CampaignSequence):
        def review(self, directory, role):
            self.check_new_actions()
            cfg_pin = self.h.pin(directory / 'independent-review-controller-config.json')
            cfg = self.read(cfg_pin)
            rjp = self.h.pin(directory / 'independent-review-job.json')
            expected = ['/usr/bin/python3.12', '-I', '-B', self.ready['leg_reviewer']['path'],
                '--observe', '--job', rjp['path'], '--job-sha256', rjp['sha256'],
                '--expected-source-sha256', self.ready['leg_reviewer']['sha256']]
            base.require(cfg['argv'] == expected, 'Original independent review selection differs')
            base.invoke_controller_once(directory, 'independent-review-', self.ready['leg_CPU_controller'],
                cfg_pin, self.h,
                lambda owner, child: self.register('ORIGINAL_REVIEW_RUNNING', role, owner, child))
            evidence = base.verify_closed_scope(directory, 'independent-review-', cfg_pin,
                self.h, self.read, self.rt, self.ctl)
            fields=evidence['fields']
            base.require(self.rt.duration_seconds(fields['CPUQuotaPerSecUSec'])==2
                and fields['MemoryMax']==str(4<<30)and fields['MemorySwapMax']=='0'
                and self.rt.duration_seconds(fields['RuntimeMaxUSec'])==1980
                and fields['TasksMax']=='128'and self.rt.duration_seconds(fields['TimeoutStopUSec'])==5
                and fields['SendSIGKILL']=='no'and fields['Restart']=='no',
                'Actual original full raw-review CPU resources differ')
            report_pin = self.h.pin(directory / 'independent-quality-leg-review-original01/review.json')
            report = self.read(report_pin)
            base.require(report['schema']=='robotron-original-quota64-independent-cohort-review-v1'
                and report['expected_selected_games']==64
                and report['valid'] is report['full_game_score_verified'] is True
                and report['quality_leg'] == role
                and report['quality_pair_precommit'] == self.ready['quality_pair']
                and report['review_job'] == rjp,
                'Original independent review failed or selected other evidence')
            statistics=report['original_games']['statistics']
            self.h.put(directory/'original-closed-display-summary.json',dict(
                valid=True,complete=True,quality_qualified=False,original_independent_review=report_pin,
                cohort=dict(count=statistics['count'],started=statistics['count'],pending=0,abandoned=0,
                    mean=statistics['mean'],median=statistics['median'],se=statistics['se'])))
            return dict(**evidence, report=report_pin)

        def validate_endpoint_CPU(self):
            pre = self.precommit
            report = self.read(pre['endpoint_CPU_report'])
            pair = self.read(self.ready['quality_pair'])
            base.require(report['status'] == 'PASS' and report['phase_metadata_verified'] is True
                and report['cuda_initialized'] is False and report['visible_cuda_devices'] == 0
                and report['held_recipe_context']['learning_control_lr_scale'] == .125
                and report['adam_group']['lr'] == 6.25e-6
                and report['sha256'] == pair['candidate']['policy']['sha256']
                and pair['candidate']['CPU_report'] == pre['endpoint_CPU_report'],
                'Actual numerical LR125 endpoint proof required before any quality leg')
            scope = pre['endpoint_CPU_scope']
            cfg, owner, closure = [self.read(scope[key]) for key in ('config', 'owner', 'closure')]
            self.ctl.checked_config(scope['config']['path'])
            fields = self.rt.archived_closure(closure, owner, self.read, exit_zero=True)
            base.require(fields['Id'] == cfg['unit'] and fields['NRestarts'] == '0'
                and ' '.join(cfg['argv']) + ' ; ignore_errors=no ;' in fields['ExecStart']
                and self.rt.duration_seconds(fields['CPUQuotaPerSecUSec']) == 2
                and fields['MemoryMax'] == str(4 << 30) and fields['MemorySwapMax'] == '0'
                and self.rt.duration_seconds(fields['RuntimeMaxUSec']) == 180
                and fields['TasksMax'] in ('128', '256') and fields['SendSIGKILL'] == 'no'
                and self.rt.duration_seconds(fields['TimeoutStopUSec']) == 5
                and fields['Restart'] == 'no', 'Actual endpoint CPU argv/resources differ')
            for unit in (owner['unit'], owner['timer']):
                base.require(self.ctl.show(unit)['LoadState'] == 'not-found', 'Endpoint CPU unit remains')
                base.require(not Path('/sys/fs/cgroup/user.slice/user-1001.slice/user@1001.service/app.slice', unit).exists(),
                             'Endpoint CPU cgroup remains')
            base.require(base.birth(owner['pid']) != owner['starttime_ticks'], 'Endpoint CPU owner remains')
            for pin in cfg['pins']:
                base.require(self.ctl.pin(pin['path']) == pin, 'Endpoint CPU input changed')

        def run(self):
            base.require(self.precommit['schema'] == 'robotron-fresh-LR125-quality32-sequence-precommit-v1'
                and self.precommit['source'] == self.h.pin(__file__), 'Exact fresh sequence/source required')
            base.require(PAIR_SHA!='0'*64 and PAIR_SHA!='3d3169064b25e933218e4d2dce2a3cd62ef5f3f5324354f362a9137671759650' and PAIR_SHA!='75baa58f45fc053041a90e2e5d5a66505c76137122ef647198e164e01bf5af5d'
                and self.ready['quality_pair']['sha256']==PAIR_SHA
                and self.ready['expected_selected_games']==64 and self.ready['games_per_slot']==2,
                'UNBOUND sequence requires a new fixed pair and guarded quota64 readiness')
            self.validate_endpoint_CPU()
            intent_path = self.root / 'original-fresh-sequence-observer-original01-intent.json'
            base.require(not intent_path.exists()
                and all(not (self.root / name).exists() for name in base.FOLDERS),
                'All four original leg directories must be new; no adoption or retry')
            self.events.mkdir(mode=0o700)
            (self.root / 'sequence-state-backups-prospective197-original01').mkdir(mode=0o700)
            self.h.put(intent_path, dict(source=self.h.pin(__file__), precommit=self.precommit_pin,
                pid=base.os.getpid(), birth=base.birth(base.os.getpid()), original_attempt=1, no_retry=True,
                all_four_legs_new_at_sequence_start=True, existing_R1_adopted=False, created_unix_s=time.time()))
            outcome = dict(schema='robotron-original-certified-quality32-sequence-outcome-v1',
                precommit=self.precommit_pin, original_records=self.records, quality_qualified=False,
                promotion=False, main_runtime_changed=False, original_attempts_per_leg=1,
                no_retries=True, existing_R1_adopted=False, only_this_sequence_may_launch_each_original_native=True)
            try:
                for role, folder in zip(base.ORDER, base.FOLDERS):
                    self.check_new_actions()
                    directory = self.root / folder
                    preparer = base.load('_fresh_LR125_original_leg_preparer', self.h.checked(self.ready['leg_preparer']))
                    preparer.prepare(self.ready_pin, role, self.h)
                    self.check_new_actions()
                    base.invoke_controller_once(directory, '', self.ready['native_controller'],
                        self.h.pin(directory / 'controller-config.json'), self.h,
                        lambda owner, child, role=role: self.register('ORIGINAL_NATIVE_RUNNING', role, owner, child))
                    native = self.native(directory, role)
                    self.register('ORIGINAL_NATIVE_CLOSED', role, terminal=True)
                    reviewed = self.review(directory, role)
                    self.records.append(dict(role=role, native=native, independent_review=reviewed))
                    self.register('ORIGINAL_LEG_VALIDATED', role, terminal=True)
                self.check_new_actions()
                cfg_pin = self.precommit['campaign_assessment_config']
                base.invoke_controller_once(self.root, 'campaign-assessment-', self.ready['campaign_CPU_controller'], cfg_pin,
                    self.h, lambda owner, child: self.register('CAMPAIGN_ASSESSMENT_RUNNING', 'campaign', owner, child))
                evidence = base.verify_closed_scope(self.root, 'campaign-assessment-', cfg_pin,
                    self.h, self.read, self.rt, self.ctl)
                final_fields=evidence['fields']
                base.require(self.rt.duration_seconds(final_fields['CPUQuotaPerSecUSec'])==2
                    and final_fields['MemoryMax']==str(4<<30)and final_fields['MemorySwapMax']=='0'
                    and self.rt.duration_seconds(final_fields['RuntimeMaxUSec'])==660
                    and final_fields['TasksMax']=='128'and final_fields['SendSIGKILL']=='no'
                    and self.rt.duration_seconds(final_fields['TimeoutStopUSec'])==5
                    and final_fields['Restart']=='no','Actual final assessment CPU scope differs')
                report_pin = self.h.pin(self.root / 'independent-campaign-assessment-original01/assessment.json')
                report = self.read(report_pin)
                base.require(report['valid'] is True, 'Original final campaign assessment invalid')
                outcome.update(status='ORIGINAL_FOUR_LEG_CAMPAIGN_COMPLETE', campaign_assessment=evidence,
                    assessment_report=report_pin, quality_qualified=report['quality_qualified'])
                self.register('QUALIFIED_PENDING_PROTECTION' if report['quality_qualified'] else 'VALID_NOT_IMPROVED',
                              'campaign', terminal=True)
            except base.StopNewActions as error:
                outcome.update(status='SEQUENCING_STOPPED_NO_NEW_ACTIONS', reason=str(error))
                self.register('SEQUENCING_STOPPED_REQUESTED', 'campaign', terminal=True)
            except Exception as error:
                outcome.update(status='ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY', error=repr(error),
                               traceback=traceback.format_exc())
                self.register('ORIGINAL_SEQUENCE_FAILED', 'campaign', terminal=True)
            outcome['ended_unix_s'] = time.time()
            pin = self.h.put(self.root / 'original-fresh-sequence-observer-original01-outcome.json', outcome)
            print(json.dumps(dict(outcome=pin, status=outcome['status'], quality_qualified=outcome['quality_qualified'])),
                  flush=True)
            return 0 if outcome['status'] in ('ORIGINAL_FOUR_LEG_CAMPAIGN_COMPLETE', 'SEQUENCING_STOPPED_NO_NEW_ACTIONS') else 1
    return FreshSequence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--precommit'); parser.add_argument('--precommit-sha256'); parser.add_argument('--source-sha256')
    args = parser.parse_args()
    if not args.run:
        print('PLAN_ONLY: no source/config/runtime reads or actions')
        return 0
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != args.source_sha256:
        raise ValueError('Fresh sequence source changed')
    base = checked_module('_closed_original_quality_sequence_helpers', B / 'sequence_quality32_2259_prospective197_v1.py', BASE_SHA)
    h = checked_module('_fresh_sequence_helpers', B / 'run_full_policy_startup_v3.py',
        '2b6902933b502ac20dacbd444fbf786315d6c960fcad1d5b5bf223dd569708c1')
    reader = checked_module('_fresh_sequence_reader', G / 'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py',
        'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071')
    pin = h.pin(args.precommit)
    if pin['sha256'] != args.precommit_sha256:
        raise ValueError('Fresh sequence precommit changed')
    return sequence_type(base)(pin, h, reader).run()


if __name__ == '__main__':
    raise SystemExit(main())
