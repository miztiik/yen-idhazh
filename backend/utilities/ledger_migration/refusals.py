"""Which two refusals stop a migration, each with exit 1?"""

from __future__ import annotations


class NotProvenError(Exception):
    """A day would not read, or did not come across whole, so nothing is deleted. Exit 1."""


class RefusedError(Exception):
    """A ledger the run names cannot move yet, so nothing is read or written. Exit 1."""
