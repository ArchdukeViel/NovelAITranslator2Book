# Security Policy

## Reporting a vulnerability

**Do not open a public issue for security defects.**

- Report privately via GitHub Private Vulnerability Reporting on this
  repository (Security → Report a vulnerability).
- Include: affected component and version, steps to reproduce (sanitized),
  impact, and suggested fix if known.
- Never include secrets, tokens, `.env` contents, DB URLs, or credential
  fragments in a report.

## Response

- The maintainer will acknowledge within 7 days.
- Critical / high issues are fixed on a private branch and disclosed after
  a patch is published.

## Supported versions

- Only the latest `main` is supported.
- Active pull requests are reviewed through CodeQL, GitGuardian, dependency review, and required CI before merge.

## Security features enabled

- Secret scanning + push protection.
- CodeQL (actions, javascript-typescript, python).
- GitGuardian secret scan on push and pull_request.
- Dependabot security updates (uv, pip, npm).
