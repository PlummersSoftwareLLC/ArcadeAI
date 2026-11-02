"""Same source edits and matched scope as v1; select the distinct v2 observer."""
import hashlib
import importlib.util
from pathlib import Path

H=Path(__file__).resolve().parent
BUILDER_V1_SHA='d483651a916e734736064f82408bdb97419b9a93469bf081fe6b1066e859039e'
EXPOSURE_SHA='30d9191e9fc845d80e52a7a891244fcf0c7041cf60529f6559b15e6d47ac5c7f'


def previous():
    path=H/'prepare_matched_trace_sources_v1.py'
    if hashlib.sha256(path.read_bytes()).hexdigest()!=BUILDER_V1_SHA:raise ValueError('Exact prior matched builder required')
    spec=importlib.util.spec_from_file_location('_matched_v2_builder_dependency',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def select(source):
    before='import matched_frame_trace_v1 as _request_trace'
    if source.count(before)!=1:raise ValueError('Exact single observer import required')
    return source.replace(before,'import matched_frame_trace_v2 as _request_trace',1)


def socket_source(source):return select(previous().socket_source(source))
def agent_source(source):return select(previous().agent_source(source))
def exposure_source(source,expected_sha256):return select(previous().exposure_source(source,expected_sha256))
def stripped_tree(source):return previous().stripped_tree(source)
def method(source,name,owner=None):return previous().method(source,name,owner)
