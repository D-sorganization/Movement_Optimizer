# Criterion H Assessment — Movement-Optimizer

**Date:** 2026-04-26
**Score:** 6.0/10
**Weight:** 10%

## Findings

### [P1] No SAST scan artifacts

No bandit_output.json or similar.

### [P2] Subprocess shell usage checked

No tracked Python subprocess calls use shell=True; regression coverage now enforces list-form subprocess calls.
