"""Pure exact-payload descriptors shared by stopped verification/startup hold.

Default import performs no file, process, numerical-library or device actions.
Callers supply already loaded Torch/NumPy APIs. No RNG/trajectory equivalence is
claimed; this describes the actual serialized/restored training payload only.
"""
import hashlib
import json
import math


def require(value,message):
    if not value:raise RuntimeError(message)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)


def bytes_sha(view,chunk=8<<20):
    value=memoryview(view).cast('B');digest=hashlib.sha256()
    for start in range(0,len(value),chunk):digest.update(value[start:start+chunk])
    return digest.hexdigest()


def typed_tree(value,torch):
    """Canonical typed keys preserve Adam integer IDs and tuple/list distinctions."""
    if isinstance(value,torch.Tensor):
        require(value.device.type=='cpu'and value.layout==torch.strided,'Explicit CPU strided tensor required')
        raw=value.detach().contiguous().reshape(-1).view(torch.uint8).numpy()
        return dict(kind='tensor',dtype=str(value.dtype),shape=list(value.shape),sha256=bytes_sha(raw))
    if value is None:return dict(kind='none')
    if type(value)in(bool,int,str):return dict(kind=type(value).__name__,value=value)
    if type(value)is float:
        require(math.isfinite(value),'Nonfinite scalar in restoration payload')
        return dict(kind='float',value=value)
    if isinstance(value,dict):
        items=[dict(key=typed_tree(key,torch),value=typed_tree(item,torch))for key,item in value.items()]
        items.sort(key=lambda row:canonical(row['key']))
        require(len({canonical(row['key'])for row in items})==len(items),'Duplicate typed payload key')
        return dict(kind='dict',items=items)
    if type(value)in(list,tuple):return dict(kind=type(value).__name__,items=[typed_tree(item,torch)for item in value])
    raise RuntimeError('Unsupported restoration payload type: '+type(value).__name__)


def ndarray_payload(value,np):
    """Exact contiguous array payload; NumPy is supplied, not imported here."""
    require(not value.dtype.hasobject,'Object array cannot be restoration evidence')
    raw=np.ascontiguousarray(value).reshape(-1).view(np.uint8)
    return dict(dtype=value.dtype.str,shape=list(value.shape),sha256=bytes_sha(raw))


def bank_valid_prefix_payload(array,lengths,stride,np):
    """Hash all valid episode prefixes in source episode order, excluding padding.

    The complete NPY files have separate stopped full-file hashes. This payload
    descriptor can also be computed from the actual loaded bank RAM arrays.
    """
    require(not array.dtype.hasobject and len(array.shape)in(1,2),'Plain bank array required')
    require(array.shape[0]>=len(lengths)*stride,'Loaded bank has insufficient original episode storage')
    digest=hashlib.sha256();rows=0
    row_bytes=array.dtype.itemsize*math.prod(array.shape[1:])
    chunk_rows=max(1,(8<<20)//max(1,row_bytes))
    for episode,length in enumerate(lengths):
        require(type(length)is int and 0<=length<=stride,'Invalid source episode length')
        for start in range(0,length,chunk_rows):
            part=np.ascontiguousarray(array[episode*stride+start:episode*stride+min(length,start+chunk_rows)])
            digest.update(memoryview(part.reshape(-1).view(np.uint8)).cast('B'))
        rows+=length
    return dict(dtype=array.dtype.str,valid_rows=rows,tail_shape=list(array.shape[1:]),
        episode_lengths=list(lengths),stride=stride,sha256=digest.hexdigest(),
        order='episode_index_then_valid_prefix_row_then_contiguous_C_bytes')


if __name__=='__main__':print('PURE_HELPER_NO_READS_OR_RUNTIME_ACTIONS')
