"""Export only reviewed source files, never a private repo's history or workspace."""
import argparse, hashlib, json, re, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATTERNS=[r'(?i)[A-Z]:[\\/]Users[\\/][^\\/\s]+',r'(?i)(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_]{12,}',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'(?i)(?:api[_-]?key|access[_-]?token|password)\s*[:=]\s*["\x27][A-Za-z0-9+/=_-]{16,}["\x27]']

def inventory(root):
    entries=json.loads((root/'release-files.json').read_text('utf-8-sig'))
    if len(entries)!=len(set(entries)): raise ValueError('Duplicate release path')
    files=[]
    for rel in entries:
        path=root/rel
        if Path(rel).is_absolute() or '..' in Path(rel).parts or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):raise ValueError('Unsafe path in release list')
        if not path.is_file():raise ValueError('Missing release source: '+rel)
        if path.suffix.lower() in {'.mp4','.mov','.wav','.mp3','.sqlite','.db','.pyc','.log'} or '.git' in Path(rel).parts:raise ValueError('Forbidden release type')
        data=path.read_bytes()
        text=data.decode('utf-8-sig')
        for pattern in PATTERNS:
            if re.search(pattern,text):raise ValueError('Sensitive-looking content in '+rel)
        files.append((rel,data))
    return files

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    files=inventory(ROOT)
    if a.out.exists():raise ValueError('Archive exists; select a new version')
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.out,'x',zipfile.ZIP_DEFLATED) as z:
        for rel,data in files:z.writestr('maliang-cut/'+rel,data)
    receipt={'files':len(files),'sha256':hashlib.sha256(a.out.read_bytes()).hexdigest(),'status':'ALLOWLIST_AND_PATTERN_SCAN_PASS_REQUIRES_CONTENT_REVIEW'}
    print(json.dumps(receipt))
if __name__=='__main__':main()
