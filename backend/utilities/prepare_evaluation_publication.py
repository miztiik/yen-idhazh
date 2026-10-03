"""Make named evaluation inputs durable, then prepare their atomic Git publication."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--paths-file", type=Path, required=True)
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--inbox-only", action="store_true")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--inputs", type=Path)
    source.add_argument("--batch-id", action="append", default=[])
    arguments = parser.parse_args(argv)
    state = arguments.state_dir.resolve()
    repository = state.parent
    destination = (repository / arguments.paths_file).resolve()
    inputs = (repository / arguments.inputs).resolve() if arguments.inputs is not None else None
    if destination == inputs:
        parser.error("the prepared path list must not overwrite the immutable input manifest")
    destination.relative_to(repository)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("[]\n", encoding="ascii", newline="\n")
    if inputs is not None and not inputs.exists():
        return 0

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from idhazh.atomic_write import write_atomic
    from idhazh.config import load_observation_lookup
    from idhazh.contracts.base import canonical_json, derive_text_digest
    from idhazh.contracts.observation_lookup import ObservationPreparation
    from idhazh.evals.observation_batches import (
        incoming_path,
        input_root,
        load_batch,
        preparation_path,
        prepare,
    )
    from utilities.evaluation_inbox import committed_receipts, prepare_inputs, publish_inputs

    if arguments.inbox_only:
        if inputs is None:
            parser.error("inbox preparation needs a local input manifest")
        manifest = ObservationPreparation.read(inputs)
        batches = [load_batch(state, batch_id) for batch_id in manifest.batches]
        write_atomic(destination, json.dumps(prepare_inputs(state, batches)) + "\n")
        return 0

    if inputs is None:
        named_ids = [
            incoming_path(state, batch_id).stem for batch_id in dict.fromkeys(arguments.batch_id)
        ]
        completed = committed_receipts(state, named_ids)
        batches = [
            load_batch(state, batch_id)
            for batch_id in named_ids
            if batch_id not in completed or incoming_path(state, batch_id).exists()
        ]
        if not batches:
            return 0
        batch_ids = sorted(batch.batch_id for batch in batches)
        recovery_id = derive_text_digest(canonical_json(batch_ids))
        inputs = input_root(state) / "recoveries" / f"{recovery_id}.json"
        if not inputs.exists():
            write_atomic(
                inputs,
                ObservationPreparation.model_validate(
                    {"batches": batch_ids, "paths": []}
                ).to_json(),
            )
    else:
        manifest = ObservationPreparation.read(inputs)
        batches = [load_batch(state, batch_id) for batch_id in manifest.batches]
        if any(preparation_path(state, batch.identity).resolve() != inputs for batch in batches):
            raise ValueError("the input manifest does not belong to the batch's run, job and shard")
    if arguments.attempt is not None and any(
        batch.identity.attempt != arguments.attempt for batch in batches
    ):
        raise ValueError("the input manifest does not belong to this run attempt")
    publish_inputs(state, batches)
    config_dir = (
        repository / arguments.config_dir
        if arguments.config_dir is not None
        else repository / "config"
    )
    paths = prepare(state, inputs, settings=load_observation_lookup(config_dir)) if batches else []
    write_atomic(destination, json.dumps(paths) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())