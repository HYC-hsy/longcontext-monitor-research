"""One-time mechanical replacement of Git checkout newline conversion with blob bytes."""
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
VENDOR = HERE / 'vendor'
COMMIT = '6818cfa6434dbc91fcf67f0b3eb12a91db47433f'

for target in sorted(VENDOR.rglob('*')):
    if not target.is_file() or '__pycache__' in target.parts:
        continue
    relative = target.relative_to(VENDOR).as_posix()
    blob = subprocess.run(['git', '-C', str(HERE / 'upstream'), 'show',
                           f'{COMMIT}:{relative}'], check=True,
                          capture_output=True).stdout
    existing = target.read_bytes()
    if existing != blob:
        if existing.replace(b'\r\n', b'\n') != blob:
            raise RuntimeError(f'not newline-only conversion: {relative}')
        target.write_bytes(blob)
        print('restored original Git blob bytes:', relative)
