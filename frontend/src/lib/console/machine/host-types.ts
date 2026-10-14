/** The host contract shape and the instruction-set flags native machine cards draw. */
export const SERVER_JOB = [
	'plan',
	'work',
	'assemble',
	'visuals',
	'runtime',
	'decide',
	'migrate',
	'run-tasks',
	'history',
	'save_council_results',
	'collect',
	'operator'
] as const;

export type ServerJob = (typeof SERVER_JOB)[number];

export const WATCHED_FLAG = [
	'amx_bf16',
	'amx_int8',
	'amx_tile',
	'avx2',
	'avx512_bf16',
	'avx512_fp16',
	'avx512_vnni',
	'avx512f',
	'avx_vnni',
	'f16c',
	'fma',
	'sse4_2'
] as const;

export type WatchedFlag = (typeof WATCHED_FLAG)[number];

/** Hand-written HostFingerprintRow, held to the producer by the field-set test. */
export interface HostFingerprintRow {
	version?: string;
	date: string;
	run_id: string;
	job?: ServerJob | string | null;
	pipeline_name?: string | null;
	task_name?: string | null;
	shard: number;
	fingerprint?: string | null;
	fingerprint_version?: number | null;
	cpu_model?: string | null;
	cpu_vendor?: string | null;
	cpu_family?: number | null;
	cpu_model_number?: number | null;
	cpu_stepping?: number | null;
	microcode?: string | null;
	cpu_physical_cores?: number | null;
	cpu_logical_processors?: number | null;
	cpu_allowed_processors?: number | null;
	cpu_quota_cores?: number | null;
	cpu_quota_state?: string | null;
	cpu_target_measured_at?: string | null;
	l3_cache_bytes?: number | null;
	cpu_observed_mhz?: number | null;
	cpu_reported_max_mhz?: number | null;
	flags?: string;
	boot_seconds?: number | null;
	memcpy_gib_s?: number | null;
	memcpy_probe_mib?: number | null;
	vm_size?: string | null;
	vm_location?: string | null;
	vm_zone?: string | null;
	vm_fault_domain?: string | null;
	runner_name?: string | null;
	measured_at?: string | null;
	model_load_ms?: number | null;
	job_seconds?: number | null;
	server_prompt_tokens?: number | null;
	server_prompt_seconds?: number | null;
}

export type HostFingerprint = Required<HostFingerprintRow> & { fingerprint: string };

/** The probe's own order, bound to WatchedFlag by the vocabulary test. */
export function watchedFlags(): WatchedFlag[] {
	return [...WATCHED_FLAG];
}
