"""ConfigForge: layered, schema-aware configuration with encrypted secrets.

ConfigForge merges configuration from multiple layered sources (default files,
environment-specific overlays, environment variables, and encrypted secrets)
into a single resolved configuration, validates it against a schema, and
exposes it as a clean Python object or JSON.

It is intentionally dependency-free for the core merge/validate path (only
the optional secrets feature pulls in `age`/`cryptography`).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ConfigForgeError(Exception):
    """Base class for all ConfigForge errors."""


class ValidationError(ConfigForgeError):
    """Raised when a resolved config violates its schema."""


class MergeConflictError(ConfigForgeError):
    """Raised when two layers set the same scalar key with different values."""


class LayerLoadError(ConfigForgeError):
    """Raised when a layer file cannot be read or parsed."""


# ---------------------------------------------------------------------------
# Schema primitives (tiny, dependency-free)
# ---------------------------------------------------------------------------


_VALID_TYPES = {"str", "int", "float", "bool", "list", "dict", "any"}


def _coerce(value: Any, typ: str) -> Any:
    if typ == "any":
        return value
    if typ == "str":
        return str(value)
    if typ == "int":
        if isinstance(value, bool):
            raise ValidationError("expected int but got bool")
        return int(value)
    if typ == "float":
        if isinstance(value, bool):
            raise ValidationError("expected float but got bool")
        return float(value)
    if typ == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on"}:
                return True
            if lowered in {"false", "0", "no", "off"}:
                return False
            raise ValidationError(f"cannot coerce {value!r} to bool")
        return bool(value)
    if typ == "list":
        if isinstance(value, list):
            return value
        raise ValidationError(f"expected list but got {type(value).__name__}")
    if typ == "dict":
        if isinstance(value, dict):
            return value
        raise ValidationError(f"expected dict but got {type(value).__name__}")
    raise ValidationError(f"unknown schema type {typ!r}")


def _validate_against_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> None:
    """Validate resolved data against a schema dict.

    Schema format:
        {
          "fields": {
             "port": {"type": "int", "required": True, "min": 1, "max": 65535},
             "host": {"type": "str", "required": False, "default": "localhost"},
          },
          "additional": False   # disallow keys not in schema
        }
    """
    fields = schema.get("fields", {})
    additional = schema.get("additional", True)

    known = set(fields.keys())
    for key, spec in fields.items():
        present = key in data
        if not present:
            if spec.get("required", False):
                raise ValidationError(f"missing required field {key!r}")
            if "default" in spec:
                data[key] = spec["default"]
            continue
        value = data[key]
        typ = spec.get("type", "any")
        try:
            value = _coerce(value, typ)
        except (ValueError, TypeError) as exc:
            raise ValidationError(f"field {key!r}: {exc}")
        if typ in {"int", "float"}:
            if "min" in spec and value < spec["min"]:
                raise ValidationError(f"field {key!r} below min {spec['min']}")
            if "max" in spec and value > spec["max"]:
                raise ValidationError(f"field {key!r} above max {spec['max']}")
        if typ == "str" and "pattern" in spec:
            import re

            if not re.match(spec["pattern"], value):
                raise ValidationError(f"field {key!r} does not match {spec['pattern']}")
        data[key] = value

    if not additional:
        extras = set(data.keys()) - known
        if extras:
            raise ValidationError(f"unexpected fields: {sorted(extras)}")


# ---------------------------------------------------------------------------
# Layered merge
# ---------------------------------------------------------------------------


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any], path: str = "") -> Dict[str, Any]:
    """Merge overlay into base deeply. Scalars that collide must be equal."""
    for key, value in overlay.items():
        full = f"{path}.{key}" if path else key
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = _deep_merge(base[key], value, full)
        elif (
            key in base
            and base[key] != value
            and not isinstance(base[key], dict)
            and not isinstance(value, dict)
        ):
            raise MergeConflictError(
                f"conflicting value for {full!r}: {base[key]!r} vs {value!r}"
            )
        else:
            base[key] = value
    return base


def _flatten_env(prefix: str, env: Dict[str, str], sep: str = "__") -> Dict[str, Any]:
    """Convert FLAT__NESTED__KEY env vars into a nested dict."""
    out: Dict[str, Any] = {}
    for raw_key, raw_val in env.items():
        if not raw_key.startswith(prefix):
            continue
        rest = raw_key[len(prefix):]
        if not rest:
            continue
        parts = rest.strip(sep).split(sep) if sep in rest else [rest.lstrip(sep)]
        parts = [p for p in parts if p]
        if not parts:
            continue
        cur = out
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
            if not isinstance(cur, dict):
                break
        cur[parts[-1]] = raw_val
    return out


# ---------------------------------------------------------------------------
# Secrets (optional, requires the `cryptography` package)
# ---------------------------------------------------------------------------

# ConfigForge uses a Fernet-compatible envelope (AES-128-CBC + HMAC-SHA256)
# implemented through `cryptography`. Keys are 32 url-safe base64 bytes, the
# same format `age`/Fernet tooling expects, so they interoperate. Without the
# optional `cryptography` dependency the secrets feature is unavailable and a
# clear error is raised.


def _get_fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # optional dependency
        raise ConfigForgeError(
            "secrets support requires the 'cryptography' package: pip install configforge[secrets]"
        ) from exc
    return Fernet


def encrypt_secrets(data: Dict[str, Any], key: str, *, path: Optional[str] = None) -> bytes:
    """Encrypt a dict into a Fernet token. Writes to `path` if given.

    `key` is a 32-byte url-safe base64 Fernet key (see `generate_key()`).
    """
    Fernet = _get_fernet()
    token = Fernet(key).encrypt(json.dumps(data).encode("utf-8"))
    if path is not None:
        try:
            with open(path, "wb") as fh:
                fh.write(token)
        except OSError as exc:
            raise LayerLoadError(f"cannot write secrets file {path!r}: {exc}")
    return token


def decrypt_secrets(path: str, *, key: Optional[str] = None) -> Dict[str, Any]:
    """Decrypt a Fernet-encrypted JSON secrets file written by `encrypt_secrets`.

    `key` is a 32-byte url-safe base64 Fernet key. Required unless your
    deployment injects it another way.
    """
    Fernet = _get_fernet()
    if key is None:
        raise ConfigForgeError("a Fernet key is required to decrypt secrets (--key)")
    try:
        with open(path, "rb") as fh:
            token = fh.read()
    except OSError as exc:
        raise LayerLoadError(f"cannot read secrets file {path!r}: {exc}")
    try:
        plain = Fernet(key).decrypt(token)
    except Exception as exc:  # cryptography raises its own exception types
        raise ConfigForgeError(f"secrets decrypt failed: {exc}")
    try:
        return json.loads(plain.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ConfigForgeError(f"decrypted secrets are not valid JSON: {exc}")


def generate_key() -> str:
    """Return a fresh 32-byte url-safe base64 Fernet key (ASCII string)."""
    Fernet = _get_fernet()
    return Fernet.generate_key().decode("ascii")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class Layer:
    """A single configuration source."""

    data: Dict[str, Any]
    name: str = "layer"

    @classmethod
    def from_dict(cls, data: Dict[str, Any], name: str = "dict") -> "Layer":
        return cls(data=data, name=name)

    @classmethod
    def from_json_file(cls, path: str, name: Optional[str] = None) -> "Layer":
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            raise LayerLoadError(f"cannot load JSON layer {path!r}: {exc}")
        if not isinstance(data, dict):
            raise LayerLoadError(f"JSON layer {path!r} must be an object")
        return cls(data=data, name=name or path)

    @classmethod
    def from_env(
        cls, prefix: str, *, env: Optional[Dict[str, str]] = None, sep: str = "__", name: str = "env"
    ) -> "Layer":
        source = env if env is not None else dict(os.environ)
        return cls(data=_flatten_env(prefix, source, sep), name=name)


@dataclass
class Config:
    """Resolved configuration object."""

    data: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def __contains__(self, key: str) -> bool:
        return key in self.data

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.data, indent=indent, sort_keys=True)


def forge(
    *layers: Layer,
    schema: Optional[Dict[str, Any]] = None,
    secrets: Optional[Dict[str, Any]] = None,
    env_prefix: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    fail_on_conflict: bool = True,
) -> Config:
    """Merge layers (in order) and optionally validate against a schema.

    Later layers win on nested dicts; scalar conflicts raise MergeConflictError
    unless fail_on_conflict is False (then later value silently wins).
    """
    merged: Dict[str, Any] = {}
    for layer in layers:
        try:
            if fail_on_conflict:
                merged = _deep_merge(merged, dict(layer.data))
            else:
                _deep_merge_shallow_win(merged, dict(layer.data))
        except MergeConflictError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise LayerLoadError(f"merge failed for {layer.name!r}: {exc}")

    if env_prefix:
        env_layer = Layer.from_env(env_prefix, env=env).data
        merged = _deep_merge(merged, env_layer) if fail_on_conflict else _deep_merge_shallow_win(
            merged, env_layer
        )

    if secrets:
        merged = _deep_merge(merged, dict(secrets)) if fail_on_conflict else _deep_merge_shallow_win(
            merged, dict(secrets)
        )

    if schema is not None:
        _validate_against_schema(merged, schema)

    return Config(data=merged)


def _deep_merge_shallow_win(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Like _deep_merge but later scalar values always win (no conflict error)."""
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            base[key] = _deep_merge_shallow_win(base[key], value)
        else:
            base[key] = value
    return base


def load_schema(path: str) -> Dict[str, Any]:
    """Load a JSON schema file."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise LayerLoadError(f"cannot load schema {path!r}: {exc}")
