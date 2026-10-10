//! Which metadata describes one corrected whole row and its actual native codec?

use crate::canonical_json::{rows_bytes, sha256};
use crate::codec::{jsonl, parquet};
use crate::config::CodecConfig;
use crate::contracts::file_envelope::{CandidateFileEnvelope, HostWriterIdentity, Tier, Writer};
use crate::contracts::host::{HostStoredRow, Result, VERSION, Validate};
use crate::ledger::{filenames, identity};

pub fn build(
    row: &HostStoredRow,
    writer: &HostWriterIdentity,
    codec: &CodecConfig,
    written_at_ms: i64,
) -> Result<CandidateFileEnvelope> {
    identity::preserve(row, writer)?;
    codec.validate()?;
    let native = match codec.format {
        crate::contracts::file_envelope::Format::Json => Writer::RustJson,
        crate::contracts::file_envelope::Format::Parquet => Writer::RustParquet,
    };
    let envelope = CandidateFileEnvelope {
        version: VERSION.to_owned(),
        row_schema_version: VERSION.to_owned(),
        tier: Tier::Raw,
        ledger: row.ledger.clone(),
        covers: row.covers.clone(),
        period: None,
        written_at_ms,
        identity: writer.clone(),
        unit_id: row.unit_id,
        file_id: filenames::file_id(row.unit_id, row.attempt, written_at_ms)?,
        content_sha256: sha256(&rows_bytes(std::slice::from_ref(row))?),
        writer: native,
        writer_version: match native {
            Writer::RustJson => jsonl::ENGINE_VERSION,
            _ => parquet::engine_version(),
        }
        .to_owned(),
        compression: codec.effective_compression(),
        built_from: None,
    };
    envelope.validate_rows(std::slice::from_ref(row))?;
    Ok(envelope)
}
