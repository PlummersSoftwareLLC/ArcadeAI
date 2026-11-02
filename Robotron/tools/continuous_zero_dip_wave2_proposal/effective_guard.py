"""Dormant one-helper installer for a future isolated evaluator process only.

No action at import. Root must authenticate/select this file separately from
the held socket source. No training/runtime module is imported here.
"""
import ast
import hashlib
import os
from pathlib import Path
import stat
from types import FunctionType
from typing import NamedTuple

BASE_SHA = 'f44ddfe31408b77b6d622e1d4ec4cda60a03999dc984d9e11b5aeac38911a9ed'
BODY_SHA = 'f7a4d367162bafb87f4bc94ddad54573a76ab9159ae11e07540b2690c2c6eba4'
NAME = '_continuous_play_score_dip'
ARGS = ('frame', 'client', 'previous_score', 'previous_wave', 'recent_start')
OLD = '        and (int(frame.game_score) > 0 or not recent_start)\n'
NEW = ('        and (int(frame.game_score) > 0 or not recent_start\n'
       '             or int(frame.level_number) >= 2)\n')


def require(value, message):
    if not value:
        raise ValueError(message)


def read_fixed(path, expected):
    path = Path(path)
    require(path.is_absolute() and path.suffix == '.py', 'Exact Python source path required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read((512 << 10)+1)
        after = os.fstat(stream.fileno())
    def identity(info):
        return dict(device=info.st_dev, inode=info.st_ino, bytes=info.st_size,
            mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns,
            mode=oct(stat.S_IMODE(info.st_mode)), uid=info.st_uid, nlink=info.st_nlink)
    require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
        and before.st_nlink == 1 and before.st_size <= 512 << 10
        and identity(before) == identity(after) == identity(path.lstat())
        and hashlib.sha256(raw).hexdigest() == expected, 'Authenticated source changed')
    return raw, dict(path=str(path), sha256=expected, bytes=len(raw), identity=identity(before))


def helper_node(raw, filename, *, body_only):
    tree = ast.parse(raw, filename=str(filename))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == NAME]
    require(len(nodes) == 1 and (not body_only or len(tree.body) == 1), 'Exactly the intended helper required')
    node = nodes[0]
    require(not node.decorator_list and node.returns is None and node.type_comment is None
        and not node.args.posonlyargs and not node.args.kwonlyargs
        and not node.args.defaults and not node.args.kw_defaults
        and node.args.vararg is None and node.args.kwarg is None
        and tuple(arg.arg for arg in node.args.args) == ARGS
        and all(arg.annotation is None for arg in node.args.args), 'Exact five-argument helper signature required')
    require(not any(isinstance(child, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal,
        ast.Lambda, ast.ClassDef, ast.AsyncFunctionDef, ast.Yield, ast.YieldFrom, ast.Await))
        or isinstance(child, ast.FunctionDef) and child is not node for child in ast.walk(node)),
        'No imports, global statements, closures or nested code allowed')
    return node


class GuardToken(NamedTuple):
    module: object
    function: object
    code: object
    globals: object
    config: object
    base_pin: dict
    installer_pin: dict
    body_pin: dict


def verify(token):
    require(type(token) is GuardToken, 'Installer-issued token required')
    current = token.module.__dict__.get(NAME)
    require(current is token.function and current.__code__ is token.code
        and current.__globals__ is token.globals is token.module.__dict__
        and current.__closure__ is None and current.__defaults__ is None
        and current.__kwdefaults__ is None and not current.__annotations__
        and current.__code__.co_argcount == 5 and current.__code__.co_kwonlyargcount == 0
        and current.__code__.co_posonlyargcount == 0
        and token.module.__dict__.get('RL_CONFIG') is token.config,
        'Effective function/code/globals/config identity drift')
    return dict(base_socket=token.base_pin, installer=token.installer_pin,
        effective_helper=token.body_pin, function_code_globals_config_identity=True,
        only_one_module_global_replaced=True, effective_source_is_not_base_source=True)


def install(socket_module, *, expected_module_path, expected_installer_sha256):
    """Call once before SocketServer construction in an explicitly isolated child.

    The imported base file stays byte-exact f44. Only this module-global pure
    helper changes; its function globals are the existing socket module dict.
    Future plan/receipt companions must record both source and effective body.
    """
    installer_path = Path(__file__).resolve()
    _, installer_pin = read_fixed(installer_path, expected_installer_sha256)
    source_path = Path(expected_module_path)
    require(source_path == Path(socket_module.__file__).resolve(), 'Imported socket path differs')
    raw, base_pin = read_fixed(source_path, BASE_SHA)
    body_path = installer_path.with_name('effective_guard_body.py')
    body, body_pin = read_fixed(body_path, BODY_SHA)
    base_node = helper_node(raw, source_path, body_only=False)
    body_node = helper_node(body, body_path, body_only=True)
    base_text = ast.get_source_segment(raw.decode(), base_node)
    require(base_text.count(OLD.rstrip('\n')) == 1
        and body.decode().strip() == base_text.replace(OLD.rstrip('\n'), NEW.rstrip('\n')).strip(),
        'Effective body must be exactly the one reviewed predicate change')
    current = socket_module.__dict__.get(NAME)
    require(type(current) is FunctionType and current.__globals__ is socket_module.__dict__
        and current.__closure__ is None and current.__defaults__ is None
        and current.__kwdefaults__ is None and not current.__annotations__,
        'Unmodified original module-global helper required')
    # Compile ONLY the extracted original helper to authenticate the imported
    # function's code. This temporary namespace is never installed or invoked.
    canonical = {}
    exec(compile(ast.Module(body=[base_node], type_ignores=[]), str(source_path),
                 'exec', dont_inherit=True), canonical)
    require(current.__code__ == canonical[NAME].__code__, 'Imported base helper code differs')
    # Compile only the exact sealed candidate helper. Construct its function
    # directly with the EXISTING module globals; no exec into that globals dict.
    temporary = {}
    exec(compile(ast.Module(body=[body_node], type_ignores=[]), str(body_path),
                 'exec', dont_inherit=True), temporary)
    require(set(temporary) == {'__builtins__', NAME}, 'Unexpected effective helper namespace')
    code = temporary[NAME].__code__
    require(not code.co_freevars and not code.co_cellvars, 'No closure state permitted')
    function = FunctionType(code, socket_module.__dict__, NAME)
    before = dict(socket_module.__dict__)
    socket_module.__dict__[NAME] = function
    require(set(before) == set(socket_module.__dict__)
        and all(socket_module.__dict__[name] is value for name, value in before.items() if name != NAME),
        'Unexpected other module-global mutation')
    token = GuardToken(socket_module, function, code, socket_module.__dict__,
        socket_module.__dict__['RL_CONFIG'], base_pin, installer_pin, body_pin)
    verify(token)
    return token
