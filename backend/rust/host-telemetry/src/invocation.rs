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

const DEFAULT_HOST_LEDGER_PREFIX: &str = "host-fingerprint";
const MAX_HOST_LEDGER_PREFIX_BYTES: usize = 255;
const MAX_HOST_LEDGER_PREFIX_SEGMENTS: usize = 8;
const MAX_HOST_LEDGER_PREFIX_SEGMENT_BYTES: usize = 64;

fn validate_output_root(output_roots: &[String], target_root: &str) -> Result<()> {
    require(
        output_roots.iter().any(|root| root == target_root)
            && (target_root == "state"
                || (target_root != "raw"
                    && !target_root.starts_with("raw/")
                    && !target_root.starts_with("state/"))),
        "output root not an isolated manifest root",
    )
}

fn host_ledger_prefix(value: Option<&str>) -> Result<Vec<String>> {
    let value = value.unwrap_or(DEFAULT_HOST_LEDGER_PREFIX);
    require(
        value.len() <= MAX_HOST_LEDGER_PREFIX_BYTES,
        "host ledger prefix exceeds byte cap",
    )?;
    let segments = value.split('/').collect::<Vec<_>>();
    require(
        !segments.is_empty() && segments.len() <= MAX_HOST_LEDGER_PREFIX_SEGMENTS,
        "host ledger prefix has invalid depth",
    )?;
    for segment in &segments {
        require(
            !segment.is_empty() && segment.len() <= MAX_HOST_LEDGER_PREFIX_SEGMENT_BYTES,
            "host ledger prefix has invalid segment length",
        )?;
        crate::contracts::host::pattern(
            segment,
            r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
            "invalid host ledger prefix segment",
        )?;
    }
    require(
        (segments.len() == 1 && segments[0] == DEFAULT_HOST_LEDGER_PREFIX)
            || (segments.first() == Some(&"pipeline-tests")
                && segments.last() == Some(&DEFAULT_HOST_LEDGER_PREFIX)),
        "host ledger prefix is not an approved namespace",
    )?;
    Ok(segments.into_iter().map(str::to_owned).collect())
}

pub fn execute(verb: &str, args: BTreeMap<String, String>) -> Result<()> {
    let required = |name: &str| {
        args.get(name)
            .map(String::as_str)
            .ok_or_else(|| format!("missing {name}"))
    };
    let workspace = std::fs::canonicalize(required("--workspace")?).map_err(|e| e.to_string())?;
    let config: ExperimentConfig = document(&workspace, required("--config")?, 65536)?;
    config.validate()?;
    let mut manifest: HostSessionManifest = document(
        &workspace,
        required("--manifest")?,
        config.limits.max_manifest_bytes as usize,
    )?;
    manifest.validate()?;
    manifest.controls.memory_profiling_enabled = config
        .effective_controls(crate::config::memory_profiling_override(
            args.get("--memory-profiling").map(String::as_str),
        )?)
        .memory_profiling_enabled;
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
    let result_sequence = required("--result-sequence")?
        .parse::<i64>()
        .map_err(|e| e.to_string())?;
    let completion_id = args
        .get("--completion-id")
        .map(|value| value.parse().map_err(|e: uuid::Error| e.to_string()))
        .transpose()?;
    let target_root = args
        .get("--output-root")
        .map(String::as_str)
        .unwrap_or(&manifest.output_roots[0]);
    validate_output_root(&manifest.output_roots, target_root)?;
    let prefix = host_ledger_prefix(args.get("--ledger-prefix").map(String::as_str))?;
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
    let result_path = args
        .get("--result-output")
        .cloned()
        .unwrap_or_else(|| format!("{}/results/{result_id}.json", manifest.event_root));
    require(
        result_path == format!("{}/results/{result_id}.json", manifest.event_root)
            || result_path == format!("{}/results/.pending-{result_id}.json", manifest.event_root),
        "result output path is not bound to result ID",
    )?;
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
                && result.completion_event_ids == [completion_id.unwrap_or(command.event_id)],
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
        // Probe and target are separate lifecycle commands.  The manifest
        // selects the legal target, but a probe must not silently capture it;
        // host.target owns that enrichment and its successor checks.
        let selected = body.target.as_ref();
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
    let mut result = match verb {
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
    if let Some(completion_id) = completion_id {
        result.completion_event_ids = vec![completion_id];
    }
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
    event.sequence = result_sequence;
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
    immutable_event(workspace, result_path, &event, limits.max_document_bytes)?;
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
fn immutable_event(
    workspace: &Path,
    relative: &str,
    value: &HostEvent,
    maximum: usize,
) -> Result<()> {
    let path = paths::resolve_document(workspace, relative)?;
    let bytes = crate::canonical_json::row_line(value)?;
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

#[cfg(test)]
mod tests {
    use super::*;

    fn workspace(name: &str) -> PathBuf {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("var")
            .join(format!("d7-invocation-{name}"));
        if root.exists() {
            std::fs::remove_dir_all(&root).unwrap();
        }
        std::fs::create_dir_all(&root).unwrap();
        root.canonicalize().unwrap()
    }

    fn run_with_prefix(name: &str, prefix: Option<&str>) -> (PathBuf, IntendedResult) {
        let workspace = workspace(name);
        let mut manifest: HostSessionManifest = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../tests/fixtures/host-events/manifest.json"
        )))
        .unwrap();
        manifest.output_roots = vec!["state".to_owned()];
        manifest.named_inputs = vec![NamedHostInput {
            name: "snapshot".to_owned(),
            source: CaptureSource::Cpuinfo,
            relative_path: "capture.json".to_owned(),
        }];
        let command = HostEvent {
            version: manifest.version.clone(),
            kind: EventKind::HostProbe,
            event_id: Uuid::from_u128(501),
            reply_to: None,
            date: manifest.date.clone(),
            run_id: manifest.run_id.clone(),
            attempt: manifest.attempt,
            job: manifest.job,
            shard: manifest.shard,
            session_id: manifest.session_id,
            emitter_id: manifest.operator_emitter_id.clone(),
            sequence: 1,
            emitted_at: "2026-10-10T12:00:00Z".to_owned(),
            body: EventBody::HostCommand(HostCommandBody {
                controls: manifest.controls.clone(),
                input_names: vec!["snapshot".to_owned()],
                target: Some(ProcessTarget {
                    pid: 100,
                    start_ticks: 800,
                }),
                previous_result_id: None,
            }),
        };
        command.validate().unwrap();
        let replay: ProbeReplay = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../tests/fixtures/host-events/probe-clock.json"
        )))
        .unwrap();
        for (name, bytes) in [
            ("manifest.json", serde_json::to_vec(&manifest).unwrap()),
            ("command.json", serde_json::to_vec(&command).unwrap()),
            ("capture.json", serde_json::to_vec(&replay).unwrap()),
        ] {
            std::fs::write(workspace.join(name), bytes).unwrap();
        }
        std::fs::write(
            workspace.join("config.json"),
            include_bytes!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../config/host-telemetry-experiment.json"
            )),
        )
        .unwrap();
        let mut args = BTreeMap::from([
            (
                "--workspace".to_owned(),
                workspace.to_string_lossy().into_owned(),
            ),
            ("--manifest".to_owned(), "manifest.json".to_owned()),
            ("--config".to_owned(), "config.json".to_owned()),
            ("--command".to_owned(), "command.json".to_owned()),
            ("--snapshot".to_owned(), "snapshot".to_owned()),
            ("--output-root".to_owned(), "state".to_owned()),
            ("--cache-multiple".to_owned(), "2".to_owned()),
            ("--format".to_owned(), "json".to_owned()),
            ("--compression".to_owned(), "none".to_owned()),
            (
                "--result-id".to_owned(),
                "00000000-0000-0000-0000-000000002001".to_owned(),
            ),
            ("--result-sequence".to_owned(), "3".to_owned()),
        ]);
        if let Some(prefix) = prefix {
            args.insert("--ledger-prefix".to_owned(), prefix.to_owned());
        }
        execute("probe", args).unwrap();
        let intent_path = workspace.join(format!(
            "{}/writes/{}.intent.json",
            manifest.event_root, command.event_id
        ));
        let intended = serde_json::from_slice(&std::fs::read(intent_path).unwrap()).unwrap();
        (workspace, intended)
    }

    #[test]
    fn state_root_emits_host_files_under_default_and_trial_prefixes() {
        for (name, supplied_prefix, expected_prefix) in [
            ("default", None, vec!["host-fingerprint".to_owned()]),
            (
                "trial",
                Some("pipeline-tests/host-fingerprint"),
                vec!["pipeline-tests".to_owned(), "host-fingerprint".to_owned()],
            ),
        ] {
            let (workspace, intended) = run_with_prefix(name, supplied_prefix);
            assert_eq!(intended.plan.target_root, "state");
            assert_eq!(intended.plan.prefix, expected_prefix);
            assert!(
                intended.plan.files[0]
                    .relative_path
                    .starts_with(&format!("raw/{}/", expected_prefix.join("/")))
            );
            let raw = workspace
                .join(&intended.plan.target_root)
                .join(&intended.plan.files[0].relative_path);
            assert!(raw.is_file());
            std::fs::remove_dir_all(workspace).unwrap();
        }
    }

    #[test]
    fn output_roots_keep_scratch_isolation_and_refuse_other_state_paths() {
        assert!(validate_output_root(&["state".to_owned()], "state").is_ok());
        assert!(
            validate_output_root(
                &["experiment-output/state".to_owned()],
                "experiment-output/state"
            )
            .is_ok()
        );
        assert!(
            validate_output_root(
                &["state/raw/item-health".to_owned()],
                "state/raw/item-health"
            )
            .is_err()
        );
        assert!(validate_output_root(&["state".to_owned()], "other-root").is_err());
        assert!(validate_output_root(&["raw".to_owned()], "raw").is_err());
    }

    #[test]
    fn host_ledger_prefix_accepts_only_default_or_bounded_trial_namespaces() {
        assert_eq!(
            host_ledger_prefix(None).unwrap(),
            vec!["host-fingerprint".to_owned()]
        );
        assert_eq!(
            host_ledger_prefix(Some("pipeline-tests/host-fingerprint")).unwrap(),
            vec!["pipeline-tests".to_owned(), "host-fingerprint".to_owned()]
        );
        assert_eq!(
            host_ledger_prefix(Some("pipeline-tests/bench-01/host-fingerprint")).unwrap(),
            vec![
                "pipeline-tests".to_owned(),
                "bench-01".to_owned(),
                "host-fingerprint".to_owned()
            ]
        );
        for value in [
            "",
            "item-health",
            "other/host-fingerprint",
            "pipeline-tests/item-health",
            "pipeline-tests/../host-fingerprint",
            "pipeline-tests//host-fingerprint",
            "/pipeline-tests/host-fingerprint",
            "pipeline-tests/host-fingerprint/",
            "pipeline-tests\\host-fingerprint",
            "pipeline-tests/-bad/host-fingerprint",
            "pipeline-tests/bad--segment/host-fingerprint",
            "pipeline-tests/Upper/host-fingerprint",
            "pipeline-tests/a/a/a/a/a/a/a/host-fingerprint",
        ] {
            assert!(
                host_ledger_prefix(Some(value)).is_err(),
                "accepted malformed or untrusted prefix: {value:?}"
            );
        }
        let long_segment = format!(
            "pipeline-tests/{}/host-fingerprint",
            "a".repeat(MAX_HOST_LEDGER_PREFIX_SEGMENT_BYTES + 1)
        );
        assert!(host_ledger_prefix(Some(&long_segment)).is_err());
        let full_segment = "a".repeat(MAX_HOST_LEDGER_PREFIX_SEGMENT_BYTES);
        let long_prefix = format!(
            "pipeline-tests/{full_segment}/{full_segment}/{full_segment}/{full_segment}/host-fingerprint"
        );
        assert!(long_prefix.len() > MAX_HOST_LEDGER_PREFIX_BYTES);
        assert!(host_ledger_prefix(Some(&long_prefix)).is_err());
    }
}
