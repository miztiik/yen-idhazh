# What the data explorer borrowed

**Last Updated**: 2026-10-04

The Records page borrowed only the parts of the reference workbench that fit this console's data, trust boundary and visual system.

## What it kept

| Feature | Result | Reason |
| --- | --- | --- |
| Written SQL area | Kept | The page exists for questions no panel author predicted. |
| Run action beside cost | Kept | The operator sees file count and bytes before paying the fetch. |
| Result table | Kept | A free-form answer needs a table before it needs a chart. |
| Shape switch | Kept | The answer may fit more than one chart shape. |
| History and saved questions | Kept | Operators repeat useful questions, and a browser-local list avoids a persisted query contract. |
| Link sharing | Kept | A link can carry a question safely because it never runs it. |
| Documentation mark | Kept as the `docs` icon | The page needs a syntax help link, and the icon joins the existing Lucide system. |

## What it refused

| Feature | Result | Reason |
| --- | --- | --- |
| Separate icon rail and breadcrumb | Refused | The console already owns navigation in the route strip and panel frame. |
| Decorative query-engine metrics | Refused | A number on Records is a reading from this run or it is not printed. |
| Green and red value badges | Refused | A verdict needs a rule, and this page does not know which ledger values are good or bad. |
| Google Material Symbols font | Refused | The repository already has a committed Lucide-derived icon system and a two-way icon test. |
| File download | Refused | Copy as JSON and Copy as table cover the useful handoff without opening spreadsheet formula risk. |

## Rules for the next borrowed feature

1. A number on this page is a reading or it is not printed.
2. The console owns a job once.
3. A verdict needs a rule.

## See also

- [Design system](../design-system.md)
- [Query a ledger from the Records console](../../how-to/query-a-ledger-from-the-console.md)
