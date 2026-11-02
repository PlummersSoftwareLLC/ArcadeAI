"""Lossless API wire witness with a strict-JSON projection of guard inputs.

The caller archives response bytes before parsing or health checks. This module
does not write files, query services, decide main health, or qualify a runtime.
Independent review rejoins the projection to the original wire bytes and then
applies the existing critical-health/exposure/progress checks to the parsed API.
"""
import copy
import json
import math

FORMAT = 'robotron-raw-api-critical-projection-v1'
MAX_WIRE_BYTES = 2 << 20
TOP_FIELDS = ('ts', 'client_count', 'training_enabled', 'measurement_active',
    'managed_experiment', 'lr', 'pipeline_read_error', 'bank_persistence_read_error',
    'pipeline_snapshot_age_s', 'frame_count', 'learner_frame_count',
    'optimized_samples', 'training_steps')
ERROR_KINDS = ('inference', 'actor_refresh', 'target_refresh', 'learner_priority')


def require(value, message):
    if not value:
        raise ValueError(message)


def parse_wire(raw):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_WIRE_BYTES,
            'Missing, empty or oversized API response')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate API object key')
            result[key] = value
        return result
    # Python's HTTP producer emits nonfinite diagnostic floats. Preserve its
    # received bytes; parsing these floats does not assert they are healthy.
    value = json.loads(raw, object_pairs_hook=unique)
    require(type(value) is dict, 'API response must be an object')
    return value


def project_api(api):
    result = {key: copy.deepcopy(api[key]) for key in TOP_FIELDS}
    pipe = api['host_pipeline']
    result['host_pipeline'] = {key: copy.deepcopy(pipe[key])
                              for key in ('schema', 'available', 'generation')}
    for kind in ERROR_KINDS:
        result['host_pipeline'][kind] = dict(errors=pipe[kind]['errors'])
    result['host_pipeline']['learning_exposure'] = copy.deepcopy(pipe['learning_exposure'])
    result['bank_persistence'] = dict(write_failures=api['bank_persistence']['write_failures'])
    return result


def nonfinite_paths(value):
    result = []
    def visit(item, path, depth):
        require(depth <= 64, 'API nesting exceeds witness bound')
        if isinstance(item, float) and not math.isfinite(item):
            kind = 'nan' if math.isnan(item) else 'positive_infinity' if item > 0 else 'negative_infinity'
            result.append(dict(path=path, kind=kind))
        elif isinstance(item, dict):
            for key, child in item.items():
                visit(child, path + [key], depth + 1)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, path + [index], depth + 1)
    visit(value, [], 0)
    return result


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def witness_fields(api, raw_pin):
    projection = project_api(api)
    canonical(projection)  # Critical nonfinite values cannot enter accepted metadata.
    return dict(API=projection, API_wire=copy.deepcopy(raw_pin),
                API_witness_format=FORMAT, API_nonfinite_paths=nonfinite_paths(api))


def rejoin_witness(sample, read_wire):
    require(sample.get('API_witness_format') == FORMAT, 'Missing exact raw API witness format')
    raw = read_wire(sample['API_wire'])
    api = parse_wire(raw)
    require(canonical(sample['API']) == canonical(project_api(api)),
            'Stored critical projection differs from original API response')
    require(sample['API_nonfinite_paths'] == nonfinite_paths(api),
            'Nonfinite diagnostics differ from original API response')
    return api
