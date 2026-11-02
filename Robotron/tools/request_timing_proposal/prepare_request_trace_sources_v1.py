"""Build isolated instrumented copies from exact source; never launch/import them."""
import ast
import hashlib
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
EXPECTED = {
    'socket_server.py': '84901c887437e99873d65c2348f18ca9e2f022a393f3c5282d68064c9f1fbf40',
    'agent.py': '865a0df717b39951b7f7c516e4a962e3d48cf4d3dc11295ff266e58653e6c74b',
}


def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Exact unique source anchor required: ' + repr(before))
    return source.replace(before, after, 1)


def instrument(name, source):
    if hashlib.sha256(source.encode()).hexdigest() != EXPECTED[name]:
        raise ValueError('Pinned source hash differs')
    # Keep all imports and operational code in the copies; compile, never exec
    # the complete module. Tests extract only the two inert batcher classes.
    tree = ast.parse(source)
    first = next(n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))
                 and not (isinstance(n, ast.ImportFrom) and n.module == '__future__'))
    lines = source.splitlines(keepends=True)
    lines.insert(first.lineno - 1, 'import request_phase_trace_v1 as _request_trace\n')
    source = ''.join(lines)
    if name == 'socket_server.py':
        pairs = [
          ('"cancelled", "error")', '"cancelled", "error", "trace")'),
          ('        self.error = None\n', '        self.error = None\n        self.trace = _request_trace.new_request()\n'),
          ('            self.queue.put(req, timeout=', '            _request_trace.mark(req.trace, "enqueue_attempt")\n            self.queue.put(req, timeout='),
          ('        except queue.Full as exc:\n', '            _request_trace.mark(req.trace, "enqueue_return")\n        except queue.Full as exc:\n            _request_trace.mark(req.trace, "queue_full")\n'),
          ('            # Cancellation can skip queued work,', '            _request_trace.mark(req.trace, "wait_timeout")\n            # Cancellation can skip queued work,'),
          ('                req.cancelled = True\n            raise TimeoutError("Batched', '                req.cancelled = True\n                _request_trace.mark(req.trace, "cancelled")\n            raise TimeoutError("Batched'),
          ('        with self._request_lock:\n            error, action = req.error, req.action', '        _request_trace.mark(req.trace, "waiter_awake")\n        with self._request_lock:\n            error, action = req.error, req.action'),
          ('        if error is not None:\n            raise RuntimeError(error)', '        if error is not None:\n            _request_trace.mark(req.trace, "returned_error")\n            raise RuntimeError(error)'),
          ('            raise RuntimeError("Inference completed without an action")', '            _request_trace.mark(req.trace, "missing_action")\n            raise RuntimeError("Inference completed without an action")'),
          ('        return action\n\n    def _finish', '        _request_trace.mark(req.trace, "returned")\n        return action\n\n    def _finish'),
          ('                if req.cancelled:\n                    continue', '                if req.cancelled:\n                    _request_trace.mark(req.trace, "finish_cancelled")\n                    continue'),
          ('                req.event.set()\n\n    def _consume', '                _request_trace.mark(req.trace, "signal_before")\n                req.event.set()\n\n    def _consume'),
          ('                first = self.queue.get(timeout=0.01)', '                first = self.queue.get(timeout=0.01)\n                _request_trace.mark(first.trace, "dequeued")'),
          ('                    batch.append(self.queue.get(timeout=remaining))', '                    batch.append(self.queue.get(timeout=remaining))\n                    _request_trace.mark(batch[-1].trace, "dequeued")'),
          ('                states = [r.state for r in batch]', '                _request_trace.batch_begin([r.trace for r in batch])\n                _request_trace.batch_mark("coalescing_end")\n                states = [r.state for r in batch]'),
          ('                actions = self.agent.act_batch(states, epsilons, locked_fires=locked_fires)', '                _request_trace.batch_mark("act_begin")\n                actions = self.agent.act_batch(states, epsilons, locked_fires=locked_fires)\n                _request_trace.batch_mark("act_end")'),
          ('                error = f"Batched inference failed', '                _request_trace.batch_mark("dispatch_error")\n                _request_trace.batch_end()\n                error = f"Batched inference failed'),
          ('            self._finish(batch, actions=actions)', '            _request_trace.batch_mark("validation_end")\n            _request_trace.batch_end()\n            self._finish(batch, actions=actions)'),
          ('                req.error = "Inference batcher stopped before completion"', '                _request_trace.mark(req.trace, "stop_cancel")\n                req.error = "Inference batcher stopped before completion"\n                _request_trace.mark(req.trace, "signal_before")'),
          ('            req.error = "Inference batcher stopped before dispatch"', '            _request_trace.mark(req.trace, "stop_queue_signal")\n            req.error = "Inference batcher stopped before dispatch"'),
        ]
    else:
        # Restrict replacements to act_batch: similarly named greedy code in
        # solo act() and warmup is outside this request timing scope.
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == 'act_batch')
        lines = source.splitlines(keepends=True)
        prefix, source, suffix = ''.join(lines[:node.lineno-1]), ''.join(lines[node.lineno-1:node.end_lineno]), ''.join(lines[node.end_lineno:])
        pairs = [
          ('        for i in range(n):', '        _request_trace.batch_mark("epsilon_begin")\n        for i in range(n):'),
          ('        if greedy_idx:', '        _request_trace.batch_mark("epsilon_end")\n        if greedy_idx:\n            _request_trace.batch_mark("state_pack_begin")'),
          ('            joint_q = self._infer_q_joint(st, return_cpu=True)', '            _request_trace.batch_mark("state_pack_end")\n            _request_trace.batch_mark("model_begin")\n            joint_q = self._infer_q_joint(st, return_cpu=True)\n            _request_trace.batch_mark("model_end")\n            _request_trace.batch_mark("reduce_begin")'),
          ('        return [a if a is not None', '            _request_trace.batch_mark("reduce_end")\n\n        return [a if a is not None'),
        ]
    for before, after in pairs:
        source = once(source, before, after)
    if name == 'agent.py':
        source = prefix + source + suffix
    compile(source, name, 'exec')
    return source


def stripped_tree(source):
    """Remove diagnostic-only additions; require original operational AST."""
    class Strip(ast.NodeTransformer):
        def visit_Import(self, node):
            return None if any(a.asname == '_request_trace' for a in node.names) else node
        def visit_Expr(self, node):
            call = node.value
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name) and call.func.value.id == '_request_trace':
                return None
            return self.generic_visit(node)
        def visit_Assign(self, node):
            if any(isinstance(t, ast.Attribute) and t.attr == 'trace' for t in node.targets):
                return None
            if any(isinstance(t, ast.Name) and t.id == '__slots__' for t in node.targets):
                node.value.elts = [n for n in node.value.elts if not (isinstance(n, ast.Constant) and n.value == 'trace')]
            return self.generic_visit(node)
    return ast.dump(Strip().visit(ast.parse(source)), include_attributes=False)
