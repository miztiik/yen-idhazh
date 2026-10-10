//! Which ordered scalar columns exist even when no host rows exist?

use crate::{Result, contracts::host::require};
use serde::Serialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum ColumnType {
    String,
    Int64,
    Float64,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub struct Column {
    pub name: &'static str,
    pub r#type: ColumnType,
    pub nullable: bool,
}
macro_rules! columns {($($name:literal:$ty:ident:$nullable:literal),*$(,)?)=>{&[$(Column{name:$name,r#type:ColumnType::$ty,nullable:$nullable}),*]};}
pub const HOST_COLUMNS: &[Column] = columns![
    "version":String:false,"date":String:false,"run_id":String:false,"job":String:false,
    "shard":Int64:false,"fingerprint":String:true,"fingerprint_version":Int64:true,
    "cpu_model":String:true,"cpu_vendor":String:true,"cpu_family":Int64:true,
    "cpu_model_number":Int64:true,"cpu_stepping":Int64:true,"microcode":String:true,
    "cpu_physical_cores":Int64:true,"cpu_logical_processors":Int64:true,
    "cpu_allowed_processors":Int64:true,"cpu_quota_cores":Float64:true,"cpu_quota_state":String:true,
    "cpu_target_measured_at":String:true,"l3_cache_bytes":Int64:true,"cpu_observed_mhz":Float64:true,
    "cpu_reported_max_mhz":Float64:true,"flags":String:false,"boot_seconds":Float64:true,
    "memcpy_gib_s":Float64:true,"memcpy_probe_mib":Int64:true,"vm_size":String:true,
    "vm_location":String:true,"vm_zone":String:true,"vm_fault_domain":String:true,
    "runner_name":String:true,"measured_at":String:true,"model_load_ms":Float64:true,
    "job_seconds":Int64:true,"server_prompt_tokens":Int64:true,"server_prompt_seconds":Float64:true,
    "ledger":String:false,"covers":String:false,"attempt":Int64:false,"unit_id":String:false,
];
pub fn columns_for(ledger: &str, version: &str) -> Result<&'static [Column]> {
    require(
        ledger == "host-fingerprint" && version == crate::contracts::host::VERSION,
        "unsupported ledger or logical schema",
    )?;
    Ok(HOST_COLUMNS)
}
