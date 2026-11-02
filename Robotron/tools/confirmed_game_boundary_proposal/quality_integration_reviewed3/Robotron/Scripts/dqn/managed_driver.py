"""Durable orchestration for explicitly requested frozen-policy measurements."""
import json
import os
from pathlib import Path
import time


def _atomic_json(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, default=str))
    os.replace(tmp, path)


def consume_save_request(agent, model_dir):
    directory = Path(model_dir)
    request = directory / 'managed_save.request.json'
    if not request.exists():
        return False
    try:
        data = json.loads(request.read_text())
        tag = str(data.get('tag', ''))
        if not tag or len(tag) > 80 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in tag):
            raise ValueError('invalid managed checkpoint tag')
        destination = directory / 'managed-checkpoints'
        destination.mkdir(exist_ok=True)
        path = destination / (tag + '.pt')
        agent.save(str(path), show_status=False, save_replay=False)
        os.replace(request, str(request)+'.completed')
        print(f'[MANAGED CHECKPOINT] {path}', flush=True)
        return True
    except Exception as exc:
        # A malformed local request must not stop the trainer or be retried
        # noisily on every main-loop iteration.
        os.replace(request, str(request)+'.failed')
        print(f'[MANAGED CHECKPOINT] rejected request: {exc}', flush=True)
        return False


class ManagedMeasurementDriver:
    def __init__(self, agent, metrics, server, model_dir, controller_factory=None):
        if controller_factory is None:
            try:
                from .managed_measurement import ManagedMeasurement
            except ImportError:
                from managed_measurement import ManagedMeasurement
            controller_factory = ManagedMeasurement
        self.agent, self.metrics = agent, metrics
        self.directory = Path(model_dir)/'managed-measurements'
        self.directory.mkdir(exist_ok=True)
        self.controller = controller_factory(agent, metrics, server.game_journal,
                                             boundary_status=server.measurement_boundary_status)
        self.request = None
        self.handled = {path.stem for path in self.directory.glob('*.json')}

    def _publish(self, status):
        self.metrics.managed_measurement_status = dict(status)

    def _finish(self, status):
        request = dict(self.request)
        # Restoration is a prerequisite to resuming training; never swallow a
        # failed restore and continue serving the reference policy by mistake.
        prior_status = self.controller.status()
        try:
            restored_status = self.controller.exit()
        except Exception as exc:
            self._publish(dict(prior_status, complete=True, valid=False, active=True,
                               phase='restore_failed', reason=str(exc)))
            raise
        # Keep an interrupted cohort's denominator and clock evidence. A failed
        # request prepared before enter() owns no old controller results.
        prior_status = prior_status if prior_status.get('label') == request['label'] else {}
        restored_status = (restored_status if isinstance(restored_status, dict)
                           and restored_status.get('label') == request['label'] else {})
        result = dict(prior_status, **restored_status)
        result.update(status)
        result.update(active=False, phase='finished', label=request['label'], request=request,
                      ended_unix_s=time.time())
        _atomic_json(self.directory/(request['label']+'.json'), result)
        self.handled.add(request['label'])
        self.request = None
        self._publish(result)
        print(f"[MANAGED MEASUREMENT] finished {request['label']}: valid={result.get('valid')}", flush=True)

    def update(self, request):
        if self.request is not None:
            if request is None or request['label'] != self.request['label']:
                self._finish(dict(complete=True, valid=False, reason='cancelled'))
            else:
                status = self.controller.tick()
                if status is None:
                    status = self.controller.status()
                self._publish(status)
                if status.get('complete'):
                    self._finish(status)
                return
        if request is None or request['label'] in self.handled:
            return
        self.request = dict(request)
        try:
            self.controller.enter(request['label'], checkpoint_path=request.get('checkpoint'),
                                  cohort_s=request.get('cohort_s', 120),
                                  timeout_s=request.get('timeout_s', 600))
            if request.get('checkpoint') is None:
                # Online weights are quiescent, so this checkpoint is exactly
                # the current policy about to be measured, with optimizer state.
                self.agent.save(str(self.directory/(request['label']+'.pt')),
                                show_status=False, save_replay=False)
            self._publish(self.controller.status())
            print(f"[MANAGED MEASUREMENT] started {request['label']}: "
                  f"learner paused; all actors greedy; admission {request.get('cohort_s', 120):g}s; "
                  "every admitted game must finish", flush=True)
        except Exception as exc:
            self._finish(dict(complete=True, valid=False, reason=str(exc)))

    def close(self):
        if self.request is not None:
            self._finish(dict(complete=True, valid=False, reason='trainer_shutdown'))
