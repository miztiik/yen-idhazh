//! How does an envelope-first host JSONL file encode and decode in memory?

use crate::Result;
use crate::canonical_json::{row_line, rows_bytes, sha256};
use crate::contracts::file_envelope::{CandidateFileEnvelope, EnvelopeMetadata, Format, Writer};
use crate::contracts::host::{HostStoredRow, require};

pub const ENGINE_VERSION: &str = env!("CARGO_PKG_VERSION");
pub fn render(rows: &[HostStoredRow], envelope: &CandidateFileEnvelope) -> Result<Vec<u8>> {
    envelope.validate_container(Format::Json)?;
    require(
        envelope.writer == Writer::RustJson && envelope.writer_version == ENGINE_VERSION,
        "JSONL render needs truthful native writer/version",
    )?;
    envelope.validate_rows(rows)?;
    let body = rows_bytes(rows)?;
    require(
        sha256(&body) == envelope.content_sha256,
        "JSONL content hash mismatch",
    )?;
    let mut bytes = row_line(&envelope.metadata()?)?;
    bytes.extend(body);
    Ok(bytes)
}
pub fn read(bytes: &[u8], max_bytes: usize) -> Result<(CandidateFileEnvelope, Vec<HostStoredRow>)> {
    require(bytes.len() <= max_bytes, "JSONL exceeds read bound")?;
    require(
        bytes.is_ascii() && !bytes.contains(&b'\r') && bytes.ends_with(b"\n"),
        "JSONL requires ASCII LF-terminated lines",
    )?;
    let text = std::str::from_utf8(bytes).map_err(|e| e.to_string())?;
    let mut lines = text.split_terminator('\n');
    let head = lines.next().ok_or("missing envelope")?;
    let metadata: EnvelopeMetadata = serde_json::from_str(head).map_err(|e| e.to_string())?;
    let envelope = metadata.envelope()?;
    envelope.validate_container(Format::Json)?;
    let mut rows = Vec::new();
    for line in lines {
        let row: HostStoredRow = serde_json::from_str(line).map_err(|e| e.to_string())?;
        require(
            row_line(&row)? == format!("{line}\n").as_bytes(),
            "noncanonical JSONL row",
        )?;
        rows.push(row);
    }
    require(
        sha256(&rows_bytes(&rows)?) == envelope.content_sha256,
        "JSONL content hash mismatch",
    )?;
    envelope.validate_rows(&rows)?;
    Ok((envelope, rows))
}
