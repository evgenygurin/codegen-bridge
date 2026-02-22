#!/usr/bin/env python3
"""OpenAPI spec sync and governance CLI.

Fetch the live spec from Codegen's API, detect drift against the local
copy, validate structural integrity, and check endpoint parity.

Usage::

    # Check for drift (no modifications, exit 1 if drifted)
    python scripts/openapi_sync.py drift

    # Update local spec from live API
    python scripts/openapi_sync.py sync

    # Validate local spec integrity (no network required)
    python scripts/openapi_sync.py validate

    # Check endpoint parity (no network required)
    python scripts/openapi_sync.py parity

    # Run all offline governance checks (validate + parity)
    python scripts/openapi_sync.py check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path so bridge.* imports work
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from bridge.openapi_utils import (  # noqa: E402
    LIVE_SPEC_URL,
    SPEC_PATH,
    diff_specs,
    load_raw_spec,
    validate_endpoint_parity,
    validate_spec_integrity,
)


def _fetch_live_spec() -> dict[str, Any]:
    """Fetch the live OpenAPI spec from the Codegen API.

    Uses synchronous httpx since this is a CLI script.
    """
    import httpx

    resp = httpx.get(LIVE_SPEC_URL, timeout=30.0, follow_redirects=True)
    resp.raise_for_status()
    result: dict[str, Any] = resp.json()
    return result


def _normalize_spec(spec: dict[str, Any]) -> str:
    """Serialize spec as normalized JSON (sorted keys, 2-space indent)."""
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ── Commands ──────────────────────────────────────────────────────


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate local spec structural integrity."""
    print("Validating spec integrity...")
    errors = validate_spec_integrity()
    if errors:
        print(f"\n❌ {len(errors)} integrity error(s):")
        for err in errors:
            print(f"  • {err}")
        return 1
    print("✅ Spec integrity OK")
    return 0


def cmd_parity(args: argparse.Namespace) -> int:
    """Check endpoint parity (all operationIds accounted for)."""
    print("Checking endpoint parity...")
    result = validate_endpoint_parity()

    ok = True
    if result["unmapped"]:
        ok = False
        print(f"\n❌ {len(result['unmapped'])} unmapped operationId(s):")
        for op_id in sorted(result["unmapped"]):
            print(f"  • {op_id}")
        print(
            "\n  Add to TOOL_NAMES (if auto-generated) or "
            "EXCLUDED_OPERATIONS (if manual) in bridge/openapi_utils.py"
        )

    if result["stale_tool_names"]:
        ok = False
        print(f"\n⚠️  {len(result['stale_tool_names'])} stale TOOL_NAMES entry/ies:")
        for op_id in sorted(result["stale_tool_names"]):
            print(f"  • {op_id}")
        print("\n  These operationIds no longer exist in the spec — remove from TOOL_NAMES")

    if result["stale_excluded"]:
        ok = False
        print(f"\n⚠️  {len(result['stale_excluded'])} stale EXCLUDED_OPERATIONS entry/ies:")
        for op_id in sorted(result["stale_excluded"]):
            print(f"  • {op_id}")
        print(
            "\n  These operationIds no longer exist in the spec — remove from EXCLUDED_OPERATIONS"
        )

    if ok:
        print("✅ Endpoint parity OK — all operationIds accounted for")
    return 0 if ok else 1


def cmd_check(args: argparse.Namespace) -> int:
    """Run all offline governance checks (validate + parity)."""
    rc = cmd_validate(args)
    print()
    rc |= cmd_parity(args)
    return rc


def cmd_drift(args: argparse.Namespace) -> int:
    """Detect drift between local and live spec."""
    print(f"Fetching live spec from {LIVE_SPEC_URL}...")
    try:
        remote = _fetch_live_spec()
    except Exception as exc:
        print(f"❌ Failed to fetch live spec: {exc}")
        return 2

    local = load_raw_spec()
    result = diff_specs(local, remote)

    has_drift = bool(
        result["added_endpoints"]
        or result["removed_endpoints"]
        or result["added_schemas"]
        or result["removed_schemas"]
    )

    print(f"\nLocal version:  {result['version_local']}")
    print(f"Remote version: {result['version_remote']}")

    if result["added_endpoints"]:
        print(f"\n➕ {len(result['added_endpoints'])} new endpoint(s) in live API:")
        for method, path in result["added_endpoints"]:
            print(f"  {method:6s} {path}")

    if result["removed_endpoints"]:
        print(f"\n➖ {len(result['removed_endpoints'])} endpoint(s) removed from live API:")
        for method, path in result["removed_endpoints"]:
            print(f"  {method:6s} {path}")

    if result["added_schemas"]:
        print(f"\n📦 {len(result['added_schemas'])} new schema(s):")
        for name in result["added_schemas"]:
            print(f"  • {name}")

    if result["removed_schemas"]:
        print(f"\n🗑️  {len(result['removed_schemas'])} removed schema(s):")
        for name in result["removed_schemas"]:
            print(f"  • {name}")

    if has_drift:
        print("\n⚠️  Drift detected — run `python scripts/openapi_sync.py sync` to update")
        return 1
    else:
        print("\n✅ No drift — local spec matches live API")
        return 0


def cmd_sync(args: argparse.Namespace) -> int:
    """Fetch the live spec and update the local copy."""
    print(f"Fetching live spec from {LIVE_SPEC_URL}...")
    try:
        remote = _fetch_live_spec()
    except Exception as exc:
        print(f"❌ Failed to fetch live spec: {exc}")
        return 2

    local = load_raw_spec()
    result = diff_specs(local, remote)

    has_changes = bool(
        result["added_endpoints"]
        or result["removed_endpoints"]
        or result["added_schemas"]
        or result["removed_schemas"]
    )

    if not has_changes:
        print("✅ Already up to date — no changes needed")
        return 0

    # Write normalized spec
    normalized = _normalize_spec(remote)
    SPEC_PATH.write_text(normalized, encoding="utf-8")
    print(f"✅ Updated {SPEC_PATH}")

    print("\nChanges:")
    if result["added_endpoints"]:
        print(f"  ➕ {len(result['added_endpoints'])} new endpoint(s)")
    if result["removed_endpoints"]:
        print(f"  ➖ {len(result['removed_endpoints'])} removed endpoint(s)")
    if result["added_schemas"]:
        print(f"  📦 {len(result['added_schemas'])} new schema(s)")
    if result["removed_schemas"]:
        print(f"  🗑️  {len(result['removed_schemas'])} removed schema(s)")

    # Run parity check on the new spec
    print("\nRunning parity check on updated spec...")
    parity = validate_endpoint_parity(remote)
    if parity["unmapped"]:
        print(f"\n⚠️  {len(parity['unmapped'])} new operationId(s) need mapping:")
        for op_id in sorted(parity["unmapped"]):
            print(f"  • {op_id}")
        print("\n  Add to TOOL_NAMES or EXCLUDED_OPERATIONS in bridge/openapi_utils.py")
        return 1

    return 0


# ── CLI ──────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="OpenAPI spec sync and governance CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="Validate local spec integrity (offline)")
    subparsers.add_parser("parity", help="Check endpoint parity (offline)")
    subparsers.add_parser("check", help="Run all offline governance checks")
    subparsers.add_parser("drift", help="Detect drift against live API (network)")
    subparsers.add_parser("sync", help="Update local spec from live API (network)")

    args = parser.parse_args()

    commands = {
        "validate": cmd_validate,
        "parity": cmd_parity,
        "check": cmd_check,
        "drift": cmd_drift,
        "sync": cmd_sync,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
