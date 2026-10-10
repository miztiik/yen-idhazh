//! Which finite codec, collection and bounded transport settings apply?

use crate::contracts::events::{
    CollectionControls, HostCaptureLimits, HostEventLimits, default_version,
};
use crate::contracts::file_envelope::{Compression, Format};
use crate::contracts::host::*;
use serde::{Deserialize, Serialize};

contract!(VerificationLimits {
    max_files: i64,
    max_file_bytes: i64,
    max_total_bytes: i64,
    max_rows: i64,
    max_footer_bytes: i64,
    max_decode_bytes: i64,
    max_thrift_items: i64,
    max_json_depth: i64,
});
impl Validate for VerificationLimits {
    fn validate(&self) -> Result<()> {
        for v in [
            self.max_files,
            self.max_file_bytes,
            self.max_total_bytes,
            self.max_rows,
            self.max_footer_bytes,
            self.max_decode_bytes,
            self.max_thrift_items,
            self.max_json_depth,
        ] {
            positive(v)?;
        }
        Ok(())
    }
}
contract!(ExperimentConfig {
    version: String,
    controls: CollectionControls,
    limits: HostEventLimits,
    capture_limits: HostCaptureLimits,
    verification_limits: VerificationLimits,
});
impl Validate for ExperimentConfig {
    fn validate(&self) -> Result<()> {
        require(self.version == default_version(), "unknown config version")?;
        self.controls.validate()?;
        self.limits.validate()?;
        self.capture_limits.validate()?;
        self.verification_limits.validate()
    }
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Lifecycle {
    Active,
    Paused,
    Retired,
}
contract!(CodecConfig {
    format: Format,
    compression: Compression
});
impl Validate for CodecConfig {
    fn validate(&self) -> Result<()> {
        Ok(())
    }
}
impl CodecConfig {
    pub fn effective_compression(&self) -> Compression {
        if self.format == Format::Json {
            Compression::None
        } else {
            self.compression
        }
    }
}
impl ExperimentConfig {
    pub fn from_bytes(bytes: &[u8], max_bytes: usize) -> Result<Self> {
        require(bytes.len() <= max_bytes, "config exceeds read bound")?;
        serde_json::from_slice(bytes).map_err(|e| e.to_string())
    }
    pub fn effective_controls(&self, memory_override: Option<bool>) -> CollectionControls {
        let mut controls = self.controls.clone();
        if let Some(value) = memory_override {
            controls.memory_profiling_enabled = value;
        }
        controls
    }
}
pub fn admits_raw(lifecycle: Lifecycle, _job: ServerJob) -> bool {
    lifecycle == Lifecycle::Active
}
