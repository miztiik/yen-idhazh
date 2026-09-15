"""What the model was sent and what it sent back, kept where a person can read it.

The census row says a reply was 1,158 tokens where it used to be 229. It cannot
say what the model was asked, so it cannot say whether the prompt moved, whether
the article was longer, or whether the decoder simply ran on. That question was
open for six days on the regression this module was written for, and it was open
because the only copy of the text was in a runner that had already been deleted.

**This is a run artifact and never a commit.** A rendered prompt carries the
article body inside it, and republishing an article body is a non-goal
(CLAUDE.md section 0a). `digest.yml` uploads the directory with a retention
window and nothing in `commit-and-push.sh` names it, which is exactly how the
faithfulness evidence already handles the same problem.

**The digest is recorded whether or not the text is.** `sha256` and a character
count cost nothing, survive both flags being off, and answer the one question a
regression really asks: did the prompt change between these two runs?
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from idhazh.contracts.base import canonical_json, derive_text_digest


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
) -> Capture:
    """Measure the pair, write whichever halves the flags allow, and report both.

    `write` is handed in rather than imported so this module owns no atomic-write
    policy of its own and a test can drive it without a filesystem.

    Nothing is written when both flags are off, which is the cheap default this
    is designed to survive: the digest and the two counts are computed either
    way, because they are what the log record carries and the log record is the
    copy that outlives the runner.
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
                "call": call,
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
