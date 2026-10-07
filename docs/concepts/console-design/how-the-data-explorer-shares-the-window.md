# How the Data explorer shares the window

**Last Updated**: 2026-10-06

Where each region of the Data explorer stands, how much of the window it takes, and what holds still while an operator uses it. The words, states and colours on the page are ruled by [../console-design.md](../console-design.md).

## The workbench fills the window

The Data explorer uses the whole browser window below the site header and the route strip, at every width. No region has a fixed size: each takes a share of the window, and each scrolls inside itself. The route's workbench chrome lifts the console's width cap, leaves out the site footer, and runs the workbench to the window's edges; the header keeps its gutter.

From 1024 px the workbench is two halves of the window's height. The top half asks: the span and the dates, the question chips, then three columns - the ledger rail, the editor with the status bar under it, and the column rail. Each rail takes one sixth of the width and never less than 12rem; the editor takes the rest. The bottom half answers: the answer table on the left and the chart on the right, each half the width. Each half keeps the smallest size its parts need - the editor at least `console.explorer_editor_lines_shown[1]` lines, the chart at least one chart's height - so a window too short for both makes the page scroll rather than cut a region off. Below 1024 px the regions stack in one column, the page scrolls, and the answer is one window tall. The question above it is rounded up to a whole pixel, so the answer starts on a whole pixel wherever the question does.

Run stands at the right end of the editor's heading line, after Save and Copy link, in one group of buttons. It is the group's last button, so naming a question - which turns Save and Copy link into a name field, Keep and Cancel - never moves it. Below 640 px the group stands on a line of its own; Run and the two buttons beside it hold the group's first line, and the name field or `Copy question` takes a whole line beneath them. Save puts focus in the name field with the suggested name selected, and Keep and Cancel put it back on Save. Ctrl+Enter in the editor still runs the question.

The answer has a heading line of its own, one control tall: the word `Answer` at its start, and `Copy as JSON` and `Copy as table` at its end. The chart's heading line carries the word `Chart` and, when more than one shape fits the answer, the shape tiles; the line holds still and the drawing scrolls in its own box beneath it, so nothing passes under the tiles. What a copy did is said in the page's floating notice.

From 640 px the question strip is one line beside the History and how-to links. It shows as many chips as fit, this browser's saved questions first and then the examples, at most `console.explorer_strip_shown[1]`, and folds the rest into `{n} more`, whose list opens under the strip. Saving a question therefore folds an example away instead of making the strip taller. The list closes on a press or a focus anywhere outside it, and that press still does what it pressed; Escape closes it too and puts focus back on `{n} more`. Picking a question from the list closes it and leaves focus on `{n} more`. Forget leaves it open and moves focus to the nearest Forget left in it. Forget on a chip on the line moves focus to the nearest Forget left on the line, then to `{n} more`, then to the last chip on the line, so focus never falls to the page. Below 640 px the strip keeps its column of `console.explorer_strip_shown[0]` chips. History's list hangs from the end of the links, not from History itself, so it opens under them and inside the window at every width. It closes the way `{n} more` does: on a press or a focus outside it, on Escape, and after a pick, which leaves focus on History.

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

**On a phone the name field takes a line of its own.** The page's text uses the system's own face, and faces differ in width. At 390 px Linux's wider face pushed Run alone onto a second line when a question was named, so Run moved; Windows' narrower face kept one line only by squeezing the name field to about 48 px, too small to type a name in. With the buttons on the first line and the field beneath them, Run holds still and the field has the phone's whole width with any face (Jony, 2026-10-06). **What it costs:** the editor moves down one line while a question is named on a phone, which is less than the phone's keyboard moves the page.

**Below 1024 px the question is a whole number of pixels tall** (found 2026-10-06). Its text lines are 1.3rem and 1.6rem tall, 20.8 and 25.6 px, so left to its content the question ended between two pixels - 1,100.375 px tall at 768 px - and so did the answer under it and the page's foot. The browser scrolls and sizes the page in whole pixels, so the window-tall answer could never fill the window exactly, and at 768 px the page's last 0.375 px lay past the last pixel a scroll reaches. The panel pictures could hold neither. Rounding the question adds no fraction of its own, but the strip above it can: in a desktop browser whose scroll bars take room, the strip's tabs show a scroll bar at 390 px and the strip is 42.67 px tall, where the browser that takes the pictures, whose scroll bars take none, measures 33 px. **What it costs:** less than one pixel of empty space at the question's foot. A browser without `calc-size()` keeps the content's height, which moves nothing a reader can see.

**The question strip is one line.** Saving a question added a chip, and on a strip that wraps the chip pushed it onto a second line: at 1440 x 900 the editor, the rails and the status bar moved down 40 px, which breaks the rule that only a region's content changes. A line that folds what does not fit has one height whatever is saved (the executing owner, 2026-10-06).

**Both floating lists close themselves.** While open, `{n} more` lies over the ledger rail and the editor, and History's list over Save, Copy link and Run, so a list that waits to be closed covers what a person reaches for next. After a pick, focus stays on the list's own control rather than in the editor, because a phone's keyboard would rise over the question that was just loaded. One helper, `floating-list.ts`, closes both, so the two cannot drift apart (Jony, 2026-10-06).

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
