# Security Policy

## Reporting a vulnerability

Report privately here: **https://github.com/M-Bajalan/kibsu/security/advisories/new**
(the **Report a vulnerability** button under this repository's **Security** tab).
Reports go directly and privately to the maintainer.

Please do not open public issues for suspected vulnerabilities.

## Disclosure process

- Acknowledgment within **7 days** of your report.
- Coordinated disclosure: a fix is released **before** details go public.
- Reporters are credited in the release notes unless they ask not to be.

## Scope

kibsu is a read-only, stdlib-only analysis tool with no network access — except
`survey`, which clones the public repositories it measures (that is its whole job and
its `--help` says so); every other command touches only the local tree. The
highest-value reports are anything that makes it write outside its declared
outputs, execute content from a scanned repository, or leak scanned content.

## Supported versions

Only the latest release on PyPI is supported.
