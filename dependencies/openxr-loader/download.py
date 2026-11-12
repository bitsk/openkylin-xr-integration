#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fetch the exact upstream loader package missing from the target package archive."""
import argparse,hashlib,json,urllib.request
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
lock=json.loads(Path(__file__).with_name('source.lock.json').read_text());a.output.mkdir(parents=True,exist_ok=True);target=a.output/lock['filename']
if not target.exists():
 temporary=target.with_suffix('.download')
 with urllib.request.urlopen(lock['url']) as source,temporary.open('wb') as output:
  while chunk:=source.read(1024*1024):output.write(chunk)
 temporary.replace(target)
if target.stat().st_size!=lock['bytes'] or hashlib.sha256(target.read_bytes()).hexdigest()!=lock['sha256']:raise ValueError('Upstream loader package checksum mismatch')
print(target)
