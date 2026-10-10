//! Produce concrete native files and contract answers for cross-language tests.

use idhazh_host_telemetry::canonical_json::{float_text, object_bytes, rows_bytes, sha256};
use idhazh_host_telemetry::codec::{jsonl, parquet};
use idhazh_host_telemetry::config::{CodecConfig, ExperimentConfig};
use idhazh_host_telemetry::contracts::events::{HostEvent, HostSessionManifest, HostWindowCells};
use idhazh_host_telemetry::contracts::file_envelope::*;
use idhazh_host_telemetry::contracts::host::*;
use idhazh_host_telemetry::contracts::write_plan::*;
use idhazh_host_telemetry::ledger::schema::HOST_COLUMNS;
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::io::{Read, Write};
use std::path::Path;
use uuid::Uuid;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    row: CorrectedHostFingerprintRow,
    identity: HostWriterIdentity,
    written_at_ms: i64,
    event_id: Uuid,
}
#[derive(Serialize)]
struct Proof {
    plan: HostWritePlan,
    completion: HostWriteCompletion,
    physical_sha256: String,
    size_bytes: usize,
}
fn fixture(input: &str, output: &str) -> Result<Vec<Proof>> {
    rel_path(input)?;
    rel_path(output)?;
    require(
        output.starts_with("backend/var/"),
        "fixture output must be test-owned backend/var",
    )?;
    let bytes = std::fs::read(input).map_err(|e| e.to_string())?;
    require(bytes.len() <= 65536, "fixture input exceeds bound")?;
    let input: Input = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    let mut row = input.row;
    row.fingerprint = row.fingerprint_v2()?;
    row.fingerprint_version = row.fingerprint.as_ref().map(|_| 2);
    row.validate()?;
    let unit = host_unit_id(&row.date, &row.run_id, row.job, row.shard)?;
    let file = host_file_id(unit, input.identity.attempt, input.written_at_ms)?;
    let stored = HostStoredRow {
        covers: row.date.clone(),
        host: row,
        ledger: "host-fingerprint".to_owned(),
        attempt: input.identity.attempt,
        unit_id: unit,
    };
    stored.validate()?;
    let mut proofs = Vec::new();
    for (name, format, compression) in [
        ("json", Format::Json, Compression::None),
        ("parquet-none", Format::Parquet, Compression::None),
        ("parquet-snappy", Format::Parquet, Compression::Snappy),
        ("parquet-zstd", Format::Parquet, Compression::Zstd),
    ] {
        let rows = vec![stored.clone()];
        let envelope = CandidateFileEnvelope {
            version: VERSION.to_owned(),
            row_schema_version: VERSION.to_owned(),
            tier: Tier::Raw,
            ledger: "host-fingerprint".to_owned(),
            covers: stored.covers.clone(),
            period: None,
            written_at_ms: input.written_at_ms,
            identity: input.identity.clone(),
            unit_id: unit,
            file_id: file,
            content_sha256: sha256(&rows_bytes(&rows)?),
            writer: if format == Format::Json {
                Writer::RustJson
            } else {
                Writer::RustParquet
            },
            writer_version: if format == Format::Json {
                jsonl::ENGINE_VERSION
            } else {
                parquet::engine_version()
            }
            .to_owned(),
            compression,
            built_from: None,
        };
        let suffix = if format == Format::Json {
            "json"
        } else {
            "parquet"
        };
        let relative_path = format!(
            "raw/host-fingerprint/{}/{}.{}",
            stored.covers.replace('-', "/"),
            file,
            suffix
        );
        let plan = HostWritePlan {
            version: VERSION.to_owned(),
            event_id: input.event_id,
            target_root: format!("{output}/{name}/state"),
            publication_identity: input.identity.clone(),
            prefix: vec!["host-fingerprint".to_owned()],
            files: vec![HostPlannedFile {
                envelope: envelope.clone(),
                format,
                relative_path: relative_path.clone(),
                rows: rows.clone(),
            }],
        };
        plan.validate()?;
        let bytes = if format == Format::Json {
            jsonl::render(&rows, &envelope)?
        } else {
            parquet::render(&rows, &envelope)?
        };
        let (decoded, decoded_rows) = if format == Format::Json {
            jsonl::read(&bytes, 1048576)?
        } else {
            parquet::read(&bytes, 1048576)?
        };
        require(
            decoded == envelope && decoded_rows == rows,
            "native fixture self-roundtrip mismatch",
        )?;
        let destination = format!("{}/{}", plan.target_root, relative_path);
        std::fs::create_dir_all(Path::new(&destination).parent().ok_or("fixture parent")?)
            .map_err(|e| e.to_string())?;
        std::fs::write(&destination, &bytes).map_err(|e| e.to_string())?;
        let digest = sha256(&bytes);
        let completion = HostWriteCompletion {
            version: VERSION.to_owned(),
            event_id: input.event_id,
            receipt: HostPublicationReceipt {
                version: "2026-10-09".to_owned(),
                identity: input.identity.clone(),
                writes: BTreeMap::from([(destination, digest.clone())]),
            },
        };
        completion.validate_plan(&plan, true)?;
        proofs.push(Proof {
            plan,
            completion,
            physical_sha256: digest,
            size_bytes: bytes.len(),
        });
    }
    Ok(proofs)
}
fn checked<T: serde::de::DeserializeOwned + Serialize>(bytes: &[u8]) -> Result<Vec<u8>> {
    let result: T = serde_json::from_slice(bytes).map_err(|e| e.to_string())?;
    object_bytes(&result)
}
fn run() -> Result<Vec<u8>> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    if args.first().is_some_and(|v| v == "render") {
        require(
            args.len() == 3,
            "render needs input and project-owned output path",
        )?;
        return object_bytes(&fixture(&args[1], &args[2])?);
    }
    require(
        args.len() == 2 && args[0] == "validate",
        "use render or validate for the fixture tests",
    )?;
    let mut bytes = Vec::new();
    std::io::stdin()
        .take(1048577)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    require(bytes.len() <= 1048576, "fixture stdin exceeds bound")?;
    match args[1].as_str() {
        "row" => checked::<CorrectedHostFingerprintRow>(&bytes),
        "stored" => checked::<HostStoredRow>(&bytes),
        "event" => checked::<HostEvent>(&bytes),
        "manifest" => checked::<HostSessionManifest>(&bytes),
        "envelope" => checked::<CandidateFileEnvelope>(&bytes),
        "metadata" => checked::<EnvelopeMetadata>(&bytes),
        "plan" => checked::<HostWritePlan>(&bytes),
        "completion" => checked::<HostWriteCompletion>(&bytes),
        "config" => checked::<ExperimentConfig>(&bytes),
        "codec-config" => checked::<CodecConfig>(&bytes),
        "cells" => checked::<HostWindowCells>(&bytes),
        "schema" => object_bytes(&HOST_COLUMNS),
        "canonical" => object_bytes(
            &serde_json::from_slice::<serde_json::Value>(&bytes).map_err(|e| e.to_string())?,
        ),
        "float-bits" => {
            let values: Vec<String> = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
            let results = values
                .iter()
                .map(|v| {
                    u64::from_str_radix(v, 16)
                        .map_err(|e| e.to_string())
                        .and_then(|v| float_text(f64::from_bits(v)))
                })
                .collect::<Result<Vec<_>>>()?;
            object_bytes(&results)
        }
        _ => Err("unknown fixture contract".to_owned()),
    }
}
fn main() {
    match run() {
        Ok(mut bytes) => {
            bytes.push(b'\n');
            if let Err(error) = std::io::stdout().write_all(&bytes) {
                eprintln!("{error}");
                std::process::exit(1);
            }
        }
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
}
