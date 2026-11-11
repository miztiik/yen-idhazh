"""Read consumed server flags through the pinned runtime's recorded declarations."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Final

# These are existing recorded keys, not preferred spellings for runtime argv.
SETTING_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "n_ctx": "--ctx-size",
        "n_batch": "--batch-size",
        "n_ubatch": "--ubatch-size",
        "n_threads": "--threads",
        "n_parallel": "-np",
        "load_mode": "-lm",
    }
)

DIGESTED_FLAGS: Final = (
    "-ctk",
    "-ctv",
    "-fa",
    "-np",
    "-tb",
    "-cms",
    "-ctxcp",
    "-cram",
    "--cache-prompt",
    "--no-cache-prompt",
    "-sps",
    "--jinja",
    "--no-jinja",
    "--reasoning-preserve",
    "--no-reasoning-preserve",
)

# The resource is the pinned binary's specification, bound to the pin by a test.
RECORDED_SERVER_HELP: Final = "b10598-llama-server-help.txt"
_CONSUMED_FLAGS: Final = frozenset((*SETTING_KEYS.values(), *DIGESTED_FLAGS))
_DECLARATION: Final = re.compile(
    r"^(-{1,2}[A-Za-z0-9][A-Za-z0-9-]*(?:,\s*-{1,2}[A-Za-z0-9][A-Za-z0-9-]*)*)"
)


@dataclass(frozen=True)
class ServerFlagContract:
    aliases: Mapping[str, tuple[str, ...]]
    exclusive: tuple[tuple[str, ...], ...]

    def interpret(self, server: Mapping[str, Any]) -> dict[str, Any]:
        """Return recorded keys without changing any supplied spelling or value."""
        for switches in self.exclusive:
            supplied = [flag for flag in switches if flag in server]
            if len(supplied) > 1:
                raise ValueError(f"opposing server switches: {', '.join(supplied)}")
        recorded: dict[str, Any] = {}
        for key, aliases in self.aliases.items():
            supplied = [flag for flag in aliases if flag in server]
            if len(supplied) > 1:
                raise ValueError(f"multiple spellings for {key}: {', '.join(supplied)}")
            if supplied:
                recorded[key] = server[supplied[0]]
        return recorded


def parse_server_help(text: str, consumed: frozenset[str]) -> ServerFlagContract:
    """Interpret only consumed option declarations, never prose or guessed polarity."""
    aliases: dict[str, tuple[str, ...]] = {}
    exclusive: list[tuple[str, ...]] = []
    declarations: list[tuple[tuple[str, ...], bool]] = []
    occurrences: Counter[str] = Counter()
    for line in text.splitlines():
        declaration = _DECLARATION.match(line)
        if declaration is None:
            continue
        flags = tuple(flag.strip() for flag in declaration[1].split(","))
        remainder = line[declaration.end():]
        takes_value = remainder.startswith(" ") and not remainder.startswith("  ")
        declarations.append((flags, takes_value))
        occurrences.update(flags)
    for flags, takes_value in declarations:
        keys = consumed.intersection(flags)
        if not keys:
            continue
        named = ", ".join(flags)
        if any(occurrences[flag] != 1 for flag in flags):
            raise ValueError(f"ambiguous server-help declaration: {named}")
        if takes_value:
            if len(keys) != 1:
                raise ValueError(f"ambiguous server-help aliases: {named}")
            aliases[next(iter(keys))] = flags
        else:
            # Help groups opposing bare switches on one line, not just aliases.
            if keys != set(flags):
                raise ValueError(f"unsupported bare server-help aliases: {named}")
            aliases.update((key, (key,)) for key in flags)
            if len(flags) > 1:
                exclusive.append(flags)
    missing = consumed.difference(aliases)
    if missing:
        raise ValueError(f"server help declares no consumed flags: {', '.join(sorted(missing))}")
    return ServerFlagContract(MappingProxyType(aliases), tuple(exclusive))


def read_recorded_server_help() -> str:
    return files("idhazh.llm").joinpath(RECORDED_SERVER_HELP).read_text(encoding="ascii")


@cache
def _recorded_flag_contract() -> ServerFlagContract:
    return parse_server_help(read_recorded_server_help(), _CONSUMED_FLAGS)


def interpret_server_flags(server: Mapping[str, Any]) -> dict[str, Any]:
    return _recorded_flag_contract().interpret(server)
