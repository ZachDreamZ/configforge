"""Generate demo fixtures and run an end-to-end audit of ConfigForge.

Writes outputs to examples/ and prints a machine-readable evidence block.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))

from configforge import (  # noqa: E402
    decrypt_secrets,
    encrypt_secrets,
    forge,
    generate_key,
    load_schema,
    Layer,
)

KEY = generate_key()
with open(os.path.join(HERE, ".key.txt"), "w") as fh:
    fh.write(KEY)

base = {"app": "demo", "server": {"host": "0.0.0.0", "port": 8080}, "debug": False}
override = {"server": {"port": 9090}, "debug": True}
schema = {
    "fields": {
        "server": {"type": "dict"},
        "debug": {"type": "bool"},
        "app": {"type": "str", "required": True},
    }
}
secrets = {"db": {"password": "s3cr3t-pw"}}

with open(os.path.join(HERE, "base.json"), "w") as fh:
    json.dump(base, fh, indent=2)
with open(os.path.join(HERE, "override.json"), "w") as fh:
    json.dump(override, fh, indent=2)
with open(os.path.join(HERE, "schema.json"), "w") as fh:
    json.dump(schema, fh, indent=2)

token = encrypt_secrets(secrets, KEY)
with open(os.path.join(HERE, "secrets.token"), "wb") as fh:
    fh.write(token)


def run_cli(args):
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(HERE, "..", "src")
    return subprocess.run(
        [sys.executable, "-m", "configforge.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


print("=== AUDIT: ConfigForge end-to-end ===")

# 1) merge + validate + env (override wins on nested scalar via no-fail-on-conflict,
#    demonstrating intentional override; conflicts are caught separately in step 3)
env = dict(os.environ)
env["PYTHONPATH"] = os.path.join(HERE, "..", "src")
env["APP__FEATURE__NEW"] = "true"
r1 = subprocess.run(
    [
        sys.executable, "-m", "configforge.cli",
        "-l", os.path.join(HERE, "base.json"),
        "-l", os.path.join(HERE, "override.json"),
        "--no-fail-on-conflict",
        "--env-prefix", "APP__",
        "--schema", os.path.join(HERE, "schema.json"),
    ],
    capture_output=True,
    text=True,
    env=env,
)
assert r1.returncode == 0, r1.stderr
merged = json.loads(r1.stdout)
print("merge+validate+env OK:", merged)
assert merged["server"]["port"] == 9090
assert merged["debug"] is True
assert merged["FEATURE"]["NEW"] == "true"

# 2) secrets
r2 = run_cli(
    [
        "-l", os.path.join(HERE, "base.json"),
        "--secrets", os.path.join(HERE, "secrets.token"),
        "--key", KEY,
    ]
)
assert r2.returncode == 0, r2.stderr
with_secrets = json.loads(r2.stdout)
print("secrets merge OK:", with_secrets)
assert with_secrets["db"]["password"] == "s3cr3t-pw"

# 3) conflict detection
conflict_base = os.path.join(HERE, "cb.json")
conflict_over = os.path.join(HERE, "co.json")
with open(conflict_base, "w") as fh:
    json.dump({"port": 1}, fh)
with open(conflict_over, "w") as fh:
    json.dump({"port": 2}, fh)
r3 = run_cli(["-l", conflict_base, "-l", conflict_over])
print("conflict detection rc:", r3.returncode, "(expect 1)")
assert r3.returncode == 1

# 4) generate-key
r4 = run_cli(["--generate-key"])
assert r4.returncode == 0 and len(r4.stdout.strip()) > 0
print("generate-key OK:", r4.stdout.strip()[:12], "...")

print("=== ALL AUDIT CHECKS PASSED ===")
