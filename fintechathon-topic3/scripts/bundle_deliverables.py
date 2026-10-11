"""Create the complete deliverable archive and a hashed file inventory."""
import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {'.venv', '.mpl-cache', '__pycache__', 'data', 'build'}
EXCLUDED_NAMES = {'analysis-package.zip', '交付文件清单.json', 'merchant_features.csv', 'sample_split.csv', 'test_predictions.csv'}


def main():
    paths = sorted(p for p in ROOT.rglob('*') if p.is_file()
                   and not EXCLUDED_PARTS.intersection(p.relative_to(ROOT).parts)
                   and p.name not in EXCLUDED_NAMES and p.suffix not in {'.otf', '.log', '.pyc'})
    inventory = {'scope': 'reports, aggregate analyses, figures, sources, reproducible scripts; excludes raw and merchant-level data',
                 'files': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                            'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}
    manifest = ROOT / '交付文件清单.json'
    manifest.write_text(json.dumps(inventory, ensure_ascii=False, indent=2))
    destination = ROOT / 'analysis-package.zip'
    with ZipFile(destination, 'w', compression=ZIP_DEFLATED) as archive:
        for path in [*paths, manifest]:
            archive.write(path, 'FinTechathon-topic3/' + path.relative_to(ROOT).as_posix())
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(paths) + 1
        for entry in inventory['files']:
            content = archive.read('FinTechathon-topic3/' + entry['path'])
            assert hashlib.sha256(content).hexdigest() == entry['sha256']
    print(f'Validated {len(paths)} deliverable files plus inventory; archive {destination.stat().st_size} bytes')


if __name__ == '__main__':
    main()
