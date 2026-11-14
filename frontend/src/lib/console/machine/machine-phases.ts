/** What is the mean phase time per article for each CPU and reported L3 group? */
import type { Row } from '../../data/ledger';
import { shardPhases } from './shard-phases';

export function machinePhases(rows: readonly Row[], hosts: readonly Row[]) {
	const work = shardPhases(rows, hosts);
	const groups = new Map<string, {
		key: string; cpuModels: string[]; l3CacheBytes: number[];
		articles: number; shards: number; prefill: number; decode: number; input: number; output: number
	}>();
	for (const shard of work.shards) {
		const key = JSON.stringify([shard.cpuModels, shard.l3CacheBytes]);
		const held = groups.get(key) ?? {
			key, cpuModels: shard.cpuModels, l3CacheBytes: shard.l3CacheBytes,
			articles: 0, shards: 0, prefill: 0, decode: 0, input: 0, output: 0
		};
		held.articles += shard.articles;
		held.shards++;
		held.prefill += shard.prefill;
		held.decode += shard.decode;
		held.input += shard.input;
		held.output += shard.output;
		groups.set(key, held);
	}
	return {
		excluded: work.excluded,
		machines: [...groups.values()].map((group) => {
			const prefill = group.prefill / group.articles;
			const decode = group.decode / group.articles;
			return {
				key: group.key, cpuModels: group.cpuModels, l3CacheBytes: group.l3CacheBytes,
				articles: group.articles, shards: group.shards, prefill, decode, total: prefill + decode,
				prefillShare: 100 * group.prefill / (group.prefill + group.decode),
				prefillTps: group.input / group.prefill, decodeTps: group.output / group.decode
			};
		})
	};
}
