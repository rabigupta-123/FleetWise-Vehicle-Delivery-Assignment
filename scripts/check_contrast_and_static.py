"""
FleetWise — WCAG 2.1 Contrast Ratio Calculator & Static Truthfulness Scanner.
1. Computes and prints the WCAG 2.1 contrast ratio of every text/background pair
   in the White & Orange Light/Dark design token system and asserts >= 4.5:1 (or >= 3.0:1 for large text).
2. Scans static/ for forbidden unverified marketing claims, external font CDNs, and hard-coded mock arrays.
"""
from pathlib import Path
import re
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"


def relative_luminance(hex_color: str) -> float:
    h = hex_color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def channel_lum(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    l1 = relative_luminance(fg_hex)
    l2 = relative_luminance(bg_hex)
    brightest = max(l1, l2)
    darkest = min(l1, l2)
    return (brightest + 0.05) / (darkest + 0.05)


# All token pairs used for text/background across Light & Dark themes
TEXT_BG_PAIRS: list[tuple[str, str, str, float]] = [
    # Light Theme Core Text
    ("Light: ink (#16181D) on bg (#F6F4F1)", "#16181D", "#F6F4F1", 4.5),
    ("Light: ink (#16181D) on surface (#FFFFFF)", "#16181D", "#FFFFFF", 4.5),
    ("Light: muted (#5B6270) on bg (#F6F4F1)", "#5B6270", "#F6F4F1", 4.5),
    ("Light: muted (#5B6270) on surface (#FFFFFF)", "#5B6270", "#FFFFFF", 4.5),
    # Orange Accent & Buttons
    ("Light: white (#FFFFFF) on orange-700 (#C2410C) [primary button text]", "#FFFFFF", "#C2410C", 4.5),
    ("Light: ink (#16181D) on orange-500 (#F97316) [small text on orange card]", "#16181D", "#F97316", 4.5),
    ("Light: ink (#16181D) on orange-100 (#FFEDD5) [orange pill text]", "#16181D", "#FFEDD5", 4.5),
    ("Light: orange-700 (#C2410C) on surface (#FFFFFF) [accent text]", "#C2410C", "#FFFFFF", 4.5),
    ("Light: orange-700 (#C2410C) on bg (#F6F4F1) [accent text on bg]", "#C2410C", "#F6F4F1", 4.5),
    ("Light: orange-600 (#EA580C) on surface (#FFFFFF) [large text / icons >=3:1]", "#EA580C", "#FFFFFF", 3.0),
    # Dark Contrast Card (#14161B)
    ("Dark Card: white (#FFFFFF) on dark-card (#14161B)", "#FFFFFF", "#14161B", 4.5),
    ("Dark Card: slate-300 (#CBD5E1) on dark-card (#14161B)", "#CBD5E1", "#14161B", 4.5),
    ("Dark Card: orange-500 (#F97316) on dark-card (#14161B)", "#F97316", "#14161B", 4.5),
    # Semantic Status Colours on White Surface (#FFFFFF) and Soft Tints
    ("Status Success: #15803D on surface (#FFFFFF)", "#15803D", "#FFFFFF", 4.5),
    ("Status Success: #15803D on green-50 (#F0FDF4)", "#15803D", "#F0FDF4", 4.5),
    ("Status Danger: #B91C1C on surface (#FFFFFF)", "#B91C1C", "#FFFFFF", 4.5),
    ("Status Danger: #B91C1C on red-50 (#FEF2F2)", "#B91C1C", "#FEF2F2", 4.5),
    ("Status Info: #1D4ED8 on surface (#FFFFFF)", "#1D4ED8", "#FFFFFF", 4.5),
    ("Status Info: #1D4ED8 on blue-50 (#EFF6FF)", "#1D4ED8", "#EFF6FF", 4.5),
    ("Status Warning: #B45309 on surface (#FFFFFF)", "#B45309", "#FFFFFF", 4.5),
    ("Status Warning: #B45309 on amber-50 (#FFFBEB)", "#B45309", "#FFFBEB", 4.5),
    # Opt-in Dark Theme
    ("Dark Theme: #F8FAFC on #0F1115", "#F8FAFC", "#0F1115", 4.5),
    ("Dark Theme: #94A3B8 on #14161B", "#94A3B8", "#14161B", 4.5),
]

FORBIDDEN_STATIC_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("Unverified claim '100% Conflict-Free'", re.compile(r"100%\s+Conflict-Free", re.IGNORECASE)),
    ("Hard-coded '44 Verified Endpoints' claim", re.compile(r"44\s+Verified\s+Endpoints", re.IGNORECASE)),
    ("Hard-coded 'Sub-Second Live GPS' claim", re.compile(r"Sub-Second\s+Live\s+GPS", re.IGNORECASE)),
    ("External Google Fonts CDN import", re.compile(r"fonts\.googleapis\.com|fonts\.gstatic\.com", re.IGNORECASE)),
    ("Third-party reference name", re.compile(r"codealpha|getlayers\.ai", re.IGNORECASE)),
    (
        "Hard-coded mock array in JS/HTML",
        re.compile(r"(?:const|let|var)\s+(?:MOCK_|FAKE_|DUMMY_|SAMPLE_DATA)[A-Z0-9_]*\s*=\s*\[", re.IGNORECASE),
    ),
]


def check_contrast() -> tuple[bool, list[str]]:
    errors: list[str] = []
    print("=" * 88)
    print(f"{'Text / Background Pair':<58} | {'Ratio':<9} | {'Min':<6} | {'Status'}")
    print("-" * 88)
    # Also explicitly print the negative reference noted in spec: orange-500 on white
    ref_ratio = contrast_ratio("#F97316", "#FFFFFF")
    print(
        f"{'[Spec Check] orange-500 (#F97316) on white (#FFFFFF)':<58} | {ref_ratio:>6.2f}:1 | {'4.5:1':<6} | "
        f"{'FAILS 4.5:1 (restricted to fills/icons/large text)'}"
    )
    print("-" * 88)

    for label, fg, bg, min_req in TEXT_BG_PAIRS:
        r = contrast_ratio(fg, bg)
        passed = r >= min_req
        status = "PASS" if passed else "FAIL"
        print(f"{label:<58} | {r:>6.2f}:1 | {min_req:>3.1f}:1 | {status}")
        if not passed:
            errors.append(f"{label} has contrast {r:.2f}:1, below required {min_req}:1")
    print("=" * 88)
    return len(errors) == 0, errors


def check_static_truthfulness() -> tuple[bool, list[str]]:
    errors: list[str] = []
    files_to_scan = [
        p
        for p in STATIC_DIR.rglob("*")
        if p.is_file()
        and p.suffix in {".html", ".css", ".js"}
        and "vendor" not in p.parts
    ]
    for path in sorted(files_to_scan):
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(ROOT_DIR)
        for desc, pattern in FORBIDDEN_STATIC_PATTERNS:
            match = pattern.search(text)
            if match:
                errors.append(f"{rel}: matched forbidden pattern ({desc}): '{match.group(0)}'")
    return len(errors) == 0, errors


def main() -> int:
    ok_c, err_c = check_contrast()
    ok_s, err_s = check_static_truthfulness()
    if err_s:
        print("\nStatic Truthfulness Scan Failures:")
        for e in err_s:
            print(f"  - {e}")
    else:
        print("\nStatic Truthfulness Scan: PASS (0 forbidden claims, 0 external font CDNs, 0 mock arrays)")
    return 0 if (ok_c and ok_s) else 1


if __name__ == "__main__":
    sys.exit(main())

