"""Run the unchanged quota64 review with exact pinned-source reads.

Only the eleven declared, independently bound Python dependencies use checked
source reads. Every game, receipt, descriptor and other artifact retains the
original immutable full8/reduced5 reader. Default invocation is inert.
"""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
CORE_SHA='db65dd2f807b68be44fc0ed36cdb85288fc3f9e8ba143c16c8c3e9ae1c16e7c5'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module


class ReviewReader:
    def __init__(self,job,h):
        self.h=h
        p=load('_fullgame_review_source_reader_pipeline',HERE/'fullgame_review_pipeline.py')
        p.require(job['schema']=='robotron-original-quota64-independent-leg-review-job-v1'
            and job['sources']==p.sources(h),'Exact eleven declared review dependencies required')
        self.sources={pin['path']:pin for pin in job['sources'].values()}
        self.immutable=p.read

    def read_pin(self,pin,*,as_json=True):
        declared=self.sources.get(pin['path'])
        if declared is None:return self.immutable(pin,as_json=as_json)
        self.h.require(pin==declared and as_json is False,'Only exact declared raw Python source may use source reads')
        path=self.h.checked(pin)
        self.h.require(path.suffix=='.py'and path.is_absolute()and path.resolve(strict=True)==path
            and not path.is_symlink()and set(pin['identity'])=={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'},
            'Exact canonical full-identity Python source required')
        raw=path.read_bytes();self.h.checked(pin)
        self.h.require(hashlib.sha256(raw).hexdigest()==pin['sha256'],'Source changed during read')
        return raw


def execute(args):
    p=load('_fullgame_review_entry_pipeline',HERE/'fullgame_review_pipeline.py');h=p.helpers()
    p.require(h.pin(Path(__file__).resolve())['sha256']==args.expected_source_sha256,'Actual selected review entry differs')
    core_pin=h.pin(HERE/'review_fullgame_rounds_v2.py');p.require(core_pin['sha256']==CORE_SHA,'Actual unchanged quota64 reviewer differs')
    jp=h.pin(args.job.resolve());p.require(jp['sha256']==args.job_sha256,'Actual original review job differs')
    job=p.read(jp);subject=p.read(job['native_job'])
    p.require(subject['engineering_only']is False,'Engineering contexts cannot execute a scientific review entry')
    reader=ReviewReader(job,h);core=load('_fullgame_unchanged_original_reviewer',h.checked(core_pin))
    return core.review(jp,h,reader)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--observe',action='store_true');a.add_argument('--job',type=Path)
    a.add_argument('--job-sha256');a.add_argument('--expected-source-sha256');args=a.parse_args()
    if args.observe:sys.exit(execute(args))
    else:print('PLAN_ONLY_NO_READS_OR_ACTIONS')
