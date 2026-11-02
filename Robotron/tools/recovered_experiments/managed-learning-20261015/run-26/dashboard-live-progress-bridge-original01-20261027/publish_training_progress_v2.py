"""Display-only bridge for the already loaded training report; default inert.

Reads canonical activity and closed seals. Writes only this UI directory.
It never changes canonical state, sources, training, jobs, processes or controls.
Active unknown game counts are omitted rather than displayed as zero.
"""
import argparse
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
STATE = HERE.parent.parent/'state.json'
STUDY = HERE.parent/'deadline-score32-fixed-fleet-admission-original03-preparation-20261026/fixed-RCRC-deadline32-study-original03'
ORDER = ('R1', 'C1', 'R2', 'C2')


def read(path, limit=2_000_000):
    with Path(path).open('rb') as f:
        raw = f.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Display input too large')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError('Display object required')
    return value


def put(name, value):
    # Fixed own-directory basenames only; no canonical/source destination.
    if '/' in name or name.startswith('.'):
        raise ValueError('Own display filename required')
    path = HERE/name
    temp = HERE/(name + '.next')
    with temp.open('w') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
    os.replace(temp, path)


def publish_once():
    now = time.time()
    state = read(STATE)
    goal = state.get('optimization_goal') or {}
    active = goal.get('active_deadline_score_job') or state.get('active_deadline_score_job') or {}
    validation = goal.get('active_readonly_validation_job') or state.get('active_readonly_validation_job') or {}
    leg = active.get('leg') or 'C2'
    if leg not in ORDER:
        leg = 'C2'
    qualified = {name: (STUDY/name/('root-' + name + '-independent-qualified.json')).exists() for name in ORDER}
    native = {}
    status_path = STUDY/leg/'deadline-output-original01/status.json'
    if status_path.exists():
        native = read(status_path)
    anchor = native.get('anchor') or {}
    deadline = active.get('deadline_monotonic_ns') or anchor.get('deadline_monotonic_ns')
    remaining = max(0, (deadline - time.monotonic_ns()) / 1e9) if isinstance(deadline, int) else None
    end_wall = now + remaining if remaining is not None else None
    audit_state = str(validation.get('status', '')).upper()
    audit_running = bool(validation) and not any(word in audit_state for word in ('CLOSED', 'QUALIFIED', 'FINISHED', 'FAILED'))
    native_closed = active.get('native_closed') is True or active.get('tool_terminal_exit') == 0
    if all(qualified.values()):
        phase = 'All4 fixed-cutoff legs audited; final comparison pending'
        wait = 'ROOT comparison verdict and owned preview preparation'
        eta = 'Preview timing pending the verdict; no firm start time yet'
        short = 'All4 legs audited; final verdict pending'
    elif qualified.get(leg):
        phase = leg + ' audited; preparing the next leg'
        wait = 'Fresh readiness and ROOT launch of C2'
        eta = 'C2 needs60min after all32 start, then audit up to10min'
        short = 'C2 readiness; about60–75min after launch'
    elif native_closed:
        phase = leg + (' independent audit running' if audit_running else ' sealed; waiting for independent audit')
        wait = 'Independent raw/source/ownership audit and its closed CPU scope'
        eta = 'Audit budget up to10min; cleanup may add a short delay'
        short = leg + ' audit; budget up to10min'
    elif remaining is not None:
        stamp = time.strftime('%H:%M UTC', time.gmtime(end_wall))
        minutes = max(0, int((remaining + 59) // 60))
        phase = leg + ' running all32 first games at a fixed60min cutoff'
        wait = 'Fixed deadline; unfinished game scores are retained at cutoff'
        eta = stamp + ' cutoff (~' + str(minutes) + 'min); audit then up to10min'
        short = leg + ' (4/4) running; cutoff ' + stamp + ' (~' + str(minutes) + 'min)'
    else:
        phase = leg + ' startup active'
        wait = 'All32 certified first-play/startup prefixes and common start'
        eta = 'About60–75min from common start including audit; precise cutoff follows startup'
        short = leg + ' (4/4) starting;60min begins after all32 ready'
    # ROOT may advance the display after the fixed series without changing
    # evaluation/training controls or rewriting this publisher.
    override = goal.get('dashboard_progress') or {}
    if not isinstance(override, dict):
        override = {}
    for key, current in (('current_stage', phase), ('waiting_for', wait), ('eta', eta)):
        value = override.get(key)
        if isinstance(value, str) and value.strip():
            if key == 'current_stage': phase = value.strip()
            elif key == 'waiting_for': wait = value.strip()
            else: eta = value.strip()
    if override:
        display_deadline = override.get('deadline_monotonic_ns')
        remaining = max(0, (display_deadline - time.monotonic_ns()) / 1e9) if type(display_deadline) is int else None
        end_wall = now + remaining if remaining is not None else None
        short = phase + '. ' + eta
    elif native_closed or all(qualified.values()):
        remaining, end_wall = None, None
    first_label = ('NOW: ' + short + ('. Main training continues.' if override else '. Training continues; live counts unknown until seal.'))[:160]
    next_label = 'NEXT: C2 audit up to10min, then30FPS preview trial BEFORE learning tweaks. Cards count naturally completed games only.'
    if all(qualified.values()):
        next_label = 'NEXT:30FPS preview trial BEFORE learning tweaks; final comparison verdict first. Cards count naturally completed games only.'
    default_next = '30FPS preview trial after C2 audit/verdict, BEFORE learning tweaks.'
    display_next = override.get('next_stage')
    if not isinstance(display_next, str) or not display_next.strip():
        display_next = default_next
    if override:
        next_label = ('NEXT: ' + display_next.strip())[:160]
    legs = []
    summaries = []
    for index, name in enumerate(ORDER, 1):
        path = STUDY/name/'deadline-output-original01/original-deadline-score-seal.json'
        # An active/missing count is not0. Only closed known legs get legacy cards.
        known_closed = qualified[name] or (name == leg and native_closed)
        if not path.exists() or not known_closed:
            continue
        seal = read(path)
        completed = [row for row in seal['rows'] if row['status'] == 'completed']
        count = seal['n_completed']
        if type(count) is not int or len(completed) != count:
            raise ValueError('Natural completion count differs')
        receipt = dict(label=next_label if name.startswith('C') else first_label,
            phase='sealed', count=count, started=seal['n_scored'], pending=0,
            complete=True, valid=True if qualified[name] else None,
            source_leg=name, n_scored=seal['n_scored'], n_completed=count,
            n_censored=seal['n_censored'], source_seal=str(path),
            metric='Legacy card count/mean refer only to naturally completed first games; fixed-cutoff metric is separate.')
        if completed:
            receipt['mean'] = sum(row['score_at_deadline'] for row in completed) / count
        put(name + '-display.json', receipt)
        legs.append(dict(index=index, role='candidate' if name.startswith('C') else 'reference',
                         receipt_path=name + '-display.json'))
        summaries.append(dict(leg=name, audited=qualified[name], n_scored=seal['n_scored'],
            n_completed=count, n_censored=seal['n_censored'],
            fixed_cutoff_mean=seal['mean_score'], fixed_cutoff_median=seal['median_score']))
    put('plan.json', dict(schema='read-only-dashboard-display-bridge-v1', legs=legs,
        scientific_order=list(ORDER), display_scope='Only closed known legs have legacy cards; active unknown counts are omitted. Header carries current phase.'))
    put('status.json', dict(state='running', current_leg=max((v['index'] for v in legs), default=1),
        updated_unix_s=now, legs=[dict(index=v['index'], state='finished') for v in legs],
        reason=phase + '. ' + wait + '. ' + eta,
        scientific_current_leg=leg, active_counts_known=native_closed))
    progress = dict(schema='training-progress-display-v1', updated_unix_s=now,
        current_stage=phase, waiting_for=wait, eta=eta, cutoff_estimated_unix_s=end_wall,
        remaining_s=remaining, next_stage=display_next.strip(),
        main_training='Continues unchanged', scientific_current_leg=leg, scientific_total_legs=4,
        known_closed_legs=summaries, active_counts_known=native_closed,
        ui_legacy_note='Legacy cohort suffix counts displayed closed cards; header states actual scientific stage. Legacy means cover natural completions only.',
        display_only=True, canonical_state_modified=False)
    put('progress.json', progress)
    return dict(current_stage=phase, eta=eta, updated_unix_s=now, directory=str(HERE))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--publish-once', action='store_true')
    p.add_argument('--watch', action='store_true')
    p.add_argument('--interval', type=float, default=10)
    a = p.parse_args()
    if not a.publish_once and not a.watch:
        print('PLAN_ONLY: no display reads/writes or actions')
        return
    if not 5 <= a.interval <= 30:
        raise ValueError('Display interval must be5–30seconds')
    while True:
        try:
            print(json.dumps(publish_once()), flush=True)
        except (OSError, ValueError, KeyError, TypeError) as error:
            put('publisher-error.json', dict(updated_unix_s=time.time(), error=str(error),
                last_good_display_retained=True, canonical_state_modified=False))
            print(json.dumps(dict(display_error=str(error))), flush=True)
            if not a.watch:
                raise
        if not a.watch:
            return
        time.sleep(a.interval)


if __name__ == '__main__':
    main()
