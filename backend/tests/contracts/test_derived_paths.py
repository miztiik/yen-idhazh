"""Does the one list of derived paths hold what the commit step can act on?"""

from __future__ import annotations

import pytest

from idhazh import paths

pytestmark = pytest.mark.contract

#: A day directory as the plan job derives one, so the two entries that carry a
#: placeholder are rendered against something real.
A_DAY_DIR = "frontend/public/digest/2026/08/25"


def test_no_derived_entry_carries_a_second_placeholder_or_a_space() -> None:
    """One placeholder, because the caller has one value in its hand.

    The commit step word-splits what it is given, so a path with a space in it
    is read as two paths and the rebuild hands back a file that does not exist.
    That rule used to be a comment above a hand-written string in a workflow,
    which nothing could check.

    A second kind of placeholder would be a second thing every caller has to
    know, and the caller is a workflow step that knows which day it published
    and nothing else.
    """
    assert paths.DERIVED, "the refresh set is what a rebuild owns; empty means it owns nothing"

    for entry in paths.DERIVED:
        assert " " not in entry, f"{entry} carries a space and the commit step splits on spaces"
        assert entry.count("{") == entry.count("}"), f"{entry} has an unbalanced placeholder"
        assert entry.count("{") <= 1, f"{entry} carries more than one placeholder"
        if "{" in entry:
            assert paths.DAY_DIR in entry, f"{entry} names a placeholder this module cannot fill"
        assert not entry.startswith("/"), f"{entry} must be relative (CLAUDE.md section 2)"
        assert "\\" not in entry, f"{entry} must use POSIX separators (CLAUDE.md section 2)"


def test_the_rendered_line_is_every_derived_path_in_one_order_with_single_spaces() -> None:
    """The step output is one line, and the script splits it back into the paths."""
    rendered = paths.refresh_paths(day_dir=A_DAY_DIR)

    assert rendered.split(" ") == [
        entry.format(day_dir=A_DAY_DIR) for entry in paths.DERIVED if "/" in entry
    ]
    assert "  " not in rendered, "two spaces is an empty path the script would try to stage"
    assert f"{A_DAY_DIR}/digest.json" in rendered.split()
    assert f"{A_DAY_DIR}/run.json" in rendered.split()
    # Never the day's directory itself. The visuals artifact unpacks this run's
    # rendered charts into it and no producer in the assemble job can make them
    # again, so handing the directory back would delete them.
    assert A_DAY_DIR not in rendered.split()


def test_a_derived_filename_is_never_handed_back_because_no_step_can_rebuild_it() -> None:
    """A bare name in the list is derived, and it is the one kind left out.

    `settled.csv` is the fold of a closed day. It is derived - two runs that
    fold one day compute the same bytes - but it names a file in many
    directories rather than one path, and `idhazh assemble` re-emits no fold. A
    job that handed one back would delete it instead of rebuilding it.

    A conflicted fold refuses the push rather than merging, which is the
    mechanism working: the name carries no writer identity, so the resolver
    answers "not mine" and stops.
    """
    names = [entry for entry in paths.DERIVED if "/" not in entry]

    assert names, "the class holds a name, and dropping the last one would pass this by accident"
    handed_back = paths.refresh_paths(day_dir=A_DAY_DIR).split(" ")
    for name in names:
        assert name not in handed_back


def test_a_path_that_carries_a_space_is_refused_where_it_is_written() -> None:
    """The check that could not exist while the list was a YAML string.

    A day directory with a space in it is the only way a caller can produce one
    today, and it fails in the job that wrote it rather than in the rebase that
    could not find the file.
    """
    with pytest.raises(ValueError) as refused:
        paths.refresh_paths(day_dir="frontend/public/digest/2026/08/25 copy")
    assert "word-splits" in str(refused.value)


def test_the_days_metrics_record_is_rebuilt_and_never_merged() -> None:
    """`state/day-metrics` is one whole-file-per-day JSON, written by assemble.

    It is the same two-writer shape as `digest.json` one directory over, and it
    was in no refresh list until now - so two runs of one day wrote it from two
    bases and git held two versions of one file with no way to choose. A text
    merge of two JSON objects is a file that is not JSON, which is a console
    payload no reader can parse.

    It needs no fragments and no fold. It is already a pure function of the day's
    item-health rows and the published day, so two runs compute the same file and
    the only question left is who wins a race - which the rebuild answers in
    milliseconds.

    What this cannot settle is that the rebuild reproduces the file byte for byte
    from a different tip. That is the producer's own test.
    """
    assert "state/day-metrics" in paths.DERIVED
    assert "frontend/public/day-metrics" in paths.DERIVED
