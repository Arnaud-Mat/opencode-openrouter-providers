#!/usr/bin/env python3
"""
opencode-openrouter-providers
=============================

OpenCode does not auto-discover the individual providers behind an
OpenRouter model. The second dropdown in the prompt bar (the *variant*
selector, shown as "Default") only lists what you declare yourself.

This script fetches every model from OpenRouter's public API, and for each
model that is served by more than one provider it writes one variant per
provider into your `opencode.jsonc`. The result: pick a model, and the
variant dropdown lets you choose which upstream provider serves it.

No API key required — OpenRouter's models/endpoints endpoints are public.

Usage
-----
    python3 gen-providers.py                 # update the default config
    python3 gen-providers.py --dry-run       # show what would change
    python3 gen-providers.py --config PATH   # target another config file
    python3 gen-providers.py --min-providers 3
    python3 gen-providers.py --models deepseek/deepseek-v4.1-flash,openai/gpt-5

Re-run it any time to refresh providers and prices.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

API = "https://openrouter.ai/api/v1"
PROVIDER = "openrouter"
AUTO_LABEL = "Auto (OpenRouter)"
SCHEMA = "https://opencode.ai/config.json"

DEFAULT_CONFIG = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
    "opencode",
    "opencode.jsonc",
)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def _get(url: str, retries: int = 3):
    last = None
    for _ in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001 - best effort, retried
            last = e
            time.sleep(1)
    if os.environ.get("OPENCODE_PROVIDERS_VERBOSE"):
        print(f"  ! {url}: {last}", file=sys.stderr)
    return None


def fetch_model_ids() -> list[str]:
    data = _get(f"{API}/models")
    if not data or "data" not in data:
        raise SystemExit("Could not fetch the OpenRouter model list.")
    return [m["id"] for m in data["data"]]


def fetch_endpoints(model_id: str):
    """Return [(provider_name, tag, completion_price)] for one model."""
    data = _get(f"{API}/models/{model_id}/endpoints")
    if not data:
        return model_id, []
    out = []
    for e in data.get("data", {}).get("endpoints", []):
        tag = e.get("tag")
        if not tag:
            continue
        try:
            price = float((e.get("pricing") or {}).get("completion", 0) or 0)
        except (TypeError, ValueError):
            price = float("inf")
        out.append((e.get("provider_name") or tag, tag, price))
    return model_id, out


# --------------------------------------------------------------------------- #
# JSONC
# --------------------------------------------------------------------------- #
def strip_jsonc(text: str) -> str:
    """Best-effort JSONC -> JSON: drop // and /* */ comments and trailing commas."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def load_config(path: str) -> dict:
    if not os.path.exists(path):
        return {"$schema": SCHEMA}
    with open(path, encoding="utf-8") as f:
        return json.loads(strip_jsonc(f.read()))


# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
def build_variants(endpoints, allow_fallbacks: bool):
    """One variant per provider. Cheapest last, so it stays visible in the TUI
    menu (which is bottom-anchored and clips the top when the list is long)."""
    seen: dict[str, tuple[str, float]] = {}
    for name, tag, price in endpoints:
        if tag not in seen or price < seen[tag][1]:
            seen[tag] = (name, price)
    if len(seen) < 2:
        return None

    items = sorted(seen.items(), key=lambda kv: (-kv[1][1], kv[1][0]))
    variants, used = {}, set()
    for tag, (name, _price) in items:
        label = name
        if label in used:
            label = f"{name} ({tag})"
        used.add(label)
        variants[label] = {
            "provider": {"only": [tag], "allow_fallbacks": allow_fallbacks}
        }
    variants[AUTO_LABEL] = {"provider": {"sort": "price"}}
    return variants


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--config", default=DEFAULT_CONFIG,
                    help=f"opencode config to update (default: {DEFAULT_CONFIG})")
    ap.add_argument("--min-providers", type=int, default=2,
                    help="only add variants to models with at least N providers (default: 2)")
    ap.add_argument("--models", default=None,
                    help="comma-separated model ids to limit the run to")
    ap.add_argument("--allow-fallbacks", action="store_true",
                    help="let OpenRouter fall back to another provider if the chosen one is down")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the result without writing anything")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    ids = args.models.split(",") if args.models else fetch_model_ids()
    ids = [i.strip() for i in ids if i.strip()]

    print(f"Fetching providers for {len(ids)} model(s)...")
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(fetch_endpoints, ids))

    generated: dict[str, dict] = {}
    for model_id, endpoints in results:
        variants = build_variants(endpoints, args.allow_fallbacks)
        if variants and len(variants) - 1 >= args.min_providers:
            generated[model_id] = variants

    if not generated:
        print("Nothing to do (no model with enough providers).")
        return 0

    cfg = load_config(args.config)
    prov = cfg.setdefault("provider", {}).setdefault(PROVIDER, {})
    models_cfg = prov.setdefault("models", {})
    for model_id, variants in generated.items():
        models_cfg.setdefault(model_id, {})["variants"] = variants

    total = sum(len(v) for v in generated.values())
    print(f"{len(generated)} model(s) with a provider choice, {total} variants total.")

    if args.dry_run:
        print("--dry-run: nothing written.")
        return 0

    os.makedirs(os.path.dirname(args.config) or ".", exist_ok=True)
    if os.path.exists(args.config) and not args.no_backup:
        shutil.copy(args.config, args.config + ".bak")
    with open(args.config, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {args.config}")
    print("Restart OpenCode for the changes to take effect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())