//! Which completed native bytes survive an interruption as bounded, immutable evidence?

use crate::canonical_json::{object_bytes, sha256};
use crate::contracts::host::{Result, VERSION, Validate, require};
use crate::contracts::write_plan::{HostPublicationReceipt, HostWriteCompletion, HostWritePlan};
use crate::fs::atomic;
use crate::ledger::{paths, store};
use std::collections::BTreeMap;
use std::io::ErrorKind;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Copy)]
pub struct ReceiptLimits {
    pub max_files: usize,
    pub max_file_bytes: usize,
    pub max_total_bytes: usize,
    pub max_document_bytes: usize,
}

impl ReceiptLimits {
    pub fn validate(&self) -> Result<()> {
        require(
            self.max_files > 0
                && self.max_file_bytes > 0
                && self.max_total_bytes > 0
                && self.max_document_bytes > 0,
            "receipt limits must be positive",
        )
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Checkpoint {
    PlanPersisted,
    BeforeFilePublish(usize),
    FilePublished(usize),
    BeforeReceiptPersist(usize),
    ReceiptPersisted(usize),
}

#[derive(Debug)]
pub struct ReceiptFailure {
    pub message: String,
    pub completion: HostWriteCompletion,
}

pub fn plan_path(evidence_root: &str, plan: &HostWritePlan) -> String {
    format!("{evidence_root}/{}.plan.json", plan.event_id)
}

pub fn completion_path(evidence_root: &str, plan: &HostWritePlan, count: usize) -> String {
    format!("{evidence_root}/{}.completed-{count}.json", plan.event_id)
}

fn empty_completion(plan: &HostWritePlan) -> HostWriteCompletion {
    HostWriteCompletion {
        version: VERSION.to_owned(),
        event_id: plan.event_id,
        receipt: HostPublicationReceipt {
            version: "2026-10-09".to_owned(),
            identity: plan.publication_identity.clone(),
            writes: BTreeMap::new(),
        },
    }
}

fn document_bytes(value: &impl serde::Serialize, limits: &ReceiptLimits) -> Result<Vec<u8>> {
    let mut bytes = object_bytes(value)?;
    bytes.push(b'\n');
    require(
        bytes.len() <= limits.max_document_bytes,
        "evidence document exceeds byte bound",
    )?;
    Ok(bytes)
}

fn validate_prepared(prepared: &store::PreparedWrite, limits: &ReceiptLimits) -> Result<()> {
    limits.validate()?;
    let plan = prepared.plan();
    plan.validate()?;
    require(
        plan.files.len() <= limits.max_files,
        "plan exceeds file count bound",
    )?;
    let mut total = 0usize;
    let mut full = empty_completion(plan);
    for (file, bytes) in plan.files.iter().zip(prepared.rendered_bytes()) {
        require(
            bytes.len() <= limits.max_file_bytes,
            "planned file exceeds byte bound",
        )?;
        total = total
            .checked_add(bytes.len())
            .ok_or("planned total byte overflow")?;
        full.receipt.writes.insert(
            format!("{}/{}", plan.target_root, file.relative_path),
            sha256(bytes),
        );
    }
    require(
        total <= limits.max_total_bytes,
        "plan exceeds total byte bound",
    )?;
    document_bytes(plan, limits)?;
    document_bytes(&full, limits)?;
    Ok(())
}

fn evidence_directory(prepared: &store::PreparedWrite, evidence_root: &str) -> Result<PathBuf> {
    let workspace = prepared.workspace();
    let evidence = paths::resolve_directory(workspace, evidence_root)?;
    let target = paths::resolve_directory(workspace, &prepared.plan().target_root)?;
    require(
        !within(&evidence, &target) && !within(&target, &evidence),
        "evidence root must be separate from the target root",
    )?;
    require(
        !within(&evidence, &workspace.join("state")) && !within(&evidence, &workspace.join("raw")),
        "evidence root cannot be state or raw",
    )?;
    for reserved in ["state", "raw"] {
        let reserved = paths::resolve_directory(workspace, reserved)?;
        require(
            !within(&evidence, &reserved),
            "evidence root aliases reserved state or raw",
        )?;
    }
    Ok(evidence)
}

fn within(path: &Path, root: &Path) -> bool {
    #[cfg(windows)]
    {
        // Missing Windows descendants may have different caller-supplied casing.
        let path = PathBuf::from(path.as_os_str().to_string_lossy().to_ascii_lowercase());
        let root = PathBuf::from(root.as_os_str().to_string_lossy().to_ascii_lowercase());
        path.starts_with(root)
    }
    #[cfg(not(windows))]
    path.starts_with(root)
}

fn evidence_document(
    prepared: &store::PreparedWrite,
    evidence_root: &str,
    relative_path: &str,
) -> Result<PathBuf> {
    let root = evidence_directory(prepared, evidence_root)?;
    let path = paths::resolve_document(prepared.workspace(), relative_path)?;
    require(
        path.parent() == Some(root.as_path()),
        "document escapes evidence root",
    )?;
    Ok(path)
}

fn read_optional(path: &Path, bound: usize) -> Result<Option<Vec<u8>>> {
    match std::fs::symlink_metadata(path) {
        Err(error) if error.kind() == ErrorKind::NotFound => Ok(None),
        Err(error) => Err(error.to_string()),
        Ok(metadata) => {
            require(
                metadata.is_file() && !metadata.file_type().is_symlink(),
                "evidence must be a regular non-symlink file",
            )?;
            store::read_bounded(path, bound).map(Some)
        }
    }
}

fn persist(
    prepared: &store::PreparedWrite,
    evidence_root: &str,
    relative_path: &str,
    value: &impl serde::Serialize,
    limits: &ReceiptLimits,
) -> Result<()> {
    let bytes = document_bytes(value, limits)?;
    let path = evidence_document(prepared, evidence_root, relative_path)?;
    if let Some(previous) = read_optional(&path, limits.max_document_bytes)? {
        return require(
            previous == bytes,
            "immutable evidence conflicts with existing document",
        );
    }
    std::fs::create_dir_all(path.parent().ok_or("evidence parent missing")?)
        .map_err(|e| e.to_string())?;
    let path = evidence_document(prepared, evidence_root, relative_path)?;
    atomic::publish_immutable(&path, &bytes).map_err(|e| e.to_string())?;
    require(
        store::read_bounded(&path, limits.max_document_bytes)? == bytes,
        "persisted evidence bytes differ",
    )
}

/// Load exactly the retained event plan, not a substitute input or a directory scan.
pub fn load_plan(
    workspace: &Path,
    relative_path: &str,
    evidence_root: &str,
    limits: &ReceiptLimits,
) -> Result<store::PreparedWrite> {
    limits.validate()?;
    let path = paths::resolve_document(workspace, relative_path)?;
    let bytes =
        read_optional(&path, limits.max_document_bytes)?.ok_or("retained plan is missing")?;
    let plan: HostWritePlan = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    require(
        plan.files.len() <= limits.max_files,
        "plan exceeds file count bound",
    )?;
    let prepared = store::prepare_plan(workspace, plan)?;
    validate_prepared(&prepared, limits)?;
    let expected = evidence_document(
        &prepared,
        evidence_root,
        &plan_path(evidence_root, prepared.plan()),
    )?;
    require(
        path == expected,
        "recovery must name the retained event plan",
    )?;
    Ok(prepared)
}

fn persist_completion(
    prepared: &store::PreparedWrite,
    evidence_root: &str,
    limits: &ReceiptLimits,
    completion: &HostWriteCompletion,
) -> Result<()> {
    completion.validate_plan(prepared.plan(), false)?;
    let count = completion.receipt.writes.len();
    if count != 0 {
        persist(
            prepared,
            evidence_root,
            &completion_path(evidence_root, prepared.plan(), count),
            completion,
            limits,
        )?;
    }
    Ok(())
}

fn recover_existing(
    prepared: &store::PreparedWrite,
    evidence_root: &str,
    limits: &ReceiptLimits,
    completion: &mut HostWriteCompletion,
) -> Result<()> {
    validate_prepared(prepared, limits)?;
    let plan = prepared.plan();
    let path = evidence_document(prepared, evidence_root, &plan_path(evidence_root, plan))?;
    let bytes =
        read_optional(&path, limits.max_document_bytes)?.ok_or("retained plan is missing")?;
    let retained: HostWritePlan = serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
    require(
        retained == *plan,
        "retained plan differs from expected immutable plan",
    )?;
    let expected = plan
        .files
        .iter()
        .zip(prepared.rendered_bytes())
        .map(|(file, bytes)| {
            (
                format!("{}/{}", plan.target_root, file.relative_path),
                sha256(bytes),
            )
        })
        .collect::<BTreeMap<_, _>>();
    let mut promised = BTreeMap::new();
    // There are at most as many cumulative snapshot names as immutable planned files.
    for count in 1..=plan.files.len() {
        let path = evidence_document(
            prepared,
            evidence_root,
            &completion_path(evidence_root, plan, count),
        )?;
        if let Some(bytes) = read_optional(&path, limits.max_document_bytes)? {
            let prior: HostWriteCompletion =
                serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;
            prior.validate_plan(plan, false)?;
            require(
                prior.receipt.writes.len() == count,
                "snapshot count contradicts its name",
            )?;
            require(
                prior
                    .receipt
                    .writes
                    .iter()
                    .all(|(path, digest)| expected.get(path) == Some(digest)),
                "prior receipt hash differs from actual planned bytes",
            )?;
            require(
                promised
                    .iter()
                    .all(|(path, digest)| prior.receipt.writes.get(path) == Some(digest)),
                "later receipt drops prior completed files",
            )?;
            promised = prior.receipt.writes;
        }
    }
    for (index, file) in plan.files.iter().enumerate() {
        let path = format!("{}/{}", plan.target_root, file.relative_path);
        match prepared.verify_existing(index)? {
            Some(file) => {
                completion
                    .receipt
                    .writes
                    .insert(file.relative_path, file.physical_sha256);
            }
            None => require(
                !promised.contains_key(&path),
                "prior receipt promises a missing file",
            )?,
        }
    }
    Ok(())
}

/// Reconstruct evidence only from the same existing planned files; publish no targets.
pub fn recover(
    prepared: &store::PreparedWrite,
    evidence_root: &str,
    limits: &ReceiptLimits,
) -> std::result::Result<HostWriteCompletion, Box<ReceiptFailure>> {
    let mut completion = empty_completion(prepared.plan());
    let result = recover_existing(prepared, evidence_root, limits, &mut completion)
        .and_then(|()| persist_completion(prepared, evidence_root, limits, &completion));
    match result {
        Ok(()) => Ok(completion),
        Err(message) => Err(Box::new(ReceiptFailure {
            message,
            completion,
        })),
    }
}

pub fn write(
    prepared: &store::PreparedWrite,
    evidence_root: &str,
    limits: &ReceiptLimits,
) -> std::result::Result<HostWriteCompletion, Box<ReceiptFailure>> {
    write_observed(prepared, evidence_root, limits, &mut |_| Ok(()))
}

/// Retain the plan before first target publication and a cumulative receipt per complete file.
pub fn write_observed(
    prepared: &store::PreparedWrite,
    evidence_root: &str,
    limits: &ReceiptLimits,
    observer: &mut impl FnMut(Checkpoint) -> Result<()>,
) -> std::result::Result<HostWriteCompletion, Box<ReceiptFailure>> {
    let mut completion = empty_completion(prepared.plan());
    let start = validate_prepared(prepared, limits)
        .and_then(|()| {
            persist(
                prepared,
                evidence_root,
                &plan_path(evidence_root, prepared.plan()),
                prepared.plan(),
                limits,
            )
        })
        .and_then(|()| observer(Checkpoint::PlanPersisted))
        .and_then(|()| recover_existing(prepared, evidence_root, limits, &mut completion))
        .and_then(|()| persist_completion(prepared, evidence_root, limits, &completion));
    if let Err(message) = start {
        return Err(Box::new(ReceiptFailure {
            message,
            completion,
        }));
    }
    let result = store::publish_observed(prepared, &mut |stage, completed| match stage {
        store::PublishCheckpoint::BeforeFilePublish(index) => {
            observer(Checkpoint::BeforeFilePublish(index))
        }
        store::PublishCheckpoint::FilePublished(index) => {
            for file in completed {
                completion
                    .receipt
                    .writes
                    .insert(file.relative_path.clone(), file.physical_sha256.clone());
            }
            observer(Checkpoint::FilePublished(index))?;
            observer(Checkpoint::BeforeReceiptPersist(index))?;
            persist_completion(prepared, evidence_root, limits, &completion)?;
            observer(Checkpoint::ReceiptPersisted(index))
        }
    });
    match result {
        Ok(_) => match completion.validate_plan(prepared.plan(), true) {
            Ok(()) => Ok(completion),
            Err(message) => Err(Box::new(ReceiptFailure {
                message,
                completion,
            })),
        },
        Err(failure) => {
            for file in failure.completed {
                completion
                    .receipt
                    .writes
                    .insert(file.relative_path, file.physical_sha256);
            }
            let message = match persist_completion(prepared, evidence_root, limits, &completion) {
                Ok(()) => failure.message,
                Err(error) => format!("{}; completion evidence failed: {error}", failure.message),
            };
            Err(Box::new(ReceiptFailure {
                message,
                completion,
            }))
        }
    }
}
