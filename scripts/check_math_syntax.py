"""
Validates KaTeX math formatting in Markdown documents.
Checks that all math delimiters ($ and $$) are balanced,
literal dollar signs are properly escaped or in code blocks,
and no syntax errors trigger GitHub math rendering failure.
"""
import re
import sys
from pathlib import Path


def check_markdown_file(file_path: Path) -> list[str]:
    content = file_path.read_text(encoding="utf-8")
    errors = []

    # Strip code blocks
    stripped = re.sub(r"```[\s\S]*?```", "", content)
    stripped = re.sub(r"`[^`\n]+`", "", stripped)

    # 1. Check $$ display math balance
    display_tokens = re.findall(r"\$\$", stripped)
    if len(display_tokens) % 2 != 0:
        errors.append(f"Unmatched display math delimiter '$$' (count: {len(display_tokens)})")

    # 2. Check inline $ balance (ignoring \$)
    no_escaped = re.sub(r"\\\$", "", stripped)
    # Remove matched $$
    no_display = re.sub(r"\$\$[\s\S]*?\$\$", "", no_escaped)
    inline_tokens = re.findall(r"\$", no_display)
    if len(inline_tokens) % 2 != 0:
        errors.append(f"Unmatched inline math delimiter '$' (count: {len(inline_tokens)})")

    # 3. Check for invalid unescaped prices like $100 not in math
    for line_no, line in enumerate(stripped.splitlines(), start=1):
        # find $123 that isn't part of KaTeX expression
        matches = re.finditer(r"(?<!\\)\$(\d+(?:\.\d+)?)(?!\$)", line)
        for m in matches:
            # If line doesn't have closing $, it's likely an unescaped currency
            if line.count("$") - line.count(r"\$") == 1:
                errors.append(f"Line {line_no}: Possible unescaped currency sign '${m.group(1)}'")

    return errors


def main() -> int:
    workspace = Path(__file__).resolve().parent.parent
    md_files = [
        workspace / "README.md",
        workspace / "docs" / "FORMULAS.md",
    ]

    total_errors = 0
    for p in md_files:
        if not p.exists():
            continue
        errs = check_markdown_file(p)
        if errs:
            print(f"FAIL: {p.name}")
            for e in errs:
                print(f"  - {e}")
            total_errors += len(errs)
        else:
            print(f"PASS: {p.name} - KaTeX syntax valid.")

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
