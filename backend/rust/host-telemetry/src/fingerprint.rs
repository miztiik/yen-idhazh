//! Which sourced static hardware facts give a new row its algorithm-2 identity?

use crate::contracts::host::{CorrectedHostFingerprintRow, Result};
use std::collections::{BTreeMap, BTreeSet};

pub const WATCHED_FLAGS: [&str; 12] = [
    "amx_bf16",
    "amx_int8",
    "amx_tile",
    "avx2",
    "avx512_bf16",
    "avx512_fp16",
    "avx512_vnni",
    "avx512f",
    "avx_vnni",
    "f16c",
    "fma",
    "sse4_2",
];
pub fn hardware(
    row: &mut CorrectedHostFingerprintRow,
    cpuinfo: Option<&str>,
    cache: Option<i64>,
) -> Result<()> {
    let mut fields = BTreeMap::new();
    for line in cpuinfo.unwrap_or("").lines() {
        if let Some((key, value)) = line.split_once(':') {
            fields.entry(key.trim()).or_insert(value.trim());
        }
    }
    let string = |key| {
        fields
            .get(key)
            .filter(|v| !v.is_empty())
            .map(|v| (*v).to_owned())
    };
    let integer = |key| {
        fields
            .get(key)
            .and_then(|v| v.parse::<i64>().ok())
            .filter(|v| *v >= 0)
    };
    row.cpu_model = string("model name");
    row.cpu_vendor = string("vendor_id");
    row.cpu_family = integer("cpu family");
    row.cpu_model_number = integer("model");
    row.cpu_stepping = integer("stepping");
    row.microcode = string("microcode");
    row.l3_cache_bytes = cache.filter(|v| *v > 0);
    let present: BTreeSet<_> = fields
        .get("flags")
        .into_iter()
        .flat_map(|v| v.split_whitespace())
        .collect();
    row.flags = WATCHED_FLAGS
        .into_iter()
        .filter(|v| present.contains(v))
        .collect::<Vec<_>>()
        .join(" ");
    row.fingerprint = row.fingerprint_v2()?;
    row.fingerprint_version = row.fingerprint.as_ref().map(|_| 2);
    Ok(())
}
