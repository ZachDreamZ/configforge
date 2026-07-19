"""End-to-end example: build app config by merging a static layer with live
data fetched from a free, no-auth public API (dog.ceo), then validate it.

Run:  python examples/live_config_example.py
This demonstrates ConfigForge resolving config that includes data pulled from
a real, audited free API at runtime.
"""
import json
import sys
import urllib.request

sys.path.insert(0, "src")

from configforge import forge, Layer, load_schema  # noqa: E402


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "configforge-example/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    # 1) Static base config
    base = Layer.from_dict(
        {
            "app": "pet-wall",
            "features": {"random_image": True},
            "limits": {"max_requests": 100},
        },
        name="base",
    )

    # 2) Live data from a free, no-auth API (audited: https://dog.ceo)
    try:
        live = fetch("https://dog.ceo/api/breeds/image/random")
        live_layer = Layer.from_dict(
            {"runtime": {"image_url": live["message"], "status": live["status"]}}, name="live:dog.ceo"
        )
    except Exception as exc:  # network may be unavailable in some CI
        print(f"warning: could not reach free API ({exc}); using offline fallback")
        live_layer = Layer.from_dict(
            {"runtime": {"image_url": "https://dog.ceo/", "status": "offline"}}, name="live:fallback"
        )

    # 3) Schema
    schema = {
        "fields": {
            "app": {"type": "str", "required": True},
            "features": {"type": "dict"},
            "limits": {"type": "dict"},
            "runtime": {"type": "dict", "required": True},
        }
    }

    config = forge(base, live_layer, schema=schema)

    print(json.dumps(config.data, indent=2, sort_keys=True))
    assert config["app"] == "pet-wall"
    assert "image_url" in config["runtime"]
    print("\nOK: resolved config merges static + live free-API data and passes schema.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
