"""Which static import routes do the named council source inputs declare?"""

from __future__ import annotations

import ast
from pathlib import Path

from conftest import REPO_ROOT

MODULE_NAMES = (
    "idhazh",
    "idhazh.atomic_write",
    "idhazh.config",
    "idhazh.contracts.app_config",
    "idhazh.contracts.appearance_config",
    "idhazh.contracts.article",
    "idhazh.contracts.base",
    "idhazh.contracts.call_cost",
    "idhazh.contracts.collection_prune",
    "idhazh.contracts.council_shard_outcome",
    "idhazh.contracts.counterfactual_score",
    "idhazh.contracts.eval_row",
    "idhazh.contracts.feed_health",
    "idhazh.contracts.feed_retirement",
    "idhazh.contracts.file_envelope",
    "idhazh.contracts.fingerprint",
    "idhazh.contracts.fitted_similarity_threshold",
    "idhazh.contracts.host_fingerprint",
    "idhazh.contracts.item_health",
    "idhazh.contracts.item_health_summary",
    "idhazh.contracts.knobs.assist",
    "idhazh.contracts.knobs.bench",
    "idhazh.contracts.knobs.collect",
    "idhazh.contracts.knobs.console",
    "idhazh.contracts.knobs.council",
    "idhazh.contracts.knobs.evaluation",
    "idhazh.contracts.knobs.extract",
    "idhazh.contracts.knobs.finetune",
    "idhazh.contracts.knobs.gardener",
    "idhazh.contracts.knobs.ledger",
    "idhazh.contracts.knobs.model_server",
    "idhazh.contracts.knobs.models",
    "idhazh.contracts.knobs.observability",
    "idhazh.contracts.knobs.page_weight",
    "idhazh.contracts.knobs.placement",
    "idhazh.contracts.knobs.removed",
    "idhazh.contracts.knobs.retention",
    "idhazh.contracts.knobs.run",
    "idhazh.contracts.knobs.summarize",
    "idhazh.contracts.knobs.ui",
    "idhazh.contracts.knobs.visuals",
    "idhazh.contracts.knobs.windows",
    "idhazh.contracts.ledger_fault",
    "idhazh.contracts.ledger_index",
    "idhazh.contracts.ledger_name",
    "idhazh.contracts.run_plan",
    "idhazh.contracts.ledgers",
    "idhazh.contracts.run_manifest",
    "idhazh.contracts.seen",
    "idhazh.contracts.sources",
    "idhazh.contracts.story_similarity_distribution",
    "idhazh.contracts.story_similarity_pair",
    "idhazh.contracts.taxonomy",
    "idhazh.contracts.validation_row",
    "idhazh.contracts.visual_decision",
    "idhazh.contracts.visual_prune",
    "idhazh.contracts.watchlist",
    "idhazh.council",
    "idhazh.council.__init__",
    "idhazh.council.deadline",
    "idhazh.council.metrics_sink",
    "idhazh.council.night_plan",
    "idhazh.council.registry",
    "idhazh.council.run_identity",
    "idhazh.council.session",
    "idhazh.council.tenancy",
    "idhazh.day_partition",
    "idhazh.ledger",
    "idhazh.ledger.arrow_schema",
    "idhazh.ledger.csv_file",
    "idhazh.ledger.day_removal",
    "idhazh.ledger.filenames",
    "idhazh.ledger.headers",
    "idhazh.ledger.json_lines",
    "idhazh.ledger.keys",
    "idhazh.ledger.ledger_files",
    "idhazh.ledger.lifecycle",
    "idhazh.ledger.paths",
    "idhazh.ledger.persist",
    "idhazh.ledger.raw_files",
    "idhazh.ledger.rows",
    "idhazh.ledger.settle",
    "idhazh.llm.server",
    "idhazh.sanitize",
)


def module_file(dotted: str) -> Path | None:
    """Resolve one named import, never list a directory."""
    parts = dotted.split(".")
    if parts[0] != "idhazh":
        return None
    base = REPO_ROOT.joinpath("backend", *parts)
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def imported_at_import_time(path: Path, dotted: str) -> set[str]:
    """Read one named source file's imports, excluding functions and TYPE_CHECKING."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = dotted if path.name == "__init__.py" else dotted.rsplit(".", 1)[0]
    found: set[str] = set()

    def walk(body: list[ast.stmt]) -> None:
        for node in body:
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names if alias.name.startswith("idhazh"))
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    above = (
                        package.split(".")[: -(node.level - 1)]
                        if node.level > 1
                        else package.split(".")
                    )
                    root = ".".join([*above, node.module]) if node.module else ".".join(above)
                else:
                    root = node.module or ""
                if not root.startswith("idhazh"):
                    continue
                found.add(root)
                found.update(f"{root}.{alias.name}" for alias in node.names)
            elif isinstance(node, ast.If) and "TYPE_CHECKING" not in ast.unparse(node.test):
                walk(node.body)
                walk(node.orelse)
            elif isinstance(node, ast.Try):
                walk(node.body)
                walk(node.orelse)
                walk(node.finalbody)
                for handler in node.handlers:
                    walk(handler.body)

    walk(tree.body)
    return found


def static_routes() -> dict[str, tuple[str, ...]]:
    """Read at most the named module list; an unlisted dependency fails before it is read."""
    seeds = [name for name in MODULE_NAMES if name.startswith("idhazh.council.")]
    routes: dict[str, tuple[str, ...]] = {seed: (seed,) for seed in seeds}
    pending = list(seeds)
    while pending:
        dotted = pending.pop(0)
        path = module_file(dotted)
        assert path is not None, f"named import input moved or disappeared: {dotted}"
        for name in sorted(imported_at_import_time(path, dotted)):
            if name in routes or module_file(name) is None:
                continue
            assert name in MODULE_NAMES, (
                f"{dotted} imports {name}, outside the named import inputs. "
                "Review the new dependency and update MODULE_NAMES to include it."
            )
            routes[name] = (*routes[dotted], name)
            pending.append(name)
    return routes
