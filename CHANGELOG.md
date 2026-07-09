# Changelog

All notable changes to `agent-trace-lite` will be documented in this file.

The format is based on Keep a Changelog, and this project uses semantic versioning.

## [Unreleased]

- Added bounded `validate` command with deterministic JSON diagnostics for malformed JSONL and invalid record fields.
- Added duplicate, orphaned, and open span lifecycle detection with validation exit codes.
- Added configurable physical-line and total-input byte limits.

## [0.1.2] - 2026-07-06

- Updated GitHub Actions workflow dependencies to current major versions.
- Modernized package license metadata to avoid current Setuptools deprecation warnings.
- Added first timestamp, last timestamp, and wall-clock runtime metrics to trace summaries.
- Added Markdown summary rendering for PR comments, issue updates, and release notes.

## [0.1.1] - 2026-06-17

- Added open span counts, event level counts, span status counts, and average duration to trace summaries.
- Updated text summary output to include the new open-span and average-duration metrics.
- Fixed GitHub Actions workflow pins to supported action versions.

## [0.1.0] - 2026-06-03

- Initial open-source release with CLI, examples, tests, GitHub workflows, security policy, and contributor docs.
