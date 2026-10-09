"""Why a gardener pass stopped, and what it recovered instead of stopping.

A pass that meets a fault it can record records it on the period or member it
is about and moves on. A pass that cannot go on stops, and says why in one
closed word. Each word is declared once here, so the record row, the log line a
step writes and any reader of either spell it the same way. Neither vocabulary
is text the pass read: a word, a period and a member id are all a record holds
(Guardrail #11).
"""

from __future__ import annotations

from enum import StrEnum


class GardenerFault(StrEnum):
    """Why one pass stopped: a defect, a named refusal, or a cause a later wake settles.

    `raised` and `manual-action` end a pass `failed` and turn the job red.
    Every other word ends it `deferred`, and the job stays green.
    """

    #: A code defect: an error no other word names, including any answer from
    #: GitHub that refuses the request itself. A person reads the log.
    RAISED = "raised"
    #: A named refusal the task recognizes but cannot settle itself. The log
    #: and task record name it, and a person acts before the task can continue.
    MANUAL_ACTION = "manual-action"
    #: GitHub's API did not answer: a 429 or 5xx, or a connection that failed or
    #: timed out. Nothing inside a wake asks again; the next wake does.
    API_UNAVAILABLE = "api-unavailable"
    #: A range a person named starts after a period that is ready before it, so
    #: the step would skip that period. The person widens the range.
    RANGE_STARTS_LATE = "range-starts-late"
    #: A raw day sits in a month the monthly mark is past that no monthly entry
    #: names: the month never closed, was dropped, or sits in a packed year, so
    #: there is no month to re-open. Its files wait for a person.
    NO_MONTH_TO_REOPEN = "no-month-to-reopen"
    #: A packed day or month file that a re-run or a late file would be settled
    #: into cannot be read, or its index names it and it is not there. Every
    #: file is kept, and a person restores the packed file from git history.
    PACKED_FILE_UNREADABLE = "packed-file-unreadable"


class RecoveryNote(StrEnum):
    """What one pass did with a fault it met, instead of stopping at it."""

    #: A day inside the ledger's history had no index entry and raw files left
    #: in its folder, so the pass packed it again from them.
    REPACKED_FROM_RAW = "repacked-from-raw"
    #: A day inside the ledger's history had no index entry and nothing left to
    #: rebuild it from, so its month lists it in `lost_days`.
    RECORDED_LOST = "recorded-lost"
    #: Raw files landed in a month already closed, so the pass settled their rows
    #: into the month's file and entry and deleted them.
    REOPENED_MONTH = "reopened-month"
    #: A period's own packed file was at its named path while no index entry
    #: named it, so the pass adopted the file as the period's record.
    INDEX_REBUILT = "index-rebuilt"
    #: A file the pass could not read was moved under its ledger's set-aside
    #: folder, and its period was packed from the rest and counts it.
    SET_ASIDE = "set-aside"
    #: A day held more raw files than one period is built from, so the pass
    #: packed the oldest and left the rest for the next wake to take in.
    CARRIED_OVER = "carried-over"
    #: GitHub would not delete a member, answering 409 or 422, so the pass
    #: recorded its id, counted it against the ceiling and went on.
    NOT_DELETABLE = "not-deletable"
