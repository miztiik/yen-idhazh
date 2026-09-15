"""What bounds a route that grows every time a run publishes?"""

from __future__ import annotations

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh.contracts.app_config import AppConfig
from idhazh.contracts.knobs.page_weight import PageWeightConfig

pytestmark = pytest.mark.contract


def test_no_page_number_names_a_route_that_grows_when_a_run_publishes() -> None:
    """This test was the opposite of itself until 2026-09-10, and the inversion is
    the point.

    It used to insist `/archive/` and the three `/console/` routes each carried a
    byte number, on the argument that an unnamed route grows unwatched. What
    actually happened is that those four numbers moved when the pipeline
    published rather than when anybody wrote code, so the gate fired on ordinary
    publishing and the recorded answer was always a bigger number - `/archive/`
    twice in one day on 2026-08-26. Meanwhile `/console/` drifted to 7.2 times
    the page it bounded and stood there four days with the build green. A number
    that cannot tell correct from far-too-loose is not an instrument.

    **The property those numbers were a proxy for is asserted directly**, by
    `frontend/tests/payload-weight.spec.ts`: no document that does not render a
    day may contain a day payload marker. That is the one regression this surface
    has ever had - a layout inlining a day, 313,300 gzipped bytes on 2026-08-26 -
    and the marker check returns the same verdict whatever the archive holds.

    So the assertion is now on absence. `/404` and `/evals/` stay, because they
    pass the test in the name: they move only when a person edits source, never
    when a run appends a day. Owner ruling, 2026-09-10.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    ceilings = committed.page_weight.ceilings_bytes

    assert PageWeightConfig().ceilings_bytes == {}, "the model default must stay empty"
    assert ceilings["/404"] > 0
    assert ceilings["/evals/"] > 0
    for route in ("/archive/", "/console/", "/console/model/", "/console/machine/"):
        assert route not in ceilings, (
            f"{route} has a byte number again. Its weight moves when the pipeline "
            "publishes, so the number has to move too, and the only way past it is to "
            "type a bigger one - which is what got these four deleted. The regression "
            "worth catching here is a day payload inlined by a layout, and "
            "frontend/tests/payload-weight.spec.ts asserts that directly."
        )


def test_the_committed_config_caps_what_a_cold_console_load_fetches() -> None:
    """The page ceilings above cannot see these bytes, and that is why they exist.

    The console stopped inlining its telemetry on 2026-09-09. That took 3.4 MB out
    of a document a ceiling watched and put it into files nothing watched, and a
    reader still waits for them - measured 2026-09-10 in a real browser, a cold
    `/console/` load fetches two telemetry shards worth 303,306 bytes on the wire
    and no other payload at all. A document ceiling now reads as a bound on what
    the console costs a reader, and it is not one.

    `cold_console_load_bytes` bounds the design rather than the data: the per-file
    ceilings say how heavy one shard may be, this says how many of them one
    opening of the page is allowed to want. The two are asserted against each
    other here, because a total below the sum of its parts is a gate that cannot
    be satisfied at the limit and a total far above it is a gate that never fires.
    """
    committed = AppConfig.from_json(read_text(CONFIG_DIR / "idhazh.json"))
    weight = committed.page_weight
    payloads = weight.payload_ceilings_bytes

    assert PageWeightConfig().payload_ceilings_bytes == {}, "the model default must stay empty"
    assert PageWeightConfig().cold_console_load_bytes == 0, "the model default must stay empty"

    for path in ("console/band.json", "telemetry/"):
        assert path in payloads, (
            f"{path} is fetched by a reader's browser and has no ceiling - the bundle "
            "gate cannot fail a file nobody named, so this one would grow unwatched"
        )

    # The worst case a run of N consecutive days can land in, because February is
    # the shortest month there is. Mirrors the arithmetic in bundle-gate.mjs.
    window = committed.console.default_window_days
    months_touched = 1 + -(-(window - 1) // 28)
    worst = payloads["console/band.json"] + months_touched * payloads["telemetry/"]
    assert weight.cold_console_load_bytes >= worst, (
        "a cold load of every payload sitting exactly on its own ceiling is already "
        f"over cold_console_load_bytes ({worst} against "
        f"{weight.cold_console_load_bytes}) - the two gates contradict each other"
    )
    assert weight.cold_console_load_bytes < worst + payloads["telemetry/"], (
        "cold_console_load_bytes has room for one more telemetry shard than the "
        "default window reaches, so widening console.default_window_days past a "
        "month would not fire it - which is the one thing it exists to catch"
    )


def test_a_page_ceiling_bounds_a_route_and_bounds_it_above_zero() -> None:
    """A ceiling of zero passes nothing and a key that is not a route bounds nothing."""
    with pytest.raises(ValueError, match="above zero"):
        PageWeightConfig(ceilings_bytes={"/evals/": 0})
    with pytest.raises(ValueError, match="is not a route"):
        PageWeightConfig(ceilings_bytes={"evals": 2475})


def test_a_payload_ceiling_bounds_a_path_in_the_build() -> None:
    """The leading slash is what tells the two objects apart.

    A route ceiling has one and a payload ceiling does not, so a number typed
    into the wrong object is refused by shape here rather than discovered later
    as a gate quietly checking nothing.
    """
    with pytest.raises(ValueError, match="above zero"):
        PageWeightConfig(payload_ceilings_bytes={"telemetry/": 0})
    with pytest.raises(ValueError, match="is a route, not a path"):
        PageWeightConfig(payload_ceilings_bytes={"/telemetry/": 500_000})
    with pytest.raises(ValueError, match="not a relative POSIX path"):
        PageWeightConfig(payload_ceilings_bytes={"telemetry\\2026-09.csv": 500_000})
    with pytest.raises(ValueError, match="not a relative POSIX path"):
        PageWeightConfig(payload_ceilings_bytes={"../telemetry/": 500_000})
