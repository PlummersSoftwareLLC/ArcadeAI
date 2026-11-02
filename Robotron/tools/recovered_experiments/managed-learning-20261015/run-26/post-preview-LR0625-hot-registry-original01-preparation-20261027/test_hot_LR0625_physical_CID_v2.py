"""Actual V2 monitor function, retained232 fixture, fake API/proc/unit collaborators only."""
import copy
import io
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
SOURCE=HERE/'prepare_hot_LR0625_registry_v2.py'
m=types.ModuleType('_physical_CID_test'); m.__file__=str(SOURCE)
exec(compile(SOURCE.read_bytes(),str(SOURCE),'exec'),m.__dict__)


class Tests(unittest.TestCase):
    def setUp(self):
        self.binding=json.loads(m.HOT_PRIOR.read_text())
        self.policy=json.loads(Path(self.binding['supervision_policy']['path']).read_text())
        self.capture=json.loads(Path(self.binding['actual_192_capture']['path']).read_text())
        self.manifest=json.loads(Path(self.capture['manifest']['path']).read_text())
        self.bp=dict(path=str(m.HOT_PRIOR),sha256=m.HOT_PRIOR_SHA)
        self.values={str(m.HOT_PRIOR):self.binding,self.binding['supervision_policy']['path']:self.policy,
                     self.binding['actual_192_capture']['path']:self.capture,self.capture['manifest']['path']:self.manifest}
        self.ownerfields={v['unit']['Id']:v['unit'] for v in self.policy['baseline_owners'].values()}
        self.processes={v['process']['pid']:v['process'] for v in self.policy['baseline_owners'].values()}
        self.processes.update({v['pid']:v for v in self.policy['baseline_actors'].values()})
        self.birth_fault=False
        def process(pid):
            value=copy.deepcopy(self.processes[pid])
            if self.birth_fault and pid==self.policy['baseline_actors']['1']['pid']: value['starttime_ticks']+=1
            return value
        helper=types.SimpleNamespace(validate_manifest=lambda x:None,verify_rendered_wrapper=lambda *x:None,
                                      unit_show=lambda unit:copy.deepcopy(self.ownerfields[unit]))
        collector=types.SimpleNamespace(process_record=process)
        self.p=types.SimpleNamespace(read=lambda pin:self.values[pin['path']],
            pin=lambda path:self.policy['source_files'][str(path)],
            module=lambda pin,name:collector if name=='_mixed_current_processes' else helper)
        self.api1=copy.deepcopy(self.capture['api']); self.api2=copy.deepcopy(self.api1)
        self.now=float(self.api1['ts'])+.1
        for n,api in enumerate((self.api1,self.api2),1):
            api['pipeline_snapshot_age_s']=.01
            for row in api['client_rows']: row['client_id']+=n*1000
        self.apis=iter((self.api1,self.api2))
        self.groups={str(Path('/sys/fs/cgroup'+self.policy[key]['cgroup'])/'cgroup.procs'):
            ' '.join(str(a['pid']) for slot,a in self.policy['baseline_actors'].items() if self.policy['actor_ownership'][slot]==key)
            for key in ('trainer','fleet','supplemental0')}
        self.environment='\0'.join(k+'='+v for k,v in self.policy['trainer_curated_environment'].items()).encode()+b'\0'

    def run_actual(self):
        original_text=Path.read_text; original_bytes=Path.read_bytes
        def read_text(path,*a,**kw):
            if str(path) in self.groups: return self.groups[str(path)]
            raise AssertionError('Unexpected file read: '+str(path))
        def read_bytes(path,*a,**kw):
            if str(path)==f"/proc/{self.policy['trainer']['pid']}/environ": return self.environment
            if str(path).startswith('/proc/') and path.name=='cmdline':
                pid=int(path.parent.name); return '\0'.join(self.processes[pid]['command']).encode()+b'\0'
            raise AssertionError('Unexpected file read: '+str(path))
        with patch.object(m.urllib.request,'urlopen',lambda *a,**k:io.BytesIO(json.dumps(next(self.apis)).encode())),\
             patch.object(Path,'read_text',read_text),patch.object(Path,'read_bytes',read_bytes),\
             patch.object(m.time,'time',lambda:self.now),patch.object(m.time,'monotonic',side_effect=(0,1)):
            return m.check_before_hot(self.p,self.bp)

    def test_rotating_CIDs_are_observations_and_physical192_remains_authority(self):
        result=self.run_actual()
        self.assertEqual(result['status'],'READONLY_PASS'); self.assertEqual(result['actor_count'],192)
        self.assertEqual(len(result['historical_CID_changed_slots']),192)
        self.assertEqual(len(result['within_observation_CID_changed_slots']),192)
        self.assertEqual(result['historical_CID_roles'],self.policy['actual_API_roles'])
        self.assertEqual(m.slot_roles(result['current_CID_observations']['after']),m.slot_roles(self.policy['actual_API_roles']))
        self.assertEqual(result['expected_effective_lr'],6.25e-6)

    def test_actual_physical_birth_change_is_refused(self):
        self.birth_fault=True
        with self.assertRaisesRegex(ValueError,'actor birth/source/environment'): self.run_actual()

    def test_slot_role_change_is_refused(self):
        self.api1['client_rows'][0]['eval']=not self.api1['client_rows'][0]['eval']
        with self.assertRaisesRegex(ValueError,'unique role/slot/CID'): self.run_actual()

    def test_duplicate_CID_in_one_snapshot_is_refused(self):
        self.api1['client_rows'][0]['client_id']=self.api1['client_rows'][1]['client_id']
        with self.assertRaisesRegex(ValueError,'Duplicate actual CID'): self.run_actual()


if __name__=='__main__': unittest.main(verbosity=2)
