"""Validated, persistent controls for measured live learning experiments."""
from dataclasses import dataclass
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class EpsilonRamp:
    anchor: int
    start: float
    end: float
    duration: int

    def value(self, learner_frame):
        progress = min(1.0, max(0.0, (learner_frame-self.anchor)/self.duration))
        return self.start + progress*(self.end-self.start)


class LearningControl:
    def __init__(self, path):
        self.path = Path(path)
        self.label = 'natural-schedule'
        self.ramp = None
        self.measurement = None
        self.lr_scale = 1.0
        self._raw = None
        self.refresh()

    def refresh(self):
        """Called on the main thread; invalid files retain the last valid control."""
        try:
            raw = self.path.read_text() if self.path.exists() else '{}'
            if raw == self._raw:
                return False
            data = json.loads(raw)
            if not isinstance(data, dict) or set(data) - {'experiment', 'epsilon_ramp', 'reason', 'measurement', 'lr_scale'}:
                raise ValueError('unsupported learning control fields')
            lr_scale = data.get('lr_scale', 1.0)
            if isinstance(lr_scale, bool):
                raise ValueError('invalid learning rate scale')
            lr_scale = float(lr_scale)
            if not math.isfinite(lr_scale) or not 0.01 <= lr_scale <= 2.0:
                raise ValueError('learning rate scale must be within 0.01..2')
            label = str(data.get('experiment', 'natural-schedule'))
            candidate = data.get('epsilon_ramp')
            ramp = None
            if candidate is not None:
                if set(candidate) != {'anchor', 'start', 'end', 'duration'}:
                    raise ValueError('epsilon ramp requires anchor/start/end/duration')
                anchor, duration = int(candidate['anchor']), int(candidate['duration'])
                start, end = float(candidate['start']), float(candidate['end'])
                if anchor < 0 or duration <= 0 or not all(math.isfinite(x) and 0.02 <= x <= 1 for x in (start, end)):
                    raise ValueError('invalid epsilon ramp bounds')
                ramp = EpsilonRamp(anchor, start, end, duration)
            measurement = data.get('measurement')
            if measurement is not None:
                if not isinstance(measurement, dict) or set(measurement) - {'label', 'checkpoint', 'cohort_s', 'timeout_s'}:
                    raise ValueError('unsupported measurement control')
                name = measurement.get('label', '')
                if not isinstance(name, str) or not name or len(name) > 80 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in name):
                    raise ValueError('invalid measurement label')
                cohort_s = float(measurement.get('cohort_s', 120))
                timeout_s = float(measurement.get('timeout_s', 600))
                if not (math.isfinite(cohort_s) and 30 <= cohort_s <= 3600
                        and math.isfinite(timeout_s) and cohort_s + 30 <= timeout_s <= 7200):
                    raise ValueError('invalid measurement duration/timeout')
                checkpoint = measurement.get('checkpoint')
                if checkpoint is not None and not isinstance(checkpoint, str):
                    raise ValueError('measurement checkpoint must be a path string')
                measurement = dict(label=name, checkpoint=checkpoint,
                                   cohort_s=cohort_s, timeout_s=timeout_s)
            self.measurement = measurement
            self.lr_scale = lr_scale
            # Publish one immutable ramp reference; actor readers never observe
            # partially edited ramp parameters on free-threaded CPython.
            self.ramp = ramp
            self.label = label
            self._raw = raw
            print(f'[LEARNING CONTROL] {self.label}: {self.ramp}; LR scale={self.lr_scale:g}', flush=True)
            return True
        except (OSError, ValueError, TypeError) as exc:
            print(f'[LEARNING CONTROL] rejected {self.path}: {exc}', flush=True)
            return False

    def epsilon(self, learner_frame, natural):
        ramp = self.ramp
        return natural if ramp is None else ramp.value(learner_frame)
