# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

The FleetWise engineering team takes application security, cryptographic integrity, and data protection seriously.

If you discover a security vulnerability or confidentiality issue within FleetWise:
1. **Do not create a public GitHub issue.**
2. Report the vulnerability privately via **[GitHub Private Security Advisory](https://github.com/rabigupta-123/FleetWise-Vehicle-Delivery-Assignment/security/advisories/new)**.
3. Include a detailed description of the vulnerability, step-by-step reproduction steps, proof-of-concept payload, and affected endpoints.

### Response Timeline
- **Initial Response**: Within 48 hours of submission.
- **Triage & Assessment**: Within 5 business days.
- **Fix & Disclosure**: Coordinated disclosure after resolution and validation.

## Security Controls Implemented

- **Append-Only Audit Log**: Enforced via SQLite triggers forbidding `UPDATE` and `DELETE` queries on `audit_log`.
- **Zero-Allocation Leaks**: Database connections serialized with `BEGIN IMMEDIATE` transactions under SQLite WAL mode.
- **CSRF & Injection Defenses**: Formula prefix escaping on CSV exports/imports (`=`, `+`, `-`, `@`), constant-time OTP comparison via `secrets.compare_digest`.
- **Truthfulness Contract**: Zero fabricated GPS, battery, or device measurements. Hard constraint rejection ($0.0$) on invalid states.
