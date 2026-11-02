"""Prepare future9000 CPU/campaign metadata only after actual complete CPU proof.

Default is inert. No verifier, model capture, quality service or publication is
launched. Original CPU/campaign assembly is preserved from the prior preparer.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')


def require(value, message):
    if not value:
        raise ValueError(message)


def run(step, precommit_path, expected_precommit):
    reader_path = G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    require(hashlib.sha256(reader_path.read_bytes()).hexdigest() ==
            'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', 'Immutable reader changed')
    spec = importlib.util.spec_from_file_location('_tail_followup_reader', reader_path)
    reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
    path = Path(precommit_path)
    P = path.parent
    require(path.is_absolute() and path.resolve() == path and path.name == 'tested-followup-precommit.json',
            'Exact new prospective precommit path required')
    entry = reader.pin(path)
    require(entry['sha256'] == expected_precommit, 'Exact tested root precommit required')
    pre = reader.read_pin(entry)
    require(reader.pin(__file__) == pre['preparer'], 'Followup preparation source changed')
    require(pre['schema'] == 'robotron-supervised-quality32-followup-precommit-v1'
            and pre['protocol_id'] == 'prospective-tail9000-v1'
            and pre['quality_precommit']['same_fixed_admission_s'] == 5400
            and pre['quality_precommit']['same_whole_cohort_timeout_s'] == 9000
            and pre['source_package']['sha256'] == '3ee43f9bd95fdda8f02abc048999a84513da71125dfd6b2e6558f45d2de6caf9',
            'Only the separately tested prospective9000 chain is selected')
    control = reader.checked_module('_tail_followup_controller', pre['CPU_controller'])
    read = lambda value, as_json=True: reader.read_pin(value, as_json=as_json)
    runtime = reader.checked_module('_tail_followup_archives', pre['archive_checker'])
    authority = reader.checked_module('_tail_followup_authority', pre['chain_authority_source'])
    proof = read(pre['chain_independent_readback'])
    tested = read(proof['precommit']); tested_job = read(tested['job'])
    authority.validate(proof, tested, tested_job, pre['selected_sources'], read,
        runtime.archived_closure, lambda unit: control.show(unit)['LoadState'] == 'not-found', runtime.duration_seconds)
    own_proof = read(pre['chain_authority_CPU_readback'])
    require(own_proof['status'] == 'ORIGINAL_CPU_AUTHORITY11_PASS_ALL6_EXIT0_OWNED_RELEASE_VERIFIED'
            and own_proof['actual_count'] == 11 and own_proof['source'] == pre['chain_authority_source']
            and own_proof['original_units_absent'] is True and own_proof['all_six_original_archives_verified'] is True,
            'Original CPU authority refusal tests must pass')
    own_owner = read(own_proof['original_owner'])
    runtime.archived_closure(read(own_proof['original_closure']), own_owner, read, exit_zero=True)
    require(all(control.show(own_owner[key])['LoadState'] == 'not-found' for key in ('unit', 'timer')),
            'Original CPU authority service/timer remains loaded')
    for key in ('new_boot_authority', 'source_scope_review', 'clock_budget_clarification', 'prior_invalid1306_disposition'):
        read(pre[key])
    require(read(pre['window_job'])['quality_precommit'] == pre['quality_precommit'],
            'The new prospective capture must use the same tested9000 protocol')
    window = read(pre['window_job'])
    cpu = Path(pre['CPU_preparation'])
    if step == 'CPU':
        window_closure = reader.pin(pre['window_closure_path'])
        finished = read(window_closure)
        runtime.archived_closure(finished,read(pre['window_owner']),read,exit_zero=True)
        module = reader.checked_module('_actual_new_owner_CPU_preparation',pre['selected_sources']['prepare_quality32_candidate_CPU_v3.py'])
        job = dict(schema='robotron-quality32-original-candidate-CPU-preparation-v2',
            window_job=pre['window_job'],window_source=pre['window_source'],window_owner=pre['window_owner'],
            window_closure=window_closure,CPU_template=pre['CPU_template'],CPU_controller=pre['CPU_controller'],
            destination=str(cpu),CPU_unit=pre['CPU_unit'])
        root_pin = control.publish(P/'actual-candidate-CPU-preparation-root-job.json',job)
        report = module.prepare(job,reader.pin(root_pin['path']),reader)
        print(json.dumps(dict(status=report['status'],CPU_job=report['CPU_job'],CPU_controller_config=report['CPU_controller_config'],CPU_verified=False)))
        return
    require(step == 'campaign', 'Only the selected CPU or campaign preparation step is allowed')
    cpu_job_pin = reader.pin(cpu/'candidate-CPU-job.json')
    cpu_job = read(cpu_job_pin)
    closure_pin = reader.pin(cpu/'controller-execution/root-original-result-and-owned-release.json')
    closed = read(closure_pin)
    runtime.archived_closure(closed,closed['original'],read,exit_zero=True)
    producer = Path(cpu_job['output_directory'])/'cpu-verification.json'
    producer_pin = reader.pin(producer)
    require(producer_pin['identity']['uid'] == os.getuid() and producer_pin['identity']['nlink'] == 1,
            'Original CPU producer report ownership differs')
    raw = producer.read_bytes()
    require(reader.pin(producer) == producer_pin and hashlib.sha256(raw).hexdigest() == producer_pin['sha256'],
            'Original CPU producer report changed while archiving')
    value = json.loads(raw)
    require(value['status'] == 'PASS' and value['root_job'] == cpu_job
            and value['job_file']['sha256'] == cpu_job_pin['sha256'], 'Actual original CPU PASS and job required')
    archive = cpu/'candidate-CPU-report-readonly.json'
    with archive.open('xb') as stream:
        stream.write(raw);stream.flush();os.fchmod(stream.fileno(),0o444);os.fsync(stream.fileno())
    report_pin = reader.pin(archive)
    require(report_pin['sha256'] == producer_pin['sha256'], 'Readonly CPU report copy differs')
    control.publish(cpu/'original-CPU-producer-report-archive.json',dict(original=producer_pin,readonly_archive=report_pin,
                    original_bytes_unchanged=True,original_job=cpu_job_pin,original_closure=closure_pin))
    module = reader.checked_module('_actual_new_owner_campaign_preparation',pre['selected_sources']['prepare_quality32_campaign_v4.py'])
    lease = Path(pre['lease_path'])
    info = lease.stat()
    require(dict(device=info.st_dev,inode=info.st_ino) == pre['lease_identity'], 'Original private lease object changed')
    job = dict(schema='robotron-quality32-supervised-campaign-preparation-job-v1',main_fleet_transition=pre['main_fleet_transition'],phase_cpu_job=cpu_job_pin,
        phase_cpu_report=report_pin,phase_cpu_closure=closure_pin,phase_cpu_config=reader.pin(cpu/'CPU-controller-config.json'),
        window_job=pre['window_job'],window_result=reader.pin(Path(window['output'])/'result.json'),
        window_latch=reader.pin(Path(window['output'])/'first-durable-both-horizons.json'),source_package=pre['source_package'],
        reference=pre['reference'],main_binding_template=pre['main_binding_template'],capacity_review=pre['capacity_review'],
        preceding_originals=pre['preceding_originals'],output=pre['campaign_preparation'],native_unit=pre['native_unit'],
        outer_unit=pre['outer_unit'],review_unit=pre['review_unit'],lease_path=pre['lease_path'],lease_identity=pre['lease_identity'],
        binary_inputs=pre['binary_inputs'],campaign_parameters=pre['campaign_parameters'],hypothesis_description=pre['hypothesis_description'])
    root_pin = control.publish(P/'actual-campaign-preparation-root-job.json',job)
    report = module.prepare(job,reader.pin(root_pin['path']),reader)
    print(json.dumps(dict(status=report['status'],native_controller_config=report['native_controller_config'],
                         outer_launch_plan=report['outer_launch_plan'],CPU_completion=report['CPU_completion'])))


if __name__ == '__main__':
    if '--execute' not in sys.argv[1:]:
        print('PLAN_ONLY: no reads, copies, queries, outputs or launches')
        raise SystemExit(0)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--step', choices=('CPU', 'campaign'), required=True)
    parser.add_argument('--precommit', type=Path, required=True)
    parser.add_argument('--precommit-sha256', required=True)
    args = parser.parse_args()
    run(args.step, args.precommit, args.precommit_sha256)
