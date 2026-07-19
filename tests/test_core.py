"""Tests for ConfigForge core behaviour."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from configforge import (  # noqa: E402
    ConfigForgeError,
    Layer,
    MergeConflictError,
    ValidationError,
    _coerce,
    _flatten_env,
    _validate_against_schema,
    decrypt_secrets,
    encrypt_secrets,
    forge,
    generate_key,
    load_schema,
)


def test_coerce_bool_strings():
    assert _coerce("true", "bool") is True
    assert _coerce("FALSE", "bool") is False
    assert _coerce("yes", "bool") is True
    assert _coerce("0", "bool") is False


def test_coerce_int_rejects_bool():
    import pytest

    with pytest.raises(ValidationError):
        _coerce(True, "int")


def test_validate_required_missing():
    import pytest

    schema = {"fields": {"port": {"type": "int", "required": True}}}
    with pytest.raises(ValidationError):
        _validate_against_schema({}, schema)


def test_validate_applies_default():
    schema = {"fields": {"host": {"type": "str", "default": "localhost"}}}
    data: dict = {}
    _validate_against_schema(data, schema)
    assert data["host"] == "localhost"


def test_validate_min_max():
    import pytest

    schema = {"fields": {"port": {"type": "int", "min": 1, "max": 10}}}
    with pytest.raises(ValidationError):
        _validate_against_schema({"port": 99}, schema)
    # valid passes without raising
    _validate_against_schema({"port": 5}, schema)


def test_validate_additional_false():
    import pytest

    schema = {"fields": {"a": {"type": "str"}}, "additional": False}
    with pytest.raises(ValidationError):
        _validate_against_schema({"a": "x", "b": "y"}, schema)


def test_flatten_env_nested():
    env = {"APP__DB__HOST": "localhost", "APP__DB__PORT": "5432", "OTHER": "x"}
    flat = _flatten_env("APP__", env)
    assert flat == {"DB": {"HOST": "localhost", "PORT": "5432"}}


def test_deep_merge_nested_conflict_raises():
    import pytest

    base = {"db": {"host": "a", "port": 1}}
    overlay = {"db": {"port": 2}}
    from configforge import _deep_merge

    with pytest.raises(MergeConflictError):
        _deep_merge(dict(base), overlay)


def test_deep_merge_nested_no_conflict():
    base = {"db": {"host": "a"}}
    overlay = {"db": {"port": 2}}
    from configforge import _deep_merge

    merged = _deep_merge(dict(base), overlay)
    assert merged == {"db": {"host": "a", "port": 2}}


def test_merge_conflict_scalar():
    import pytest

    a = Layer.from_dict({"port": 1}, "a")
    b = Layer.from_dict({"port": 2}, "b")
    with pytest.raises(MergeConflictError):
        forge(a, b)


def test_merge_no_conflict_equal_scalar():
    a = Layer.from_dict({"port": 1}, "a")
    b = Layer.from_dict({"port": 1}, "b")
    cfg = forge(a, b)
    assert cfg["port"] == 1


def test_forge_with_schema_validation():
    a = Layer.from_dict({"port": "8080"}, "a")
    schema = {"fields": {"port": {"type": "int", "min": 1, "max": 65535}}}
    cfg = forge(a, schema=schema)
    assert cfg["port"] == 8080


def test_forge_env_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("APP__NAME", "svc")
    monkeypatch.setenv("APP__LIMIT", "5")
    a = Layer.from_dict({"name": "default"}, "a")
    cfg = forge(a, env_prefix="APP__")
    assert cfg["NAME"] == "svc"
    assert cfg["LIMIT"] == "5"


def test_layer_from_json_file(tmp_path):
    p = tmp_path / "layer.json"
    p.write_text(json.dumps({"k": "v"}))
    layer = Layer.from_json_file(str(p))
    assert layer.data == {"k": "v"}


def test_layer_from_json_file_invalid(tmp_path):
    import pytest

    p = tmp_path / "bad.json"
    p.write_text("{not json")
    with pytest.raises(ConfigForgeError):
        Layer.from_json_file(str(p))


def test_load_schema_invalid(tmp_path):
    import pytest

    p = tmp_path / "s.json"
    p.write_text("nope")
    with pytest.raises(ConfigForgeError):
        load_schema(str(p))


def test_forge_secrets_merge(monkeypatch):
    a = Layer.from_dict({"public": "yes"}, "a")
    secrets = {"api_key": "secret-value"}
    cfg = forge(a, secrets=secrets)
    assert cfg["api_key"] == "secret-value"
    assert cfg["public"] == "yes"


def test_decrypt_secrets_requires_key(tmp_path):
    import pytest

    p = tmp_path / "secrets.token"
    p.write_bytes(b"dummy-token")
    with pytest.raises(ConfigForgeError):
        decrypt_secrets(str(p))


def test_to_json_sorted():
    cfg = forge(Layer.from_dict({"b": 1, "a": 2}))
    assert cfg.to_json() == json.dumps({"a": 2, "b": 1}, indent=2, sort_keys=True)


def test_secrets_roundtrip():
    key = generate_key()
    secrets = {"api_key": "super-secret", "nested": {"token": "abc"}}
    token = encrypt_secrets(secrets, key)
    assert isinstance(token, bytes)
    # token must not contain plaintext
    assert b"super-secret" not in token
    decrypted = decrypt_secrets_from_token(token, key)
    assert decrypted == secrets


def test_decrypt_wrong_key_fails():
    import pytest

    key1 = generate_key()
    key2 = generate_key()
    token = encrypt_secrets({"x": "y"}, key1)
    with pytest.raises(ConfigForgeError):
        decrypt_secrets_from_token(token, key2)


def test_forge_with_real_secrets(tmp_path):
    key = generate_key()
    token = encrypt_secrets({"db": {"password": "hunter2"}}, key)
    sp = tmp_path / "secrets.token"
    sp.write_bytes(token)
    base = Layer.from_dict({"db": {"host": "localhost", "port": 5432}})
    cfg = forge(base, secrets=decrypt_secrets(str(sp), key=key))
    assert cfg["db"]["password"] == "hunter2"
    assert cfg["db"]["host"] == "localhost"


def decrypt_secrets_from_token(token: bytes, key: str) -> dict:
    import tempfile

    with tempfile.NamedTemporaryFile(delete=False, suffix=".token") as fh:
        fh.write(token)
        path = fh.name
    try:
        return decrypt_secrets(path, key=key)
    finally:
        os.unlink(path)
