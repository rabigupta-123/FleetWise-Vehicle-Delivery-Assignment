# Contributing to FleetWise

Thank you for contributing to the FleetWise Conflict-Free Fleet & Delivery Assignment Engine.

## Development Setup

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/rabigupta-123/FleetWise-Vehicle-Delivery-Assignment.git
   cd FleetWise-Vehicle-Delivery-Assignment
   ```

2. **Set up Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
   pip install -r requirements.txt -r requirements-dev.txt
   ```

3. **Verify Standards Before Submitting**:
   ```bash
   # 1. Run Secrets Check
   python scripts/check_secrets.py

   # 2. Run Ruff Linter
   ruff check app tests

   # 3. Run Pyrefly Static Type Checker
   pyrefly check --min-severity=warn

   # 4. Run KaTeX Math Syntax Validation
   python scripts/check_math_syntax.py

   # 5. Run Node Unit Tests
   node --test tests/test_battery_states.test.js

   # 6. Run Pytest Suite
   pytest -v --junitxml=junit.xml

   # 7. Check Documentation Synchronization
   python scripts/update_readme.py --check
   ```

## Contribution Principles

- **Truthfulness Contract**: Never introduce fallback defaults, hardcoded mock analytics, or fabricated telemetry. If an input or measurement is unavailable, record `null` with explicit status and reason.
- **Transaction Safety**: All state-mutating endpoints must operate inside atomic SQLite `BEGIN IMMEDIATE` transactions.
- **Documentation**: If you modify API endpoints or mathematical heuristics, update `docs/FORMULAS.md` and synchronize `README.md` via `python scripts/update_readme.py`.
