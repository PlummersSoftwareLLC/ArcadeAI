"""UNEXECUTED stdlib metadata guards; no application/model/runtime access."""
import copy
import importlib.util
import io
import contextlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

HERE=Path(__file__).resolve().parent
S=importlib.util.spec_from_file_location('_future_entry_capture_metadata',HERE/'capture_entry.py')
M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
R=M.RUN
BASELINE=R/'CE2048-trial02-first-LATCH-followup-quality-root-preparation-20261017/runtime-baseline.json'


def fake_pin(path):
    return dict(path=str(path),sha256='a'*64,bytes=100,identity=dict(mode='0o444'))


def fixture():
    """Authentic historical shapes; future release/readiness are synthetic ONLY."""
    baseline=json.loads(BASELINE.read_text())
    maintenance=json.loads(Path(baseline['actual_maintenance']['path']).read_text())
    historical=json.loads(Path(maintenance['startup']['phase_CPU_readonly_archive']['path']).read_text())
    archived=historical['root_job']['source_control_context']['archived_control']
    raw_control=Path(archived['path']).read_bytes()
    current_control=copy.deepcopy(archived);current_control['path']=str(M.GAME/'models_dqn/learning_control.json')
    slot=copy.deepcopy(historical['root_job']['phase_snapshot'])
    acquisition=json.loads(Path(slot['acquisition']['path']).read_text())
    completed=acquisition['completed_slot_transition']['after']['actual_pin']
    release=fake_pin('/synthetic/future-current-quality-release.json')
    base=fake_pin('/synthetic/future-baseline.json');ready=fake_pin('/synthetic/future-readiness.json')
    case=dict(schema=M.SCHEMA,capture_authorized=True,source_freeze_release=release,runtime_baseline=base,
        readiness=ready,control_before=current_control,completed_slot=completed,tag='synthetic_unique_entry_unactivated',
        output_directory=str(R/'synthetic-unactivated-entry-output'),cpu_python='/synthetic/root-verified-python')
    driver=SimpleNamespace(CURRENT_PLAN='fdb13f963f7433d8dcd816934fe266f327760a7953d47a1208f752f284d5fe85',
        CURRENT_BINDING='25bde9295865770d9a0317ad32a65efa464abb3f71ec3d68f8adc0c8978eeb5b',
        FOUNDER='9b3b839fe39044538412f0f78a8c28feae60170ea2d1c363d21efeead17d84d1',
        HELD=dict(historical['root_job']['source_control_context']['held_recipe_context'],learning_control_lr_scale=.25,optimizer_lr=1.25e-5))
    released=dict(source_freeze_released=True,owned_cleanup_complete=True,released_unix_s=4990.,
        plan=dict(sha256=driver.CURRENT_PLAN),binding_job=dict(sha256=driver.CURRENT_BINDING))
    readiness=dict(status='PASS',observed_unix_s=5000.,**{k:baseline[k] for k in
        ('main_owner','fleet_owner','inference_worker','actors','source_hashes','control_hashes','unit_files','environment_sha256')},
        resources=dict(GPU0_free_bytes=14*(1<<30),**{k:True for k in
        ('GPU0_no_compute_owner','GPU1_main_only','port9999_clear','lease_free','no_competing_helpers',
         'no_private_cgroup_tmpfs_processes','no_pending_save','owned_units_released')}))
    decoded={release['path']:released,base['path']:baseline,ready['path']:readiness}
    def read(pin,raw_only=False):
        if pin['path'] in decoded:return copy.deepcopy(decoded[pin['path']])
        # Only immutable saved metadata descriptors are followed. No PT paths.
        p=Path(pin['path']);assert p.suffix not in ('.pt','.pth','.npy','.npz')
        raw=p.read_bytes();return raw if raw_only else json.loads(raw)
    files=SimpleNamespace(fingerprint=lambda path,*_:copy.deepcopy(completed))
    return case,driver,files,decoded,read,raw_control


@contextlib.contextmanager
def scope(case,reader,raw_control,existing=()):
    with patch.object(M,'pinned',side_effect=reader),patch.object(M,'fingerprint',return_value=(raw_control,case['control_before'])), \
            patch.object(M.time,'time',return_value=5001.),patch.object(Path,'resolve',lambda self,strict=False:self), \
            patch.object(Path,'exists',lambda self:str(self) in existing), \
            patch.object(Path,'mkdir',side_effect=AssertionError('metadata validation must not write')):
        yield


class EntryMetadataContracts(unittest.TestCase):
    def test_default_PLAN_has_no_reads_imports_or_requests(self):
        with patch.object(M,'fingerprint',side_effect=AssertionError('no reads')), \
                patch.object(M,'load',side_effect=AssertionError('no imports')),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(M.main([]),0)
        self.assertIn('PLAN_ONLY_UNSELECTED',output.getvalue())

    def test_authentic_maintenance_shape_keeps_startup0_as_floor_only(self):
        case,driver,files,decoded,reader,raw=fixture()
        with scope(case,reader,raw):ctx=M.validate(case,Path(case['output_directory']),driver,files)
        self.assertEqual(ctx['phase']['expected']['founder_phase_record_sha256'],driver.FOUNDER)
        self.assertEqual(ctx['historical_report']['root_job']['phase_snapshot']['purpose'],'startup')
        self.assertEqual(ctx['historical_report']['root_job']['phase_snapshot']['observed_clients'],0)
        self.assertEqual(ctx['historical_floor'],{k:ctx['historical_report']['clocks'][k] for k in M.CLOCKS})
        self.assertEqual(set(ctx['historical_floor']),set(M.CLOCKS))
        self.assertNotIn('entry_CPU',ctx)

    def test_wrong_release_readiness_and_control_refuse_before_any_save(self):
        for fault in ('release','old_plan','readiness','control_path','unauthorized'):
            case,driver,files,decoded,reader,raw=fixture()
            if fault=='release':decoded[case['source_freeze_release']['path']]['source_freeze_released']=False
            elif fault=='old_plan':decoded[case['source_freeze_release']['path']]['plan']['sha256']='b'*64
            elif fault=='readiness':decoded[case['readiness']['path']]['resources']['owned_units_released']=False
            elif fault=='control_path':case['control_before']['path']=str(M.GAME/'models_dqn/copied-control.json')
            else:case['capture_authorized']=False
            snapshot=Mock(side_effect=AssertionError('no request before prerequisites'))
            modules=dict(driver=driver,ops=SimpleNamespace(),capture=SimpleNamespace(Files=lambda _:files),
                snapshot=SimpleNamespace(Snapshot=snapshot),observer=None,phase=None)
            with self.subTest(fault=fault),scope(case,reader,raw),self.assertRaises(RuntimeError):
                M.run(case,fake_pin('/synthetic/root-case.json'),Path(case['output_directory']),modules)
            snapshot.assert_not_called()

    def test_foreign_completion_pending_failed_and_startup_tag_refuse(self):
        for fault in ('completion','pending','failed','startup'):
            case,driver,files,decoded,reader,raw=fixture();existing=[]
            if fault=='completion':files.fingerprint=lambda *_:dict(case['completed_slot'],sha256='b'*64)
            elif fault in ('pending','failed'):existing=[str(M.GAME/'models_dqn'/('managed_save.request.json'+('.failed' if fault=='failed' else '')))]
            else:
                b=decoded[case['runtime_baseline']['path']];m=reader(b['actual_maintenance']);j=reader(m['root_job']);case['tag']=j['startup_tag']
            with self.subTest(fault=fault),scope(case,reader,raw,existing),self.assertRaises(RuntimeError):
                M.validate(case,Path(case['output_directory']),driver,files)

    def test_real_job_builder_emits_exact_b2e_candidate192_mapping_without_numeric(self):
        case,driver,files,decoded,reader,raw=fixture()
        with scope(case,reader,raw):ctx=M.validate(case,Path(case['output_directory']),driver,files)
        floor=copy.deepcopy(ctx['historical_floor']);source=fake_pin('/synthetic/new-unique-entry.pt')
        frozen=dict(source=source,verification_copy=fake_pin('/synthetic/independent-copy.pt'),acquisition=fake_pin('/synthetic/acquisition.json'))
        snapshot=SimpleNamespace(raw_pin=fake_pin('/synthetic/raw-trigger-API.json'))
        files=SimpleNamespace(exclusive_copy=lambda src,dst:(fake_pin(src),fake_pin(dst)))
        ops=SimpleNamespace(command=Mock(return_value=dict(returncode=0,stdout='actual mocked trainer unit\n')),
            write_bytes=lambda path,raw:fake_pin(path))
        base=SimpleNamespace(check_context=Mock(return_value=M.GAME/'models_dqn'))
        phase=SimpleNamespace(SCHEMA='robotron-phase-snapshot-checkpoint-CPU-job-v1',
            STRICT_SHA256='9ef38e17e1b9eee3f6c43e40005812f2ebe3cff16d08bf61d3e820c2d41134c8',
            ORIGINAL_SHA256='7d1103daf2a77be8250884cb75ce04a640000f04b4376e994d493bc6fd0f7ead',
            load_base=lambda:base,check_acquisition=Mock())
        with patch.object(Path,'mkdir',return_value=None):
            job=M.build_CPU_job(case,fake_pin('/synthetic/case.json'),ctx,frozen,floor,snapshot,
                fake_pin('/synthetic/before.json'),fake_pin('/synthetic/after.json'),files,ops,phase,Path('/synthetic/new-output'))
        self.assertEqual(set(job),{'schema','verifier_sha256','strict_phase_base_sha256','original_strict_base_sha256',
            'experiment','source','verification_copy','clock_floor','source_control_context','output_directory','phase_snapshot'})
        self.assertEqual(job['source'],frozen['source']);self.assertEqual(job['clock_floor'],floor)
        self.assertEqual(job['phase_snapshot']['purpose'],'candidate');self.assertEqual(job['phase_snapshot']['observed_clients'],192)
        self.assertEqual(job['phase_snapshot']['expected_phase'],ctx['phase']['expected'])
        self.assertEqual(job['phase_snapshot']['boot_checkpoint'],ctx['phase']['boot_checkpoint'])
        self.assertEqual(set(job['phase_snapshot']['sources']),set(M.SOURCE_NAMES))
        self.assertEqual(job['source_control_context']['held_recipe_context'],ctx['historical_report']['root_job']['source_control_context']['held_recipe_context'])
        base.check_context.assert_called_once();phase.check_acquisition.assert_called_once()
        self.assertNotIn('mode',job);self.assertNotIn('lr25_context',job)


if __name__=='__main__':unittest.main()
