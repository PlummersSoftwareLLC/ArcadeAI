"""Construct matched-scope source strings only; never import or deploy them."""
import ast
import hashlib
import importlib.util
from pathlib import Path

H=Path(__file__).resolve().parent
OLD_BUILDER_SHA='a31fbfdb3f30ad4bbe3136cecc329054621091b3b49af4af609e6c50411aa6ad'
EXPOSURE_SHA='30d9191e9fc845d80e52a7a891244fcf0c7041cf60529f6559b15e6d47ac5c7f'


def old_builder():
    path=H/'prepare_request_trace_sources_v1.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=OLD_BUILDER_SHA:
        raise ValueError('Exact earlier isolated source builder required')
    spec=importlib.util.spec_from_file_location('_matched_scope_old_builder',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def method(source,name,owner=None):
    tree=ast.parse(source)
    if owner is not None:
        tree=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==owner)
    return next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)


def replace_lines(source,start,end,lines):
    all_lines=source.splitlines(keepends=True)
    all_lines[start-1:end]=lines
    return ''.join(all_lines)


def wrap_method(source,name,scope,owner=None):
    node=method(source,name,owner);lines=source.splitlines(keepends=True)
    start=node.body[0].lineno;indent=' '*(node.col_offset+4)
    return replace_lines(source,start,node.end_lineno,
        [indent+'with '+scope+':\n']+['    '+s if s.strip() else s for s in lines[start-1:node.end_lineno]])


def socket_source(source):
    old=old_builder();source=old.instrument('socket_server.py',source)
    source=old.once(source,'import request_phase_trace_v1 as _request_trace',
        'import matched_frame_trace_v1 as _request_trace')
    pairs=[
      ('                self._rejected_gaps.event("received", _gap_connection)',
       '                self._rejected_gaps.event("received", _gap_connection)\n                _request_trace.frame_mark("payload_complete")'),
      ('                frame = parse_frame_data(data, parse_preview=should_parse_preview)',
       '                _request_trace.frame_mark("parse_begin")\n                frame = parse_frame_data(data, parse_preview=should_parse_preview)\n                _request_trace.frame_mark("parse_end")'),
      ('                    _gap_ticket = self._rejected_gaps.event("accepted",',
       '                    _request_trace.frame_mark("accepted_frame")\n                    _gap_ticket = self._rejected_gaps.event("accepted",'),
      ('                        t0 = time.perf_counter()\n                        if self.inference_batcher is not None:',
       '                        _request_trace.frame_mark("inference_wait_begin")\n                        t0 = time.perf_counter()\n                        if self.inference_batcher is not None:'),
      ('                        metrics.add_inference_time(time.perf_counter() - t0)',
       '                        metrics.add_inference_time(time.perf_counter() - t0)\n                        _request_trace.frame_mark("inference_wait_end")'),
      ('                self._rejected_gaps.event("finish", _gap_ticket, outcome="accepted_action_write_completed")',
       '                self._rejected_gaps.event("finish", _gap_ticket, outcome="accepted_action_write_completed")\n                _request_trace.frame_mark("action_write_completed")'),
    ]
    for before,after in pairs:source=old.once(source,before,after)
    # One frame scope per handler loop iteration, including all original
    # continue/break/raise paths. Handshake work remains outside the frame span.
    handler=method(source,'handle_client','SocketServer')
    loop=next(n for n in ast.walk(handler) if isinstance(n,ast.While)
              and ast.unparse(n.test)=='self.running and (not self.shutdown_event.is_set())')
    lines=source.splitlines(keepends=True);indent=' '*loop.col_offset
    source=replace_lines(source,loop.lineno,loop.end_lineno,[
        indent+'_host_trace_connection = _request_trace.connection(cid, client_slot)\n',
        lines[loop.lineno-1],indent+'    with _request_trace.frame(_host_trace_connection):\n',
    ]+['    '+s if s.strip() else s for s in lines[loop.lineno:loop.end_lineno]])
    # Preserve the exact put/backpressure loop and publish only after a put
    # actually returns. A stopped producer never receives the admitted stamp.
    source=old.once(source,'                self.queue.put(item, timeout=0.1)\n                return',
        '                self.queue.put(item, timeout=0.1)\n                _request_trace.enqueue_succeeded(item)\n                return')
    source=wrap_method(source,'_enqueue_preserving','_request_trace.enqueue(item)','AsyncReplayBuffer')
    consume=method(source,'_consume','AsyncReplayBuffer')
    lines=source.splitlines(keepends=True)
    loop=next(n for n in ast.walk(consume) if isinstance(n,ast.For) and ast.unparse(n.iter)=='batch')
    indent=' '*loop.col_offset
    source=replace_lines(source,loop.lineno,loop.end_lineno,[
        indent+'for _host_trace_item in batch:\n',
        indent+'    with _request_trace.consume(_host_trace_item):\n',
        indent+'        cmd, cid, a, kw = _host_trace_item\n',
    ]+['    '+s if s.strip() else s for s in lines[loop.lineno:loop.end_lineno]])
    # These anchors are restricted to AsyncReplayBuffer so the inference
    # batcher's separate dequeue markers remain untouched.
    consume=method(source,'_consume','AsyncReplayBuffer');lines=source.splitlines(keepends=True)
    part=''.join(lines[consume.lineno-1:consume.end_lineno])
    part=old.once(part,'                item = self.queue.get(timeout=0.01)',
        '                item = self.queue.get(timeout=0.01)\n                _request_trace.dequeued(item)')
    part=old.once(part,'                    batch.append(self.queue.get_nowait())',
        '                    batch.append(self.queue.get_nowait())\n                    _request_trace.dequeued(batch[-1])')
    part=old.once(part,'                            idx = self.agent.step(*a, **kw)',
        '                            idx = self.agent.step(*a, **kw)\n                            _request_trace.consumer_mark("agent_step_returned")')
    part=old.once(part,'                        print(f"AsyncReplayBuffer error: {e}")',
        '                        _request_trace.consumer_mark("consumer_error")\n                        print(f"AsyncReplayBuffer error: {e}")')
    source=replace_lines(source,consume.lineno,consume.end_lineno,[part])
    # Stop's drain uses the same original get/unpack/dispatch operations. Keep
    # the actual item temporarily named so its diagnostic identity survives.
    stop=method(source,'stop','AsyncReplayBuffer');lines=source.splitlines(keepends=True)
    body=next(n for n in ast.walk(stop) if isinstance(n,ast.Try) and any(
        isinstance(s,ast.Assign) and isinstance(s.value,ast.Call)
        and ast.unparse(s.value)=='self.queue.get_nowait()' for s in n.body))
    start=body.body[0].lineno;end=body.body[-1].end_lineno;indent=' '*body.body[0].col_offset
    source=replace_lines(source,start,end,[
        indent+'_host_trace_item = self.queue.get_nowait()\n',
        indent+'_request_trace.dequeued(_host_trace_item)\n',
        indent+'with _request_trace.consume(_host_trace_item):\n',
        indent+'    cmd, cid, a, kw = _host_trace_item\n',
    ]+['    '+s if s.strip() else s for s in lines[start:end]])
    compile(source,'socket_server.py','exec');return source


def agent_source(source):
    old=old_builder();source=old.instrument('agent.py',source)
    return old.once(source,'import request_phase_trace_v1 as _request_trace',
        'import matched_frame_trace_v1 as _request_trace')


def exposure_source(source,expected_sha256):
    if expected_sha256!=EXPOSURE_SHA or hashlib.sha256(source.encode()).hexdigest()!=expected_sha256:
        raise ValueError('Exact exposure source required')
    old=old_builder();tree=ast.parse(source)
    first=next(n for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom)))
    lines=source.splitlines(keepends=True);lines.insert(first.lineno-1,
        'import matched_frame_trace_v1 as _request_trace\n')
    return old.once(''.join(lines),'        self.counts[category] += 1',
        '        self.counts[category] += 1\n        _request_trace.insert_accepted(self, category)')


def stripped_tree(source):
    class Strip(ast.NodeTransformer):
        def visit_With(self,node):
            node=self.generic_visit(node)
            if len(node.items)==1:
                call=node.items[0].context_expr
                if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id=='_request_trace':
                    return node.body
            return node
        def visit_Assign(self,node):
            if any(isinstance(t,ast.Name) and t.id=='_host_trace_connection' for t in node.targets):return None
            return self.generic_visit(node)
        def visit_For(self,node):
            node=self.generic_visit(node)
            if isinstance(node.target,ast.Name) and node.target.id=='_host_trace_item':
                assign=node.body[0]
                assert isinstance(assign,ast.Assign) and isinstance(assign.value,ast.Name) and assign.value.id=='_host_trace_item'
                node.target=assign.targets[0];node.body=node.body[1:]
            return node
        def visit_Try(self,node):
            node=self.generic_visit(node)
            # Fold the named diagnostic alias used by stop's original drain.
            if len(node.body)>=2 and isinstance(node.body[0],ast.Assign) and isinstance(node.body[1],ast.Assign):
                first,second=node.body[:2]
                if isinstance(first.targets[0],ast.Name) and first.targets[0].id=='_host_trace_item' and isinstance(second.value,ast.Name) and second.value.id=='_host_trace_item':
                    second.value=first.value;node.body=node.body[1:]
            return node
        def visit_Expr(self,node):
            call=node.value
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute) and isinstance(call.func.value,ast.Name) and call.func.value.id=='_request_trace':return None
            return self.generic_visit(node)
    tree=Strip().visit(ast.parse(source));return old_builder().stripped_tree(ast.unparse(tree))
