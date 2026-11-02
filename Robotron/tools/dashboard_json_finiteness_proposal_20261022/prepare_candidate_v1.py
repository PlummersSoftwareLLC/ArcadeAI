"""Build an unapplied dashboard-only JSON fix from the held production source."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
SOURCE = P.parents[1]/'Scripts/dqn/metrics_dashboard.py'

HELPER = '''def _json_safe_diagnostic_snapshot(snapshot):
    """Keep a nonfinite optional gradient diagnostic explicit in valid JSON.

    All other fields are left intact for strict serialization and health checks.
    The source snapshot and numerical training metrics are never mutated.
    """
    value = snapshot.get("grad_norm")
    if isinstance(value, float) and not math.isfinite(value):
        snapshot = dict(snapshot)
        snapshot["grad_norm"] = None
        snapshot["grad_norm_nonfinite"] = (
            "nan" if math.isnan(value) else
            "positive_infinity" if value > 0 else "negative_infinity"
        )
    return snapshot


'''


def build(source):
    def replace(old, new, count=1):
        nonlocal source
        if source.count(old) != count:
            raise ValueError('Exact held source fragment differs: '+old[:70])
        source = source.replace(old, new)

    replace('def _tail_mean(', HELPER+'def _tail_mean(')
    replace('        snap = self._build_snapshot()\n        with self.lock:', '''        try:
            snap = _json_safe_diagnostic_snapshot(self._build_snapshot())
            body = json.dumps(snap, allow_nan=False).encode("utf-8")
        except (TypeError, ValueError):
            # Do not serve a previous healthy snapshot as the failed new one.
            failure = {"ts": time.time(), "snapshot_error": "Metric snapshot is not valid finite JSON"}
            with self.lock:
                self.latest = failure
                self._cached_now_body = json.dumps(failure, allow_nan=False).encode("utf-8")
            raise
        with self.lock:''')
    replace('json.dumps(snap).encode("utf-8")', 'body', 2)
    replace('    function fmtPaddedFloat(', '''    function chartNumber(value) {
      return value === null || value === undefined ? NaN : Number(value);
    }

    function fmtPaddedFloat(''')
    replace('''    function fmtPaddedFloat(v, intDigits = 2, decDigits = 2, padChar = "0") {
      if (v === null || v === undefined || Number.isNaN(v)) return "0";''',
        '''    function fmtPaddedFloat(v, intDigits = 2, decDigits = 2, padChar = "0") {
      if (v === null || v === undefined || !Number.isFinite(Number(v))) return "--";''')
    for old in ['Number(row[s.key])', 'Number(points[j][s.key])', 'Number(points[i][s.key])',
                'Number(row[key])', 'Number(rowStart[key])']:
        replace(old, 'chartNumber('+old[len('Number('):])
    replace('''        const readVal = mw >= 3
          ? (i) => medianNeighbors(i, n, mw, (j) => chartNumber(points[j][s.key]))
          : (i) => chartNumber(points[i][s.key]);''', '''        const readVal = (i) => {
          const value = chartNumber(points[i][s.key]);
          if (!Number.isFinite(value)) return NaN;
          return mw >= 3
            ? medianNeighbors(i, n, mw, (j) => chartNumber(points[j][s.key]))
            : value;
        };''')
    replace('          const avg = counts[k] > 0 ?', '''          if (!Number.isFinite(vNow)) {
            nextRow[key] = null;
            continue;
          }
          const avg = counts[k] > 0 ?''')
    replace('        const now = await res.json();\n        latestNow = now;',
        '        const now = await res.json();\n        if (now && now.snapshot_error) throw new Error(now.snapshot_error);\n        latestNow = now;')
    replace('        const now = payload && payload.now ? payload.now : null;\n        const history',
        '        const now = payload && payload.now ? payload.now : null;\n        if (now && now.snapshot_error) throw new Error(now.snapshot_error);\n        const history')
    ast.parse(source)
    return source


if __name__ == '__main__':
    original = SOURCE.read_text()
    candidate = build(original)
    target = P/'metrics_dashboard_candidate_v1.py'
    with target.open('x') as stream:
        stream.write(candidate)
    with (P/'unapplied-json-diagnostic.patch').open('x') as stream:
        stream.write(''.join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True),
            fromfile='a/Robotron/Scripts/dqn/metrics_dashboard.py',
            tofile='b/Robotron/Scripts/dqn/metrics_dashboard.py')))
    print(json.dumps(dict(source_sha256=hashlib.sha256(original.encode()).hexdigest(),
        candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(), applied=False)))
