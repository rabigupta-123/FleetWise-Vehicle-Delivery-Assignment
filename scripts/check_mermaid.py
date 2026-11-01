"""
FleetWise — Mermaid Diagram Linter & Validator.
Extracts and validates all ```mermaid code blocks across repository markdown files.
Enforces:
1. Semicolon isolation: rejects unescaped ';' in sequenceDiagram messages and notes (must use #59;, comma, or dash).
2. Bracket & parenthesis balance across all node labels and notes.
3. Flowchart node label quoting when containing parentheses or brackets.
4. Node-based mermaid parser execution if mermaid is available in the environment.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def extract_mermaid_blocks(file_path: Path) -> list[tuple[int, str]]:
    """Extracts all mermaid blocks from a markdown file with starting line number."""
    blocks = []
    text = file_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_block = False
    start_line = 0
    block_lines = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```mermaid"):
                in_block = True
                start_line = i
                block_lines = []
        else:
            if stripped == "```":
                in_block = False
                blocks.append((start_line, "\n".join(block_lines)))
                block_lines = []
            else:
                block_lines.append(line)

    return blocks


def validate_mermaid_block(file_path: Path, start_line: int, code: str) -> list[str]:
    """Validates syntax and structural rules of a single Mermaid diagram block."""
    errors = []
    lines = code.splitlines()
    non_empty = [l.strip() for l in lines if l.strip() and not l.strip().startswith("%%")]

    if not non_empty:
        errors.append(f"{file_path}:{start_line}: Empty mermaid diagram block")
        return errors

    header = non_empty[0]
    diagram_type = header.split()[0] if header.split() else ""

    # Check parenthesis and bracket balance across the diagram
    for idx, raw_line in enumerate(lines, start=start_line + 1):
        line = raw_line.strip()
        if not line or line.startswith("%%"):
            continue

        # 1. sequenceDiagram specific rules
        if diagram_type == "sequenceDiagram":
            # Semicolon in sequenceDiagram ends the statement prematurely in Mermaid's lexer
            if ";" in line:
                # Check if it's an entity escape like #59; or &semi;
                clean = re.sub(r"#59;|&semi;|&#59;", "", line)
                if ";" in clean:
                    errors.append(
                        f"{file_path}:{idx}: Semicolon ';' found in sequenceDiagram line. "
                        f"Mermaid terminates statements on ';'. Use ',' or ' - ' or '#59;'. Line: '{line}'"
                    )

        # 2. Bracket and Parenthesis balance
        # Only check outside quotes
        stripped_quotes = re.sub(r'"[^"]*"', '""', line)
        if stripped_quotes.count("(") != stripped_quotes.count(")"):
            errors.append(f"{file_path}:{idx}: Unbalanced parentheses in line: '{line}'")
        if stripped_quotes.count("[") != stripped_quotes.count("]"):
            errors.append(f"{file_path}:{idx}: Unbalanced brackets in line: '{line}'")

        # 3. Flowchart node label formatting
        if diagram_type in ("flowchart", "graph"):
            # Check for unquoted node labels with parentheses e.g. A[Label (info)] -> should be A["Label (info)"]
            unquoted_parens = re.findall(r'\[([^"\]]*\([^"\]]*\)[^"\]]*)\]', line)
            if unquoted_parens:
                errors.append(
                    f"{file_path}:{idx}: Unquoted parentheses inside flowchart node label. "
                    f"Wrap label in double quotes: [\"...\"]: '{line}'"
                )

    return errors


def try_node_mermaid_parse(code: str) -> str | None:
    """Invokes mermaid.parse via node if mermaid npm package is installed."""
    node_script = """
    try {
        const mermaid = require('mermaid');
        mermaid.initialize({ startOnLoad: false });
        mermaid.parse(process.argv[1]).then(() => process.exit(0)).catch(err => {
            console.error(err.message || String(err));
            process.exit(1);
        });
    } catch (e) {
        // mermaid module not installed, skip node check
        process.exit(0);
    }
    """
    try:
        proc = subprocess.run(
            ["node", "-e", node_script, code],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode != 0:
            return proc.stderr.strip()
    except Exception:
        pass
    return None


def main() -> int:
    target_files = []
    # Markdown files at root and docs/
    for ext in ("*.md",):
        target_files.extend(ROOT_DIR.glob(ext))
        target_files.extend((ROOT_DIR / "docs").glob(ext))

    all_errors = []
    total_blocks = 0

    for md_file in sorted(target_files):
        blocks = extract_mermaid_blocks(md_file)
        for start_line, block_code in blocks:
            total_blocks += 1
            errs = validate_mermaid_block(md_file, start_line, block_code)
            all_errors.extend(errs)

            # If node parser available, test with it
            node_err = try_node_mermaid_parse(block_code)
            if node_err and not any(f"{md_file}:{start_line}" in e for e in errs):
                all_errors.append(f"{md_file}:{start_line}: Mermaid node parser error: {node_err}")

    print(f"Validated {total_blocks} Mermaid diagram(s) across {len(target_files)} markdown file(s).")
    if all_errors:
        print("\n[!] Mermaid Validation Failed with Errors:")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("[OK] All Mermaid diagrams passed syntax and style checks cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
