"""Create an unapplied opt-in transport filter; no live source or socket changes."""
import ast
import difflib
import hashlib
import json
import os
from pathlib import Path

G = Path('/home/dave/source/repos/ArcadeAI/Robotron')
P = Path(__file__).resolve().parent
SOURCE = G/'Scripts/dqn/socket_server.py'

PARSER = '''def _parse_allowed_training_peers(raw):
    """Optional exact IPv4 peers for a managed training listener."""
    if raw is None or not raw.strip():
        return None
    if len(raw) > 512:
        raise ValueError("Training peer list is too long")
    parts = raw.split(",")
    if len(parts) > 16 or any(not part.strip() for part in parts):
        raise ValueError("Training peers require 1..16 explicit IPv4 addresses")
    peers = frozenset(ipaddress.ip_address(part.strip()) for part in parts)
    if any(not isinstance(peer, ipaddress.IPv4Address) or peer.is_unspecified
           or peer.is_multicast or int(peer) == 0xFFFFFFFF for peer in peers):
        raise ValueError("Training peers require explicit unicast IPv4 addresses")
    return peers


'''

METHOD = '''    def _admit_training_peer(self, sock, address):
        """Reject unselected training peers before allocating any client state."""
        if not self.replay_enabled or self._allowed_training_peers is None:
            return True
        try:
            allowed = ipaddress.ip_address(address[0]) in self._allowed_training_peers
        except (ValueError, TypeError, IndexError):
            allowed = False
        if allowed:
            return True
        try:
            sock.close()
        except OSError:
            pass
        now = time.monotonic()
        if now - self._last_peer_rejection_log >= 5.0:
            self._last_peer_rejection_log = now
            print(f"[ADMISSION] rejected unselected training peer {address[0]}", flush=True)
        return False

'''


def write(path, raw):
    with path.open('x') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), 0o444); os.fsync(stream.fileno())


def main():
    original = SOURCE.read_text()
    replacements = [
        ('import numpy as np\n', 'import numpy as np\nimport ipaddress\n'),
        ('class SocketServer:\n', PARSER + 'class SocketServer:\n'),
        ('    def __init__(self, host, port, agent, metrics_wrapper=None, *, replay_enabled=True):\n',
         '    def __init__(self, host, port, agent, metrics_wrapper=None, *, replay_enabled=True):\n'
         '        self._allowed_training_peers = (_parse_allowed_training_peers(\n'
         '            os.getenv("ROBOTRON_ALLOWED_TRAINING_PEERS")) if replay_enabled else None)\n'
         '        self._last_peer_rejection_log = 0.0\n'),
        ('    def start(self):\n        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n',
         METHOD + '    def start(self):\n        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n'),
        ('                    cid = self._alloc_id()\n',
         '                    if not self._admit_training_peer(cs, addr):\n'
         '                        continue\n'
         '                    cid = self._alloc_id()\n')]
    candidate = original
    for old, new in replacements:
        assert candidate.count(old) == 1
        candidate = candidate.replace(old, new)
    reverse = candidate
    for old, new in reversed(replacements):
        assert reverse.count(new) == 1
        reverse = reverse.replace(new, old)
    assert reverse == original
    original_ast, candidate_ast = ast.parse(original), ast.parse(candidate)
    def methods(tree):
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SocketServer')
        return {n.name: ast.dump(n, include_attributes=False) for n in cls.body if isinstance(n, ast.FunctionDef)}
    before, after = methods(original_ast), methods(candidate_ast)
    assert [name for name in before if before[name] != after[name]] == ['__init__', 'start']
    assert set(after)-set(before) == {'_admit_training_peer'}
    write(P/'original-socket-server.readonly.txt', original)
    write(P/'socket_server_candidate.py', candidate)
    write(P/'unapplied.patch', ''.join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True),
        fromfile='a/Robotron/Scripts/dqn/socket_server.py', tofile='b/Robotron/Scripts/dqn/socket_server.py')))
    write(P/'source-binding.json', json.dumps(dict(original_source=str(SOURCE),
        original_sha256=hashlib.sha256(original.encode()).hexdigest(),
        candidate_source=str(P/'socket_server_candidate.py'), candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest(),
        default_behavior_unchanged=True, activation_requires_future_owned_main_handoff=True,
        proposed_managed_peer_list='127.0.0.1,192.168.1.131',
        inference_only_servers_exempt=True, replaces_runtime_validity_checks=False,
        existing_remote_client_touched=False, active_source_changed=False,
        source_replacements=replacements), separators=(',', ':'), allow_nan=False)+'\n')
    assert SOURCE.read_text() == original
    print(json.dumps(dict(prepared=True, applied=False, original_sha256=hashlib.sha256(original.encode()).hexdigest(),
                          candidate_sha256=hashlib.sha256(candidate.encode()).hexdigest())))


if __name__ == '__main__':
    main()
