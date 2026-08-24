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


def _rss_gb() -> float:
    """Resident memory, so an out-of-memory kill leaves a number behind it."""
    try:
        with Path("/proc/self/status").open(encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024 / 1024
    except OSError:
        pass
    return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Tongyi-MAI/Z-Image-Turbo")
    ap.add_argument("--steps", type=int, default=9)
    ap.add_argument("--sizes", default="512,768")
    ap.add_argument("--out", type=Path, default=Path("backend/var"))
    ap.add_argument(
        "--dtype",
        default="bfloat16",
        choices=("bfloat16", "float16", "float32"),
        help="float32 needs about 24 GB for a 6B model. The runner has 16.",
    )
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    import torch
    from diffusers import DiffusionPipeline

    torch.set_num_threads(int(os.environ.get("BENCH_THREADS", "4")))

    t0 = time.perf_counter()
    # The first attempt loaded float32 and the runner agent was killed under it -
    # a shutdown signal with 72 minutes still on the clock, which is what memory
    # exhaustion looks like from inside a job.
    pipe = DiffusionPipeline.from_pretrained(
        args.model,
        torch_dtype=getattr(torch, args.dtype),
        low_cpu_mem_usage=True,
    )
    pipe.to("cpu")
    load_s = time.perf_counter() - t0
    print(f"loaded {args.model} as {args.dtype} in {load_s:.1f}s rss={_rss_gb():.1f}GB", flush=True)

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
        png = args.out / f"{size}.png"
        image.save(png)
        webp = args.out / f"{size}.webp"
        image.save(webp, format="WEBP", quality=80)
        results.append(
            {
                "size": size,
                "steps": args.steps,
                "seconds": round(elapsed, 1),
                "png_bytes": png.stat().st_size,
                "webp_q80_bytes": webp.stat().st_size,
                "peak_rss_gb": round(_rss_gb(), 2),
            }
        )
        print(
            f"{args.model} {size}x{size} {args.steps} steps -> {elapsed:.1f}s "
            f"png={png.stat().st_size} webp={webp.stat().st_size} rss={_rss_gb():.1f}GB",
            flush=True,
        )

    payload = {
        "model": args.model,
        "dtype": args.dtype,
        "threads": torch.get_num_threads(),
        "load_seconds": round(load_s, 1),
        "runs": results,
    }
    (args.out / "image.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
