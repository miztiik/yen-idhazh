# Report visual attempts

**Last Updated**: 2026-10-31

Produce an on-demand Parquet table file from recorded visual decisions. The
pipeline step that processes each article writes these records under
`state/raw/visual-design-attempts/`. The maintenance step packs older records
under `state/compact/visual-design-attempts/`. The command reads local state
for named UTC dates. It does not collect human input, call a model, fetch
data, change settings or write a ledger.

## Run the command

Use the installed Python development environment. From the repository root,
with PowerShell 7.4 or newer:

```powershell
$env:PYTHONPATH = "backend"
python -m utilities.visual_attempt_report --date 2026-08-21 --date 2026-08-22 > visual-attempts.parquet
```

Repeat `--date YYYY-MM-DD` for each required UTC day. At least one date is
required. Invalid calendar dates, other date formats and timestamps are
refused. Repeated dates count once.

`--state-dir state` selects an explicit local state root. Without it, the
command uses this checkout's existing `state` directory, not the current
working directory. Only requested dates contribute rows. The shared reader
opens the named compact indexes and the raw days or compact files needed for
those dates, not the whole state tree.

Stdout contains binary Parquet, not CSV or text. Stderr carries warnings and
errors separately. PowerShell versions older than 7.4 can convert redirected
native output to text; do not use their `>` or `Out-File` for this command.
Shell redirection can create an empty destination on refusal. A report is
usable only after the command exits successfully.

The existing Parquet adapter writes the report using the configured
`ledger.compression_compact` value. No new dependency or setting is needed.
The file has no ledger envelope and is neither committed pipeline state nor
input to a later pipeline run.

## Read the columns

Each row combines attempts with the same first six column values. These six
columns store strings (text); `attempts` is a required signed 64-bit integer.
Optional columns preserve nulls (no recorded value), not empty strings or
invented labels. The column order is fixed.

**Table A - Report columns**

| ID | Column | Meaning |
| --- | --- | --- |
| A1 | `date` | Requested UTC day recorded on the attempt |
| A2 | `potential_primary` | Recorded article class: `chartable`, `narrative` or `unclassified`; null when unrecorded |
| A3 | `state` | Recorded delivery outcome: `rendered`, `absent` or `render_failed` |
| A4 | `rejection_reason` | First validator check that rejected the original request; null when no rejection was recorded |
| A5 | `planned_type` | Original requested visual type, including one later refused; null when unrecorded |
| A6 | `rendered_type` | Successfully written visual type; null without delivery or when an older row did not record it |
| A7 | `attempts` | Number of recorded attempts after duplicate and retry rules, with the same first six column values |

Rows sort by the first six columns in order, with nulls before recorded
values. Equivalent records produce the same report regardless of argument
order or whether their selected source is raw, daily, monthly or yearly
storage.

A first validator rejection can accompany a successful replacement.
`rendered` means that a visual data file was written, not that it was published
or that a person kept it. Null types on older rendered records stay null; the
command does not reconstruct them from other files. These are recorded-attempt
counts, not quality scores, keep rates or final rejection rates.

## Handle missing records

The shared ledger reader selects one storage source for each day. It removes
duplicate copies and resolves retries using its existing record identities.
Raw and compact copies do not count twice. Separate recorded decisions remain
separate attempts.

The command finishes the read and builds all Parquet bytes before writing any
stdout. It refuses the entire report if the reader marks requested evidence
incomplete, including an unreadable source, incomplete indexes, a missing
indexed file or a day recorded as lost.

A requested date with no recorded rows is named once on stderr. It contributes
no group and no invented zero count. Other dates can still produce a report
when the read is complete. If every requested date has no rows, no Parquet
bytes are emitted.

**Table B - Exit results**

| ID | Exit code | Meaning |
| --- | --- | --- |
| B1 | `0` | Complete, nonempty report written to stdout |
| B2 | `1` | Report refused or I/O failed; inspect stderr and do not use the destination |
| B3 | `2` | Command arguments refused; correct the required UTC dates |

## See also

- [Telemetry](../concepts/telemetry.md#visual-design-attempts) - who records these decisions.
- [The ledger registry](../architecture/contracts/ledger-registry.md#visual-design-attempts) - attempt identities and storage.
- [Run the gates](run-the-gates.md) - the local development checks.
