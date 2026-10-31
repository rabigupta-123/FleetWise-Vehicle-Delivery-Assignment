"""
Pre-commit / CI secrets scanning script.
Verifies that no private keys, tracked database files, sensitive credentials,
or uncommitted environment files are present in the repository.
"""
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

FORBIDDEN_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"), "Private key block detected"),
    (re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}"), "GitHub token detected"),
    (re.compile(r"ey[A-Za-z0-9_-]{10,}\.ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "Raw JWT token detected"),
]

FORBIDDEN_EXTENSIONS = [
    ".pem",
    ".key",
    ".db",
    ".db-wal",
    ".db-shm",
    ".sqlite",
    ".sqlite3",
]


def check_git_tracked_files() -> list[str]:
    violations = []
    try:
        proc = subprocess.run(
            ["git", "ls-files"],
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            check=True,
        )
        files = proc.stdout.splitlines()
    except Exception as e:
        return [f"Failed to run git ls-files: {e}"]

    for rel_path in files:
        p = WORKSPACE / rel_path

        # 1. Check extension
        for ext in FORBIDDEN_EXTENSIONS:
            if rel_path.lower().endswith(ext):
                violations.append(f"Tracked forbidden file type '{ext}': {rel_path}")

        if rel_path.lower() == ".env":
            violations.append(f"Tracked active environment file: {rel_path}")

        # 2. Check content for sensitive patterns
        if p.exists() and p.is_file() and p.stat().st_size < 2_000_000:
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                for pattern, msg in FORBIDDEN_PATTERNS:
                    if pattern.search(text):
                        violations.append(f"{msg} in {rel_path}")
            except Exception:
                pass

    return violations


def main() -> int:
    violations = check_git_tracked_files()
    if violations:
        print("SECURITY CHECK FAILED:")
        for v in violations:
            print(f"  [X] {v}")
        return 1
    print("SECURITY CHECK PASSED: Zero forbidden secrets or database files tracked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
