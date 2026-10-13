from pathlib import Path

def test_v2_has_real_modules_not_a_renamed_archive():
 root = Path(__file__).resolve().parents[1]
 for name in ['config','auth','store','scope','registry','jobs','terminal','ai','app','cli']:
  assert (root / 'foxworx' / f'{name}.py').is_file(), f'missing v2 module: {name}'

def test_distribution_documents_boundaries():
 root = Path(__file__).resolve().parents[1]
 for name in ['SECURITY.md','TOOL-COVERAGE.md','UX-REVIEW.md','INSTALL.md']:
  assert (root / 'docs' / name).is_file(), f'missing operator document: {name}'
