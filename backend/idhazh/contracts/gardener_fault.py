"""What a gardener pass recovered instead of stopping.

A pass that meets a fault it can record records it on the period and moves on.
Each kind of recovery has one word, declared once here, so the log line a step
writes and any reader of it spell the word the same way. No persisted shape
carries these words yet: a step logs one line for each recovery, naming the
word and the period it is about, and nothing else.
"""

from __future__ import annotations

from enum import StrEnum


class RecoveryNote(StrEnum):
    """What one pass did with a fault it met, instead of stopping at it."""

    #: A day inside the ledger's history had no index entry and nothing left to
    #: rebuild it from, so its month lists it in `lost_days`.
    RECORDED_LOST = "recorded-lost"
    #: Raw files landed in a month already closed, so the pass settled their rows
    #: into the month's file and entry and deleted them.
    REOPENED_MONTH = "reopened-month"
    #: A period's own packed file was at its named path while no index entry
    #: named it, so the pass adopted the file as the period's record.
    INDEX_REBUILT = "index-rebuilt"
