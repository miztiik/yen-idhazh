"""Print llama-server argv from committed config, before package install runs."""

from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--alias", required=True)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--format", choices=("shell", "nul"), default="shell")
    args = parser.parse_args()

    app = json.loads((args.config / "idhazh.json").read_text(encoding="utf-8"))
    inference = app["models"]["inference"]
    argv = [
        str(args.binary),
        "--model",
        str(args.weights),
        "--alias",
        args.alias,
        "--ctx-size",
        str(inference.get("n_ctx", 8192)),
        "--batch-size",
        str(inference.get("n_batch", 512)),
        "--ubatch-size",
        str(inference.get("n_ubatch", 512)),
        "--threads",
        str(inference.get("n_threads", 4)),
        "--port",
        str(args.port),
    ]
    optional = (
        ("n_parallel", "-np"),
        ("flash_attention", "-fa"),
        ("load_mode", "-lm"),
        ("cache_type_k", "-ctk"),
        ("cache_type_v", "-ctv"),
        ("priority", "--prio"),
        ("poll", "--poll"),
        ("n_threads_batch", "-tb"),
    )
    for field, flag in optional:
        value = inference.get(field)
        if value is not None:
            argv.extend((flag, str(value)))
    if not inference.get("startup_warmup", True):
        argv.append("--no-warmup")

    if args.format == "nul":
        print("\0".join(argv), end="\0")
    else:
        print(shlex.join(argv))


if __name__ == "__main__":
    main()
