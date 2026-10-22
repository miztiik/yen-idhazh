/** Generate the six Python-contract ledgers and stage their actual bytes for delivery tests. */
import { execFileSync } from 'node:child_process';
import { copyFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { ledgerCopy } from '../../scripts/published-ledgers.mjs';
import { backendPython } from './backend-python';
import { buildLedger } from './ledger-lifecycle';

export const FEED_LEDGERS = [
	'dispatches', 'rejections', 'source-runs', 'article-assessments', 'diversity', 'editorial-selections'
] as const;

export interface FeedFixture {
	columns: Record<string, { name: string; type: string }[]>;
	rawFile: string;
}

export async function buildFeedLedgers(state: string): Promise<FeedFixture> {
	const repo = resolve('..');
	const fixture: FeedFixture = JSON.parse(execFileSync(backendPython(repo), ['-c', `
import json
import sys
from pathlib import Path
import duckdb
from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Format, Period, WriterIdentity
from idhazh.contracts.ledger_index import CompactEntry, CompactIndex, EntryState
from idhazh.contracts.ledger_name import LedgerName

state = Path(sys.argv[1])
fixtures = Path("tests/fixtures/contracts")
names = {
    "dispatches": "feed-ingest-dispatch/one-article.json",
    "rejections": "feed-ingest-rejection/empty-feed.json",
    "source-runs": "feed-ingest-source-run/one-observation.json",
    "article-assessments": "feed-ingest-article-assessment/one-observation.json",
    "diversity": "feed-ingest-diversity/one-observation.json",
    "editorial-selections": "feed-ingest-editorial-selection/one-article.json",
}
identity = WriterIdentity(
    run_id="2026-10-20-1", attempt=1, job=ServerJob.PLAN, shard=0,
    producer="tests.feed_ledgers", git_sha="a" * 40,
)
columns = {}
for name, fixture in names.items():
    which = LedgerName(name)
    model = ledger.door_contract(which)
    row = model.from_json((fixtures / fixture).read_text(encoding="utf-8"))
    raw = ledger.persist(state, [row], ledger=which, covers="2026-10-20",
                         identity=identity, fmt=Format.PARQUET)
    stored = ledger.load_stored(raw, model=model)
    packed = ledger.persist_period(
        state, stored, model=model, ledger=which, period=Period.DAILY,
        covers="2026-10-20", identity=identity, built_from=1, fmt=Format.PARQUET,
    )
    for file in raw:
        file.unlink()
    daily = [CompactEntry(covers="2026-10-20", rows=1, bytes=packed.stat().st_size)]
    if name == "dispatches":
        earlier = row.model_dump(mode="json")
        earlier["content"]["date"] = earlier["selection"]["date"] = "2026-10-19"
        earlier["content"]["fetched_at"] = "2026-10-19T19:40:00Z"
        raw = ledger.persist(state, [model.model_validate(earlier)], ledger=which, covers="2026-10-19",
                             identity=identity, fmt=Format.PARQUET)
        previous = ledger.persist_period(
            state, ledger.load_stored(raw, model=model), model=model, ledger=which,
            period=Period.DAILY, covers="2026-10-19", identity=identity, built_from=1, fmt=Format.PARQUET,
        )
        daily.insert(0, CompactEntry(covers="2026-10-19", rows=1, bytes=previous.stat().st_size))
        for file in raw:
            file.unlink()
    for period in Period:
        entries = list(daily)
        if period is Period.DAILY:
            entries.append(CompactEntry(covers="2026-10-21", rows=0, bytes=0, state=EntryState.EMPTY))
        else:
            entries = []
        target = ledger.compact_index_path(state, which, period)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(CompactIndex(ledger=which, period=period, entries=entries).to_json(), encoding="utf-8")
    described = duckdb.read_parquet(str(packed))
    columns[name] = [{"name": n, "type": str(t)} for n, t in zip(described.columns, described.types)]
raw = ledger.persist(
    state, [ledger.door_contract(LedgerName("dispatches")).from_json(
        (fixtures / names["dispatches"]).read_text(encoding="utf-8"))],
    ledger=LedgerName("dispatches"), covers="2026-10-23", identity=identity, fmt=Format.PARQUET,
)
print(json.dumps({"columns": columns, "rawFile": raw[0].relative_to(state).as_posix()}))
`, state], {
		cwd: repo, env: { ...process.env, PYTHONPATH: join(repo, 'backend') }, encoding: 'utf8'
	}));
	await buildLedger(state, {
		ledger: 'host-fingerprint', pinned: '2026-10-20', days: [{ ago: 0, rows: 1 }],
		columns: { cores: 4 }
	});
	return fixture;
}

export function stageFeedLedgers(source: string, target: string) {
	const copy = ledgerCopy(source, [...FEED_LEDGERS, 'host-fingerprint']);
	if (copy.refused.length || copy.missing.length) {
		throw new Error(`Fixture publication refused: ${[...copy.refused, ...copy.missing].join('\n')}`);
	}
	const build = join(target, '..', 'publication-build', 'frontend');
	mkdirSync(build, { recursive: true });
	mkdirSync(join(build, '..', 'config'), { recursive: true });
	copyFileSync(resolve('..', 'config', 'ledgers.json'), join(build, '..', 'config', 'ledgers.json'));
	execFileSync(process.execPath, [resolve('scripts', 'stage-publication.mjs')], {
		cwd: build, encoding: 'utf8',
		env: { ...process.env, STATE_ROOT: source, DIGEST_ROOT: join(build, 'public', 'digest') }
	});
	for (const file of copy.files) {
		const destination = join(target, ...file.split('/'));
		mkdirSync(dirname(destination), { recursive: true });
		copyFileSync(join(build, 'static', 'state', ...file.split('/')), destination);
	}
	return copy;
}
