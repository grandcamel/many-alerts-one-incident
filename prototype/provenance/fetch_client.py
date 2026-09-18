#!/usr/bin/env python3
"""Fetch the pinned public artifact; do not execute it or inherit tenant credentials."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, default=Path('/tmp/maoi-mcp-client'))
    args = parser.parse_args()
    manifest = json.loads(Path(__file__).with_name('manifest.json').read_text())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(manifest['binary_url'], timeout=30) as response:
        data = response.read(150 * 1024 * 1024 + 1)
    if hashlib.sha256(data).hexdigest() != manifest['archive_sha256']:
        raise SystemExit('Archive checksum mismatch')
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        members = [m for m in archive.getmembers() if m.name == 'mcp-grafana' and m.isfile()]
        if len(members) != 1:
            raise SystemExit('Expected one regular binary')
        binary = archive.extractfile(members[0]).read()
    if hashlib.sha256(binary).hexdigest() != manifest['binary_sha256']:
        raise SystemExit('Binary checksum mismatch')
    args.destination.mkdir(parents=True, exist_ok=True)
    target = args.destination / 'mcp-grafana'
    if target.is_symlink():
        raise SystemExit('Refusing symlink destination')
    target.write_bytes(binary)
    target.chmod(0o755)
    print(target)


if __name__ == '__main__':
    main()
