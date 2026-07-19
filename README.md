# ConfigForge

<p align="center">
  <img src="assets/logo.svg" alt="ConfigForge logo" width="160" height="160" />
</p>

<p align="center">
  <strong>Layered, schema-aware configuration with encrypted secrets for 12-factor apps.</strong>
</p>

<p align="center">
  <a href="https://github.com/ZachDreamZ/configforge/actions/workflows/ci.yml"><img src="https://github.com/ZachDreamZ/configforge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://github.com/ZachDreamZ/configforge/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9%2B-3776AB.svg" alt="Python 3.9+"></a>
  <a href="https://pypi.org/project/configforge/"><img src="https://img.shields.io/badge/pypi-0.1.0-ff69b4.svg" alt="PyPI"></a>
  <img src="https://img.shields.io/badge/coverage-22%20tests%20passing-brightgreen.svg" alt="Tests passing">
  <img src="https://img.shields.io/badge/platforms-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg" alt="Platforms">
</p>

---

ConfigForge merges configuration from **multiple layered sources** — default
files, environment-specific overlays, environment variables, and encrypted
secrets — into a single resolved config, **validates** it against a schema, and
exposes it as a clean Python object or JSON.

It is dependency-free for the core path (merge + validate + env). The optional
encrypted-secrets feature uses [`cryptography`](https://pypi.org/project/cryptography)
under a Fernet envelope.

## Why

Most config libraries either (a) just read one file, or (b) silently let later
values clobber earlier ones. ConfigForge does three things most don't, in one
small package:

- **Strict conflict detection** — a scalar set differently by two layers is a
  hard error by default, so "who wins?" bugs surface at startup, not in prod.
- **Schema validation at resolve time** — types, required fields, ranges, and
  patterns are checked when config is built, with helpful messages.
- **Encrypted secrets as a first-class layer** — decrypt a Fernet token and
  merge it like any other layer, no separate codepath.

## Install

```bash
pip install configforge            # core only (no deps)
pip install "configforge[secrets]" # + encrypted secrets support
```

Or build from source:

```bash
git clone https://github.com/ZachDreamZ/configforge.git
cd configforge
pip install -e ".[dev,secrets]"
```

## Quick start

```python
from configforge import forge, Layer

base = Layer.from_dict({"app": "demo", "server": {"host": "0.0.0.0", "port": 8080}})
override = Layer.from_dict({"server": {"port": 9090}})

config = forge(base, override)
print(config["server"]["port"])  # 9090 (later layer wins, nested merge)
```

## CLI

```bash
# Merge two JSON layers, fold in APP__* env vars, validate against a schema
configforge \
  -l base.json -l override.json \
  --env-prefix APP__ \
  --schema schema.json

# Decrypt a Fernet secrets token and merge it in
export CONFIGFORGE_KEY="<32-byte base64 key>"
configforge -l base.json --secrets secrets.token

# Generate a fresh key
configforge --generate-key
```

### Real demo output

Merging `base.json` + `override.json` + env `APP__FEATURE__NEW=true`, validated
by `schema.json`:

```json
{
  "FEATURE": { "NEW": "true" },
  "app": "demo",
  "debug": true,
  "server": { "host": "0.0.0.0", "port": 9090 }
}
```

Decrypting `secrets.token` and merging:

```json
{
  "app": "demo",
  "db": { "password": "s3cr3t-pw" },
  "debug": false,
  "server": { "host": "0.0.0.0", "port": 8080 }
}
```

A conflicting scalar (`{"port":1}` vs `{"port":2}`) exits non-zero:

```
configforge: error: conflicting value for 'port': 1 vs 2
```

## Features

- **Layered merge** — any number of `Layer` sources; later wins on nested dicts.
- **Conflict safety** — scalar collisions raise `MergeConflictError` (disable
  with `--no-fail-on-conflict` for intentional overrides).
- **Schema validation** — `type`, `required`, `default`, `min`/`max`,
  `pattern`, and `additional: false` (reject unknown keys).
- **Env folding** — `APP__DB__HOST` becomes `{"DB": {"HOST": ...}}`.
- **Encrypted secrets** — Fernet envelope via the `secrets` extra; decrypt and
  merge like any other layer.
- **Zero core dependencies**, Python 3.9+, works on Windows / Linux / macOS.
- **Fully tested** — 22 unit + integration tests, CI on 3 OS × 4 Python
  versions.

## Schema reference

```json
{
  "fields": {
    "port":  { "type": "int",  "required": true, "min": 1, "max": 65535 },
    "host":  { "type": "str",  "default": "localhost", "pattern": "^[a-z0-9.-]+$" },
    "debug": { "type": "bool" }
  },
  "additional": false
}
```

| Key        | Meaning                                                        |
| ---------- | -------------------------------------------------------------- |
| `type`     | `str` `int` `float` `bool` `list` `dict` `any`                 |
| `required` | error if missing and no `default`                              |
| `default`  | value used when the field is absent                            |
| `min`/`max` | numeric bounds (int/float)                                   |
| `pattern`  | regex the string must match                                    |
| `additional` | `false` rejects keys not declared in `fields`                |

## Python API

```python
from configforge import forge, Layer, load_schema, decrypt_secrets

layers = [Layer.from_json_file("base.json"), Layer.from_json_file("override.json")]
schema = load_schema("schema.json")
secrets = decrypt_secrets("secrets.token", key=KEY)

config = forge(*layers, schema=schema, secrets=secrets, env_prefix="APP__")

config.get("server.port")        # via the underlying dict
config["server"]["host"]
"debug" in config
config.to_json()                  # pretty JSON string
```

## Architecture

```
Layer (dict source)  ─┐
Layer (json file)    ─┤
env (APP__*)         ─┼─►  forge()  ─►  deep merge  ─►  validate(schema)  ─►  Config
secrets (Fernet)     ─┘                    │
                                           └─► MergeConflictError on scalar clash
```

The merge is pure and deterministic; validation mutates nothing but fills in
declared defaults. Secrets are decrypted to a plain dict before merge, so they
are indistinguishable from any other layer.

## Examples

See [`examples/`](examples/) for runnable fixtures and `make_demo.py`, which
performs an end-to-end audit (merge + validate + env, secrets round-trip,
conflict detection, key generation) and asserts the results.

## Development

```bash
pip install -e ".[dev,secrets]"
pytest
```

## Roadmap

- YAML / TOML layer loaders (via optional extras).
- Remote layers (HTTP/S3) behind a pluggable `LayerSource` protocol.
- `configforge diff` to visualize what each layer contributed.

## License

[MIT](LICENSE) © ZachDreamZ
