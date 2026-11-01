"""
Tests that documentation does not drift from application code:
- Verifies README.md API route table matches app.routes
- Verifies README.md test counts match pytest test collection
- Verifies WCAG 2.1 contrast ratios and scans static/ for forbidden claims and mock arrays
"""
from scripts.check_contrast_and_static import main as check_contrast_and_static_main
from scripts.check_mermaid import main as check_mermaid_main
from scripts.update_readme import update_readme


def test_readme_docs_drift():
    in_sync = update_readme(check_only=True)
    assert in_sync, "README.md dynamic sections are out of sync. Run 'python scripts/update_readme.py' to synchronize."


def test_mermaid_diagrams_syntax():
    exit_code = check_mermaid_main()
    assert exit_code == 0, "One or more Mermaid diagrams failed syntax/lint checks."


def test_static_contrast_and_truthfulness():
    exit_code = check_contrast_and_static_main()
    assert exit_code == 0, "Static contrast or truthfulness scan failed."
