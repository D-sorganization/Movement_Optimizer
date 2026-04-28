# Type Ignore Suppression Tracking

Issue #333 identified that checked-in `# type: ignore[...]` suppressions existed
without an explicit repository tracking mechanism.

The current suppression baseline is recorded in
`docs/typing/type_ignore_suppressions.json` and enforced by
`scripts/check_type_ignore_suppressions.py`. The checker scans Python files under
`src/` and `tests/`, verifies that every suppression is part of the reviewed
baseline, and rejects bare `# type: ignore` comments without explicit mypy error
codes.

## Current Baseline

- Total tracked suppressions: 170
- Source suppressions: 133
- Test suppressions: 37
- Most common categories: `attr-defined` (92), `arg-type` (45), `misc` (10),
  `override` (7), `operator` (6)

## Remediation Policy

1. Prefer removing a suppression by improving local typing, protocol coverage, or
   third-party annotations when the change is focused.
2. Keep dynamic GUI, matplotlib, PyQt, and optional native-extension suppressions
   explicit when removing them would require broad refactors.
3. When adding, removing, or relocating a suppression, run:

   ```powershell
   python scripts/check_type_ignore_suppressions.py --write
   python scripts/check_type_ignore_suppressions.py
   ```

4. Review the resulting JSON diff before committing so the suppression inventory
   remains an intentional typing-debt ledger.
