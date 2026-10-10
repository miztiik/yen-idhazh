//! File real bounded fixture rows through the retained native storage door.

use idhazh_host_telemetry::canonical_json::object_bytes;
use idhazh_host_telemetry::config::{CodecConfig, Lifecycle};
use idhazh_host_telemetry::contracts::file_envelope::*;
use idhazh_host_telemetry::contracts::host::*;
use idhazh_host_telemetry::contracts::write_plan::*;
use idhazh_host_telemetry::ledger::{identity, store};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;
use std::io::Write;
use std::path::Path;
use uuid::Uuid;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Input {
    rows: Vec<CorrectedHostFingerprintRow>,
    identity: HostWriterIdentity,
    written_at_ms: i64,
    event_id: Uuid,
}

#[derive(Serialize)]
struct Proof {
    plan: HostWritePlan,
    completion: HostWriteCompletion,
}

fn run() -> Result<Vec<Proof>> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    require(
        args.len() == 2,
        "storage-fixture needs input and project-owned output",
    )?;
    rel_path(&args[0])?;
    rel_path(&args[1])?;
    require(
        args[1].starts_with("backend/var/"),
        "fixture output must be test-owned",
    )?;
    let input: Input = serde_json::from_slice(&store::read_bounded(Path::new(&args[0]), 65536)?)
        .map_err(|e| e.to_string())?;
    let rows = input
        .rows
        .iter()
        .map(|row| {
            let mut row = row.clone();
            row.fingerprint = row.fingerprint_v2()?;
            row.fingerprint_version = row.fingerprint.as_ref().map(|_| 2);
            identity::stamp(&row, &input.identity)
        })
        .collect::<Result<Vec<_>>>()?;
    let mut result = Vec::new();
    for (name, format, compression) in [
        ("json", Format::Json, Compression::None),
        ("parquet-none", Format::Parquet, Compression::None),
        ("parquet-snappy", Format::Parquet, Compression::Snappy),
        ("parquet-zstd", Format::Parquet, Compression::Zstd),
    ] {
        let target = format!("{}/{name}/state", args[1]);
        let mut publisher = input.identity.clone();
        publisher.producer = "utilities.host-fixture".to_owned();
        let prepared = store::prepare(
            Path::new("."),
            store::WriteRequest {
                target_root: &target,
                prefix: &["trial".to_owned(), "host-fingerprint".to_owned()],
                publication_identity: &publisher,
                rows: &rows,
                codec: &CodecConfig {
                    format,
                    compression,
                },
                lifecycle: Lifecycle::Active,
                event_id: input.event_id,
                written_at_ms: input.written_at_ms,
            },
        )?
        .ok_or("fixture must produce nonempty output")?;
        let files = store::publish(&prepared).map_err(|e| e.message)?;
        require(
            store::publish(&prepared).map_err(|e| e.message)? == files,
            "immutable retry differs",
        )?;
        let completion = HostWriteCompletion {
            version: VERSION.to_owned(),
            event_id: input.event_id,
            receipt: HostPublicationReceipt {
                version: "2026-10-09".to_owned(),
                identity: publisher,
                writes: files
                    .into_iter()
                    .map(|f| (f.relative_path, f.physical_sha256))
                    .collect::<BTreeMap<_, _>>(),
            },
        };
        completion.validate_plan(prepared.plan(), true)?;
        result.push(Proof {
            plan: prepared.plan().clone(),
            completion,
        });
    }
    Ok(result)
}

fn main() {
    match run().and_then(|proofs| object_bytes(&proofs)) {
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
