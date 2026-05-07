# Movement-Optimizer — Comprehensive A-O Health Assessment

**Date:** 2026-05-07
**Branch:** fix/unstable-edge-case-tests
**HEAD:** `f343ce7e0ea292fcf2476b59443b11132bcb0b2f`
**Owner/Repo:** D-sorganization/Movement-Optimizer
**Source LOC:** 9852
**Test LOC:** 8019
**Code Files:** 138
**Branch Protection:** No

## Scores

| Criterion | Name | Score | Weight | Weighted |
|-----------|------|-------|--------|----------|
| A | Project Organization | 59 | 5% | 2.95 |
| B | Documentation | 100 | 8% | 8.00 |
| C | Testing | 65 | 12% | 7.80 |
| D | Error Handling | 96.9 | 10% | 9.69 |
| E | Performance | 60 | 7% | 4.20 |
| F | Code Quality | 90 | 10% | 9.00 |
| G | Dependency Hygiene | 90 | 8% | 7.20 |
| H | Security | 95 | 10% | 9.50 |
| I | Configuration Management | 100 | 6% | 6.00 |
| J | Observability | 60 | 7% | 4.20 |
| K | Maintenance Debt | 84.5 | 7% | 5.92 |
| L | CI/CD | 90 | 8% | 7.20 |
| M | Deployment | 90 | 5% | 4.50 |
| N | Legal & Compliance | 100 | 4% | 4.00 |
| O | Agentic Usability | 100 | 3% | 3.00 |
| **Total** | | | | **93.16** |

## Findings Summary

- **P0 (Critical):** 0
- **P1 (High):** 2
- **P2 (Medium):** 0

### P1 Findings

- **[A]** [Movement-Optimizer] Top-level repository clutter (18 files)
- **[L]** [Movement-Optimizer] No branch protection on main


## Full Evidence

```json
{
  "repo": "Movement-Optimizer",
  "branch": "fix/unstable-edge-case-tests",
  "head_sha": "f343ce7e0ea292fcf2476b59443b11132bcb0b2f",
  "head_date": "2026-04-30",
  "owner_repo": "D-sorganization/Movement-Optimizer",
  "A": {
    "src_files": 70,
    "test_files": 39,
    "manifests": 1,
    "gitignore_lines": 22,
    "has_readme": 1,
    "clutter_files": 18
  },
  "B": {
    "readme_lines": 180,
    "readme_headers": 29,
    "docs_files": 4,
    "md_files": 7
  },
  "C": {
    "test_py": 39,
    "test_rs": 0,
    "src_py": 65,
    "src_rs": 0,
    "test_total": 39,
    "src_total": 65,
    "has_coverage": 0,
    "has_pytest_config": 1
  },
  "D": {
    "bare_except": 0,
    "except_exception": 0,
    "noqa_suppressions": 31
  },
  "E": {
    "benchmark_files": 0,
    "cache_decorators": 0
  },
  "F": {
    "todo_fixme": 0,
    "duplicate_risk": 0
  },
  "G": {
    "req_lockfiles": 1,
    "req_files": 1
  },
  "H": {
    "secrets_raw": 0,
    "bandit_cfg": 0,
    "security_md": 1
  },
  "I": {
    "env_example": 1,
    "config_files": 3
  },
  "J": {
    "logging_refs": 22,
    "metrics_refs": 9
  },
  "K": {
    "suppressions": 31,
    "todo_total": 0
  },
  "L": {
    "workflow_files": 10,
    "precommit_config": 1
  },
  "M": {
    "dockerfile": 1,
    "compose_files": 1
  },
  "N": {
    "license": 1,
    "copyright_headers": 103,
    "contributing": 1
  },
  "O": {
    "claude_md": 1,
    "agents_md": 1,
    "claude_lines": 90,
    "agents_lines": 110
  },
  "code_files": 138,
  "src_loc": 9852,
  "test_loc": 8019,
  "branch_protection": false
}
```