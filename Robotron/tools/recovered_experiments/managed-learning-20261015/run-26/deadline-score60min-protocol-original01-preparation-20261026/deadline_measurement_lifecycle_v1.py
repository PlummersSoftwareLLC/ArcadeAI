"""Private deadline-mode lifecycle using the frozen entry/restore implementation.

This wrapper never asks the historical complete-game controller to judge the new
deadline metric. Its entry barrier, frozen policy and restoration remain real.
Only DeadlineScoreRecorder can produce the new scored/censored result.
"""
import copy
import hashlib
import importlib.util
from pathlib import Path
import time

SOURCE = Path('/home/dave/source/repos/ArcadeAI/Robotron/tools/quality_capacity_proposal/profile06/Robotron/Scripts/dqn/managed_measurement.py')
SOURCE_SHA = '9649d0ba199bdc0943202164da7a9058e5d578b9c411ce26a950b2595c7e96e6'
SLOTS = list(range(4096,4128))


def require(ok,message):
    if not ok: raise ValueError(message)


class DeadlineMeasurementLifecycle:
    def __init__(self,agent,metrics,journal,*,boundary_status,clock=time.time):
        require(hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA,'Frozen entry/restore source differs')
        spec=importlib.util.spec_from_file_location('_deadline_frozen_measurement_lifecycle',SOURCE)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.origin=module.ManagedMeasurement(agent,metrics,journal,boundary_status=boundary_status,clock=clock)
        self.boundary_status=boundary_status
        self.phase='idle'
        self.fixed_admission=None
        self.seal_pin=None

    @property
    def generation(self): return self.origin.generation

    def enter(self,label):
        require(self.phase=='idle','One original lifecycle only')
        # START authorization must finish within the selected 300s startup bound;
        # this wall-clock window never sets or extends the monotonic score D.
        self.origin.enter(label,cohort_s=300,timeout_s=4200)
        self.phase='warming'
        return self.status()

    def admit_when_ready(self):
        require(self.phase in ('warming','active'),'Lifecycle cannot admit now')
        if self.phase=='warming':
            value=self.origin.tick()
            require(value['valid'] is not False and not value['complete'],'Entry barrier failed or old metric terminated')
            if self.origin.start_ts is None: return None
            require(self.origin.phase=='collecting','Frozen entry did not finish its boundary')
            self.fixed_admission=dict(open_unix_ns=int(self.origin.start_ts*1e9),
                close_unix_ns=int(self.origin.close_ts*1e9),generation=self.generation,experiment=self.origin.label)
            self.phase='active'
        self.guard()
        return copy.deepcopy(self.fixed_admission)

    def guard(self):
        require(self.phase in ('active','sealed') and self.origin._owns_mode,'Frozen deadline mode is not active')
        require(self.origin._clock_values()==self.origin._clocks and
                self.origin._replay_values()==self.origin._replay_guard,'Frozen policy clocks or replay changed')
        value=self.boundary_status(self.generation)
        require(value['ready'] is value['active'] is True and
                value['generation']==value['requested_generation']==self.generation and
                value['clients']==value['expected']==value['acknowledged']==32 and
                value['actor_slots']==SLOTS and not value['pending_client_ids'] and
                not value['replay_pending_client_ids'],'All32 actual origin acknowledgements required')
        return copy.deepcopy(value)

    def mark_sealed(self,pin):
        require(self.phase=='active' and type(pin) is dict and type(pin.get('sha256')) is str
                and len(pin['sha256'])==64,'Exact original cutoff seal pin required')
        self.guard();self.seal_pin=copy.deepcopy(pin);self.phase='sealed'

    def exit(self,*,all_original_threads_stopped):
        require(type(all_original_threads_stopped) is bool and all_original_threads_stopped,
                'Stop original ingestion before restoring private measurement flags')
        before=self.origin.status()
        sealed=self.phase=='sealed'
        # Deliberately do not call complete-game exit()/finish(): pending first
        # games are ordinary censored members of this separately sealed metric.
        self.origin._restore()
        self.phase='finished'
        return dict(schema='robotron-deadline32-measurement-restoration-v1',
            metric_sealed=sealed,original_cutoff_seal=self.seal_pin,
            frozen_entry_controller_before_restore=before,
            measurement_active_after=self.origin.metrics.measurement_active,
            owns_mode_after=self.origin._owns_mode,
            replay_values_after=self.origin._replay_values(),
            all_original_threads_stopped=True,complete_game_judgment_not_requested=True)

    def status(self):
        return dict(schema='robotron-deadline32-measurement-lifecycle-v1',phase=self.phase,
            measurement_generation=self.generation,fixed_admission=copy.deepcopy(self.fixed_admission),
            original_cutoff_seal=self.seal_pin,complete_game_judgment_not_requested=True)
