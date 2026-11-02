"""Prepare this original window's CPU job, then its fresh quality metadata.

Default is inert. Neither step launches a verifier or quality service. Both
require actual successful predecessor closures and the exact sealed precommit.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
P = G/'logs/managed-learning-20261015/run-26/post-score-carry849-next8M-original01-preparation-20261019'


def require(value, message):
    if not value:
        raise ValueError(message)


def run(step, expected_precommit):
    reader_path = G/'tools/confirmed_game_boundary_proposal/protect_confirmed_winner_reviewed4.py'
    require(hashlib.sha256(reader_path.read_bytes()).hexdigest() ==
            'c083d2b325bb843c18742b7993792860bd2647263d3607c6687ca415ddb37071', 'Immutable reader changed')
    spec = importlib.util.spec_from_file_location('_followup_reader',reader_path)
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    entry = reader.pin(P/'tested-followup-precommit.json')
    require(entry['sha256'] == expected_precommit, 'Exact tested root precommit required')
    pre = reader.read_pin(entry)
    require(reader.pin(__file__) == pre['preparer'], 'Followup preparation source changed')
    control = reader.checked_module('_followup_controller',pre['CPU_controller'])
    read = lambda value,as_json=True:reader.read_pin(value,as_json=as_json)
    runtime = reader.checked_module('_followup_archives',pre['archive_checker'])
    proof = read(pre['chain_CPU_report'])
    require(proof['status'] == 'PASS' and proof['tests_run'] == 60 and proof['failures'] == proof['errors'] == 0,
            'All selected chain checks must pass')
    closure = read(pre['chain_CPU_closure'])
    runtime.archived_closure(closure,closure['original'],read,exit_zero=True)
    for name,pin in pre['selected_sources'].items():
        original = read(pin,False)
        require(proof['source_sha256'][pre['tested_source_paths'][name]] == pin['sha256'],
                'Actual CPU test did not bind this selected source')
    for key in ('new_boot_authority','source_scope_review'):
        read(pre[key])
    window = read(pre['window_job'])
    cpu = Path(pre['CPU_preparation'])
    if step == 'CPU':
        window_closure = reader.pin(pre['window_closure_path'])
        finished = read(window_closure)
        runtime.archived_closure(finished,read(pre['window_owner']),read,exit_zero=True)
        module = reader.checked_module('_actual_new_owner_CPU_preparation',pre['selected_sources']['prepare_quality32_candidate_CPU_v2.py'])
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
    module = reader.checked_module('_actual_new_owner_campaign_preparation',pre['selected_sources']['prepare_quality32_campaign_v2.py'])
    lease = Path(pre['lease_path'])
    info = lease.stat()
    require(dict(device=info.st_dev,inode=info.st_ino) == pre['lease_identity'], 'Original private lease object changed')
    job = dict(schema='robotron-quality32-campaign-preparation-job-v2',phase_cpu_job=cpu_job_pin,
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
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--step',choices=('CPU','campaign'),required=True)
    parser.add_argument('--precommit-sha256',required=True)
    args = parser.parse_args()
    run(args.step,args.precommit_sha256)
