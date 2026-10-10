//! Which exact typed metadata describes a host file and its real writer?

use super::host::*;
use serde::{Deserialize, Serialize};
use uuid::{Uuid, Variant};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Format {
    Parquet,
    Json,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Compression {
    None,
    Snappy,
    Zstd,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Tier {
    Raw,
    Compact,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Period {
    Daily,
    Monthly,
    Yearly,
}
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Writer {
    #[serde(rename = "idhazh.ledger.parquet")]
    PythonParquet,
    #[serde(rename = "idhazh_rust.ledger.parquet")]
    RustParquet,
    #[serde(rename = "idhazh.ledger.json_lines")]
    PythonJson,
    #[serde(rename = "idhazh_rust.ledger.json_lines")]
    RustJson,
}
impl Writer {
    pub fn format(self) -> Format {
        match self {
            Self::PythonParquet | Self::RustParquet => Format::Parquet,
            _ => Format::Json,
        }
    }
    pub fn native(self) -> bool {
        matches!(self, Self::RustParquet | Self::RustJson)
    }
}
contract!(HostWriterIdentity {
    run_id: String,
    attempt: i64,
    job: ServerJob,
    shard: i64,
    producer: String,
    git_sha: String,
});
impl Validate for HostWriterIdentity {
    fn validate(&self) -> Result<()> {
        run_id(&self.run_id)?;
        positive(self.attempt)?;
        nonnegative(self.shard)?;
        require(!self.producer.is_empty(), "empty producer")?;
        hex(&self.git_sha, 40)
    }
}

contract!(CandidateFileEnvelope {
    #[serde(default="default_version")] version: String, row_schema_version: String, tier: Tier, ledger: String, covers: String,
    #[serde(default)] period: Option<Period>,
    written_at_ms: i64, identity: HostWriterIdentity, unit_id: Uuid, file_id: Uuid,
    content_sha256: String, writer: Writer, writer_version: String, compression: Compression,
    #[serde(default)] built_from: Option<i64>,
});
impl Validate for CandidateFileEnvelope {
    fn validate(&self) -> Result<()> {
        const VERSIONS: &[&str] = &[
            VERSION,
            "2026-10-06",
            "2026-10-01T16:50",
            "2026-10-01",
            "2026-09-30",
            "2026-09-28",
        ];
        const LEDGERS: &[&str] = &[
            "seen",
            "feed-health",
            "item-health",
            "host-fingerprint",
            "summary-quality-evals",
            "candidate-models",
            "item-health-summary",
            "published",
            "feed-retirements",
            "visual-prunes",
            "counterfactual-scores",
            "scored-pairs",
            "fitted-thresholds",
            "holdout-pairs",
            "score-distribution",
            "archive",
            "metrics",
            "merge-line-holdout-scores",
            "traces",
            "day-metrics",
            "digest-fragments",
            "gardener",
            "run-plan",
            "council-run-records",
        ];
        require(
            VERSIONS.contains(&self.version.as_str()),
            "unknown envelope version",
        )?;
        pattern(
            &self.row_schema_version,
            r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$",
            "invalid schema version",
        )?;
        require(LEDGERS.contains(&self.ledger.as_str()), "unknown ledger")?;
        require(
            (self.tier == Tier::Compact) == self.period.is_some(),
            "period contradicts tier",
        )?;
        require(
            self.tier != Tier::Raw || self.built_from.is_none(),
            "raw cannot carry built_from",
        )?;
        let shape = match self.period {
            Some(Period::Monthly) => r"^\d{4}-\d{2}$",
            Some(Period::Yearly) => r"^\d{4}$",
            _ => r"^\d{4}-\d{2}-\d{2}$",
        };
        pattern(&self.covers, shape, "covers contradicts period")?;
        self.identity.validate()?;
        nonnegative(self.written_at_ms)?;
        if let Some(count) = self.built_from {
            nonnegative(count)?;
        }
        require(
            self.unit_id.get_version_num() == 5
                && self.file_id.get_version_num() == 8
                && self.unit_id.get_variant() == Variant::RFC4122
                && self.file_id.get_variant() == Variant::RFC4122,
            "invalid UUID identity kind",
        )?;
        hex(&self.content_sha256, 64)?;
        require(!self.writer_version.is_empty(), "empty engine version")?;
        if self.writer.native() {
            require(
                self.version == VERSION
                    && self.row_schema_version == VERSION
                    && self.tier == Tier::Raw
                    && self.ledger == "host-fingerprint",
                "native writer is corrected raw host only",
            )?;
        }
        require(
            self.writer.format() != Format::Json || self.compression == Compression::None,
            "JSONL cannot be compressed",
        )
    }
}

// Metadata has the same finite keys as Python, all string-valued. Optional raw
// keys are absent, not empty strings or nulls.
contract!(EnvelopeMetadata {
    envelope_version: String, schema_version: String, tier: String, ledger: String, covers: String,
    #[serde(default, skip_serializing_if = "Option::is_none", deserialize_with="metadata_optional")]
    period: Option<String>,
    written_at_ms: String, run_id: String, attempt: String, job: String, shard: String,
    producer: String, unit_id: String, file_id: String, content_sha256: String, git_sha: String,
    writer: String, writer_version: String, compression: String,
    #[serde(default, skip_serializing_if = "Option::is_none", deserialize_with="metadata_optional")]
    built_from: Option<String>,
});
fn metadata_optional<'de, D: serde::Deserializer<'de>>(
    deserializer: D,
) -> std::result::Result<Option<String>, D::Error> {
    String::deserialize(deserializer).map(Some)
}
impl Validate for EnvelopeMetadata {
    fn validate(&self) -> Result<()> {
        self.envelope().map(|_| ())
    }
}
fn text<T: Serialize>(value: T) -> String {
    serde_json::to_value(value)
        .expect("finite enum")
        .as_str()
        .expect("enum text")
        .to_owned()
}
fn decimal(value: &str) -> Result<i64> {
    require(
        !value.is_empty() && value.bytes().all(|v| v.is_ascii_digit()),
        "metadata integer must be ASCII decimal",
    )?;
    value
        .parse()
        .map_err(|e: std::num::ParseIntError| e.to_string())
}
impl CandidateFileEnvelope {
    pub fn validate_rows(&self, rows: &[HostStoredRow]) -> Result<()> {
        self.validate()?;
        for row in rows {
            row.validate()?;
            if self.writer.native() {
                require(
                    row.host.fingerprint_version.is_none_or(|v| v == 2),
                    "native rows require sourced algorithm 2 or null",
                )?;
            }
            require(
                row.covers == self.covers
                    && row.host.run_id == self.identity.run_id
                    && row.host.job == self.identity.job
                    && row.host.shard == self.identity.shard
                    && row.attempt == self.identity.attempt
                    && row.unit_id == self.unit_id
                    && self.identity.producer == HOST_PRODUCER,
                "stored row/envelope identity mismatch",
            )?;
        }
        Ok(())
    }
    pub fn validate_container(&self, format: Format) -> Result<()> {
        self.validate()?;
        require(self.writer.format() == format, "writer/container mismatch")
    }
    pub fn metadata(&self) -> Result<EnvelopeMetadata> {
        self.validate()?;
        Ok(EnvelopeMetadata {
            envelope_version: self.version.clone(),
            schema_version: self.row_schema_version.clone(),
            tier: text(self.tier),
            ledger: self.ledger.clone(),
            covers: self.covers.clone(),
            period: self.period.map(text),
            written_at_ms: self.written_at_ms.to_string(),
            run_id: self.identity.run_id.clone(),
            attempt: format!("{:02}", self.identity.attempt),
            job: job_text(self.identity.job),
            shard: format!("{:02}", self.identity.shard),
            producer: self.identity.producer.clone(),
            unit_id: self.unit_id.to_string(),
            file_id: self.file_id.to_string(),
            content_sha256: self.content_sha256.clone(),
            git_sha: self.identity.git_sha.clone(),
            writer: text(self.writer),
            writer_version: self.writer_version.clone(),
            compression: text(self.compression),
            built_from: self.built_from.map(|v| v.to_string()),
        })
    }
}
impl EnvelopeMetadata {
    pub fn envelope(&self) -> Result<CandidateFileEnvelope> {
        let mut data = serde_json::json!({
            "version": self.envelope_version, "row_schema_version": self.schema_version,
            "tier": self.tier, "ledger": self.ledger, "covers": self.covers, "period": self.period,
            "written_at_ms": decimal(&self.written_at_ms)?,
            "identity": {"run_id": self.run_id, "attempt": decimal(&self.attempt)?, "job": self.job, "shard": decimal(&self.shard)?, "producer": self.producer, "git_sha": self.git_sha},
            "unit_id": self.unit_id, "file_id": self.file_id, "content_sha256": self.content_sha256,
            "writer": self.writer, "writer_version": self.writer_version, "compression": self.compression,
            "built_from": self.built_from.as_deref().map(decimal).transpose()?
        });
        // UUID metadata is canonical text, not an alternate UUID representation.
        for key in ["unit_id", "file_id"] {
            let original = data[key].as_str().ok_or("UUID metadata")?;
            let uuid = Uuid::parse_str(original).map_err(|e| e.to_string())?;
            require(uuid.to_string() == original, "noncanonical UUID metadata")?;
        }
        serde_json::from_value(data.take()).map_err(|e| e.to_string())
    }
}
