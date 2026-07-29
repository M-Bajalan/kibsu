# Security Policy

## Reporting a vulnerability

Use GitHub's private vulnerability reporting: the **Report a vulnerability** button
under this repository's **Security** tab. Reports go privately to the maintainer.
Expect a first response within a week.

Please do not open public issues for suspected vulnerabilities.

## Scope

kibsu is a read-only, stdlib-only analysis tool with no network access. The
highest-value reports are anything that makes it write outside its declared
outputs, execute content from a scanned repository, or leak scanned content.

## Supported versions

Only the latest release on PyPI is supported.
