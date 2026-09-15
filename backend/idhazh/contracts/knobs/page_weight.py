"""How heavy a prerendered route may be in gzip bytes before the build refuses it."""

from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model


class PageWeightConfig(Model):
    """A gzip-size guardrail per prerendered route, enforced by
    `frontend/scripts/bundle-gate.mjs`.

    The gate reads `config/idhazh.json`, never this model, so a number here
    would be a second copy of what the file already holds, free to drift from
    the one the gate enforces. The default is empty for that reason: the
    committed config is the single source, and this model owns only the shape
    and the validation (Guardrail #6).

    **A number may live here only if it does not have to move when a run
    publishes.** A weight that rises when the pipeline appends a day cannot be
    bounded by a constant: the only way past a firing is to type a bigger one,
    and a number too loose reads as green exactly like a number that is right.
    A route whose weight moves at publish speed takes no number here, and the
    property it stood in for is asserted directly instead -
    `frontend/tests/payload-weight.spec.ts` looks for a day-payload marker in
    every document that does not render a day, so it returns the same verdict
    whatever the archive holds.

    A route that takes a number moves only when a person edits source. A number
    that changes at review speed is a design statement; a number that changes at
    publish speed is the defect above. A page that renders a day is never named,
    for the neighbouring reason: the only way under such a number is to publish
    fewer items, which caps the news rather than catching a regression. Those
    pages are counted, reported and never failed.

    **Every number here is gzip -5, because that is what the reader pays.** The
    reading behind that choice is in
    `docs/reference/measurements-site.md`.

    **A document is capped and a payload is capped, and they are different
    jobs.** A document number catches a page that took on bytes it does not
    render. A payload number catches a file a browser fetches growing past what
    somebody priced, which no document number can see because the bytes are not
    in the document at all. Every payload number survives the test above by
    construction rather than by luck: each is derived from a bounded knob, so
    publishing more cannot move one. `console/band.json` is bounded by
    `observability.public_*_keep_months`, and `telemetry/` by the longest month
    at the heaviest day a run can produce.
    """

    ceilings_bytes: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Route class -> the largest gzip -5 size that route's prerendered HTML may "
            "reach. The committed values live in config/idhazh.json, which the gate "
            "reads; this default is empty so the numbers are not duplicated here where "
            "they could drift from the file the gate enforces (Guardrail #6). A route the "
            "object does not name is measured and reported by the gate but not failed. "
            "**A route may be named here only if its weight does not move when a run "
            "publishes** - a weight that rises as the pipeline appends a day cannot be "
            "bounded by a constant, and the property is asserted directly by "
            "frontend/tests/payload-weight.spec.ts instead. A page that renders a day is "
            "never named, because the only way under such a number is to publish less."
        ),
    )

    payload_ceilings_bytes: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Build-relative POSIX path -> the largest gzip -5 size a file a reader's "
            "browser fetches may reach. A key naming a file bounds that file; a key "
            "ending in / bounds every file under that directory, each on its own, so a "
            "month series takes one number rather than one a month. Empty by default "
            "for the same reason as ceilings_bytes: config/idhazh.json is the single "
            "source and the gate reads the file. A key that matches no file in the "
            "build fails the gate - a guardrail over nothing still reads as a bound "
            "somebody checked. Each number is a guardrail on the same rule the routes "
            "follow: at least twice the heaviest the file can realistically reach, so "
            "only a change of a different order fires it."
        ),
    )

    cold_console_load_bytes: int = Field(
        default=0,
        ge=0,
        description=(
            "The largest gzip -5 total the console's payload fetches may reach on a "
            "cold load at console.default_window_days. It bounds the design rather "
            "than the data: the per-file guardrails say how heavy one shard may be, "
            "and this says how many of them one opening of the page is allowed to "
            "want. Zero means unchecked, and the committed config is where the real "
            "number lives."
        ),
    )

    @model_validator(mode="after")
    def _a_ceiling_bounds_a_route(self) -> Self:
        for route, ceiling in self.ceilings_bytes.items():
            if not route.startswith("/"):
                raise ValueError(f"page_weight ceiling {route!r} is not a route")
            if ceiling <= 0:
                raise ValueError(f"page_weight ceiling for {route} must be above zero")
        return self

    @model_validator(mode="after")
    def _a_payload_ceiling_bounds_a_built_file(self) -> Self:
        """A payload key is a path inside the build, written the way every path
        that leaves this process is written (section 2).

        A leading slash is what separates the two objects: a route key has one
        and a payload key does not, so a value typed into the wrong object is
        refused by shape rather than discovered as a gate that checks nothing.
        """
        for path, ceiling in self.payload_ceilings_bytes.items():
            if path.startswith("/"):
                raise ValueError(
                    f"page_weight payload ceiling {path!r} is a route, not a path in the build"
                )
            if "\\" in path or ".." in path.split("/") or path == "":
                raise ValueError(
                    f"page_weight payload ceiling {path!r} is not a relative POSIX path"
                )
            if ceiling <= 0:
                raise ValueError(f"page_weight payload ceiling for {path} must be above zero")
        return self
