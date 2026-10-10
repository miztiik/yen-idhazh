//! How are all validated day groups prepared before any immutable raw file is published?

use crate::canonical_json::sha256;
use crate::codec::{jsonl, parquet};
use crate::config::{CodecConfig, Lifecycle, admits_raw};
use crate::contracts::file_envelope::{Format, HostWriterIdentity, Writer};
use crate::contracts::host::{HOST_PRODUCER, HostStoredRow, Result, VERSION, Validate, require};
use crate::contracts::write_plan::{HostPlannedFile, HostWritePlan};
use crate::fs::atomic;
use crate::ledger::{envelope, paths};
use std::collections::BTreeMap;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use uuid::Uuid;

pub struct PreparedWrite {
    workspace: PathBuf,
    plan: HostWritePlan,
    bytes: Vec<Vec<u8>>,
}

impl PreparedWrite {
    pub fn plan(&self) -> &HostWritePlan {
        &self.plan
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StoredFile {
    pub relative_path: String,
    pub physical_sha256: String,
    pub size_bytes: usize,
}

#[derive(Debug)]
pub struct StoreFailure {
    pub message: String,
    pub completed: Vec<StoredFile>,
}

/// The epoch millisecond is read from the actual UTC clock, never advanced synthetically.
pub fn actual_millis_after(previous: Option<i64>, wait: Duration) -> Result<i64> {
    let start = Instant::now();
    loop {
        let now = i64::try_from(
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map_err(|e| e.to_string())?
                .as_millis(),
        )
        .map_err(|_| "UTC clock overflows int64")?;
        if previous.is_none_or(|old| now > old) {
            return Ok(now);
        }
        require(
            start.elapsed() < wait,
            "actual clock did not advance before deadline",
        )?;
        std::thread::sleep(Duration::from_millis(1).min(wait.saturating_sub(start.elapsed())));
    }
}

pub struct WriteRequest<'a> {
    pub target_root: &'a str,
    pub prefix: &'a [String],
    pub publication_identity: &'a HostWriterIdentity,
    pub rows: &'a [HostStoredRow],
    pub codec: &'a CodecConfig,
    pub lifecycle: Lifecycle,
    pub event_id: Uuid,
    /// A captured actual clock, or an explicit recorded fixture clock during replay.
    pub written_at_ms: i64,
}

pub fn prepare(workspace: &Path, request: WriteRequest<'_>) -> Result<Option<PreparedWrite>> {
    request.publication_identity.validate()?;
    if request.rows.is_empty() || !admits_raw(request.lifecycle, request.publication_identity.job) {
        return Ok(None);
    }
    let mut days = BTreeMap::new();
    for row in request.rows {
        row.validate()?;
        require(
            days.insert(&row.covers, row).is_none(),
            "raw host requires one whole row per day",
        )?;
    }
    let mut files = Vec::new();
    let mut logical_identity = request.publication_identity.clone();
    logical_identity.producer = HOST_PRODUCER.to_owned();
    for row in days.into_values() {
        let envelope =
            envelope::build(row, &logical_identity, request.codec, request.written_at_ms)?;
        files.push(HostPlannedFile {
            relative_path: paths::raw_path(
                request.prefix,
                &row.covers,
                envelope.file_id,
                request.codec.format,
            )?,
            envelope,
            format: request.codec.format,
            rows: vec![row.clone()],
        });
    }
    prepare_plan(
        workspace,
        HostWritePlan {
            version: VERSION.to_owned(),
            event_id: request.event_id,
            target_root: request.target_root.to_owned(),
            publication_identity: request.publication_identity.clone(),
            prefix: request.prefix.to_vec(),
            files,
        },
    )
    .map(Some)
}

pub fn prepare_successor(
    workspace: &Path,
    request: WriteRequest<'_>,
    previous: &HostWritePlan,
) -> Result<Option<PreparedWrite>> {
    let prepared = prepare(workspace, request)?;
    if let Some(next) = prepared {
        let mut plan = next.plan;
        for file in &mut plan.files {
            if let Some(old) = previous.files.iter().find(|old| {
                old.envelope.unit_id == file.envelope.unit_id
                    && old.envelope.content_sha256 == file.envelope.content_sha256
            }) {
                *file = old.clone();
            }
        }
        plan.validate_successor(previous)?;
        return prepare_plan(workspace, plan).map(Some);
    }
    Ok(None)
}

/// Re-render a validated immutable plan, including restart retries, before any target I/O.
pub fn prepare_plan(workspace: &Path, plan: HostWritePlan) -> Result<PreparedWrite> {
    plan.validate()?;
    let workspace = std::fs::canonicalize(workspace).map_err(|e| e.to_string())?;
    let mut bytes = Vec::new();
    for file in &plan.files {
        paths::resolve(&workspace, &plan.target_root, &file.relative_path)?;
        require(
            match file.format {
                Format::Json => {
                    file.envelope.writer == Writer::RustJson
                        && file.envelope.writer_version == jsonl::ENGINE_VERSION
                }
                Format::Parquet => {
                    file.envelope.writer == Writer::RustParquet
                        && file.envelope.writer_version == parquet::engine_version()
                }
            },
            "store accepts only its actual native engine",
        )?;
        bytes.push(match file.format {
            Format::Json => jsonl::render(&file.rows, &file.envelope)?,
            Format::Parquet => parquet::render(&file.rows, &file.envelope)?,
        });
    }
    Ok(PreparedWrite {
        workspace,
        plan,
        bytes,
    })
}

/// Read one named file with a bound before comparing all physical bytes.
pub fn read_bounded(path: &Path, maximum: usize) -> Result<Vec<u8>> {
    let file = std::fs::File::open(path).map_err(|e| e.to_string())?;
    require(
        file.metadata().map_err(|e| e.to_string())?.is_file(),
        "not a regular file",
    )?;
    let mut bytes = Vec::new();
    file.take(maximum.saturating_add(1) as u64)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    require(bytes.len() <= maximum, "file exceeds physical read bound")?;
    Ok(bytes)
}

pub fn verify_file(
    workspace: &Path,
    plan: &HostWritePlan,
    file: &HostPlannedFile,
    bytes: &[u8],
) -> Result<StoredFile> {
    let path = paths::resolve(workspace, &plan.target_root, &file.relative_path)?;
    let physical = read_bounded(&path, bytes.len())?;
    require(
        physical == bytes,
        "planned physical bytes conflict with destination",
    )?;
    let (envelope, rows) = match file.format {
        Format::Json => jsonl::read(&physical, physical.len())?,
        Format::Parquet => parquet::read(&physical, physical.len())?,
    };
    require(
        envelope == file.envelope && rows == file.rows,
        "stored envelope/rows conflict with plan",
    )?;
    Ok(StoredFile {
        relative_path: format!("{}/{}", plan.target_root, file.relative_path),
        physical_sha256: sha256(&physical),
        size_bytes: physical.len(),
    })
}

pub fn publish(prepared: &PreparedWrite) -> std::result::Result<Vec<StoredFile>, StoreFailure> {
    let mut completed = Vec::new();
    for (file, bytes) in prepared.plan.files.iter().zip(&prepared.bytes) {
        let path = paths::resolve(
            &prepared.workspace,
            &prepared.plan.target_root,
            &file.relative_path,
        );
        let result = path.and_then(|path| {
            // Recheck after creating directories, so an existing escaping link is never admitted.
            std::fs::create_dir_all(path.parent().ok_or("raw parent missing")?)
                .map_err(|e| e.to_string())?;
            let path = paths::resolve(
                &prepared.workspace,
                &prepared.plan.target_root,
                &file.relative_path,
            )?;
            atomic::publish_immutable(&path, bytes).map_err(|e| e.to_string())?;
            verify_file(&prepared.workspace, &prepared.plan, file, bytes)
        });
        match result {
            Ok(file) => completed.push(file),
            Err(message) => {
                // Publication can succeed before cleanup fails. Include that file if its
                // complete bytes verify; still return the original I/O failure.
                if let Ok(file) = verify_file(&prepared.workspace, &prepared.plan, file, bytes) {
                    completed.push(file);
                }
                return Err(StoreFailure { message, completed });
            }
        }
    }
    Ok(completed)
}
