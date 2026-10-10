//! Interrupt and restart the real native receipt writer at named test checkpoints.

use idhazh_host_telemetry::canonical_json::object_bytes;
use idhazh_host_telemetry::config::ExperimentConfig;
use idhazh_host_telemetry::contracts::host::{Result, require};
use idhazh_host_telemetry::contracts::write_plan::{HostWriteCompletion, HostWritePlan};
use idhazh_host_telemetry::ledger::{paths, store};
use idhazh_host_telemetry::receipts::{self, Checkpoint, ReceiptLimits};
use serde::Serialize;
use std::io::Write;
use std::path::Path;

#[derive(Serialize)]
struct Proof {
    plan: HostWritePlan,
    completion: HostWriteCompletion,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<String>,
}

fn checkpoint(value: &str, files: usize) -> Result<Checkpoint> {
    if value == "plan" {
        return Ok(Checkpoint::PlanPersisted);
    }
    for (prefix, make) in [
        (
            "before-file-",
            Checkpoint::BeforeFilePublish as fn(usize) -> Checkpoint,
        ),
        (
            "after-file-",
            Checkpoint::FilePublished as fn(usize) -> Checkpoint,
        ),
        (
            "before-receipt-",
            Checkpoint::BeforeReceiptPersist as fn(usize) -> Checkpoint,
        ),
        (
            "after-receipt-",
            Checkpoint::ReceiptPersisted as fn(usize) -> Checkpoint,
        ),
    ] {
        if let Some(index) = value.strip_prefix(prefix) {
            let index = index
                .parse::<usize>()
                .map_err(|_| "checkpoint needs a file index")?;
            require(index < files, "checkpoint index exceeds planned files")?;
            return Ok(make(index));
        }
    }
    Err("unknown interruption checkpoint".to_owned())
}

fn run() -> Result<Proof> {
    let args = std::env::args().skip(1).collect::<Vec<_>>();
    require(
        args.len() == 3 || args.len() == 5,
        "receipts-fixture write|recover|retry <plan> <evidence-root> [--interrupt-after <stage>]",
    )?;
    let mode = args[0].as_str();
    require(
        matches!(mode, "write" | "recover" | "retry"),
        "unknown receipt command",
    )?;
    if args.len() == 5 {
        require(
            mode != "recover" && args[3] == "--interrupt-after",
            "invalid interruption arguments",
        )?;
    }
    require(
        args[1].starts_with("backend/var/") && args[2].starts_with("backend/var/"),
        "fixture input and evidence must be test-owned under backend/var",
    )?;
    let workspace = Path::new(".");
    // This fixed bootstrap cap bounds the one named test configuration document.
    let config_path = paths::resolve_document(workspace, "config/host-telemetry-experiment.json")?;
    let config = ExperimentConfig::from_bytes(&store::read_bounded(&config_path, 65536)?, 65536)?;
    let bounded =
        |value: i64| usize::try_from(value).map_err(|_| "fixture limit overflows usize".to_owned());
    let limits = ReceiptLimits {
        max_files: bounded(config.verification_limits.max_files)?,
        max_file_bytes: bounded(config.verification_limits.max_file_bytes)?,
        max_total_bytes: bounded(config.verification_limits.max_total_bytes)?,
        max_document_bytes: bounded(config.limits.max_result_bytes)?,
    };
    limits.validate()?;
    let prepared = if mode == "write" {
        let path = paths::resolve_document(workspace, &args[1])?;
        let plan: HostWritePlan =
            serde_json::from_slice(&store::read_bounded(&path, limits.max_document_bytes)?)
                .map_err(|e| e.to_string())?;
        require(
            plan.files.len() <= limits.max_files,
            "plan exceeds file count bound",
        )?;
        require(
            plan.target_root.starts_with("backend/var/"),
            "fixture target must be test-owned",
        )?;
        store::prepare_plan(workspace, plan)?
    } else {
        let prepared = receipts::load_plan(workspace, &args[1], &args[2], &limits)?;
        require(
            prepared.plan().target_root.starts_with("backend/var/"),
            "fixture target must be test-owned",
        )?;
        prepared
    };
    let interrupt = args
        .get(4)
        .map(|value| checkpoint(value, prepared.plan().files.len()))
        .transpose()?;
    let result = if mode == "recover" {
        receipts::recover(&prepared, &args[2], &limits)
    } else {
        receipts::write_observed(&prepared, &args[2], &limits, &mut |stage| {
            if Some(stage) == interrupt {
                // Immediate exit bypasses Drop, leaving the real named filesystem state.
                std::process::exit(70);
            }
            Ok(())
        })
    };
    let (completion, error) = match result {
        Ok(completion) => (completion, None),
        Err(failure) => (failure.completion, Some(failure.message)),
    };
    Ok(Proof {
        plan: prepared.plan().clone(),
        completion,
        error,
    })
}

fn main() {
    let result = run().and_then(|proof| {
        let failed = proof.error.is_some();
        let mut bytes = object_bytes(&proof)?;
        bytes.push(b'\n');
        std::io::stdout()
            .write_all(&bytes)
            .map_err(|e| e.to_string())?;
        Ok(failed)
    });
    match result {
        Ok(false) => {}
        Ok(true) => std::process::exit(1),
        Err(error) => {
            eprintln!("{error}");
            std::process::exit(1);
        }
    }
}
