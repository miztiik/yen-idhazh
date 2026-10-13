"""Plan a bounded host-history migration; never apply or write historical sources."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from idhazh.contracts.host_migration import HistoryManifest
from idhazh.telemetry.host_history_bundle import dry_run
from idhazh.telemetry.host_history_files import HistoryLimits
from idhazh.telemetry.host_output_verify import _json, _read_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Refused: historical application is not implemented."
    )
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args(argv)
    if args.apply:
        parser.exit(
            2, "apply is not implemented; this command only prepares isolated dry-run evidence\n"
        )
    if args.workspace_root is None or args.manifest is None:
        parser.error("--workspace-root and --manifest are required for a dry-run")
    try:
        # These repository-owned, named configs are fixed inputs, not an operator
        # history scan or an arbitrary config-file discovery mechanism.
        config_root = Path(__file__).resolve().parents[2] / "config"
        experiment = json.loads((config_root / "host-telemetry-experiment.json").read_bytes())
        migration = json.loads((config_root / "host-history-migration.json").read_bytes())
        document = {
            "verification_limits": experiment["verification_limits"],
            "history_migration_limits": migration["history_migration_limits"],
        }
        limits = HistoryLimits.from_config(document)
        workspace = args.workspace_root.absolute()
        manifest_path = args.manifest if args.manifest.is_absolute() else workspace / args.manifest
        original = _json(
            _read_bytes(manifest_path, root=workspace, cap=limits.max_manifest_bytes),
            limits.verification,
        )
        if not isinstance(original, dict) or "version" not in original:
            raise ValueError("manifest requires its explicit schema version before model stamping")
        result = dry_run(
            HistoryManifest.model_validate(original),
            workspace_root=workspace,
            config_document=document,
        )
        print(
            json.dumps(
                {
                    "inventory_complete": result.inventory_complete,
                    "historical_readiness": result.historical_readiness,
                    "production_cutover_readiness": result.production_cutover_readiness,
                    "production_cutover_blocked_by": result.production_cutover_blocked_by,
                    "scope_hash": result.scope_hash,
                    "evidence_hash": result.evidence_hash,
                    "bundle_root": result.bundle_root,
                    "blocked_by": result.blocked_by,
                },
                sort_keys=True,
            )
        )
        return 0 if result.inventory_complete else 1
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(
            json.dumps(
                {
                    "inventory_complete": False,
                    "historical_readiness": "blocked",
                    "production_cutover_readiness": "blocked",
                    "production_cutover_blocked_by": [
                        "d7_all_family_single_writer_ubuntu_evidence_not_verified"
                    ],
                    "reason": str(error).splitlines()[0],
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
