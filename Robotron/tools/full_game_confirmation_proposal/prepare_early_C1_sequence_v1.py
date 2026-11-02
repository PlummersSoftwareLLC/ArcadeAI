"""Prepare a future-only early-C1 scheduler and truthful display copies.

No active source, unit, campaign, public status or game is modified. Fresh-case
jobs and source-family/rule binding remain necessary before future execution.
"""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import sys

G=Path('/home/dave/source/repos/ArcadeAI/Robotron')
F=G/'logs/managed-learning-20261015/run-26/quality32-protectedb231-vs-postreboot1c-fullgame-original01-20261101'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module);return module


def write(path,text):
    with path.open('x')as stream:stream.write(text);stream.flush();os.fsync(stream.fileno());os.fchmod(stream.fileno(),0o444)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--output',type=Path);args=p.parse_args()
    if not args.execute:p.print_help();return 0
    h=load('_prepare_future_C1_sequence_h',G/'tools/startup_policy_journal_proposal/run_full_policy_startup_v3.py')
    original_job=json.loads((F/'original-sequence-job.json').read_text());parent=original_job['runtime'];original=h.checked(parent).read_text();source=original;edits=[]
    ap=h.pin(F/'future-authenticated-early-C1-original01/qualified-prospective-authenticated-C1-preparation.json')
    auth=json.loads(h.checked(ap).read_text());auth_source=auth['source']
    numeric_proof=auth['numeric_CPU39'];np=json.loads(h.checked(numeric_proof).read_text())

    def replace(before,after):
        nonlocal source
        assert source.count(before)==1,before
        source=source.replace(before,after,1);edits.append((before,after))

    marker='def require(value,message):\n'
    validation=f"ACTIVE_CASE=CASE\nEARLY_ASSESSOR_SHA={auth_source['sha256']!r}\nEARLY_NUMERIC_SHA={np['source']['sha256']!r}\n\n\n"
    validation+='''class EarlyC1Rejected(Exception):pass


def validate_future_prepared(job,prepared,h):
    case=Path(prepared['campaign_directory'])
    require(case.is_absolute()and case.resolve()==case and case.is_relative_to(G/'logs/managed-learning-20261015/run-26')
        and case!=ACTIVE_CASE and prepared['pair']['sha256']!='9ea5d482628964107a0543665239c5147599e543c0e3ecd0d51b759e8c7e6b62',
        'Fresh future campaign required; active original campaign excluded')
    read=lambda pin:json.loads(h.checked(pin).read_text())
    family=read(prepared['source_family']);rule=read(prepared['early_C1_rule'])
    require(prepared['sequence_source']==job['runtime']==h.pin(__file__)
        and family['sequence_source']==job['runtime']and family['pair']==prepared['pair']
        and family['early_C1_assessor']==prepared['early_C1_assessor']
        and family['early_C1_numeric']==prepared['early_C1_numeric']
        and family['early_C1_rule']==prepared['early_C1_rule']
        and prepared['early_C1_assessor']['sha256']==EARLY_ASSESSOR_SHA
        and prepared['early_C1_numeric']['sha256']==EARLY_NUMERIC_SHA,
        'Future sequence/rule/assessor/numeric source family differs')
    require(rule['schema']=='robotron-predeclared-fullgame-C1-failure-rule-v1'
        and rule['campaign_directory']==str(case)and rule['pair']==prepared['pair']
        and rule['required_closed_roles']==['R1','C1','R2']
        and rule['stage']=='after_R2_review_before_C2_launch'
        and rule['skip_C2_only_if_C1_gate_failed']is True and rule['promotion_shortcut_allowed']is False
        and rule['assessor']==prepared['early_C1_assessor']and rule['numeric_gate']==prepared['early_C1_numeric']
        and rule['scheduler']==job['runtime'],'Exact predeclared future decision rule required')
    for leg in prepared['legs']:
        native=read(leg['native_job'])
        require(native['source_family_manifest']==prepared['source_family']
            and native['quality_pair_precommit']==prepared['pair']and prepared['early_C1_rule']in native['inputs']
            and not Path(native['output']).exists()
            and not(Path(leg['directory'])/'controller-original-launch.json').exists(),
            'All four fresh native jobs must precommit this same rule; no adoption/retry')
    return case


'''
    replace(marker,validation+marker)
    replace("self.job=job;self.h=h;self.prepared=json.loads(h.checked(job['prepared']).read_text())",
        "self.job=job;self.h=h;self.prepared=json.loads(h.checked(job['prepared']).read_text())\n        validate_future_prepared(job,self.prepared,h)")
    replace("            elif current==role:\n", "            elif state['stage']=='rejected_after_C1'and role=='C2':\n"
        "                display=dict(label='Candidate',phase='skipped',valid=None,complete=False,\n"
        "                    reason='C1 failed its mean or median gate; C2 was not started',cohort={})\n"
        "                atomic(Path(leg['display_live_path']),display)\n"
        "                entry.update(state='skipped',evaluator_status_path=leg['display_live_path'])\n"
        "            elif current==role:\n")
    replace("outcome=None if state['assessment']is None else state['assessment'].get('all_candidate_gates_passed'),",
        "outcome=('not_improved_C1'if state['stage']=='rejected_after_C1'else\n"
        "                None if state['assessment']is None else\n"
        "                'qualified_pending_protection'if state['assessment'].get('all_candidate_gates_passed')else'not_improved'),")
    replace("reason=state['error']or('All original legs reviewed; final assessment complete'if state['terminal']else'All selected full games and independent review required'))",
        "reason=state['error']or('C1 failed; C2 was not started'if state['stage']=='rejected_after_C1'else\n"
        "                'All original legs reviewed; final assessment complete'if state['terminal']else'All selected full games and independent review required'))")
    replace("        elif state['terminal']:\n", "        elif state['stage']=='rejected_after_C1':\n"
        "            title='Candidate failed C1; C2 was not started';detail='Three original full-game cohorts were independently reviewed. Main training continues.'\n"
        "        elif state['stage']=='early_C1_assessment':\n"
        "            title='Checking C1 against the fresh reference';detail='All three full-game cohorts are reviewed; checking whether C2 is still required.'\n"
        "        elif state['terminal']:\n")
    replace("next_stage='Next original cohort'if not state['terminal']else'Apply the independently assessed promotion gates',",
        "next_stage='Select the next candidate'if state['stage']=='rejected_after_C1'else\n"
        "                    'Next original cohort'if not state['terminal']else'Apply the independently assessed promotion gates',")
    method='''    def assess_C1_before_C2(self):
        require([r['role']for r in self.results]==['R1','C1','R2'],
            'Exactly three original completed and reviewed legs required before early assessment')
        h=self.h;self.update(stage='early_C1_assessment',current=None)
        directory=CASE/'early-C1-assessment-CPU-original01';directory.mkdir(mode=0o700)
        job=h.put(directory/'job.json',dict(schema='robotron-predeclared-early-C1-three-leg-assessment-v1',
            runtime=self.prepared['early_C1_assessor'],campaign_directory=str(CASE),pair=self.prepared['pair'],
            source_family=self.prepared['source_family'],original_decision_kernel=self.prepared['original_decision_kernel'],
            numeric_gate=self.prepared['early_C1_numeric'],numeric_CPU_proof=self.prepared['early_C1_numeric_CPU_proof'],
            predeclared_rule=self.prepared['early_C1_rule'],legs=self.results,report=str(directory/'report.json')))
        cfg=self.CPU_config(directory,'robotron-fullgame-early-C1-CPU-original01.service',self.prepared['early_C1_assessor'],job)
        _,closed,code=self.invoke(directory,cfg,self.prepared['CPU_controller'],self.cpu_controller)
        report_pin=h.pin(directory/'report.json')if(directory/'report.json').exists()else None
        report=self.read(report_pin)if report_pin else None
        require(code==0 and report is not None and report['status']=='PASS_AUTHENTICATED_PREDECLARED_C1_FAILURE_ASSESSMENT'
            and report['valid']is True and report['original_job']==job
            and report['runtime']==self.prepared['early_C1_assessor']
            and report['pair']==self.prepared['pair']and report['source_family']==self.prepared['source_family']
            and report['predeclared_rule']==self.prepared['early_C1_rule']
            and type(report['stop_remaining_legs'])is bool and type(report['C2_required'])is bool
            and report['stop_remaining_legs']is not report['C2_required']
            and report['promotion_eligible']is False and report['cancellation_or_scheduling_performed']is False,
            'Original early assessment failed or used a foreign decision; no rescue/retry')
        h.put(directory/'positive-original-early-assessment-closeout.json',dict(actual_exit=code,
            original_Popen_reaped=True,all_original_controller_resources_closed=True,
            original_result=closed['result'],closure=closed['closure'],owner=closed['owner'],report=report_pin))
        if report['stop_remaining_legs']:
            self.update(assessment=report,stage='rejected_after_C1',current=None)
            raise EarlyC1Rejected('C1 gate failed; C2 must remain unstarted')
        return report_pin

'''
    replace('    def run(self):\n',method+'    def run(self):\n')
    replace("                self.publish()\n            self.update(stage='campaign_assessment',current=None)",
        "                self.publish()\n                if role=='R2':self.assess_C1_before_C2()\n            self.update(stage='campaign_assessment',current=None)")
    replace("        except Exception:\n            error=traceback.format_exc();", "        except EarlyC1Rejected:\n            actual_exit=0\n        except Exception:\n            error=traceback.format_exc();")
    replace('def main():\n', 'def main():\n    global CASE\n')
    replace("    job['job_path']=str(args.job);return Sequence(job,h).run()", "    prepared=json.loads(h.checked(job['prepared']).read_text())\n"
        "    CASE=validate_future_prepared(job,prepared,h)\n"
        "    active=json.loads((G/'logs/managed-learning-20261015/state.json').read_text()).get('active_quality_job')or{}\n"
        "    require(active.get('directory')==str(CASE),'Future campaign must be explicitly registered before execution')\n"
        "    job['job_path']=str(args.job);return Sequence(job,h).run()")
    back=source
    for before,after in reversed(edits):assert back.count(after)==1;back=back.replace(after,before,1)
    assert back==original
    compile(source,'<future-C1-sequence>','exec');args.output.mkdir(mode=0o700)
    target=args.output/'run_predeclared_early_C1_sequence_v1.py';write(target,source)
    old_tree=ast.parse(original);new_tree=ast.parse(source);stable=[]
    for node in old_tree.body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef))and node.name not in ('Sequence','main'):
            other=next(n for n in new_tree.body if getattr(n,'name',None)==node.name)
            assert ast.dump(node)==ast.dump(other);stable.append(node.name)
    ui=[]
    old='''        let state = leg.complete ? (leg.valid === false ? "Invalid" : "Complete") :
          leg.phase === "draining" ? "Waiting for " + Number(leg.pending || 0) + " admitted game(s) to finish" :
          leg.phase === "collecting" ? "Collecting games" : leg.state === "running" ? "Starting" : "Queued";'''
    new='''        let state = leg.state === "skipped" ? "Skipped · C1 failed" :
          leg.complete ? (leg.valid === false ? "Invalid" : "Complete") :
          (leg.phase === "independent_review" || leg.state === "reviewing") ? "Validating complete games" :
          leg.phase === "draining" ? "Waiting for " + Number(leg.pending || 0) + " admitted game(s) to finish" :
          leg.phase === "collecting" ? "Collecting games" : leg.state === "running" ? "Starting" : "Queued";'''
    for parent_path,name in [(G/'html/training-live.html','future-training-live.html'),(G/'Scripts/dqn/metrics_dashboard.py','future-metrics_dashboard.py')]:
        pp=h.pin(parent_path);text=h.checked(pp).read_text();assert text.count(old)==1
        detail='        let detail = Number(leg.count || 0) + " complete games";';assert text.count(detail)==1
        changed=text.replace(old,new,1).replace(detail,'        let detail = leg.state === "skipped" ? "Not started; C1 did not qualify" : Number(leg.count || 0) + " complete games";',1)
        out=args.output/name;write(out,changed)
        reverted=changed.replace(new,old,1).replace('        let detail = leg.state === "skipped" ? "Not started; C1 did not qualify" : Number(leg.count || 0) + " complete games";',detail,1)
        assert reverted==text and h.pin(parent_path)==pp
        ui.append(dict(parent=pp,source=h.pin(out),exact_two_label_edits=True))
    proof=h.put(args.output/'source-preparation.json',dict(status='FUTURE_EARLY_C1_SEQUENCE_AND_DISPLAY_NOT_CPU_TESTED_OR_SELECTED',
        source=h.pin(target),parent=parent,generator=h.pin(__file__),authenticated_assessor_preparation=ap,
        exact_reverse_edit_proof=True,unchanged_top_level_helpers=stable,edits=[dict(before=a,after=b)for a,b in edits],
        display_copies=ui,all_native_and_review_launch_ownership_helpers_unchanged=True,
        active_campaign_and_pair_excluded=True,canonical_future_registration_required=True,
        future_case_jobs_sourcefamily_precommit_and_preflight_still_required=True,
        active_sources_or_PUBLIC_or_units_changed=False,selected_or_deployed=False,promotion=False))
    print(json.dumps(dict(status='FUTURE_EARLY_C1_SEQUENCE_AND_DISPLAY_NOT_CPU_TESTED_OR_SELECTED',proof=proof)),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
