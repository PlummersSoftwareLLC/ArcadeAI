"""Root-only pure AST formatter checks; no publisher import or runtime actions."""
import argparse
import ast
import copy
import hashlib
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--source-sha256", required=True)
    a = p.parse_args()
    raw = a.source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == a.source_sha256
    nodes = [n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name == "format_score_screen_work"]
    assert len(nodes) == 1
    ns = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<actual-pure-formatter>", "exec"), ns)
    format_work = ns["format_score_screen_work"]
    scope = "Frozen S2 versus protected b231; exploratory screen only, no automatic promotion"
    base = dict(state="score_screen_running", current_stage="Score screen R1: 0/32 first games complete",
        detail="Reference mean 5.524M; candidate mean 6.331M.", waiting_for="Fixed cutoff",
        next_stage="Review", eta="Cutoff 8:56:23 PM CDT", updated_unix_s=123.,
        observation_unix_s=123., score_screen=dict(leg="R1", policy_scope=scope,
        counts=dict(n_scored=32, n_completed=0, n_emulators_active=32)))
    original = copy.deepcopy(base)
    r = format_work(base)
    assert r["current_stage"] == "Protected reference (b231): 32 first-game scores tracked · 0 finished · 32 playing"
    assert r["detail"].endswith("First completed comparison: " + base["detail"])
    assert base == original and {k:v for k,v in r.items() if k not in ("current_stage", "detail")} == {k:v for k,v in base.items() if k not in ("current_stage", "detail")}
    assert format_work(r) == r
    candidate = copy.deepcopy(base)
    candidate["score_screen"].update(leg="C1", counts=dict(n_scored=32, n_completed=1, n_emulators_active=31))
    assert format_work(candidate)["current_stage"] == "Frozen candidate (S2): 32 first-game scores tracked · 1 finished · 31 playing"
    rejected = 0
    for key in ("n_scored", "n_completed", "n_emulators_active"):
        for value in ("32", True, None, 0.5, -1, 33):
            bad = copy.deepcopy(base); bad["score_screen"]["counts"][key] = value
            assert format_work(bad) == bad; rejected += 1
    for field, value in (("policy_scope", "other"), ("leg", "R2"), ("counts", None)):
        bad = copy.deepcopy(base); bad["score_screen"][field] = value
        assert format_work(bad) == bad; rejected += 1
    for state in ("score_screen_review", "failed", "completed"):
        bad = dict(base, state=state); assert format_work(bad) == bad; rejected += 1
    stale = dict(base, updated_unix_s=1., observation_unix_s=1.)
    formatted = format_work(stale)
    assert formatted["updated_unix_s"] == formatted["observation_unix_s"] == 1.
    assert formatted["eta"] == stale["eta"] and formatted["waiting_for"] == stale["waiting_for"]
    print(f"PASS: reference/candidate, {rejected} typed/scope/state rejections, metadata clocks/ETA unchanged; no publisher imported")


if __name__ == "__main__":
    main()
