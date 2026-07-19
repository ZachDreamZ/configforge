# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-19

### Added
- Core `forge()` API: layered merge of multiple `Layer` sources.
- `Layer.from_dict`, `Layer.from_json_file`, `Layer.from_env` constructors.
- Deep merge with strict scalar-conflict detection (raise `MergeConflictError`).
- `--no-fail-on-conflict` escape hatch for intentional overrides.
- Schema validation: `type`, `required`, `default`, `min`/`max`, `pattern`, `additional`.
- Environment variable folding (`APP__DB__HOST` -> `{"DB": {"HOST": ...}}`).
- Optional encrypted secrets via Fernet (`cryptography` extra): `encrypt_secrets`,
  `decrypt_secrets`, `generate_key`.
- CLI: `configforge` with layer/schema/secrets/env-prefix options.
- Test suite (22 tests) and GitHub Actions CI.
