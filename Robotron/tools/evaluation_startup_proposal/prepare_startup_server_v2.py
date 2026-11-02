"""Add diagnostic hooks to a separate exact source copy, preserving operational AST."""
import ast
import hashlib

SOURCE_SHA = '84901c887437e99873d65c2348f18ca9e2f022a393f3c5282d68064c9f1fbf40'
IMPORT = 'import startup_server_prefix_v2 as _startup_prefix\n'


def stripped_tree(source):
    class Strip(ast.NodeTransformer):
        def visit_Import(self, node):
            if any(x.name == 'startup_server_prefix_v2' and x.asname == '_startup_prefix' for x in node.names):
                return None
            return node

        def visit_Expr(self, node):
            value = node.value
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                    and isinstance(value.func.value, ast.Name) and value.func.value.id == '_startup_prefix'
                    and value.func.attr == 'notify'):
                return None
            return self.generic_visit(node)

        def visit_Call(self, node):
            if (isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == '_startup_prefix' and node.func.attr == 'send'):
                if len(node.args) != 4 or node.keywords:
                    raise ValueError('Malformed diagnostic send wrapper')
                _, sock, _, payload = node.args
                return ast.copy_location(ast.Call(func=ast.Attribute(value=sock,attr='sendall',ctx=ast.Load()),
                                                  args=[self.visit(payload)],keywords=[]),node)
            return self.generic_visit(node)
    return ast.dump(Strip().visit(ast.parse(source)), include_attributes=False)


def build(source):
    if hashlib.sha256(source.encode()).hexdigest() != SOURCE_SHA:
        raise ValueError('Exact original socket source SHA required')
    original = source
    def once(before, after, count=1):
        nonlocal source
        if source.count(before) != count:
            raise ValueError('Exact diagnostic source anchor differs: ' + before[:60])
        source = source.replace(before, after)
    once('import os, sys, time, socket, select, struct, threading, traceback, random, queue\n',
         IMPORT + 'import os, sys, time, socket, select, struct, threading, traceback, random, queue\n')
    once('            BATCH = 8\n            last_payload_time = time.time()\n',
         '            _startup_prefix.notify(self, "connect", cid, client_slot)\n'
         '            BATCH = 8\n            last_payload_time = time.time()\n')
    once('                last_payload_time = time.time()\n                self._rejected_gaps.event("received", _gap_connection)\n',
         '                last_payload_time = time.time()\n'
         '                _startup_prefix.notify(self, "received", cid, data)\n'
         '                self._rejected_gaps.event("received", _gap_connection)\n')
    once('                    cs["frames"] += 1\n',
         '                    cs["frames"] += 1\n'
         '                    _startup_prefix.notify(self, "accepted", cid, cs["frames"])\n')
    once('sock.sendall(self._pack_action(', '_startup_prefix.send(self, sock, cid, self._pack_action(', count=5)
    once('            self._rejected_gaps.event("disconnect", _gap_connection)\n',
         '            _startup_prefix.notify(self, "disconnect", cid)\n'
         '            self._rejected_gaps.event("disconnect", _gap_connection)\n')
    compile(source, '<isolated-startup-server-copy>', 'exec')
    if stripped_tree(source) != ast.dump(ast.parse(original), include_attributes=False):
        raise ValueError('Operational socket AST differs after removing diagnostics')
    return source
