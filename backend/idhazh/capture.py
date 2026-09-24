"""What the model was sent and what it sent back, kept where a person can read it.

The census row says a reply was 1,158 tokens where it used to be 229. It cannot
say what the model was asked, so it cannot say whether the prompt moved, whether
the article was longer, or whether the decoder simply ran on. That question was
open for six days on the regression this module was written for, and it was open
because the only copy of the text was in a runner that had already been deleted.

**This is a run artifact and never a commit.** A rendered prompt carries the
article body inside it, and an article body is never republished to a reader.
`digest.yml` uploads the directory with a retention window and no commit call
names it, which is exactly how the faithfulness evidence already handles the
same problem.

**The digest is recorded whether or not the text is.** `sha256` and a character
count cost nothing, survive both flags being off, and answer the one question a
regression really asks: did the prompt change between these two runs?
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.call_cost import CallCost


@dataclass(frozen=True, slots=True)
class About:
    """Which story the call was about, in the three cells that identify it.

    Here because a prompt nobody can trace back to a source is a prompt nobody
    can check the summary against. The same three are on the item-health row,
    and that row is pruned to a reading window while this artifact is kept for
    90 days - so on the old run somebody is comparing against, the row has gone
    and the prompt has not.

    `title` is fetched text and stays data: it is written into the artifact and
    never into a prompt, a path or a URL (CLAUDE.md Guardrail #11).
    """

    canonical_url: str = ""
    source_id: str = ""
    title: str = ""


@dataclass(frozen=True, slots=True)
class Capture:
    """One call's text, and the two numbers that stand for it when it is absent.

    The numbers are always filled and the text is not, so a reader of the
    artifact can tell a call that was not captured from a call that returned
    nothing - which are two different findings and would otherwise look alike.
    """

    prompt_sha256: str
    prompt_chars: int
    reply_chars: int
    captured: bool

    def cells(self) -> dict[str, object]:
        """The four, under the names a record carries them by."""
        return {
            "prompt_sha256": self.prompt_sha256,
            "prompt_chars": self.prompt_chars,
            "reply_chars": self.reply_chars,
            "captured": self.captured,
        }


def path_for(root: Path, item_id: str, call: str) -> Path:
    """Where one call's capture lands: one file per call per item, under the day.

    `root` is handed in rather than derived here, so this module holds no
    repository path and a test redirects it by pointing the stage somewhere else
    rather than by patching a constant it does not own.
    """
    return root / f"{item_id}.{call}.json"


def of(
    *,
    root: Path,
    item_id: str,
    call: str,
    prompt: str,
    reply: str,
    keep_prompt: bool,
    keep_reply: bool,
    write: Callable[[Path, str], object],
    cost: CallCost | None = None,
    decode_split: Mapping[str, int | bool] | None = None,
    finish_reason: str = "",
    about: About | None = None,
) -> Capture:
    """Measure the pair, write whichever halves the flags allow, and report both.

    `write` is handed in rather than imported so this module owns no atomic-write
    policy of its own and a test can drive it without a filesystem.

    Nothing is written when both flags are off, which is the cheap default this
    is designed to survive: the digest and the two counts are computed either
    way, because they are what the log record carries and the log record is the
    copy that outlives the runner.

    **What the call cost travels with the text, and that is why it is here.**
    The same five numbers are on the item-health row, but `state/` is pruned to
    a reading window while this artifact is kept for 90 days - so on the old run
    a regression is compared against, the row has gone and the prompt has not. A
    capture that cannot say how long its own reply took makes the reader join two
    sources to answer the first question they have.
    """
    digest = derive_text_digest(prompt)
    if not (keep_prompt or keep_reply):
        return Capture(
            prompt_sha256=digest,
            prompt_chars=len(prompt),
            reply_chars=len(reply),
            captured=False,
        )
    write(
        path_for(root, item_id, call),
        canonical_json(
            {
                "about": None if about is None else asdict(about),
                "call": call,
                "cost": None if cost is None else cost.model_dump(mode="json"),
                "decode_split": None if decode_split is None else dict(decode_split),
                "finish_reason": finish_reason,
                "item_id": item_id,
                "prompt": prompt if keep_prompt else None,
                "prompt_chars": len(prompt),
                "prompt_sha256": digest,
                "reply": reply if keep_reply else None,
                "reply_chars": len(reply),
                "reply_sha256": derive_text_digest(reply),
            }
        ),
    )
    return Capture(
        prompt_sha256=digest,
        prompt_chars=len(prompt),
        reply_chars=len(reply),
        captured=True,
    )
