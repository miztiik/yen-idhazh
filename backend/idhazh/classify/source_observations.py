"""Recognize source statements that explicitly attach a reading to its roles."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from idhazh.classify.source_readings import (
    ASIDE,
    DATE_SLOT,
    QUANTITY,
    Clause,
    Span,
    source_clauses,
    words_key,
)
from idhazh.contracts.element import Element, ElementKind, ElementTable
from idhazh.elements import MONTHS, NUMBER

_Q = QUANTITY
_D = DATE_SLOT
_WORD = r"[^\W\d_]+(?:[-'\u2019][^\W\d_]+)*"
_PHRASE = rf"{_WORD}(?: +{_WORD})*?"
_PREDICATE = (
    r"rose to|fell to|stood at|opened at|closed at|was|were|is|are|had|has|reached|"
    r"recorded|reported|approved|produced|generated|weighs|weighed"
)
_CLAUSE_END = r"\s*[.!?]?\s*"
_DATE_PREFIX = rf"(?:(?:in|on|as of) +(?P<early>{_D}) *, *)?"
_DATE_SUFFIX = rf"(?: +(?:in|on|as of) +(?P<late>{_D}))?"
_RELATIVE = (
    r"(?P<relative> +(?:this week|on the same day|in (?:"
    + "|".join(sorted(MONTHS, key=len, reverse=True))
    + ")))?"
)
_EDITORIAL_TAIL = (
    rf"(?: *, *(?:the largest single award [^.!?\x01\x02]+|(?P<closing>completing the round)|"
    rf"a (?:rise|fall|change) of +{_Q} *))?"
)
_SIMPLE = re.compile(
    rf"\s*{_DATE_PREFIX}(?P<head>{_PHRASE}) +(?P<verb>{_PREDICATE}) +(?P<q>{_Q}) *"
    rf"(?: +of +(?P<measure>{_PHRASE}))?{_DATE_SUFFIX}{_RELATIVE}"
    rf"{_EDITORIAL_TAIL}{_CLAUSE_END}",
    re.I,
)
_MONEY = re.compile(
    rf"\s*(?P<actor>{_PHRASE}) +(?P<also>also +)?(?P<action>ordered the return of|"
    rf"imposed(?: a total of)?) +(?P<q>{_Q}) *(?:{ASIDE} *)?"
    rf"(?:of|in) +(?P<label>{_PHRASE})"
    rf"(?P<scope> +(?:from|on|for) +[^.!?\x01\x02]+)?{_CLAUSE_END}",
    re.I,
)
_INDIRECT_ACTOR = re.compile(
    r"(?:(?:the|this|that) )?(?:agency|authority|regulator|commission|body)|"
    r"it|they|he|she",
    re.I,
)
_NEW_CONTEXT = re.compile(r"\b(?:separate|different|unrelated|another)\b", re.I)
_ENFORCEMENT_CONTINUES = re.compile(
    rf"\s*in the {_PHRASE} case, *(?P<actor>{_PHRASE}) +also +"
    r"(?:ordered|imposed) +[^.!?]+[.!?]?\s*",
    re.I,
)
_PRICE = re.compile(
    rf"\s*(?:the +)?(?:(?P<offer>offer price) +was|(?P<opening>shares opened) +at)"
    rf" +(?P<q>{_Q}) +per share{_CLAUSE_END}",
    re.I,
)
_RELATION = re.compile(
    rf"\s*(?P<name>{_PHRASE}) +(?:reported|recorded) +(?P<y>{_Q}) +from +(?P<x>{_Q})"
    rf"{_CLAUSE_END}",
    re.I,
)
_AXES = re.compile(
    rf"\s*(?P<name>{_PHRASE}) +(?:had|has|reported|recorded) +(?P<values>.+?){_CLAUSE_END}", re.I
)
_NAMED_VALUE = re.compile(rf"\s*(?P<measure>{_PHRASE}) +(of|at|was) +(?P<q>{_Q}) *", re.I)
_CHANGE = re.compile(
    rf"\s*(?P<head>{_PHRASE}) +(?:rose|fell|changed|went) +from +(?P<first>{_Q})"
    rf" +in +(?P<early>{_D}) +to +(?P<second>{_Q}) +in +(?P<late>{_D}){_CLAUSE_END}",
    re.I,
)
_WHOLE = re.compile(
    rf"\s*(?P<group>(?:the +)?total +{_PHRASE}) +(?:was|were|is|of) +(?P<q>{_Q}) *"
    rf"[:,] *(?:split|divided|partitioned) into +"
    rf"(?P<parts>.+?){_CLAUSE_END}",
    re.I,
)
_PART = re.compile(
    rf"\s*(?P<label>{_PHRASE}) +(?:at|made up|accounted for|comprised) +(?P<q>{_Q}) *", re.I
)
_GROUP = re.compile(
    rf"\s*(?P<group>{_PHRASE}) +(?:were|are|were recorded as|were measured as) *:?"
    rf" *(?P<values>{_Q}.+?){_CLAUSE_END}",
    re.I,
)
_FORECAST = re.compile(
    rf"\s*(?P<group>{_PHRASE}) +(?:is|was) expected to (?:grow|increase)"
    rf" annually through (?P<date>{_D}) *(?P<stop>,) *with +"
    rf"(?P<parts>.+?){_CLAUSE_END}",
    re.I,
)
_AT = re.compile(rf"\s*(?P<label>{_PHRASE}) +at +(?P<q>{_Q}) *", re.I)
_LIST = re.compile(r" *, *(?:and +)?| +and +", re.I)
_AND = re.compile(r"\s*(?:;|,?\s+and(?= +(?:the +)?[A-Z])|,\s*while)\s+")
_UNSAFE = re.compile(
    r"\b(?:no|not|never|only|except|excluding|fewer than|more than|at least|at most|less than|"
    r"up to|as much as|around|about|roughly|approximately|nearly|between|could|would|might|"
    r"may|should|will|expected|forecast|projected|estimated|target|if|unless|respectively|"
    r"however|instead|claimed|claims|overlap|overlapping|among them|of which)\b",
    re.I,
)
_ARTICLE = re.compile(r"(?:the|a|an) +", re.I)
_PROPER = re.compile(r"[A-Z][^\W\d_]*(?: +[A-Z][^\W\d_]*)*")
_POSSESSIVE = re.compile(r"['\u2019]s(?: +|$)", re.I)
_NAMED_SAMPLE = re.compile(
    r"\b(?:samples?|observations?|readings?|measurements?|times?|scores?)\b", re.I
)
FactIdentity = tuple[str, str, str | None, str, str, str]


@dataclass(frozen=True)
class Observation:
    reading: Element
    label: Span | None
    measure: str
    date: Element | None = None
    scope: str = ""
    caption: str = ""
    action: str = ""
    actor: str = ""
    context: int | None = None
    continues: bool = False

    def identity(self) -> FactIdentity:
        return (
            words_key(self.label.text) if self.label else "",
            words_key(self.measure),
            self.date.value if self.date else None,
            self.scope,
            self.action,
            self.actor,
        )


@dataclass(frozen=True)
class Partition:
    whole: Observation
    parts: tuple[Observation, ...]


@dataclass(frozen=True)
class Sample:
    group: Span
    observations: tuple[Element, ...]


@dataclass(frozen=True)
class Observations:
    facts: tuple[Observation, ...]
    partitions: tuple[Partition, ...]
    samples: tuple[Sample, ...]


def _span(clause: Clause, match: re.Match[str], name: str) -> Span:
    return clause.slice(*match.span(name))


def _subject(head: Span, names: dict[int, Element]) -> tuple[Span | None, str]:
    """Keep the full measure; a named subject is not part of its name."""
    lead = _ARTICLE.match(head.text)
    start = lead.end() if lead else 0
    match = _PROPER.match(head.text, start)
    named = names.get(head.start + start)
    if named is not None and named.span_end <= head.end:
        end = named.span_end - head.start
    elif match is not None and (match.end() < len(head.text) or start == 0):
        end = match.end()
    else:
        return None, head.text[start:]
    possessive = _POSSESSIVE.match(head.text, end)
    measure = head.text[possessive.end() if possessive else end :].strip()
    return Span(head.start + start, head.start + end, head.text[start:end]), measure


def _monetary(clause: Clause, adjacent: Observation | None) -> Observation | None:
    if not (match := _MONEY.fullmatch(clause.masked)):
        return None
    reading = clause.element(match, "q")
    if reading.unit is None:
        return None
    scope = words_key(match["scope"] or "")
    if _NEW_CONTEXT.search(scope):
        return None
    actor = words_key(match["actor"])
    continued = bool(match["also"]) and adjacent is not None
    if _INDIRECT_ACTOR.fullmatch(actor):
        if not continued or adjacent is None:
            return None
        actor = adjacent.actor
    context = (
        adjacent.context
        if continued and adjacent is not None and actor == adjacent.actor
        else clause.start
    )
    label = _span(clause, match, "label")
    return Observation(
        reading,
        label,
        label.text,
        scope=scope,
        actor=actor,
        context=context,
        caption="Return ordered" if match["action"].casefold().startswith("ordered") else "",
        action="monetary",
    )


def _simple(clause: Clause, names: dict[int, Element]) -> Observation | None:
    if matched := _PRICE.fullmatch(clause.masked):
        reading = clause.element(matched, "q")
        if reading.unit in {"$", "\u00a3", "\u20ac", "\u20b9"}:
            label = _span(clause, matched, "offer" if matched["offer"] else "opening")
            return Observation(reading, label, "share price")
    if not (matched := _SIMPLE.fullmatch(clause.masked)):
        return None
    if matched["early"] and matched["late"]:
        return None
    dated = "early" if matched["early"] else "late" if matched["late"] else None
    head = _span(clause, matched, "head")
    name, measure = _subject(head, names)
    verb = matched["verb"].casefold()
    action = verb if verb in {"approved", "produced", "generated"} else ""
    tail_measure = _span(clause, matched, "measure").text if matched["measure"] else ""
    if tail_measure and measure:
        return None
    if not (tail_measure or measure or action) and name is not None:
        if name.start not in names and not name.text.isupper():
            measure = name.text
            name = None
    relative = _span(clause, matched, "relative").text if matched["relative"] else ""
    return Observation(
        clause.element(matched, "q"),
        name,
        tail_measure or measure,
        date=clause.element(matched, dated) if dated else None,
        scope=words_key(relative),
        caption=f"Stated period: {relative}" if relative.startswith("in ") else "",
        action=action,
        continues=bool(matched["closing"]) or words_key(relative) == "on the same day",
    )


def _subclauses(clause: Clause, separators: re.Pattern[str]) -> list[Clause]:
    cuts = list(separators.finditer(clause.masked))
    return [
        clause.subclause(lo, hi)
        for lo, hi in zip(
            [0, *(match.end() for match in cuts)],
            [*(match.start() for match in cuts), len(clause.masked)],
            strict=True,
        )
    ]


def _named_parts(clause: Clause, pattern: re.Pattern[str], measure: str) -> tuple[Observation, ...]:
    result: list[Observation] = []
    for piece in _subclauses(clause, _LIST):
        match = pattern.fullmatch(piece.masked)
        if match is None:
            return ()
        result.append(Observation(piece.element(match, "q"), _span(piece, match, "label"), measure))
    return tuple(result)


def _partition(clause: Clause) -> Partition | None:
    match = _WHOLE.fullmatch(clause.masked)
    if match is None:
        return None
    group = _span(clause, match, "group")
    measure = words_key(group.text).removeprefix("total ")
    parts = _named_parts(clause.subclause(*match.span("parts")), _PART, measure)
    if len(parts) < 2:
        return None
    return Partition(Observation(clause.element(match, "q"), group, measure), parts)


def _sample(clause: Clause) -> Sample | None:
    match = _GROUP.fullmatch(clause.masked)
    if match is None:
        return None
    group = _span(clause, match, "group")
    if not _NAMED_SAMPLE.search(group.text):
        return None
    values = []
    for piece in _subclauses(clause.subclause(*match.span("values")), _LIST):
        held = re.fullmatch(rf"\s*(?P<q>{_Q}) *", piece.masked)
        if held is None:
            return None
        values.append(piece.element(held, "q"))
    return Sample(group, tuple(values)) if len(values) > 1 else None


def _forecast(clause: Clause) -> tuple[Observation, ...]:
    match = _FORECAST.fullmatch(clause.masked)
    if match is None:
        return ()
    caption = clause.slice(0, match.start("stop")).text
    measure = _span(clause, match, "group").text + " growth"
    return tuple(
        replace(row, date=clause.element(match, "date"), caption=caption, scope="annual forecast")
        for row in _named_parts(clause.subclause(*match.span("parts")), _AT, measure)
    )


def _relationship(clause: Clause) -> tuple[Observation, ...]:
    if match := _RELATION.fullmatch(clause.masked):
        name = _span(clause, match, "name")
        reported, counted = (clause.element(match, role) for role in ("y", "x"))
        denominator = NUMBER.fullmatch(counted.span_excerpt)
        if (
            reported.unit and counted.unit and reported.unit != counted.unit
            and denominator is not None and denominator["unit"]
        ):
            return (
                Observation(reported, name, reported.unit, action="reported"),
                Observation(counted, name, denominator["unit"]),
            )
    match = _AXES.fullmatch(clause.masked)
    if match is None:
        return ()
    name = _span(clause, match, "name")
    values = []
    for piece in _subclauses(clause.subclause(*match.span("values")), _LIST):
        if (found := _NAMED_VALUE.fullmatch(piece.masked)) is None:
            return ()
        values.append(
            Observation(piece.element(found, "q"), name, _span(piece, found, "measure").text)
        )
    return tuple(values) if len(values) > 1 else ()


def _change(clause: Clause, names: dict[int, Element]) -> tuple[Observation, ...]:
    if not (match := _CHANGE.fullmatch(clause.masked)):
        return ()
    name, measure = _subject(_span(clause, match, "head"), names)
    if name is None or not measure:
        return ()
    return tuple(
        Observation(clause.element(match, q), name, measure, date=clause.element(match, date))
        for q, date in (("first", "early"), ("second", "late"))
    )


def read_observations(text: str, table: ElementTable) -> Observations:
    """Read relations, not just co-occurrences of substrings in the same sentence."""
    facts: list[Observation] = []
    partitions: list[Partition] = []
    samples: list[Sample] = []
    names = {
        item.span_start: item
        for item in table.elements
        if item.kind in {ElementKind.ENTITY, ElementKind.PLACE}
    }
    last_money: tuple[int, Observation] | None = None
    last_simple: tuple[int, Observation] | None = None
    for sentence in source_clauses(text, table):
        adjacent = _adjacent(last_money, text, sentence.start)
        parallel = _adjacent(last_simple, text, sentence.start)
        end = sentence.start + len(sentence.text)
        last_money = None
        last_simple = None
        if (
            adjacent is not None
            and (continuing := _ENFORCEMENT_CONTINUES.fullmatch(sentence.masked))
            and words_key(continuing["actor"]) == adjacent.actor
            and not _NEW_CONTEXT.search(sentence.masked)
        ):
            # This action names the same actor in the reported enforcement sequence.
            # Its quantity is not another monetary amount.
            last_money = (end, adjacent)
            continue
        if _UNSAFE.search(sentence.masked):
            if expected := _forecast(sentence):
                facts.extend(expected)
            else:
                # A later forecast does not turn a preceding independent,
                # fully stated actual into a forecast.
                clauses = _subclauses(sentence, _AND)
                if len(clauses) > 1 and not _UNSAFE.search(clauses[0].masked):
                    if actual := _simple(clauses[0], names):
                        facts.append(actual)
            continue
        if partition := _partition(sentence):
            partitions.append(partition)
            continue
        if sample := _sample(sentence):
            samples.append(sample)
            continue
        if related := _relationship(sentence) or _change(sentence, names):
            facts.extend(related)
            continue
        if money := _monetary(sentence, adjacent):
            facts.append(money)
            last_money = (end, money)
            continue
        for index, clause in enumerate(_subclauses(sentence, _AND)):
            observed = _simple(clause, names)
            if observed is None:
                parallel = None
                continue
            if (
                not observed.measure and observed.date is None
                and (observed.continues or index > 0)
                and parallel is not None and parallel.measure and parallel.date is None
                and observed.action and observed.action == parallel.action
                and observed.reading.unit == parallel.reading.unit
                and (not observed.scope or observed.scope == "on the same day")
            ):
                observed = replace(
                    observed, measure=parallel.measure, scope=parallel.scope,
                    caption=parallel.caption,
                )
            facts.append(observed)
            parallel = observed
        if parallel is not None:
            last_simple = (end, parallel)
    return Observations(tuple(facts), tuple(partitions), tuple(samples))


def _adjacent(
    previous: tuple[int, Observation] | None, text: str, start: int,
) -> Observation | None:
    return previous[1] if previous is not None and not text[previous[0]:start].strip() else None
