//! Which corrected host values and shared scalar constraints cross a boundary?

use chrono::{Datelike, NaiveDate, NaiveDateTime};
use regex::Regex;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub type Result<T> = std::result::Result<T, String>;
pub const VERSION: &str = "2026-10-10";
pub const HOST_PRODUCER: &str = "telemetry.silicon";

pub trait Validate {
    fn validate(&self) -> Result<()>;
}

// A closed wire shape validates before it becomes a usable contract.
macro_rules! contract {
    ($name:ident { $($(#[$meta:meta])* $field:ident: $ty:ty),* $(,)? }) => {
        #[derive(Debug, Clone, PartialEq, serde::Serialize)]
        pub struct $name { $($(#[$meta])* pub $field: $ty),* }
        impl<'de> serde::Deserialize<'de> for $name {
            fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> std::result::Result<Self, D::Error> {
                #[derive(serde::Deserialize)]
                #[serde(deny_unknown_fields)]
                struct Wire { $($(#[$meta])* $field: $ty),* }
                let wire = Wire::deserialize(deserializer)?;
                let result = Self { $($field: wire.$field),* };
                $crate::contracts::host::Validate::validate(&result).map_err(serde::de::Error::custom)?;
                Ok(result)
            }
        }
    };
}
pub(crate) use contract;

pub fn require(condition: bool, message: &str) -> Result<()> {
    if condition {
        Ok(())
    } else {
        Err(message.to_owned())
    }
}
pub fn pattern(value: &str, expression: &str, name: &str) -> Result<()> {
    require(
        Regex::new(expression)
            .map_err(|e| e.to_string())?
            .is_match(value),
        name,
    )
}
pub fn day(value: &str) -> Result<()> {
    let date = NaiveDate::parse_from_str(value, "%Y-%m-%d").map_err(|e| e.to_string())?;
    require(
        date.year() > 0 && date.format("%Y-%m-%d").to_string() == value,
        "noncanonical UTC day",
    )
}
pub fn timestamp(value: &str) -> Result<()> {
    pattern(
        value,
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
        "invalid UTC timestamp",
    )?;
    let parsed =
        NaiveDateTime::parse_from_str(value, "%Y-%m-%dT%H:%M:%SZ").map_err(|e| e.to_string())?;
    require(
        parsed.year() > 0 && value.get(17..19).is_some_and(|seconds| seconds < "60"),
        "invalid UTC calendar instant",
    )?;
    Ok(())
}
pub fn run_id(value: &str) -> Result<()> {
    pattern(value, r"^\d{4}-\d{2}-\d{2}-[0-9]+$", "invalid run_id")
}
pub fn rel_path(value: &str) -> Result<()> {
    require(
        value.chars().count() <= 512,
        "relative path exceeds 512 characters",
    )?;
    pattern(
        value,
        r"^[A-Za-z0-9._-]*[A-Za-z0-9_-][A-Za-z0-9._-]*(/[A-Za-z0-9._-]*[A-Za-z0-9_-][A-Za-z0-9._-]*)*$",
        "invalid relative path",
    )
}
pub fn hex(value: &str, length: usize) -> Result<()> {
    require(
        value.len() == length
            && value
                .bytes()
                .all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)),
        "invalid lowercase hexadecimal",
    )
}
pub fn token(value: &str) -> Result<()> {
    require(value.len() <= 128, "token exceeds 128 characters")?;
    pattern(value, r"^[a-z0-9][a-z0-9_.-]*$", "invalid token")
}
pub fn nonnegative(value: i64) -> Result<()> {
    require(value >= 0, "count must be nonnegative")
}
pub fn positive(value: i64) -> Result<()> {
    require(value > 0, "count must be positive")
}
pub fn finite(value: f64, minimum: f64, strict: bool) -> Result<()> {
    require(
        value.is_finite()
            && if strict {
                value > minimum
            } else {
                value >= minimum
            },
        "invalid finite number",
    )
}
pub fn default_true() -> bool {
    true
}
pub fn default_job() -> ServerJob {
    ServerJob::Work
}
pub fn default_version() -> String {
    VERSION.to_owned()
}
pub fn required_nullable<'de, D: serde::Deserializer<'de>, T: Deserialize<'de>>(
    deserializer: D,
) -> std::result::Result<Option<T>, D::Error> {
    Option::deserialize(deserializer)
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ServerJob {
    Plan,
    Work,
    Assemble,
    Visuals,
    Runtime,
    Decide,
    Migrate,
    #[serde(rename = "run-tasks")]
    RunTasks,
    History,
    SaveCouncilResults,
    Collect,
    Operator,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum QuotaState {
    Finite,
    Unlimited,
    Unavailable,
}

contract!(CorrectedHostFingerprintRow {
    #[serde(default="default_version")] version: String, date: String, run_id: String,
    #[serde(default = "default_job")] job: ServerJob,
    shard: i64,
    #[serde(default)] fingerprint: Option<String>,
    #[serde(default)] fingerprint_version: Option<i64>,
    #[serde(default)] cpu_model: Option<String>,
    #[serde(default)] cpu_vendor: Option<String>,
    #[serde(default)] cpu_family: Option<i64>,
    #[serde(default)] cpu_model_number: Option<i64>,
    #[serde(default)] cpu_stepping: Option<i64>,
    #[serde(default)] microcode: Option<String>,
    #[serde(default)] cpu_physical_cores: Option<i64>,
    #[serde(default)] cpu_logical_processors: Option<i64>,
    #[serde(default)] cpu_allowed_processors: Option<i64>,
    #[serde(default)] cpu_quota_cores: Option<f64>,
    #[serde(default)] cpu_quota_state: Option<QuotaState>,
    #[serde(default)] cpu_target_measured_at: Option<String>,
    #[serde(default)] l3_cache_bytes: Option<i64>,
    #[serde(default)] cpu_observed_mhz: Option<f64>,
    #[serde(default)] cpu_reported_max_mhz: Option<f64>,
    #[serde(default)] flags: String,
    #[serde(default)] boot_seconds: Option<f64>,
    #[serde(default)] memcpy_gib_s: Option<f64>,
    #[serde(default)] memcpy_probe_mib: Option<i64>,
    #[serde(default)] vm_size: Option<String>,
    #[serde(default)] vm_location: Option<String>,
    #[serde(default)] vm_zone: Option<String>,
    #[serde(default)] vm_fault_domain: Option<String>,
    #[serde(default)] runner_name: Option<String>,
    #[serde(default)] measured_at: Option<String>,
    #[serde(default)] model_load_ms: Option<f64>,
    #[serde(default)] job_seconds: Option<i64>,
    #[serde(default)] server_prompt_tokens: Option<i64>,
    #[serde(default)] server_prompt_seconds: Option<f64>,
});
impl Validate for CorrectedHostFingerprintRow {
    fn validate(&self) -> Result<()> {
        require(self.version == VERSION, "unknown corrected host schema")?;
        pattern(&self.date, r"^\d{4}-\d{2}-\d{2}$", "invalid date stamp")?;
        run_id(&self.run_id)?;
        nonnegative(self.shard)?;
        for value in [
            self.cpu_physical_cores,
            self.cpu_logical_processors,
            self.cpu_allowed_processors,
        ]
        .into_iter()
        .flatten()
        {
            positive(value)?;
        }
        for value in [
            self.l3_cache_bytes,
            self.memcpy_probe_mib,
            self.job_seconds,
            self.server_prompt_tokens,
        ]
        .into_iter()
        .flatten()
        {
            nonnegative(value)?;
        }
        for value in [
            self.cpu_quota_cores,
            self.cpu_observed_mhz,
            self.cpu_reported_max_mhz,
            self.memcpy_gib_s,
        ]
        .into_iter()
        .flatten()
        {
            finite(value, 0.0, true)?;
        }
        for value in [
            self.boot_seconds,
            self.model_load_ms,
            self.server_prompt_seconds,
        ]
        .into_iter()
        .flatten()
        {
            finite(value, 0.0, false)?;
        }
        for value in [&self.measured_at, &self.cpu_target_measured_at]
            .into_iter()
            .flatten()
        {
            timestamp(value)?;
        }
        require(
            self.fingerprint.is_some() == self.fingerprint_version.is_some(),
            "fingerprint and version must coexist",
        )?;
        if let Some(version) = self.fingerprint_version {
            require(
                version == 1 || version == 2,
                "unknown fingerprint algorithm",
            )?;
            hex(self.fingerprint.as_deref().unwrap_or(""), 16)?;
            if version == 2 {
                require(
                    self.fingerprint == self.fingerprint_v2()?,
                    "algorithm 2 fingerprint mismatch",
                )?;
            }
        }
        require(
            self.cpu_quota_cores.is_some() == (self.cpu_quota_state == Some(QuotaState::Finite)),
            "finite quota contradicts value",
        )?;
        require(
            self.cpu_target_measured_at.is_some() == self.cpu_quota_state.is_some(),
            "target time contradicts quota state",
        )?;
        if self.cpu_allowed_processors.is_some() {
            require(
                self.cpu_target_measured_at.is_some() && self.cpu_logical_processors.is_some(),
                "allowed count needs captured target and logical count",
            )?;
        }
        if let Some(logical) = self.cpu_logical_processors {
            for count in [self.cpu_physical_cores, self.cpu_allowed_processors]
                .into_iter()
                .flatten()
            {
                require(count <= logical, "CPU count exceeds logical count")?;
            }
        }
        if let (Some(target), Some(probe)) = (&self.cpu_target_measured_at, &self.measured_at) {
            require(target >= probe, "target capture precedes probe")?;
        }
        Ok(())
    }
}
impl CorrectedHostFingerprintRow {
    pub fn fingerprint_v2(&self) -> Result<Option<String>> {
        let numbers = [self.cpu_family, self.cpu_model_number, self.cpu_stepping];
        require(
            !numbers.into_iter().flatten().any(|v| v < 0),
            "algorithm 2 CPU identifiers must be nonnegative",
        )?;
        let flags = self.flags.split_whitespace().collect::<Vec<_>>();
        const WATCHED: &[&str] = &[
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
        require(
            self.flags == flags.join(" ")
                && !flags.windows(2).any(|v| v[0] >= v[1])
                && !flags.iter().any(|v| !WATCHED.contains(v)),
            "fingerprint flags must be watched, sorted and space-joined",
        )?;
        let sourced = [&self.cpu_model, &self.cpu_vendor]
            .into_iter()
            .flatten()
            .any(|v| !v.trim().is_empty())
            || numbers.into_iter().any(|v| v.is_some())
            || self.l3_cache_bytes.is_some_and(|v| v > 0)
            || !flags.is_empty();
        if !sourced {
            return Ok(None);
        }
        #[derive(Serialize)]
        struct Facts<'a> {
            cpu_vendor: &'a Option<String>,
            cpu_family: Option<i64>,
            cpu_model_number: Option<i64>,
            cpu_stepping: Option<i64>,
            cpu_model: &'a Option<String>,
            l3_cache_bytes: Option<i64>,
            flags: &'a str,
        }
        let facts = Facts {
            cpu_vendor: &self.cpu_vendor,
            cpu_family: self.cpu_family,
            cpu_model_number: self.cpu_model_number,
            cpu_stepping: self.cpu_stepping,
            cpu_model: &self.cpu_model,
            l3_cache_bytes: self.l3_cache_bytes,
            flags: &self.flags,
        };
        Ok(Some(
            crate::canonical_json::sha256(&crate::canonical_json::object_bytes(&facts)?)[..16]
                .to_owned(),
        ))
    }
}

contract!(HostStoredRow {
    #[serde(flatten)]
    host: CorrectedHostFingerprintRow,
    ledger: String,
    covers: String,
    attempt: i64,
    #[serde(deserialize_with = "canonical_unit")]
    unit_id: Uuid,
});
fn canonical_unit<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> std::result::Result<Uuid, D::Error> {
    let text = String::deserialize(deserializer)?;
    let unit = Uuid::parse_str(&text).map_err(serde::de::Error::custom)?;
    require(
        unit.to_string() == text && unit.get_version_num() == 5,
        "stored unit requires canonical lowercase UUID5",
    )
    .map_err(serde::de::Error::custom)?;
    Ok(unit)
}
impl Validate for HostStoredRow {
    fn validate(&self) -> Result<()> {
        self.host.validate()?;
        positive(self.attempt)?;
        require(
            self.ledger == "host-fingerprint" && self.covers == self.host.date,
            "stored ledger/day contradiction",
        )?;
        require(
            self.unit_id
                == host_unit_id(
                    &self.covers,
                    &self.host.run_id,
                    self.host.job,
                    self.host.shard,
                )?,
            "stored logical unit mismatch",
        )
    }
}
pub fn job_text(job: ServerJob) -> String {
    serde_json::to_value(job)
        .expect("finite enum")
        .as_str()
        .expect("string enum")
        .to_owned()
}
pub use crate::ledger::filenames::{file_id as host_file_id, unit_id as host_unit_id};
