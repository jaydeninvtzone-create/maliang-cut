"""Install this skill without overwriting existing user configuration."""
import argparse, shutil
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--target',type=Path,required=True); a=p.parse_args()
src=Path(__file__).resolve().parent; dst=a.target.expanduser().resolve()
if dst.exists(): p.error('Target exists; choose a fresh location or review an explicit upgrade.')
if dst==src or src in dst.parents: p.error('Target must be outside the source tree.')
import json
files=json.loads((src/'release-files.json').read_text('utf-8'))
dst.mkdir(parents=True)
for rel in files:
    if Path(rel).is_absolute() or '..' in Path(rel).parts: raise ValueError('Unsafe release path')
    source=src/rel; target=dst/rel
    if source.is_symlink() or not source.resolve().is_relative_to(src): raise ValueError('Unsafe source')
    target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
print('Installed maliang-cut. Run scripts/maliang.py doctor; native editor access is checked separately.')

