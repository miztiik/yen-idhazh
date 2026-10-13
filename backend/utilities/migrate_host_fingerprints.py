"""Prepare or apply one approved, bounded history batch in an offline checkout."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from idhazh.contracts.host_history_transaction import HistoryApplyApproval
from idhazh.contracts.host_migration import HistoryManifest, HistoryReport
from idhazh.telemetry.host_history_apply import HistoryApplyBlockedError, apply_history
from idhazh.telemetry.host_history_bundle import dry_run
from idhazh.telemetry.host_history_files import HistoryLimits
from idhazh.telemetry.host_history_maintenance import MaintenanceError, offline_maintenance
from idhazh.telemetry.host_output_verify import _json, _read_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply only with exact D16 evidence, approval and an offline maintenance context.",
    )
    parser.add_argument("--workspace-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--bundle-root", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args(argv)
    if args.apply:
        if not all((args.workspace_root, args.manifest, args.bundle_root, args.approval)):
            parser.error(
                "apply requires --workspace-root, --manifest, --bundle-root and --approval"
            )
    elif args.rollback:
        parser.error("--rollback requires --apply and the original approved bundle")
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
            _read_bytes(
                manifest_path, root=manifest_path.parent if args.apply else workspace,
                cap=limits.max_manifest_bytes,
            ),
            limits.verification,
        )
        if not isinstance(original, dict) or "version" not in original:
            raise ValueError("manifest requires its explicit schema version before model stamping")
        manifest = HistoryManifest.model_validate(original)
        if args.apply:
            bundle = (
                args.bundle_root if args.bundle_root.is_absolute()
                else workspace / args.bundle_root
            )
            approval_path = (
                args.approval if args.approval.is_absolute() else workspace / args.approval
            )
            approval = HistoryApplyApproval.model_validate_json(
                _read_bytes(approval_path, root=approval_path.parent, cap=limits.max_manifest_bytes)
            )
            report = HistoryReport.model_validate_json(
                _read_bytes(bundle / "report.json", root=bundle, cap=limits.max_bundle_bytes)
            )
            names = {
                "manifest.json", "report.json", "candidate-maintenance-receipt.json",
                *(file.candidate_path for file in report.files if file.candidate_path is not None),
                *("original-receipts/" + file.source.path
                  for file in report.files if file.source.kind == "receipt"),
            }
            artifacts = {
                name: _read_bytes(bundle / name, root=bundle, cap=limits.max_bundle_bytes)
                for name in names
            }
            # The replay is embedded in the validated report; older D16 bundles lack a copy.
            if report.consumer_replay is not None:
                from idhazh.contracts.base import compact_json

                artifacts["consumer-replay.json"] = compact_json(
                    report.consumer_replay.model_dump(mode="json")
                ).encode("ascii")
            with offline_maintenance(workspace, approval) as maintenance:
                transaction = apply_history(
                    manifest, report, artifacts, workspace=workspace, limits=limits,
                    approval=approval, maintenance=maintenance, rollback=args.rollback,
                )
            print(json.dumps({
                "status": "rolled_back" if args.rollback else "complete",
                "transaction_root": transaction, "scope_hash": report.scope_hash,
                "evidence_hash": report.evidence_hash,
            }, sort_keys=True))
            return 0
        result = dry_run(manifest, workspace_root=workspace, config_document=document)
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
    except (
        ValueError, OSError, KeyError, TypeError, MaintenanceError, HistoryApplyBlockedError
    ) as error:
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
