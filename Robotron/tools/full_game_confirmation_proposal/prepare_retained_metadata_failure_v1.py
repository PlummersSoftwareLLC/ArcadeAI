"""Prepare a future health observer that preserves rejected metadata inputs.

No running source is edited and no validator is relaxed. The output must be new.
"""
import argparse
import ast
import hashlib
import os
from pathlib import Path

PARENT_SHA = '5e7efde5b458ab5dd6f7dba684b412d1cf0c998b62ec69b316f0b822c1d24d4a'
HELPER = '''
def retained_metadata_validation(h, output, index, phase, fleet, connections,
                                 expected, membership, roles, *, now):
    """Retain the exact rejected inputs; never turn rejection into acceptance."""
    try:
        return validate_metadata(fleet, connections, expected, membership, roles, now=now)
    except Exception as validation_error:
        payload = dict(
            schema='robotron-current-v6-rejected-metadata-v1',
            phase=phase, sample_index=index, observed_unix_s=now,
            exception_type=type(validation_error).__name__, error=str(validation_error),
            fleet=fleet, connections=connections, expected=expected,
            membership=membership, roles=roles,
            accepted=False, quality_qualified=False,
        )
        try:
            h.put(Path(output) / f'{index:05d}-v6-{phase}-metadata-rejected.json', payload)
        except Exception as capture_error:
            raise RuntimeError(
                f'Metadata rejected ({validation_error!r}); exact failure capture also failed '
                f'({capture_error!r})'
            ) from validation_error
        raise


'''


def transform(source):
    assert hashlib.sha256(source).hexdigest() == PARENT_SHA
    text = source.decode()
    anchor = 'def validate_join('
    assert text.count(anchor) == 1
    text = text.replace(anchor, HELPER + anchor)
    changes = {
        'pending=validate_metadata(before,connections,self.expected,self.membership,self.roles,now=now)':
        "pending=retained_metadata_validation(self.h,self.output,index,'before',before,connections,self.expected,self.membership,self.roles,now=now)",
        'after_pending=validate_metadata(after,after_connections,\n            self.expected,self.membership,self.roles,now=time.time())':
        "after_pending=retained_metadata_validation(self.h,self.output,index,'after',after,after_connections,\n            self.expected,self.membership,self.roles,now=time.time())",
    }
    for old, new in changes.items():
        assert text.count(old) == 1
        text = text.replace(old, new)
    # Reversibility proves there are no unlisted semantic changes.
    restored = text
    for old, new in changes.items():
        restored = restored.replace(new, old)
    restored = restored.replace(HELPER, '', 1)
    assert restored.encode() == source
    old_tree, new_tree = ast.parse(source), ast.parse(text)
    for name in ('stable_projection', 'validate_metadata', 'validate_join'):
        before = next(n for n in old_tree.body if getattr(n, 'name', None) == name)
        after = next(n for n in new_tree.body if getattr(n, 'name', None) == name)
        assert ast.dump(before) == ast.dump(after)
    compile(text, '<future-health-observer>', 'exec')
    return text.encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = transform(args.parent.read_bytes())
    fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(result)
        stream.flush()
        os.fsync(stream.fileno())
    print(hashlib.sha256(result).hexdigest())


if __name__ == '__main__':
    main()
