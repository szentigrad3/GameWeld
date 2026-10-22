#!/usr/bin/env python3
"""Simple publication guard; not a substitute for a human secret/license review."""
from pathlib import Path
import re,sys
root=Path(__file__).resolve().parents[1]
forbidden=[
 re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----'),
 re.compile(r'gh(?:p|o|u|s|r)_[A-Za-z0-9]{25,}'),
 re.compile(r'github_pat_[A-Za-z0-9_]{25,}'),
 re.compile(r'AKIA[0-9A-Z]{16}'),
]
violations=[]
for p in root.rglob('*'):
 if p.is_symlink():violations.append(f'symlink: {p.relative_to(root)}');continue
 if not p.is_file():continue
 rel=p.relative_to(root)
 if any(part in {'.git','__pycache__','build','dist','target'} for part in rel.parts):continue
 if p.suffix.lower() in {'.exe','.dll','.appimage','.zip','.pem','.key','.pfx'}:
  violations.append(f'unsupported binary/key file: {rel}');continue
 if p.stat().st_size>3_000_000:violations.append(f'oversized file: {rel}');continue
 if p.suffix.lower() not in {'.py','.sh','.md','.yml','.yaml','.json','.toml','.c','.rs','.txt','.desktop','.xml','.gitignore',''}:continue
 try: content=p.read_text(encoding='utf-8')
 except UnicodeDecodeError: continue
 # Don't match sample patterns in this source scanner itself.
 if p.name=='publication-audit.py':continue
 for pat in forbidden:
  if pat.search(content):violations.append(f'possible secret: {rel}')
if violations:
 for item in violations: print('PUBLICATION REVIEW:',item,file=sys.stderr)
 sys.exit(1)
print('Publication audit: no disallowed binaries, symlinks or obvious secret patterns detected.')
