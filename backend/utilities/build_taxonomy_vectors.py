"""Build `config/taxonomy-vectors.bin` - one vector for each label the vocabulary offers.

A person runs this and commits the result. It is config, derived from
`config/taxonomy.json` exactly as that file is written by hand, and it is not a
model weight and not a run intermediate (CLAUDE.md section 10). It is committed
because the alternative is encoding eleven sentences on every runner, every run,
for an answer that only changes when somebody edits the vocabulary.

Run it after any edit to an active vertical or lens - the display name or the
definition - and after the encoder weights move. A run that reads a file built
under a different vocabulary or different weights refuses and names the file,
because a stale file compares today's items against last month's lenses and
produces a number that looks exactly like a real one.

    python backend/utilities/build_taxonomy_vectors.py

Not a test and not a pipeline stage: pytest never collects `backend/utilities/`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from idhazh import config
from idhazh.assemble import (
    TAXONOMY_VECTORS_RELPATH,
    label_vector_texts,
    pack_taxonomy_vectors,
    taxonomy_digest,
)
from idhazh.contracts.taxonomy import Taxonomy
from idhazh.embed import DIMENSIONS, ENCODER_REF, Embedder


def build(root: Path, taxonomy: Taxonomy) -> bytes:
    """The file's bytes, encoded through the same `Embedder` a run encodes items with.

    One encoder, so a label vector and an item vector are comparable at all. A
    second set of weights for the label side would give two vectors that agree
    until one of them is updated.
    """
    texts = label_vector_texts(taxonomy)
    if not texts:
        raise ValueError("config/taxonomy.json offers no active vertical or lens to encode")
    embedder = Embedder(root)
    if not embedder.available:
        raise ValueError(
            "the encoder is not committed in this checkout, so no label vector can be built"
        )
    embedder.load()
    return pack_taxonomy_vectors(embedder.encode(list(texts)), digest=taxonomy_digest(texts))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=config.REPO_ROOT,
        help="The repository root. The encoder and the output path are both under it.",
    )
    args = parser.parse_args()

    taxonomy = Taxonomy.read(args.root / "config" / "taxonomy.json")
    texts = label_vector_texts(taxonomy)
    payload = build(args.root, taxonomy)
    path = args.root / TAXONOMY_VECTORS_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)

    print(f"wrote {TAXONOMY_VECTORS_RELPATH}: {len(payload)} bytes")
    print(f"  {len(texts)} vectors at {DIMENSIONS} int8 dimensions = {len(texts) * DIMENSIONS}")
    print(f"  taxonomy digest {taxonomy_digest(texts)}")
    print(f"  encoder         {ENCODER_REF}")
    for text in texts:
        print(f"  encoded: {text[:76]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
