# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in ConfigForge, please **do not open a
public issue**. Instead, report it privately by opening a
[GitHub Security Advisory](https://github.com/ZachDreamZ/configforge/security/advisories/new)
on the repository, or email the maintainer.

We will acknowledge receipt within 72 hours and aim to provide a fix or
mitigation within 14 days for confirmed, exploitable issues.

## Security Design Notes

- **Secrets** are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) from the
  `cryptography` package. Decryption requires a 32-byte url-safe base64 key.
- The key should be supplied via the `CONFIGFORGE_KEY` environment variable or
  the `--key` flag. Prefer the environment variable to avoid leaking the key
  into shell history or the process list.
- Only `json.load` is used to parse layer and secrets files. No `eval`,
  `pickle`, `yaml.load`, or other code-executing deserializers are used.
- Layer files are read with an explicit `utf-8` encoding.
