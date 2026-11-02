"""Default inert. Add an exact client readiness overlay to held HC5 metadata.

Only new immutable metadata is written. No API/proc/kernel/systemd call, model
load, launch, control, runtime qualification or failed-scope adoption occurs.
The selected HC5 health profile and all original physical anchors stay fixed.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
HC5 = HERE.parent/'health-consumer-live-pidfd-current-EVAL-quiescence-original05'
LIMIT = 2 << 20
CASE_SCHEMA = 'robotron-original192-live-pidfd-current-eval-quiescence-case-v5'
INVENTORY_SCHEMA = 'robotron-root-original192-live-pidfd-current-eval-quiescence-input-inventory-v5'
PARENT_CASE_SHA = '95a87d6b9f4112970a8dd3e46dc5ee8b20316514d433592835cd5c962cdbfec6'
PARENT_INVENTORY_SHA = 'cb87a6cdbad00b5ec35139fb7e01089cc2b915839be1118793b8b81e5f41b826'
CALLBACK_SHA = 'cce755775dfa8134a446b0d42d3a13bf96bcca23257fc92b8798622bee2a7b2e'
FAMILY_SHA = '22245530f82299b2a3f634d07ba828a91678dc67a6ad5bd869a780d6d4a62651'
MAP_SHA = 'c8231a36c0028567a6a7da884046aa98ceeaf0fc6f0c338e4230fd305fb7e553'
CLIENT_SHA = '82e5e02e49c853355fd0bf1dd4839efdb498a8f798dbf08e3c7a72703778cbec'
PEER_NAME = 'independent-current-EVAL-quiescence-readiness120-client-mixed-map-source-peer-v1.json'


def require(value, reason):
    if not value:
        raise ValueError(reason)


def identity(info):
    return dict(device=info.st_dev,inode=info.st_ino,bytes=info.st_size,
        mtime_ns=info.st_mtime_ns,ctime_ns=info.st_ctime_ns,
        mode=oct(stat.S_IMODE(info.st_mode)),uid=info.st_uid,nlink=info.st_nlink)


def current(path):
    path=Path(path)
    require(path.is_absolute() and path.resolve(strict=True)==path and not path.is_symlink(),
            'Canonical non-symlink held path required')
    info=path.lstat();require(stat.S_ISREG(info.st_mode),'Regular held input required')
    return identity(info)


def pin(path):
    path=Path(path);before=current(path)
    require(0<before['bytes']<=LIMIT,'Only bounded metadata/source body may be read')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        require(identity(os.fstat(fd))==before,'Metadata open raced')
        with os.fdopen(os.dup(fd),'rb') as stream:raw=stream.read(LIMIT+1)
        require(identity(os.fstat(fd))==before and current(path)==before
                and len(raw)==before['bytes'],'Metadata changed while reading')
    finally:
        os.close(fd)
    return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),identity=before)


def checked(value, *, raw=False):
    require(type(value) is dict and set(value)=={'path','sha256','bytes','identity'}
            and set(value['identity'])=={'device','inode','bytes','mtime_ns','ctime_ns','mode','uid','nlink'},
            'Exact selected full8 metadata/source pin required')
    require(value['identity']['mode']=='0o444' and value['identity']['uid']==os.getuid()
            and value['identity']['nlink']==1 and pin(value['path'])==value,
            'Immutable selected metadata/source identity or SHA changed')
    body=Path(value['path']).read_bytes()
    require(hashlib.sha256(body).hexdigest()==value['sha256'] and pin(value['path'])==value,
            'Selected metadata changed')
    return body if raw else json.loads(body)


def put(path, value):
    body=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    require(len(body)<=LIMIT,'Bounded assembly metadata exceeded2MiB')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False)as stream:stream.write(body);stream.flush()
        os.fchmod(fd,0o444);os.fsync(fd)
    finally:
        os.close(fd)
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    return pin(path)


def callback(h):
    path=HC5/'prepare_current_eval_quiescence_case_v5.py'
    selected=h.pin(path)
    require(selected['sha256']==CALLBACK_SHA and selected['identity']['mode']=='0o444',
            'Exact unchanged HC5 strict inventory callback required')
    h.checked(selected)
    spec=importlib.util.spec_from_file_location('_readiness120_strict_HC5_inventory',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def validate_inventory(binding, h):
    authority=callback(h).validate_inventory(binding,h)
    parent_pin=authority['readiness120_parent_case']
    parent_inventory_pin=authority['readiness120_parent_inventory']
    require(parent_pin['path']==str(HC5/'actual-main-case-original01/current-EVAL-quiescence-main-case-v5.json')
            and parent_pin['sha256']==PARENT_CASE_SHA
            and parent_inventory_pin['path']==str(HC5/'actual-main-case-original01/exact-held-input-inventory-v5.json')
            and parent_inventory_pin['sha256']==PARENT_INVENTORY_SHA,
            'Exact immediate HC5 metadata parent required')
    parent=json.loads(h.checked(parent_pin).read_bytes())
    previous=json.loads(h.checked(parent_inventory_pin).read_bytes())
    require(parent['schema']==CASE_SCHEMA and len(parent['inputs'])==382
            and parent['input_inventory_authority']==parent_inventory_pin
            and previous['inputs']==parent['inputs'] and authority['all_prior382_paths_retained']is True
            and set(parent['inputs'])<=set(binding['inputs'])
            and authority['prior382_replacements']=={}
            and all(binding['inputs'][path]==value for path,value in parent['inputs'].items()),
            'Readiness-only overlay must preserve every exact HC5 held input')
    overlay=binding['observer_client_readiness_overlay']
    require(overlay['schema']=='robotron-HC5-client-readiness120-case-overlay-v1'
            and overlay['parent_case']==parent_pin and overlay['parent_inventory']==parent_inventory_pin
            and overlay['family']['sha256']==FAMILY_SHA and overlay['source_map']['sha256']==MAP_SHA
            and overlay['client']['sha256']==CLIENT_SHA and overlay['initial_samples']==100
            and overlay['readiness_wait_s']==120 and overlay['case_profile_and_protocol_unchanged']is True,
            'Exact HC5 client-only readiness overlay required')
    for value in (overlay['family'],overlay['source_map'],overlay['client'],overlay['source_peer']):
        require(binding['inputs'].get(value['path'])==dict(sha256=value['sha256'],identity=value['identity']),
                'Every selected overlay source must remain a fully held input')
        h.checked(value)
    return authority


class Reader:
    def checked(self,value):
        checked(value,raw=True);return Path(value['path'])
    def pin(self,path):
        return pin(path)


def assemble(selection_path, selection_sha, source_sha, output):
    own=pin(Path(__file__).resolve())
    require(own['sha256']==source_sha and own['identity']['mode']=='0o444','Exact frozen DATA overlay constructor required')
    selected=pin(selection_path);require(selected['sha256']==selection_sha,'Root selection SHA differs')
    choice=checked(selected)
    require(set(choice)=={'schema','parent_case','parent_inventory','overlay_family','source_map','source_peer','extra_inputs'}
            and choice['schema']=='robotron-root-HC5-readiness120-case-overlay-selection-v1',
            'Explicit Root readiness-only metadata selection required')
    parent=checked(choice['parent_case']);previous=checked(choice['parent_inventory'])
    require(choice['parent_case']['path']==str(HC5/'actual-main-case-original01/current-EVAL-quiescence-main-case-v5.json')
            and choice['parent_inventory']['path']==str(HC5/'actual-main-case-original01/exact-held-input-inventory-v5.json')
            and choice['parent_case']['sha256']==PARENT_CASE_SHA and choice['parent_inventory']['sha256']==PARENT_INVENTORY_SHA
            and parent['schema']==CASE_SCHEMA and len(parent['inputs'])==382
            and parent['input_inventory_authority']==choice['parent_inventory'] and previous['inputs']==parent['inputs'],
            'Exact held HC5 parent case/inventory required')
    require(choice['overlay_family']['path']==str(HERE/'prepared-current-EVAL-quiescence-readiness120-client-overlay-SOURCE-ONLY-NOT-QUALIFIED-v1.json')
            and choice['overlay_family']['sha256']==FAMILY_SHA
            and choice['source_map']['path']==str(HERE/'prospective-current-EVAL-quiescence-readiness120-eight-role-source-map-v1.json')
            and choice['source_map']['sha256']==MAP_SHA and choice['source_peer']['path']==str(HERE/PEER_NAME),
            'Exact selected readiness120 family/map/source peer required')
    family=checked(choice['overlay_family']);mapping=checked(choice['source_map']);checked(choice['source_peer'])
    require(family['observer_map']==choice['source_map'] and family['client']==mapping['observer_sources']['client']
            and family['client']['sha256']==CLIENT_SHA and family['readiness_wait_s']==120
            and family['initial_samples']==100,'Readiness overlay source contract differs')
    require(type(choice['extra_inputs'])is list,'Explicit extra held metadata list required')
    for path,value in parent['inputs'].items():
        require(current(path)==value['identity'],'A prior held input changed; no implicit refresh: '+path)
    additions=[choice['parent_case'],choice['parent_inventory'],choice['overlay_family'],choice['source_map'],choice['source_peer'],
        own,selected,pin(HC5/'prepare_current_eval_quiescence_case_v5.py'),family['client'],*choice['extra_inputs']]
    case=copy.deepcopy(parent);inputs=case['inputs']
    for value in additions:
        checked(value,raw=True)
        thin=dict(sha256=value['sha256'],identity=value['identity'])
        require(value['path']not in inputs or inputs[value['path']]==thin,'Overlay may not replace a historical held input')
        inputs[value['path']]=thin
    case['observer_client_readiness_overlay']=dict(schema='robotron-HC5-client-readiness120-case-overlay-v1',
        parent_case=choice['parent_case'],parent_inventory=choice['parent_inventory'],family=choice['overlay_family'],
        source_map=choice['source_map'],source_peer=choice['source_peer'],client=family['client'],initial_samples=100,
        readiness_wait_s=120,case_profile_and_protocol_unchanged=True,failed82_sample_scope_adopted=False)
    authority=copy.deepcopy(previous)
    authority.update(inputs=inputs,input_count=len(inputs),source=own,readiness120_parent_case=choice['parent_case'],
        readiness120_parent_inventory=choice['parent_inventory'],all_prior382_paths_retained=True,prior382_replacements={})
    for key,oldkey in (('replacements','parent_case'),('prior348_replacements','prior_physical_case'),('immediate_prior_replacements','immediate_prior_case')):
        older=checked(authority[oldkey])['inputs']
        authority[key]={p:dict(before=v,after=inputs[p])for p,v in older.items()if v!=inputs[p]}
    original=checked(authority['parent_case'])['inputs']
    authority['added_inputs']={p:v for p,v in inputs.items()if p not in original}
    output=Path(output)
    require(output.is_absolute() and output.parent.resolve(strict=True)==HERE and not output.exists(),
            'One new exclusive metadata output directory required')
    output.mkdir(mode=0o700)
    inventory=put(output/'exact-held-input-inventory-readiness120-v1.json',authority)
    case['input_inventory_authority']=inventory
    validate_inventory(case,Reader())
    result=put(output/'current-EVAL-quiescence-readiness120-main-case-v1.json',case)
    return put(output/'prepared-HC5-readiness120-case-NOT-QUALIFIED-v1.json',dict(
        schema='robotron-HC5-readiness120-case-DATA-preparation-v1',status='DATA_PREPARED_NOT_QUALIFIED',
        source=own,selection=selected,parent_case=choice['parent_case'],parent_inventory=choice['parent_inventory'],
        case=result,input_inventory_authority=inventory,held_input_count=len(inputs),source_family=choice['overlay_family'],
        source_map=choice['source_map'],all382_prior_inputs_exact_and_retained=True,
        original_process_owners_and_sources_recipe_epochs_roles_unchanged=True,
        actual_readiness120_or_runtime_engineering_or_quality_qualified=False,
        API_proc_systemd_kernel_model_or_scientific_actions_performed=False,
        old_failed82_scope_adopted_or_retried=False,all_three_fresh_engineering_scopes_still_required=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--selection',type=Path);parser.add_argument('--selection-sha256')
    parser.add_argument('--expected-source-sha256');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not args.prepare:
        print('PLAN_ONLY_NO_READS_WRITES_IMPORTS_PROBES_OR_ACTIONS');return
    print(json.dumps(assemble(args.selection,args.selection_sha256,args.expected_source_sha256,args.output)),flush=True)


if __name__=='__main__':
    main()
