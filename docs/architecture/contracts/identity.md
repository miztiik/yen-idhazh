# Identity and Deterministic Identifiers

**Last Updated**: 2026-10-22

How files, work units, events, and correlation contexts are identified across Python and TypeScript stages.

This page is the contract for identifiers under `state/raw/` and pipeline telemetry. Follows [persistence.md](persistence.md) and [schemas.md](schemas.md).

---

## 1. The Four Identifiers

| Identifier | Generation Standard | Seed / Components | Purpose | Lifespan |
| :--- | :--- | :--- | :--- | :--- |
| `unit_id` | RFC 4122 Version 5 (UUIDv5) | Namespace UUID `de055294-e352-5d65-a1b7-d14b5e20844d` + legacy job or pipeline-task seed | Identifies a repeatable unit of work. Identical across job re-runs. | Durable across retries |
| `file_id` | RFC 9562 Version 8 (UUIDv8) | 48-bit Unix millisecond clock + SHA-256(`{unit_id}|{attempt}|{written_at_ms}`) | Names an individual physical file under `state/raw/`. Chronologically sortable. | Immutable per file |
| `event_id` | RFC 4122 UUIDv5 | DNS namespace and the correlation identity plus event sequence | Identifies one typed feed-ingest audit event. | Durable in the event record |
| `correlation_id` | RFC 4122 UUIDv4 | Created once for one execution | Connects records from one execution; it is not file-envelope metadata. | Lifetime of the run |

---

## 2. Unit Identity (`unit_id`)

The `unit_id` answers: **which work unit does this record belong to?**

- **Namespace UUID**: `uuid.uuid5(uuid.NAMESPACE_URL, "github.com/miztiik/yen-idhazh")`, which is `de055294-e352-5d65-a1b7-d14b5e20844d`. The `uuid.NAMESPACE_URL` value is only the input to this calculation.
- **Seeding string**:
  ```
  {ledger}|{covers}|{run_id}|{job}|{shard}|{producer}
  {ledger}|{covers}|{run_id}|{pipeline_name}|{task_name}|{shard}|{producer}
  ```
  The first form is the legacy job identity. The second identifies a pipeline task.
- **Invariance**: When a GitHub Action job fails and is re-run, GitHub preserves the `run_id`. The re-run produces the identical `unit_id`.
- **Compaction resolution**: The ledger compaction union keeps the highest `attempt` for each `unit_id`, cleanly replacing earlier attempts without duplicates.

---

## 3. File Identity (`file_id`)

The `file_id` answers: **which physical file is this on disk?**

Every raw file written through the ledger door carries a newly minted `file_id`. It serves as the filename:
```
state/raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>.parquet
```

### RFC 9562 Version 8 Bit-Packing Layout

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                   unix_ts_ms (high 32 bits)                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|   unix_ts_ms (low 16 bits)    |  ver (0x8)    |  rand_a (12)  |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|var (0b10)|                   rand_b (62 bits)                 |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                       rand_b (continued)                      |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

1. **High 48 bits**: Current UTC instant as epoch milliseconds (`Date.now()` or `written_at_ms`). Guarantees lexicographical and directory sorting by time.
2. **Version nibble (4 bits)**: `0x8` (UUIDv8).
3. **Random bits**: Derived from `SHA-256("{unit_id}|{attempt}|{written_at_ms}")`.
   - `rand_a` (12 bits): The low 12 bits of digest bytes 0 and 1.
   - `variant` (2 bits): `0b10` (RFC 4122/9562 standard variant).
   - `rand_b` (62 bits): The low 62 bits of digest bytes 2 through 9.

Python (`backend/idhazh/ledger/filenames.py`) is the identity authority. The reusable TypeScript writer implements the same bit packing in `packages/ledger-file-writer/src/uuid/`.

---

## 4. Telemetry Event Identity (`event_id`)

`FeedIngestEvent.event_id` is UUIDv5. The live `eventId` is `evt_<event_id>`.
The planner-only event is declared and validated by the
[TypeScript event contract](schemas.md#one-source-of-truth-and-nothing-generated-from-it).
This uses the existing pipeline logger's DNS namespace,
`6ba7b810-9dad-11d1-80b4-00c04fd430c8`, and the same SHA-1 UUIDv5 algorithm.
The planner's audit name is `audit\n{correlation_id}\n{sequence}`; its live
progress name is `progress\n{correlation_id}\n{eventType}\n{sequence}`.
These names distinguish repeated observations without changing the UUID standard.
The shared writer's existing UUIDv5 implementation is reused.

The live envelope retains `timestamp`, `level`, `message`, `eventId`,
`eventType`, `correlationId` and `durationMs`. An audit log includes its actual
typed record under `audit`; `audit_event_type` is the record's payload discriminator.
Rejection ledger rows retain their declared shape; their live progress envelope
has its own UUID event identity.

Owner ruling, 2026-10-22, kumarsnaveen: use the existing UUID logging convention
in current planner events and correlation identities, with no TypeScript legacy
event branch. The earlier SHA event fixtures were implementation fixtures, not
evidence that the Python production planner wrote such events. No historical
ledger file is rewritten or assigned a retrospective UUID.

---

## 5. Correlation Identity (`correlation_id`)

The `correlation_id` binds all operations belonging to a single pipeline invocation.

- **Format**: UUIDv4, for example `7cef34e3-dd9f-40ce-9a56-4d01ff5115cc`.
- **Propagation**: Created once in run context and copied unchanged into logs,
  candidates, rejections, assessments, selections, dispatches, source records,
  measurements and summaries. The numeric dated run ID remains separate.
- **Boundary**: A correlation ID is not metadata in the Parquet file envelope. The envelope carries only its declared identity and provenance fields.

---

## See also

- [persistence.md](persistence.md) - how the ledger door reads and writes file envelopes.
- [schemas.md](schemas.md) - schema rules and contract definitions.
- [../../how-to/execute-a-plan.md](../../how-to/execute-a-plan.md) - execution contract.
