"""Which workflow commands does GitHub read beside a gardener event, and how is each escaped?

GitHub's runner reads a workflow command from any line of a step's output that
starts with `::`, on stdout or on stderr. When a shard runs on GitHub, the event
log writes these lines on the event's own stream, around the event's own line
(`event_log.GitHubLines`), so each one lands exactly where its event does:

- `::group::<task> (<kind>)` before `task-planned`, so every line a task logs
  folds into one group named for it;
- `::endgroup::` after `task-finished`, and then, for a task that `failed`, one
  `::error title=<task>::...`. It comes after the group, so it shows while the
  group is folded, and GitHub also lists it on the run's page;
- `::warning title=shard <n>::...` after `shard-published` when nothing landed
  because main moved on: `stale` or `lost`.

**Every value is escaped the way GitHub's own toolkit escapes it.** A message
escapes `%`, CR and LF, so nothing inside it can end its line and start a
command of its own. A property's value also escapes `:` and `,`, which would
end the property.

**No command holds an exception's text** (Guardrail #11). An error line says
the fault word, the period or member the task worked on, the exception's type
and code place, and the event's own `next`, which is the fault's own sentence
when a fault stopped the task.
"""

from __future__ import annotations

from typing import Final

from idhazh.contracts.base import Model
from idhazh.contracts.gardener_events import (
    ShardPublished,
    TaskFinished,
    TaskOutcome,
    TaskPlanned,
)
from idhazh.contracts.shard_landing import ShardLanding

#: What GitHub's toolkit replaces in a command's message, `%` first, so an
#: escape already written is never escaped a second time.
_DATA_ESCAPES: Final = (("%", "%25"), ("\r", "%0D"), ("\n", "%0A"))

#: What it replaces in a property's value: the message's three, and the `:` and
#: `,` that would end the property.
_PROPERTY_ESCAPES: Final = (*_DATA_ESCAPES, (":", "%3A"), (",", "%2C"))

#: The command that closes the group a task's lines fold into.
END_GROUP: Final = "::endgroup::"


def escaped_data(text: str) -> str:
    """A command's message, with `%`, CR and LF escaped so it stays on its own line."""
    return _replaced(text, _DATA_ESCAPES)


def escaped_property(text: str) -> str:
    """A command's property value, escaped as a message is and `:` and `,` as well."""
    return _replaced(text, _PROPERTY_ESCAPES)


def around(event: Model) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The command lines GitHub reads just before an event's line, and just after it."""
    if isinstance(event, TaskPlanned):
        return (f"::group::{escaped_data(f'{event.task} ({event.kind})')}",), ()
    if isinstance(event, TaskFinished):
        if event.outcome is TaskOutcome.FAILED:
            return (), (END_GROUP, _error_line(event))
        return (), (END_GROUP,)
    if isinstance(event, ShardPublished) and event.landing in (
        ShardLanding.STALE,
        ShardLanding.LOST,
    ):
        return (), (_warning_line(event),)
    return (), ()


def _error_line(finished: TaskFinished) -> str:
    """The one error a failed task adds: its fault, what it worked on, where, and what next.

    A live run always names the fault; a task-finished with none says `failed`.
    """
    said = str(finished.fault or finished.outcome)
    if finished.resume_from is not None:
        said += f" while it worked on {finished.resume_from}"
    if finished.error is not None:
        place = "" if finished.where is None else f" at {finished.where}"
        said += f" ({finished.error}{place})"
    title = escaped_property(finished.task)
    return f"::error title={title}::{escaped_data(f'{said}: {finished.next}')}"


def _warning_line(published: ShardPublished) -> str:
    """The warning a shard adds when nothing landed because main moved on: stale or lost."""
    if published.landing is ShardLanding.STALE:
        first, *rest = published.stale_paths
        more = f" and {len(rest)} more" if rest else ""
        said = (
            f"{ShardLanding.STALE} - main changed {first}{more} after the commit this shard "
            "ran on, so nothing landed. The next wake does the work again"
        )
    else:
        said = (
            f"{ShardLanding.LOST} - all {published.push_tries} tries failed, and main changed "
            "during the last one, so other writers were landing first. Nothing landed; the "
            "next wake does the work again"
        )
    title = escaped_property(f"shard {published.shard}")
    return f"::warning title={title}::{escaped_data(said)}"


def _replaced(text: str, escapes: tuple[tuple[str, str], ...]) -> str:
    """`text` with each character of `escapes` replaced, in their order."""
    for character, escape in escapes:
        text = text.replace(character, escape)
    return text
