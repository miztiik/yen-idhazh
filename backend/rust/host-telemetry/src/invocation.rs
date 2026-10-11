//! How does one explicit host invocation bind its observations to retained whole-row evidence?

use crate::config::{CodecConfig, ExperimentConfig, Lifecycle};
use crate::contracts::events::*;
use crate::contracts::file_envelope::{Compression, Format, HostWriterIdentity};
use crate::contracts::host::{Result, Validate, require};
use crate::probe_inputs::{
    files::read_text,
    placement,
    snapshots::{self, LiveRoots, ProbeReplay},
};
use crate::producers::{
    job_clock,
    job_probe::{self, Publication},
    target_probe,
};
use crate::{
    fs::atomic,
    ledger::{paths, store},
    receipts,
};
use serde::de::DeserializeOwned;
use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use uuid::Uuid;

#[derive(serde::Serialize, serde::Deserialize)]
#[serde(deny_unknown_fields)]
struct IntendedResult {
    arguments: BTreeMap<String, String>,
    event: HostEvent,
    plan: crate::contracts::write_plan::HostWritePlan,
}

pub fn execute(verb: &str, args: BTreeMap<String, String>) -> Result<()> {
    let required = |name: &str| {
        args.get(name)
            .map(String::as_str)
            .ok_or_else(|| format!("missing {name}"))
    };
    let workspace = std::fs::canonicalize(required("--workspace")?).map_err(|e| e.to_string())?;
    let config: ExperimentConfig = document(&workspace, required("--config")?, 65536)?;
    let manifest: HostSessionManifest = document(
        &workspace,
        required("--manifest")?,
        config.limits.max_manifest_bytes as usize,
    )?;
    let command: HostEvent = document(
        &workspace,
        required("--command")?,
        manifest.limits.max_command_bytes as usize,
    )?;
    let body = job_probe::validate_command(&manifest, &command)?;
    require(
        matches!(
            (verb, command.kind),
            ("probe", EventKind::HostProbe)
                | ("target", EventKind::HostTarget)
                | ("clock", EventKind::HostClock)
        ),
        "verb contradicts command",
    )?;
    let result_id: Uuid = required("--result-id")?
        .parse()
        .map_err(|e: uuid::Error| e.to_string())?;
    let target_root = args
        .get("--output-root")
        .map(String::as_str)
        .unwrap_or(&manifest.output_roots[0]);
    require(
        manifest.output_roots.iter().any(|v| v == target_root)
            && !target_root.starts_with("state/")
            && target_root != "state"
            && target_root != "raw"
            && !target_root.starts_with("raw/"),
        "output root not an isolated manifest root",
    )?;
    let receipt_limits = receipts::ReceiptLimits {
        max_files: config.verification_limits.max_files as usize,
        max_file_bytes: config.verification_limits.max_file_bytes as usize,
        max_total_bytes: config.verification_limits.max_total_bytes as usize,
        max_document_bytes: manifest.limits.max_result_bytes as usize,
    };
    let evidence = format!("{}/writes", manifest.event_root);
    let retained_command = format!("{}/commands/{}.json", manifest.event_root, command.event_id);
    immutable_document(
        &workspace,
        &retained_command,
        &command,
        manifest.limits.max_command_bytes as usize,
    )?;
    let result_path = format!("{}/results/{result_id}.json", manifest.event_root);
    let plan_path = format!("{evidence}/{}.plan.json", command.event_id);
    let intent_path = format!("{evidence}/{}.intent.json", command.event_id);
    if paths::resolve_document(&workspace, &intent_path)?.exists() {
        let intended: IntendedResult = document(
            &workspace,
            &intent_path,
            manifest.limits.max_result_bytes as usize,
        )?;
        intended.event.validate()?;
        intended.plan.validate()?;
        require(
            intended.arguments == args
                && intended.event.reply_to == Some(command.event_id)
                && intended.event.event_id == result_id
                && intended.event.session_id == manifest.session_id
                && intended.event.kind == EventKind::HostResult
                && intended.event.date == manifest.date
                && intended.event.run_id == manifest.run_id
                && intended.event.attempt == manifest.attempt
                && intended.event.job == manifest.job
                && intended.event.shard == manifest.shard
                && intended.event.emitter_id == manifest.monitor_emitter_id
                && intended.plan.event_id == command.event_id
                && intended.plan.target_root == target_root
                && intended.plan.publication_identity.run_id == manifest.run_id
                && intended.plan.publication_identity.attempt == manifest.attempt
                && intended.plan.publication_identity.job == manifest.job
                && intended.plan.publication_identity.shard == manifest.shard
                && intended.plan.publication_identity.git_sha == manifest.git_sha,
            "retry intended result conflict",
        )?;
        let EventBody::HostResult(result) = &intended.event.body else {
            return Err("intent is not a host result".to_owned());
        };
        require(
            intended.plan.files.len() == 1
                && intended.plan.files[0].rows.len() == 1
                && intended.plan.files[0].rows[0].host == result.row
                && result.completion_event_ids == [command.event_id],
            "intended row differs from native plan",
        )?;
        let prepared = store::prepare_plan(&workspace, intended.plan)?;
        return finish(
            &workspace,
            &result_path,
            intended.event,
            &prepared,
            &evidence,
            &receipt_limits,
        );
    }
    require(
        !paths::resolve_document(&workspace, &result_path)?.exists()
            && !paths::resolve_document(&workspace, &plan_path)?.exists(),
        "publication lacks retained intended result; recapture refused",
    )?;
    let previous: Option<HostEvent> = args
        .get("--previous-result")
        .map(|name| document(&workspace, name, manifest.limits.max_result_bytes as usize))
        .transpose()?;
    let previous_plan = args
        .get("--previous-plan")
        .map(|name| receipts::load_plan(&workspace, name, &evidence, &receipt_limits))
        .transpose()?;
    if let Some(prepared) = &previous_plan {
        receipts::recover(prepared, &evidence, &receipt_limits).map_err(|e| e.message.clone())?;
    }
    let previous_body = previous.as_ref().and_then(|event| {
        if let EventBody::HostResult(body) = &event.body {
            Some(body.as_ref())
        } else {
            None
        }
    });
    let named_text = |key: &str, maximum: usize| -> Result<Option<String>> {
        let Some(name) = args.get(key) else {
            return Ok(None);
        };
        require(
            body.input_names.contains(name),
            "input not selected by command",
        )?;
        let input = manifest
            .named_inputs
            .iter()
            .find(|v| v.name == *name)
            .ok_or("unknown named input")?;
        let path = paths::resolve_document(&workspace, &input.relative_path)?;
        let reading = read_text(&path, maximum);
        Ok(reading.value)
    };
    let replay: Option<ProbeReplay> =
        named_text("--snapshot", manifest.limits.max_read_bytes as usize)?
            .map(|text| serde_json::from_str(&text).map_err(|e| e.to_string()))
            .transpose()?;
    let now = utc_now()?;
    let captured_at = replay
        .as_ref()
        .map(|v| v.captured_at.as_str())
        .unwrap_or(&now);
    require(
        !args.contains_key("--captured-at") || replay.is_some(),
        "live capture clock cannot be supplied",
    )?;
    let captured_at = args
        .get("--captured-at")
        .map(String::as_str)
        .unwrap_or(captured_at);
    let previous_parts=||->Result<(Uuid,&HostResultBody,&crate::contracts::write_plan::HostWritePlan)>{
        Ok((previous.as_ref().ok_or("missing previous result")?.event_id,previous_body.ok_or("previous is not a host result")?,
            previous_plan.as_ref().ok_or("missing previous plan")?.plan()))
    };
    let mut live_capture = None;
    if verb != "clock" && replay.is_none() {
        let roots = LiveRoots {
            proc: Path::new(required("--proc-root")?),
            cpu: Path::new(required("--cpu-root")?),
            namespace: Path::new(required("--namespace-root")?),
        };
        let selected = body.target.as_ref().or(manifest.cpu_target.as_ref());
        if let Some(text) = named_text(
            "--affinity-input",
            manifest.capture_limits.max_proc_text_bytes as usize,
        )? {
            require(
                roots.proc != Path::new("/proc"),
                "recorded affinity cannot replace live kernel target affinity",
            )?;
            let affinity: crate::probe_inputs::files::Reading<Vec<i64>> =
                serde_json::from_str(&text).map_err(|e| e.to_string())?;
            live_capture = Some(snapshots::capture(
                &roots,
                selected,
                &manifest.capture_limits,
                Some(&affinity),
            )?);
        } else {
            live_capture = Some(snapshots::live(&roots, selected, &manifest.capture_limits)?);
        }
    }
    if let Some(text) = named_text("--hierarchy-input", manifest.limits.max_read_bytes as usize)? {
        require(
            replay.is_none() && required("--proc-root")? != "/proc",
            "recorded hierarchy cannot replace live kernel evidence",
        )?;
        let recorded: crate::probe_inputs::hierarchy::RecordedHierarchy =
            serde_json::from_str(&text).map_err(|e| e.to_string())?;
        let capture = live_capture.as_mut().ok_or("missing recorded capture")?;
        for target in [&mut capture.target_before, &mut capture.target_after]
            .into_iter()
            .flatten()
        {
            recorded.apply(target)?;
        }
    }
    let capture = || -> Result<&snapshots::CpuCapture> {
        if let Some(replay) = &replay {
            replay.selected(&manifest.capture_limits)
        } else {
            live_capture
                .as_ref()
                .ok_or_else(|| "missing CPU capture".to_owned())
        }
    };
    let result = match verb {
        "probe" => {
            let where_ = if let Some(replay) = &replay {
                placement::recorded(
                    replay
                        .placement_json
                        .value
                        .as_deref()
                        .unwrap_or("")
                        .as_bytes(),
                )
            } else if args.contains_key("--metadata-input") {
                let text = named_text(
                    "--metadata-input",
                    manifest.capture_limits.max_proc_text_bytes as usize,
                )?;
                placement::recorded(text.as_deref().unwrap_or("").as_bytes())
            } else {
                placement::live(manifest.capture_limits.max_proc_text_bytes as usize)
            };
            let runner = match &replay {
                Some(value) => value.runner_name.clone(),
                None => std::env::var("RUNNER_NAME").ok(),
            };
            let multiple = required("--cache-multiple")?
                .parse()
                .map_err(|_| "invalid cache multiple")?;
            job_probe::probe(
                &manifest,
                &command,
                capture()?,
                &where_,
                runner,
                captured_at,
                multiple,
            )?
        }
        "target" => {
            let (id, row, plan) = previous_parts()?;
            target_probe::enrich(&manifest, &command, id, row, plan, capture()?, captured_at)?
        }
        "clock" => {
            let (id, row, plan) = previous_parts()?;
            let start = named_text(
                "--job-start-input",
                manifest.capture_limits.max_log_bytes as usize,
            )?;
            let log = named_text(
                "--log-input",
                manifest.capture_limits.max_log_bytes as usize,
            )?;
            let metrics = named_text(
                "--metrics-input",
                manifest.capture_limits.max_log_bytes as usize,
            )?;
            job_clock::enrich(
                &manifest,
                &command,
                id,
                row,
                plan,
                job_clock::ClockInputs {
                    start: start.as_deref().map(str::trim),
                    finish: captured_at,
                    log: log.as_deref(),
                    metrics: metrics.as_deref(),
                },
            )?
        }
        _ => return Err("unknown producer command".to_owned()),
    };
    let codec = CodecConfig {
        format: match args
            .get("--format")
            .map(String::as_str)
            .unwrap_or("parquet")
        {
            "parquet" => Format::Parquet,
            "json" => Format::Json,
            _ => return Err("unsupported format".to_owned()),
        },
        compression: match args
            .get("--compression")
            .map(String::as_str)
            .unwrap_or("zstd")
        {
            "none" => Compression::None,
            "snappy" => Compression::Snappy,
            "zstd" => Compression::Zstd,
            _ => return Err("unsupported compression".to_owned()),
        },
    };
    let identity = HostWriterIdentity {
        run_id: manifest.run_id.clone(),
        attempt: manifest.attempt,
        job: manifest.job,
        shard: manifest.shard,
        producer: "telemetry.silicon".to_owned(),
        git_sha: manifest.git_sha.clone(),
    };
    let written_at_ms = match &replay {
        Some(v) => v.written_at_ms,
        None => store::actual_millis_after(
            previous_plan
                .as_ref()
                .and_then(|v| v.plan().files.first().map(|f| f.envelope.written_at_ms)),
            Duration::from_millis(manifest.limits.ack_timeout_ms as u64),
        )?,
    };
    let prefix = vec!["host-fingerprint".to_owned()];
    let publication = Publication {
        workspace: &workspace,
        target_root,
        evidence_root: &evidence,
        prefix: &prefix,
        identity: &identity,
        codec: &codec,
        lifecycle: Lifecycle::Active,
        event_id: command.event_id,
        written_at_ms,
        limits: &receipt_limits,
    };
    let prepared = job_probe::prepare(
        &publication,
        &result,
        previous_plan.as_ref().map(|v| v.plan()),
    )?
    .ok_or("raw family refused write")?;
    let mut event = command.clone();
    event.kind = EventKind::HostResult;
    event.event_id = result_id;
    event.reply_to = Some(command.event_id);
    event.emitter_id = manifest.monitor_emitter_id.clone();
    event.emitted_at = captured_at.to_owned();
    event.body = EventBody::HostResult(Box::new(result));
    event.validate()?;
    let intended = IntendedResult {
        arguments: args.clone(),
        event,
        plan: prepared.plan().clone(),
    };
    immutable_document(
        &workspace,
        &intent_path,
        &intended,
        manifest.limits.max_result_bytes as usize,
    )?;
    checkpoint("intended-result");
    finish(
        &workspace,
        &result_path,
        intended.event,
        &prepared,
        &evidence,
        &receipt_limits,
    )
}
fn finish(
    workspace: &Path,
    result_path: &str,
    event: HostEvent,
    prepared: &store::PreparedWrite,
    evidence: &str,
    limits: &receipts::ReceiptLimits,
) -> Result<()> {
    let completion = receipts::write_observed(prepared, evidence, limits, &mut |stage| {
        match stage {
            receipts::Checkpoint::PlanPersisted => checkpoint("plan"),
            receipts::Checkpoint::FilePublished(_) => checkpoint("publication"),
            receipts::Checkpoint::ReceiptPersisted(_) => checkpoint("receipt"),
            _ => {}
        }
        Ok(())
    })
    .map_err(|e| e.message.clone())?;
    completion.validate_plan(prepared.plan(), true)?;
    immutable_document(workspace, result_path, &event, limits.max_document_bytes)?;
    checkpoint("result");
    println!("{result_path}");
    Ok(())
}
fn checkpoint(name: &str) {
    #[cfg(debug_assertions)]
    if std::env::var("IDHAZH_HOST_CHECKPOINT").as_deref() == Ok(name) {
        eprintln!("host checkpoint: {name}");
        loop {
            std::thread::sleep(Duration::from_secs(1));
        }
    }
    let _ = name;
}
fn document<T: DeserializeOwned>(workspace: &Path, relative: &str, maximum: usize) -> Result<T> {
    let path = paths::resolve_document(workspace, relative)?;
    serde_json::from_slice(&store::read_bounded(&path, maximum)?).map_err(|e| e.to_string())
}
fn immutable_document(
    workspace: &Path,
    relative: &str,
    value: &impl serde::Serialize,
    maximum: usize,
) -> Result<()> {
    let path: PathBuf = paths::resolve_document(workspace, relative)?;
    let mut bytes = serde_json::to_vec(value).map_err(|e| e.to_string())?;
    bytes.push(b'\n');
    require(bytes.len() <= maximum, "event exceeds byte cap")?;
    atomic::publish_immutable(&path, &bytes).map_err(|e| e.to_string())
}
fn utc_now() -> Result<String> {
    let seconds = i64::try_from(
        SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|e| e.to_string())?
            .as_secs(),
    )
    .map_err(|e| e.to_string())?;
    Ok(chrono::DateTime::from_timestamp(seconds, 0)
        .ok_or("UTC clock out of range")?
        .format("%Y-%m-%dT%H:%M:%SZ")
        .to_string())
}
