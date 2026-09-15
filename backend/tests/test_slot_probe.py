"""Which response field fills which empty column, decided from built payloads?

The probe itself needs a running server and is therefore not a test (Guardrail
#7). Its reading half is pure, so every case here is built - including the two
the pinned build has never produced: a slot that has held no task, and a server
whose answer carries none of the three fields, which is the shape that would
retire the columns.

The shapes below are the ones `llama.cpp` b10598 emits, read from
`tools/server/server-task.cpp` and `tools/server/server-context.cpp` at that
tag. They are trimmed to the fields the question turns on.
"""

from __future__ import annotations

import pytest

from utilities import slot_probe

BUSY_SLOT = {
    "id": 0,
    "n_ctx": 65536,
    "speculative": False,
    "is_processing": True,
    "id_task": 135,
    "n_prompt_tokens": 1612,
    "n_prompt_tokens_processed": 44,
    "n_prompt_tokens_cache": 1568,
    "params": {},
    "next_token": [],
}

IDLE_SLOT = {"id": 1, "n_ctx": 65536, "speculative": False, "is_processing": False}

COMPLETION = {
    "index": 0,
    "content": " four,",
    "id_slot": 0,
    "stop": True,
    "tokens_predicted": 4,
    "tokens_evaluated": 44,
    "tokens_cached": 1612,
    "stop_type": "limit",
    "timings": {"cache_n": 1568, "prompt_n": 44, "prompt_ms": 1030.0, "predicted_ms": 611.0},
}


def test_a_sibling_route_keeps_the_host_and_port_the_endpoint_named() -> None:
    assert slot_probe.route("http://127.0.0.1:8081/v1/chat/completions", "/slots") == (
        "http://127.0.0.1:8081/slots"
    )


def test_the_slot_field_list_is_the_union_across_slots_not_the_first_one() -> None:
    # The idle slot comes first, so a reader that stopped at slot zero would
    # report four fields on a server that has ten.
    found = slot_probe.slot_fields([IDLE_SLOT, BUSY_SLOT])

    assert "n_prompt_tokens" in found
    assert "n_prompt_tokens_cache" in found
    assert found == sorted(found)


def test_a_slots_answer_that_is_not_a_list_of_objects_is_refused() -> None:
    with pytest.raises(ValueError, match="list of slots"):
        slot_probe.slot_fields({"error": {"code": 501}})

    with pytest.raises(ValueError, match="list of slots"):
        slot_probe.slot_fields(["not an object"])


def test_the_timings_block_is_flattened_so_cache_n_is_reachable_by_name() -> None:
    found = slot_probe.completion_fields(COMPLETION)

    assert "timings.cache_n" in found
    assert "timings.prompt_n" in found
    assert "timings" in found


def test_a_completion_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(ValueError, match="must answer with an object"):
        slot_probe.completion_fields([COMPLETION])


def test_the_completion_answers_all_three_columns_when_it_carries_those_fields() -> None:
    found = slot_probe.answered_by(
        slots=slot_probe.slot_fields([BUSY_SLOT]),
        completion=slot_probe.completion_fields(COMPLETION),
    )

    # The completion is preferred over `/slots` for every column it carries,
    # because reading it costs no extra request per item.
    assert found == {
        "slot_id": "completion:id_slot",
        "kv_tokens_at_start": "completion:tokens_cached",
        "prefix_shared_with_previous": "completion:timings.cache_n",
    }


def test_slots_answers_the_columns_the_completion_leaves_out() -> None:
    thin = {name: value for name, value in COMPLETION.items() if name != "tokens_cached"}
    thin.pop("timings")

    found = slot_probe.answered_by(
        slots=slot_probe.slot_fields([BUSY_SLOT]),
        completion=slot_probe.completion_fields(thin),
    )

    assert found["kv_tokens_at_start"] == "slots:n_prompt_tokens"
    assert found["prefix_shared_with_previous"] == "slots:n_prompt_tokens_cache"


def test_a_column_nothing_carries_reads_as_nothing_rather_than_as_a_guess() -> None:
    found = slot_probe.answered_by(slots=slot_probe.slot_fields([IDLE_SLOT]), completion=[])

    assert found["kv_tokens_at_start"] is None
    assert found["prefix_shared_with_previous"] is None
    # `/slots` always names the slot, so this one is answered even by an idle
    # server - which is why the column it fills is a constant at `-np 1`.
    assert found["slot_id"] == "slots:id"


def test_every_declared_column_gets_a_verdict_even_when_the_server_said_nothing() -> None:
    found = slot_probe.answered_by(slots=[], completion=[])

    assert tuple(found) == slot_probe.SLOT_COLUMNS
    assert set(found.values()) == {None}


def test_a_spread_names_its_sample_size_and_says_when_nothing_was_read() -> None:
    assert slot_probe.spread([]) == "not read"
    assert slot_probe.spread([0, 0, 0]) == "0 on every call, n=3"
    assert slot_probe.spread([1568, 1568, 1570]) == "min 1568, max 1570, n=3"


def test_the_three_numbers_come_back_under_the_names_the_build_used() -> None:
    assert slot_probe.readings(COMPLETION) == {
        "id_slot": 0,
        "tokens_cached": 1612,
        "timings.cache_n": 1568,
    }


def test_a_field_the_build_did_not_send_is_absent_rather_than_zero() -> None:
    # Zero is a real cache count, so a missing field defaulted to zero would
    # read as a slot that reused nothing - the opposite of "nobody asked".
    thin = {name: value for name, value in COMPLETION.items() if name != "timings"}

    found = slot_probe.readings(thin)

    assert "timings.cache_n" not in found
    assert found["id_slot"] == 0


def test_slot_zero_survives_the_filter_because_it_is_a_real_slot() -> None:
    assert slot_probe.readings({"id_slot": 0, "timings": {"cache_n": 0}}) == {
        "id_slot": 0,
        "timings.cache_n": 0,
    }
