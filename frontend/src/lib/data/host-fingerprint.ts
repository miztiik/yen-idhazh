/** Finite host-row read migration shared by disk and direct slice consumers. */

export const HOST_SCHEMA_VERSION = '2026-10-10';

const LEGACY_VERSIONS = new Set([
	'2026-09-16',
	'2026-09-17',
	'2026-09-18',
	'2026-09-19',
	'2026-09-20'
]);

export const CORRECTED_HOST_COLUMNS = [
	'version',
	'date',
	'run_id',
	'job',
	'shard',
	'fingerprint',
	'fingerprint_version',
	'cpu_model',
	'cpu_vendor',
	'cpu_family',
	'cpu_model_number',
	'cpu_stepping',
	'microcode',
	'cpu_physical_cores',
	'cpu_logical_processors',
	'cpu_allowed_processors',
	'cpu_quota_cores',
	'cpu_quota_state',
	'cpu_target_measured_at',
	'l3_cache_bytes',
	'cpu_observed_mhz',
	'cpu_reported_max_mhz',
	'flags',
	'boot_seconds',
	'memcpy_gib_s',
	'memcpy_probe_mib',
	'vm_size',
	'vm_location',
	'vm_zone',
	'vm_fault_domain',
	'runner_name',
	'measured_at',
	'model_load_ms',
	'job_seconds',
	'server_prompt_tokens',
	'server_prompt_seconds'
] as const;

export const LEGACY_HOST_COLUMNS = ['cores', 'threads', 'mhz_max', 'mhz_at_probe'] as const;

export const HOST_INPUT_COLUMNS = [...CORRECTED_HOST_COLUMNS, ...LEGACY_HOST_COLUMNS] as const;

type InputRow = Readonly<Record<string, unknown>>;

function text(value: unknown): string {
	if (value === null || value === undefined || typeof value === 'boolean') return '';
	return String(value).trim();
}

function positiveFinite(value: unknown): string {
	const raw = text(value);
	if (raw === '') return '';
	const parsed = Number(raw);
	return Number.isFinite(parsed) && parsed > 0 ? raw : '';
}

/** Normalize one declared legacy/current input without carrying legacy aliases onward. */
export function normalizeHostRow(row: InputRow): Record<string, string> | null {
	const sourceVersion = text(row.version);
	if (sourceVersion !== HOST_SCHEMA_VERSION && !LEGACY_VERSIONS.has(sourceVersion)) return null;
	const corrected = sourceVersion === HOST_SCHEMA_VERSION;
	const fingerprint = text(row.fingerprint);
	const fingerprintVersion = corrected
		? text(row.fingerprint_version)
		: fingerprint === ''
			? ''
			: '1';
	if (
		(fingerprint === '') !== (fingerprintVersion === '') ||
		(fingerprintVersion !== '' && fingerprintVersion !== '1' && fingerprintVersion !== '2')
	) {
		return null;
	}
	const migrated: Record<string, string> = {};
	for (const name of CORRECTED_HOST_COLUMNS) migrated[name] = text(row[name]);
	migrated.version = HOST_SCHEMA_VERSION;
	migrated.fingerprint = fingerprint;
	migrated.fingerprint_version = fingerprintVersion;
	if (!corrected) {
		migrated.cpu_physical_cores = '';
		migrated.cpu_logical_processors = '';
		migrated.cpu_allowed_processors = '';
		migrated.cpu_quota_cores = '';
		migrated.cpu_quota_state = '';
		migrated.cpu_target_measured_at = '';
		migrated.cpu_observed_mhz = positiveFinite(row.mhz_at_probe);
		migrated.cpu_reported_max_mhz = '';
	}
	return migrated;
}

export function normalizeHostRows(rows: readonly InputRow[]): Record<string, string>[] {
	return rows.flatMap((row) => {
		const normalized = normalizeHostRow(row);
		return normalized === null ? [] : [normalized];
	});
}
