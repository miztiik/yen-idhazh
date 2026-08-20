"""Time a diffusion model on CPU. The image leg is the one stage whose cost
nobody has published for a 4-vCPU runner, so measure it rather than guess.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

PROMPT = (
    "flat vector infographic, three labelled panels, muted editorial palette, "
    "clean sans-serif, white background, no photorealism"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Tongyi-MAI/Z-Image-Turbo")
    ap.add_argument("--steps", type=int, default=9)
    ap.add_argument("--sizes", default="512,768")
    ap.add_argument("--out", type=Path, default=Path("backend/var"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    import torch
    from diffusers import DiffusionPipeline

    torch.set_num_threads(int(os.environ.get("BENCH_THREADS", "4")))

    t0 = time.perf_counter()
    pipe = DiffusionPipeline.from_pretrained(args.model, torch_dtype=torch.float32)
    pipe.to("cpu")
    load_s = time.perf_counter() - t0

    results = []
    for size in (int(s) for s in args.sizes.split(",")):
        t0 = time.perf_counter()
        image = pipe(
            prompt=PROMPT,
            height=size,
            width=size,
            num_inference_steps=args.steps,
            guidance_scale=0.0,  # Turbo variants are distilled; CFG must be off
            generator=torch.Generator("cpu").manual_seed(0),
        ).images[0]
        elapsed = time.perf_counter() - t0
        image.save(args.out / f"{size}.png")
        results.append({"size": size, "steps": args.steps, "seconds": round(elapsed, 1)})
        print(f"{args.model} {size}x{size} {args.steps} steps -> {elapsed:.1f}s", flush=True)

    payload = {
        "model": args.model,
        "threads": torch.get_num_threads(),
        "load_seconds": round(load_s, 1),
        "runs": results,
    }
    (args.out / "image.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
