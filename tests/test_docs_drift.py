"""
Tests that documentation does not drift from application code:
- Verifies README.md API route table matches app.routes
- Verifies README.md test counts match pytest test collection
"""
from scripts.update_readme import update_readme


def test_readme_docs_drift():
    in_sync = update_readme(check_only=True)
    assert in_sync, "README.md dynamic sections are out of sync. Run 'python scripts/update_readme.py' to synchronize."
