"""Download official pinned files with normal TLS and verify recorded SHA256."""
import argparse,hashlib,json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--data-dir',type=Path,default=ROOT/'data');args=p.parse_args();args.data_dir.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((ROOT/'sources/data_manifest.json').read_text())
 for entry in manifest['files']:
  if not entry['path'].startswith('datasets/'):continue
  dest=args.data_dir/Path(entry['path']).name
  if not dest.exists():
   response=requests.get(entry['url'],timeout=90);response.raise_for_status()
   assert hashlib.sha256(response.content).hexdigest()==entry['sha256']
   dest.write_bytes(response.content)
  assert hashlib.sha256(dest.read_bytes()).hexdigest()==entry['sha256'],dest.name
  print(dest.name,dest.stat().st_size,'verified')
