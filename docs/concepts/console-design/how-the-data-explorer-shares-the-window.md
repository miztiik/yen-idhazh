# How the Data explorer shares the window

**Last Updated**: 2026-10-05

Where each region of the Data explorer stands, how much of the window it takes, and what holds still while an operator uses it. The words, states and colours on the page are ruled by [../console-design.md](../console-design.md).

## The workbench fills the window

The Data explorer uses the whole browser window below the site header and the route strip, at every width. No region has a fixed size: each takes a share of the window, and each scrolls inside itself. The route's workbench chrome lifts the console's width cap, leaves out the site footer, and runs the workbench to the window's edges; the header keeps its gutter.

From 1024 px the workbench is two halves of the window's height. The top half asks: the span and the dates, the question chips, then three columns - the ledger rail, the editor with the status bar under it, and the column rail. Each rail takes one sixth of the width and never less than 12rem; the editor takes the rest. The bottom half answers: the answer table on the left and the chart on the right, each half the width. Each half keeps the smallest size its parts need - the editor at least `console.explorer_editor_lines_shown[1]` lines, the chart at least one chart's height - so a window too short for both makes the page scroll rather than cut a region off. Below 1024 px the regions stack in one column, the page scrolls, and the answer is one window tall.

Run stands at the right end of the editor's heading line, after Save and Copy link, in one group of buttons. It is the group's last button, so naming a question - which turns Save and Copy link into a name field, Keep and Cancel - never moves it. Ctrl+Enter in the editor still runs the question.

The answer has a heading line of its own, one control tall: the word `Answer` at its start, and `Copy as JSON` and `Copy as table` at its end. The chart's heading line carries the word `Chart` and, when more than one shape fits the answer, the shape tiles. What a copy did is said in the page's floating notice.

## A workbench keeps its regions still

The Data explorer is a workbench. Pressing Run, copying text, saving a question, opening History, sorting a column or changing the chart changes only the content inside a region. The toolbar, question row, ledger rail, editor, status bar, column rail, answer region and chart region keep their boxes.

Long content scrolls inside the region that owns it. The SQL editor shows at least a set number of lines, the status bar reserves readout lines, and notices float over the page instead of entering the document flow. No region takes its size from its content, so a long question, a long note or a thousand rows never move the regions around them. The column rail may show ledger columns before a run and answer columns after an answered or quiet run, but the rail's box and its inner scroller keep their size.

## Design rationale

**The Data explorer takes the whole window** (owner, 2026-10-05; the layout is
Jony's). It is a tool an operator works in, so the room a screen has is room
for the question and the answer, not margin. Before, the page was capped at
1,600 px less two gutters and gave every region a fixed size: on a 1920 px
screen 192 px stood empty at each side, and at 1440 x 900 the page scrolled to
1,678 px. Now the regions share the window and the page does not scroll at
1440 x 900 or 1920 x 1080. **What it costs:** the site footer is not on this
page. The wordmark leads to the home page, whose footer carries the same
Archive and Source code links, and the strip already carries the Console link.
The workbench also lost its card edge: at the window's edge a border frames
nothing, and the strip's rule above it is its top edge.

**Two equal halves, and the answer beside the chart.** The top half asks and the
bottom half answers, and the reading order is the order on the page. Side by
side, each half of a 1440 px window draws the 760-unit chart at about 92
percent; a 40 percent share would draw it at 73 percent and shrink its labels.
Each share is a number in the stylesheet, not a setting: a share means something
only beside the others in the same track list, so a setting for one would quietly
change the rest.

**Run is the last button of the group by the editor.** The owner asked for Run
beside Save and Copy link. The last button of a group that stands at the end of
its line never moves when anything to its left changes, so naming a question
moves nothing. The words `DuckDB SQL` give way first, cut short with an
ellipsis, so the line never wraps after a click.

**The copy buttons stand on a line one control tall.** They were 2.75rem
buttons in a heading row one workbench control tall, which is 2rem with a
mouse, so they spilled 6 px over the ledger rail above and 6 px onto the note
below. The buttons now take the control's height, and the message after a copy
moved to the page's floating notice, so a long sentence never widens the line.

## See also

- [../console-design.md](../console-design.md) - the words, states and colours on the console, the Data explorer's included.
- [what-the-data-explorer-borrowed.md](what-the-data-explorer-borrowed.md) - what the page took from the reference workbench, and what it refused.
- [../../architecture/publishing/what-sits-above-every-console-route.md](../../architecture/publishing/what-sits-above-every-console-route.md) - the workbench chrome that gives this route the whole window.
- [../config/appearance.md](../config/appearance.md) - the `console.explorer_*` knobs, the editor's fewest lines among them.
- [../../how-to/query-a-ledger-from-the-console.md](../../how-to/query-a-ledger-from-the-console.md) - asking a question on the page.
