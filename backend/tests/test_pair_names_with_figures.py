"""Does the builder pair a figure with the name it belongs to, and refuse every table it cannot vouch for?"""

from __future__ import annotations

from typing import Final

import pytest
from support.paths import CONFIG_DIR
from support.prompts import WIND_NAMES, WIND_TEXT, tables_over

from idhazh import config
from idhazh.classify.pair_names_with_figures import (
    TABLE_FORMS,
    FigureTable,
    forms_on_offer,
    tables_of_figures,
)
from idhazh.contracts.article import Article
from idhazh.contracts.knobs.visuals import VisualsConfig
from idhazh.contracts.visual import EncodingRole, VisualType
from idhazh.elements import SpanDriftError
from idhazh.visual_vocabulary import TYPE_RULES

APP: Final = config.load(CONFIG_DIR).app
VISUALS: Final = APP.visuals

WIND: Final = WIND_TEXT
COUNTRIES: Final = (
    "Denmark", "Germany", "Poland", "Ireland", "France", "Spain", "Italy", "Norway", "Sweden",
)

built = tables_over


def rows_of(tables: list[FigureTable]) -> list[list[tuple[str, str, str]]]:
    return [
        [(row.code, row.name.span_excerpt, row.figure.span_excerpt) for row in one.rows]
        for one in tables
    ]


def only_charts_of(*kinds: str, forms: tuple[str, ...] = ("bar",)) -> VisualsConfig:
    return VisualsConfig.model_validate(
        VISUALS.model_dump()
        | {"enabled_kinds": list(kinds), "enabled_types": list(forms), "type_selection_enabled": True}
    )


def test_sentences_that_each_name_a_country_and_its_figure_are_one_table(
    article_ok: Article,
) -> None:
    _, tables = built(article_ok, WIND, WIND_NAMES)

    assert rows_of(tables) == [
        [
            ("r1", "Denmark", "1200 MW"),
            ("r2", "Germany", "900 MW"),
            ("r3", "Poland", "640 MW"),
            ("r4", "Ireland", "410 MW"),
        ]
    ]
    assert forms_on_offer(VISUALS) == (VisualType.BAR, VisualType.DOT)


def test_a_name_followed_by_two_units_gives_a_table_for_each_unit(article_ok: Article) -> None:
    text = (
        "AEM climbed 4.1% to $6.58 when the market opened, while UMS rose 2.4% to $1.68, "
        "and Frencken went up 3.0% to $2.10."
    )
    _, tables = built(article_ok, text, ("AEM", "UMS", "Frencken"))

    assert rows_of(tables) == [
        [("r1", "AEM", "4.1%"), ("r2", "UMS", "2.4%"), ("r3", "Frencken", "3.0%")],
        [("r4", "AEM", "$6.58"), ("r5", "UMS", "$1.68"), ("r6", "Frencken", "$2.10")],
    ]


def test_a_unit_the_service_labelled_a_name_does_not_hide_the_figure_it_sits_in(
    article_ok: Article,
) -> None:
    _, tables = built(article_ok, WIND, WIND_NAMES, others=(("ORG", "MW"),))

    assert [row[1] for row in rows_of(tables)[0]] == list(WIND_NAMES)


def test_a_number_inside_a_name_is_part_of_the_name(article_ok: Article) -> None:
    text = "Alpha 225 climbed 0.6%, Beta 25 gained 0.5% and Gamma 200 rose 0.4%."
    _, tables = built(article_ok, text, (), others=(("ORG", "Alpha 225"), ("ORG", "Beta 25"), ("ORG", "Gamma 200")))

    assert rows_of(tables) == [
        [("r1", "Alpha 225", "0.6%"), ("r2", "Beta 25", "0.5%"), ("r3", "Gamma 200", "0.4%")]
    ]


def test_a_name_inside_a_longer_name_is_not_a_second_name(article_ok: Article) -> None:
    text = (
        "Denmark led the round. Denmark Energy Agency approved 1200 MW. "
        "Germany Energy Agency approved 900 MW. Poland Energy Agency approved 640 MW."
    )
    _, tables = built(
        article_ok,
        text,
        ("Denmark",),
        others=(
            ("ORG", "Denmark Energy Agency"),
            ("ORG", "Germany Energy Agency"),
            ("ORG", "Poland Energy Agency"),
        ),
    )

    assert [row[1] for row in rows_of(tables)[0]] == [
        "Denmark Energy Agency", "Germany Energy Agency", "Poland Energy Agency",
    ]


def test_a_repeated_name_is_paired_where_it_stands_and_cites_its_first_occurrence(
    article_ok: Article,
) -> None:
    text = (
        "Denmark led the round. Denmark approved 1200 MW. Germany approved 900 MW. "
        "Poland approved 640 MW."
    )
    _, tables = built(article_ok, text, ("Denmark", "Germany", "Poland"))

    [denmark, *_] = tables[0].rows
    assert denmark.figure.span_excerpt == "1200 MW"
    assert denmark.name.span_start == text.index("Denmark")


def test_a_sentence_with_no_pair_ends_a_run_and_the_next_table_numbers_on(
    article_ok: Article,
) -> None:
    text = (
        "Denmark approved 1200 MW. Germany approved 900 MW. Poland approved 640 MW. "
        "Analysts were unconvinced. Spain approved 300 MW. France approved 200 MW. "
        "Italy approved 100 MW."
    )
    _, tables = built(
        article_ok, text, ("Denmark", "Germany", "Poland", "Spain", "France", "Italy")
    )

    assert [[row[0] for row in one] for one in rows_of(tables)] == [
        ["r1", "r2", "r3"],
        ["r4", "r5", "r6"],
    ]


def test_a_neighbour_that_names_nothing_is_not_a_list_that_goes_on(article_ok: Article) -> None:
    text = "Output rose 32% on the year. Denmark grew 5%. Germany grew 4%. Poland grew 3%."
    _, tables = built(article_ok, text, ("Denmark", "Germany", "Poland"))

    assert [row[1] for row in rows_of(tables)[0]] == ["Denmark", "Germany", "Poland"]


def test_a_long_name_is_shown_as_the_chart_will_draw_it(article_ok: Article) -> None:
    name = "Waaree Forever Energies Four Private Limited"
    text = f"{name} approved 1200 MW. Germany approved 900 MW. Poland approved 640 MW."
    assert len(name) > VISUALS.max_label_characters

    _, tables = built(article_ok, text, (name, "Germany", "Poland"))

    [long, *_] = tables[0].rows
    assert long.label == name[: VISUALS.max_label_characters - 3] + "..."
    assert long.name.span_excerpt == name


SHARED_START: Final = "The Danish Energy Agency for Offshore Wind Farms"
assert len(SHARED_START) > VISUALS.max_label_characters, "the cut must keep only what both share"
REFUSED: Final = {
    "a repeat of a name hides a pair": (
        "Germany is in Europe. Denmark said Germany built 1200 MW. Poland approved 640 MW. "
        "Ireland approved 410 MW.",
        ("Germany", "Denmark", "Poland", "Ireland"),
    ),
    "two names then two figures": (
        "Denmark and Germany approved 1200 and 900 MW. Poland approved 640 MW. "
        "Ireland approved 410 MW.",
        WIND_NAMES,
    ),
    "a name with two figures of one unit": (
        "Denmark approved 1200 MW, up from 900 MW. Germany approved 900 MW. "
        "Poland approved 640 MW.",
        ("Denmark", "Germany", "Poland"),
    ),
    "a neighbour that names something holds a figure it cannot pair": (
        "1200 MW went to Denmark. Germany approved 900 MW. Poland approved 640 MW. "
        "Ireland approved 410 MW.",
        WIND_NAMES,
    ),
    "a figure before the first name": (
        "1200 MW in Denmark and 900 MW more. Germany approved 640 MW. Poland approved 410 MW. "
        "Ireland approved 300 MW.",
        WIND_NAMES,
    ),
    "a name with a line break": (
        "Bank of\nEngland approved 1200 MW. Germany approved 900 MW. Poland approved 640 MW.",
        ("Bank of\nEngland", "Germany", "Poland"),
    ),
    "a name with a pipe": (
        "Vestas | Siemens approved 1200 MW. Germany approved 900 MW. Poland approved 640 MW.",
        ("Vestas | Siemens", "Germany", "Poland"),
    ),
    "two names the label cut makes equal": (
        f"{SHARED_START} North approved 1200 MW. {SHARED_START} South approved 900 MW. "
        "Poland approved 640 MW.",
        (f"{SHARED_START} North", f"{SHARED_START} South", "Poland"),
    ),
    "figures with no unit": (
        "Denmark finished 12. Germany finished 9. Poland finished 7.",
        ("Denmark", "Germany", "Poland"),
    ),
    "two units in one run": (
        "Denmark approved 1200 MW. Germany approved 900 GW. Poland approved 640 MW.",
        ("Denmark", "Germany", "Poland"),
    ),
    "a name twice in one run": (
        "Denmark approved 1200 MW. Germany approved 900 MW. Denmark approved 640 MW.",
        ("Denmark", "Germany"),
    ),
}


@pytest.mark.parametrize("case", REFUSED)
def test_a_table_the_builder_cannot_vouch_for_is_never_offered(
    article_ok: Article, case: str
) -> None:
    text, names = REFUSED[case]

    _, tables = built(article_ok, text, names)

    assert tables == []


@pytest.mark.parametrize(("count", "tables"), [(2, 0), (3, 1), (8, 1), (9, 0)])
def test_a_table_needs_the_floor_and_is_refused_whole_past_the_ceiling(
    article_ok: Article, count: int, tables: int
) -> None:
    names = COUNTRIES[:count]
    text = " ".join(f"{name} approved {110 + 10 * index} MW." for index, name in enumerate(names))
    assert (VISUALS.min_chart_points, VISUALS.max_chart_points) == (3, 8)

    _, offered = built(article_ok, text, names)

    assert len(offered) == tables


@pytest.mark.parametrize(
    "visuals",
    [only_charts_of(), only_charts_of("chart", forms=("line",))],
    ids=["charts switched off", "neither form selected"],
)
def test_no_table_is_built_when_no_chart_form_could_be_offered(
    article_ok: Article, visuals: VisualsConfig
) -> None:
    _, tables = built(article_ok, WIND, WIND_NAMES, visuals=visuals)

    assert tables == []


def test_every_offered_form_takes_one_name_and_one_figure_a_mark() -> None:
    for form in TABLE_FORMS:
        assert TYPE_RULES[form].required == {EncodingRole.CATEGORY, EncodingRole.QUANTITY}


def test_a_table_built_over_another_text_is_refused(article_ok: Article) -> None:
    table, _ = built(article_ok, WIND, WIND_NAMES)

    with pytest.raises(SpanDriftError):
        tables_of_figures(WIND + " ", table, visuals=VISUALS)
