# Security Policy

## Supported Versions

The following versions of Movement Optimizer are currently supported with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Movement Optimizer, please report it responsibly:

1. **Do not** open a public issue or PR describing the vulnerability.
2. Send an email to the maintainers with:
   - A description of the vulnerability
   - Steps to reproduce (if applicable)
   - Potential impact assessment
   - Suggested mitigation (if any)

We aim to acknowledge receipt within 48 hours and provide a timeline for remediation within 7 days.

## Security Best Practices

When deploying Movement Optimizer:

- Keep dependencies up to date
- Use the provided lockfile (`uv.lock`) for reproducible builds
- Review the `Dockerfile` and `docker-compose.yml` for security hardening
- Ensure the `.env` file (not committed) contains secure credentials
- Run the application behind a reverse proxy with TLS termination

## Disclosure Policy

We follow a coordinated disclosure policy. Once a fix is available, we will:
<<<<<<< HEAD
=======

> > > > > > > origin/main

1. Release a patched version
2. Publish a security advisory
3. Credit the reporter (unless anonymity is requested)

## Security-Related Configuration

- `mypy.ini` — type safety configuration
- `ruff.toml` — linting rules including security-related checks
- `.pre-commit-config.yaml` — pre-commit hooks for security scanning

---

<<<<<<< HEAD
_Last updated: 2026-04-27_
=======
_Last updated: 2026-04-27_

> > > > > > > origin/main
