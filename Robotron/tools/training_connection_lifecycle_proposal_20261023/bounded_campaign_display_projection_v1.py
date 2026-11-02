"""Bounded display projection of an original, closed scientific sequence.

The sequence outcome is the existing small producer summary. The large original
assessment remains evidence; this display helper never opens its contents and
does not perform scientific qualification or policy promotion.
"""
import hashlib
import json
import os
from pathlib import Path

PROJECTION_MAX_BYTES = 1 << 20


def projection_metadata(path):
    value = path.stat()
    return dict(device=value.st_dev, inode=value.st_ino, bytes=value.st_size,
                mtime_ns=value.st_mtime_ns, ctime_ns=value.st_ctime_ns,
                mode=oct(value.st_mode & 0o777), uid=value.st_uid, nlink=value.st_nlink)


def projection_owned_file(path):
    return (path.is_absolute() and path.resolve() == path and path.is_file()
            and projection_metadata(path)['mode'] == '0o444'
            and projection_metadata(path)['uid'] == os.getuid()
            and projection_metadata(path)['nlink'] == 1)


def projection_read(path, pin=None):
    if not projection_owned_file(path):
        raise ValueError('Display requires an owned immutable original receipt')
    before = projection_metadata(path)
    if before['bytes'] > PROJECTION_MAX_BYTES:
        raise ValueError('Display summary exceeds the bounded receipt limit')
    if pin is not None and (pin['path'] != str(path) or pin['bytes'] != before['bytes']
                            or pin['identity'] != before):
        raise ValueError('Original receipt identity differs')
    raw = path.read_bytes()
    if len(raw) != before['bytes'] or projection_metadata(path) != before:
        raise ValueError('Original receipt changed while reading')
    if pin is not None and hashlib.sha256(raw).hexdigest() != pin['sha256']:
        raise ValueError('Original receipt digest differs')
    result = json.loads(raw)
    if type(result) is not dict:
        raise ValueError('Original receipt must be an object')
    return result


def project_campaign(root):
    """Return a terminal display projection, or None while evidence is pending.

    The complete assessment's identity is checked against the original closed
    outcome. Its contents are deliberately not rehashed or parsed every poll.
    Scientific validity remains the responsibility of the original assessor,
    sequencer and independent closeout, never this display-only projection.
    """
    try:
        outcome = projection_read(root / 'original-fresh-sequence-observer-original01-outcome.json')
        if outcome['schema'] != 'robotron-original-certified-quality32-sequence-outcome-v1':
            return None
        precommit = projection_read(root / 'original-fresh-sequence-precommit.json', outcome['precommit'])
        if precommit['schema'] != 'robotron-fresh-LR125-quality32-sequence-precommit-v1':
            return None
        if (type(outcome['original_attempts_per_leg']) is not int or outcome['original_attempts_per_leg'] != 1
                or outcome['no_retries'] is not True or outcome['existing_R1_adopted'] is not False
                or type(outcome['quality_qualified']) is not bool):
            return None
        if outcome['status'] in ('ORIGINAL_SEQUENCE_FAILURE_PRESERVED_NO_RETRY', 'SEQUENCING_STOPPED_NO_NEW_ACTIONS'):
            if outcome['quality_qualified'] is not False:
                return None
            return dict(state='failed', outcome='invalid',
                        reason=str(outcome.get('error') or outcome.get('reason') or 'Original sequence stopped; no retry')[:2000])
        if outcome['status'] != 'ORIGINAL_FOUR_LEG_CAMPAIGN_COMPLETE':
            return None
        controller = projection_read(root / 'campaign-assessment-controller-original-result.json',
                                     outcome['campaign_assessment']['result'])
        if type(controller['actual_exit']) is not int or controller['actual_exit'] != 0:
            return None
        if controller['closure'] != outcome['campaign_assessment']['closure']:
            return None
        closure = projection_read(root / 'campaign-assessment-execution-original01/root-original-result-and-owned-release.json',
                                  controller['closure'])
        if (type(closure['original_exit']) is not int or closure['original_exit'] != 0
                or closure['lifecycle_complete'] is not True or closure['unit_released'] is not True):
            return None
        report = root / 'independent-campaign-assessment-original01/assessment.json'
        pin = outcome['assessment_report']
        if (pin['path'] != str(report) or not projection_owned_file(report)
                or pin['bytes'] != report.stat().st_size or pin['identity'] != projection_metadata(report)):
            return None
        return dict(state='finished', outcome='qualified' if outcome['quality_qualified'] else 'not_improved', reason=None)
    except (OSError, ValueError, KeyError, TypeError):
        return None
