//! How is a validated resource session driven through real files, live cadence or bounded recorded replay?

use crate::config::ExperimentConfig;
use crate::contracts::events::*;
use crate::contracts::host::require;
use crate::contracts::write_plan::HostWritePlan;
use crate::monitor::session::{NativeHostOutput, Session};
use crate::producers::job_samples::{self, Artifacts};
use crate::sampling::capture::{LiveCapture, ResourceFrame, ResourceReplay, utc_now};
use crate::transport::bounds::refuse;
use crate::transport::files::{FileTransport, read_bounded};
use crate::{Result, Validate};
use std::{
    collections::{BTreeMap, HashMap, HashSet},
    path::{Path, PathBuf},
    time::{Duration, Instant},
};

// An unread config cannot set its own bootstrap read cap.
const CONFIG_BOOTSTRAP_BYTES: usize = 65_536;

fn argument<'a>(args: &'a BTreeMap<String, String>, key: &str) -> Result<&'a str> {
    args.get(key)
        .map(String::as_str)
        .ok_or_else(|| format!("missing {key}"))
}
fn load(args: &BTreeMap<String, String>) -> Result<(PathBuf, HostSessionManifest)> {
    let workspace = PathBuf::from(argument(args, "--workspace")?)
        .canonicalize()
        .map_err(|e| e.to_string())?;
    let config_path =
        crate::ledger::paths::resolve_document(&workspace, argument(args, "--config")?)?;
    let config = ExperimentConfig::from_bytes(
        &read_bounded(&config_path, CONFIG_BOOTSTRAP_BYTES)?,
        CONFIG_BOOTSTRAP_BYTES,
    )?;
    config.validate()?;
    let path = crate::ledger::paths::resolve_document(&workspace, argument(args, "--manifest")?)?;
    let raw = read_bounded(&path, config.limits.max_manifest_bytes as usize)?;
    let mut manifest: HostSessionManifest =
        serde_json::from_slice(&raw).map_err(|e| e.to_string())?;
    manifest.validate()?;
    require(
        manifest.limits == config.limits
            && manifest.capture_limits == config.capture_limits
            && manifest.controls == config.controls,
        "manifest effective configuration differs from named config",
    )?;
    manifest.controls = config.effective_controls(crate::config::memory_profiling_override(
        args.get("--memory-profiling").map(String::as_str),
    )?);
    Ok((workspace, manifest))
}
pub fn execute(verb: &str, args: BTreeMap<String, String>) -> Result<()> {
    let (workspace, manifest) = load(&args)?;
    match verb {
        "monitor" => live(&workspace, manifest, &args),
        "resource-replay" => replay(&workspace, manifest, &args),
        "event-send" | "event-wait" => client(&workspace, manifest, &args, verb),
        "monitor-cleanup" => {
            let target = ProcessTarget {
                pid: argument(&args, "--pid")?
                    .parse::<i64>()
                    .map_err(|e| e.to_string())?,
                start_ticks: argument(&args, "--start-ticks")?
                    .parse::<i64>()
                    .map_err(|e| e.to_string())?,
            };
            target.validate()?;
            crate::transport::client::cleanup_known_pid(
                &target,
                Path::new(
                    args.get("--proc-root")
                        .map(String::as_str)
                        .unwrap_or("/proc"),
                ),
                &manifest.limits,
                &manifest.capture_limits,
            )
        }
        _ => Err("unknown resource invocation".to_owned()),
    }
}
fn client(
    workspace: &Path,
    manifest: HostSessionManifest,
    args: &BTreeMap<String, String>,
    verb: &str,
) -> Result<()> {
    let mut files = FileTransport::new(workspace, manifest)?;
    let command = args
        .get("--command")
        .map(|relative| -> Result<HostEvent> {
            let path = crate::ledger::paths::resolve_document(workspace, relative)?;
            let raw = read_bounded(&path, files.manifest.limits.max_command_bytes as usize)?;
            crate::transport::files::decode_event(&raw)
        })
        .transpose()?;
    if verb == "event-send" {
        let command = command.ok_or("event-send requires --command")?;
        files.publish(&command, "inbox")?;
        println!("{}", files.relative_path(command.event_id, "inbox")?);
    } else {
        let result = crate::transport::client::await_result(&mut files, command.as_ref())?;
        println!(
            "{}",
            String::from_utf8(crate::canonical_json::object_bytes(&result)?)
                .map_err(|e| e.to_string())?
        );
    }
    Ok(())
}
struct SampleSchedule {
    job_at: u64,
    runtime_at: u64,
    job_stopped: bool,
}
impl SampleSchedule {
    fn new() -> Self {
        Self {
            job_at: 0,
            runtime_at: 0,
            job_stopped: false,
        }
    }
    fn collect(
        &mut self,
        session: &mut Session,
        files: &mut FileTransport,
        artifacts: &mut Option<Artifacts>,
        frame: &ResourceFrame,
        now_ms: u64,
    ) -> Result<()> {
        let memory = session.manifest.controls.memory_profiling_enabled;
        if !memory {
            return Ok(());
        }
        let server = session
            .manifest
            .workers
            .iter()
            .find_map(|v| v.server.clone());
        if now_ms >= self.runtime_at {
            if let (Some(artifacts), Some(status)) = (
                artifacts.as_mut(),
                job_samples::runtime_status(frame, server.as_ref(), true),
            ) {
                artifacts.write_runtime(&status)?;
            }
            self.runtime_at = now_ms.saturating_add(job_samples::RUNTIME_INTERVAL_MS);
        }
        if !self.job_stopped && now_ms >= self.job_at {
            let target = server
                .as_ref()
                .or(session.manifest.cpu_target.as_ref())
                .or_else(|| session.manifest.workers.first().map(|v| &v.target));
            if let Some(target) = target {
                let identity = frame
                    .processes
                    .iter()
                    .find(|v| &v.target == target)
                    .map(|v| crate::sampling::process::reduce(v, false, false).identity)
                    .unwrap_or_else(|| {
                        crate::probe_inputs::files::Reading::absent(UnavailableReason::PidExited)
                    });
                if identity.reason == Some(UnavailableReason::PidReused) {
                    let error = crate::transport::bounds::refuse(
                        ProtocolFaultCode::Target,
                        "job sampler refuses reused target PID",
                    );
                    let fault = session.protocol_fault(&error, None, &frame.captured_at, now_ms)?;
                    files.publish(&fault, "results")?;
                    return Err(error.to_string());
                }
                if identity.reason == Some(UnavailableReason::PidExited) {
                    self.job_stopped = true;
                    let diagnostic = UnavailableDiagnostic {
                        source: CaptureSource::JobMemory,
                        reason: UnavailableReason::PidExited,
                    };
                    eprintln!(
                        "{}",
                        String::from_utf8(crate::canonical_json::object_bytes(&diagnostic)?)
                            .map_err(|e| e.to_string())?
                    );
                    return Ok(());
                }
            }
            match job_samples::sample(frame, server.as_ref(), true) {
                Ok(Some((record, rows))) => {
                    if let Some(artifacts) = artifacts {
                        artifacts.write_sample(&record, &rows)?;
                    }
                    let sample = session.observation(
                        EventKind::JobSample,
                        EventBody::Sample(JobSampleBody { record }),
                        &frame.captured_at,
                        now_ms,
                    )?;
                    files.publish(&sample, "results")?;
                    let rollcall = session.observation(
                        EventKind::ProcessRollcall,
                        EventBody::Rollcall(ProcessRollcallBody { records: rows }),
                        &frame.captured_at,
                        now_ms,
                    )?;
                    files.publish(&rollcall, "results")?;
                    if artifacts.is_some() {
                        // The flushed legacy files consumed these observation records.
                        for event in [&sample, &rollcall] {
                            files.consume(event)?;
                            session
                                .book
                                .consume(event.event_id)
                                .map_err(|e| e.to_string())?;
                        }
                    }
                }
                Err(error) => {
                    let diagnostic = UnavailableDiagnostic {
                        source: CaptureSource::JobMemory,
                        reason: frame
                            .population
                            .reason
                            .unwrap_or(UnavailableReason::Malformed),
                    };
                    eprintln!(
                        "{}",
                        String::from_utf8(crate::canonical_json::object_bytes(&diagnostic)?)
                            .map_err(|e| e.to_string())?
                    );
                    eprintln!("job sample unavailable: {error}");
                }
                Ok(None) => {}
            }
            self.job_at = now_ms.saturating_add(
                (session.manifest.controls.job_sample_interval_seconds * 1000.0).ceil() as u64,
            );
        }
        Ok(())
    }
    fn needs_capture(&self, session: &Session, now_ms: u64) -> bool {
        session.manifest.controls.memory_profiling_enabled
            && (now_ms >= self.runtime_at || (!self.job_stopped && now_ms >= self.job_at))
    }
}
fn artifact_root(
    manifest: &HostSessionManifest,
    args: &BTreeMap<String, String>,
) -> Result<String> {
    let root = args.get("--artifact-root").cloned().unwrap_or_else(|| {
        format!(
            "backend/var/host-resource-artifacts/{}",
            manifest.session_id
        )
    });
    require(
        root != manifest.event_root
            && !root.starts_with(&format!("{}/", manifest.event_root))
            && !manifest.event_root.starts_with(&format!("{root}/")),
        "artifacts must be separate from event root",
    )?;
    Ok(root)
}

fn native_host_output(
    workspace: &Path,
    session: &Session,
    files: &mut FileTransport,
    command: &HostEvent,
    monitor_args: &BTreeMap<String, String>,
) -> Result<NativeHostOutput> {
    let EventBody::HostCommand(body) = &command.body else {
        return Err("host command has wrong body".to_owned());
    };
    let (_, completed_id, result_id) = session.host_reply_ids(command.event_id);
    let verb = match command.kind {
        EventKind::HostProbe => "probe",
        EventKind::HostTarget => "target",
        EventKind::HostClock => "clock",
        _ => return Err("native output requested for a non-host command".to_owned()),
    };
    let mut args = BTreeMap::new();
    args.insert(
        "--workspace".to_owned(),
        workspace.to_string_lossy().into_owned(),
    );
    args.insert(
        "--manifest".to_owned(),
        monitor_args
            .get("--manifest")
            .ok_or("monitor requires --manifest for native host commands")?
            .clone(),
    );
    args.insert(
        "--config".to_owned(),
        monitor_args
            .get("--config")
            .ok_or("monitor requires --config for native host commands")?
            .clone(),
    );
    args.insert(
        "--command".to_owned(),
        files.relative_path(command.event_id, "inbox")?,
    );
    args.insert("--result-id".to_owned(), result_id.to_string());
    let staged_result_path = format!(
        "{}/results/.pending-{result_id}.json",
        session.manifest.event_root
    );
    let staged_result = crate::ledger::paths::resolve_document(workspace, &staged_result_path)?;
    let _staged_result = RemoveStagedResult(staged_result.clone());
    args.insert("--result-output".to_owned(), staged_result_path.clone());
    args.insert(
        "--result-sequence".to_owned(),
        session.host_result_sequence().to_string(),
    );
    args.insert("--completion-id".to_owned(), completed_id.to_string());
    args.insert(
        "--proc-root".to_owned(),
        monitor_args
            .get("--proc-root")
            .cloned()
            .unwrap_or_else(|| "/proc".to_owned()),
    );
    args.insert(
        "--cpu-root".to_owned(),
        monitor_args
            .get("--cpu-root")
            .cloned()
            .unwrap_or_else(|| "/sys/devices/system/cpu".to_owned()),
    );
    args.insert(
        "--namespace-root".to_owned(),
        monitor_args
            .get("--namespace-root")
            .cloned()
            .unwrap_or_else(|| "/".to_owned()),
    );
    args.insert(
        "--output-root".to_owned(),
        monitor_args
            .get("--output-root")
            .cloned()
            .unwrap_or_else(|| session.manifest.output_roots[0].clone()),
    );
    if let Some(prefix) = monitor_args.get("--ledger-prefix") {
        args.insert("--ledger-prefix".to_owned(), prefix.clone());
    }
    args.insert(
        "--format".to_owned(),
        monitor_args
            .get("--format")
            .cloned()
            .unwrap_or_else(|| "parquet".to_owned()),
    );
    args.insert(
        "--compression".to_owned(),
        monitor_args
            .get("--compression")
            .cloned()
            .unwrap_or_else(|| "zstd".to_owned()),
    );
    args.insert(
        "--cache-multiple".to_owned(),
        monitor_args
            .get("--cache-multiple")
            .cloned()
            .unwrap_or_else(|| "2".to_owned()),
    );
    args.insert(
        "--memory-profiling".to_owned(),
        if session.manifest.controls.memory_profiling_enabled {
            "on".to_owned()
        } else {
            "off".to_owned()
        },
    );
    if let Some(previous) = body.previous_result_id {
        args.insert(
            "--previous-result".to_owned(),
            files.relative_path(previous, "results")?,
        );
        let previous_plan = format!(
            "{}/writes/{}.plan.json",
            session.manifest.event_root,
            session
                .last_host_command_id()
                .ok_or("missing prior native host command")?
        );
        args.insert("--previous-plan".to_owned(), previous_plan);
    }
    for name in &body.input_names {
        let input = session
            .manifest
            .named_inputs
            .iter()
            .find(|entry| &entry.name == name)
            .ok_or("host command names an undeclared input")?;
        let key = match input.name.as_str() {
            "metadata" => "--metadata-input",
            "snapshot" => "--snapshot",
            "affinity" => "--affinity-input",
            "hierarchy" => "--hierarchy-input",
            "start" => "--job-start-input",
            "log" | "clock" => "--log-input",
            "metrics" => "--metrics-input",
            _ => match input.source {
                CaptureSource::Cpuinfo => "--metadata-input",
                CaptureSource::ClockLog => "--log-input",
                CaptureSource::Affinity => "--affinity-input",
                _ => continue,
            },
        };
        // Producer arguments name a manifest input; invocation resolves the
        // declared relative path only after validating command selection.
        args.insert(key.to_owned(), input.name.clone());
    }
    crate::invocation::execute(verb, args)?;
    let result_event = files.read_staged_result(result_id)?;
    let EventBody::HostResult(result) = result_event.body else {
        return Err("native producer wrote a non-host result".to_owned());
    };
    let evidence = format!("{}/writes", session.manifest.event_root);
    let plan_path = format!("{evidence}/{}.plan.json", command.event_id);
    let plan: HostWritePlan = serde_json::from_slice(&crate::transport::files::read_bounded(
        &crate::ledger::paths::resolve_document(workspace, &plan_path)?,
        session.manifest.limits.max_result_bytes as usize,
    )?)
    .map_err(|e| e.to_string())?;
    let completion = crate::receipts::load_latest_completion(
        workspace,
        &evidence,
        command.event_id,
        session.manifest.limits.max_result_bytes as usize,
    )?;
    // The IDs are checked by Session; keeping this assertion here makes a
    // producer that silently changes the deterministic reply reservation fail
    // before any event is admitted.
    require(
        plan.event_id == command.event_id,
        "native plan event ID differs",
    )?;
    require(
        completed_id != result_event.event_id && result_event.event_id == result_id,
        "native reply IDs drifted",
    )?;
    Ok(NativeHostOutput {
        result: *result,
        plan,
        completion,
        emitted_at: result_event.emitted_at,
    })
}

struct RemoveStagedResult(PathBuf);

impl Drop for RemoveStagedResult {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.0);
    }
}

fn publish_cancelled(
    session: &mut Session,
    files: &mut FileTransport,
    at: &str,
    now_ms: u64,
) -> Result<()> {
    let mut staged = session.clone();
    let events = staged.cancelled(at, now_ms)?;
    files.publish_batch(&events, "results")?;
    *session = staged;
    Ok(())
}
fn replay(
    workspace: &Path,
    manifest: HostSessionManifest,
    args: &BTreeMap<String, String>,
) -> Result<()> {
    let mut files = FileTransport::new(workspace, manifest.clone())?;
    let path = files.named(argument(args, "--snapshot")?)?;
    let recorded = ResourceReplay::from_bytes(
        &read_bounded(&path, manifest.capture_limits.max_log_bytes as usize)?,
        &manifest,
    )?;
    require(!recorded.frames.is_empty(), "empty resource replay")?;
    let root = artifact_root(&manifest, args)?;
    let mut artifacts = Artifacts::create(
        workspace,
        &root,
        &manifest.limits,
        manifest.controls.memory_profiling_enabled,
    )?;
    let mut session = Session::new(manifest)?;
    let ready = session.ready(&recorded.frames[0].captured_at, 0)?;
    files.publish(&ready, "results")?;
    let mut events = vec![ready];
    let mut schedule = SampleSchedule::new();
    let mut consumed = HashSet::new();
    let mut last_frame = &recorded.frames[0];
    let mut last_ms = 0;
    let run = (|| -> Result<()> {
        for action in &recorded.actions {
            let frame = &recorded.frames[action.frame];
            last_frame = frame;
            last_ms = action.at_ms;
            if session.stopped {
                break;
            }
            with_retired_consumed(
                &mut session,
                &mut files,
                &mut consumed,
                action.at_ms,
                |session, files| {
                    if let Some(command) = &action.event {
                        files.publish(command, "inbox")?;
                        let command = files.read(command.event_id, "inbox")?;
                        if matches!(
                            command.kind,
                            EventKind::HostProbe | EventKind::HostTarget | EventKind::HostClock
                        ) {
                            match session.preflight_host_command(&command, action.at_ms) {
                                Ok(Some(replies)) => {
                                    files.publish_batch(&replies, "results")?;
                                    events.extend(replies.iter().cloned());
                                    for event in std::iter::once(&command).chain(replies.iter()) {
                                        files.consume(event)?;
                                        session
                                            .book
                                            .consume(event.event_id)
                                            .map_err(|error| error.to_string())?;
                                    }
                                    return Ok(());
                                }
                                Ok(None) => {}
                                Err(error) => {
                                    let fault = session.protocol_fault(
                                        &error,
                                        Some(command.event_id),
                                        &frame.captured_at,
                                        action.at_ms,
                                    )?;
                                    files.publish(&fault, "results")?;
                                    events.push(fault);
                                    return Err(error.to_string());
                                }
                            }
                            let output =
                                match native_host_output(workspace, session, files, &command, args)
                                {
                                    Ok(value) => value,
                                    Err(error) => {
                                        let native_error = refuse(ProtocolFaultCode::Store, &error);
                                        let fault = session.protocol_fault(
                                            &native_error,
                                            Some(command.event_id),
                                            &frame.captured_at,
                                            action.at_ms,
                                        )?;
                                        files.publish(&fault, "results")?;
                                        events.push(fault);
                                        return Err(error);
                                    }
                                };
                            let mut staged = session.clone();
                            let replies = match staged.handle_host(&command, output, action.at_ms) {
                                Ok(replies) => replies,
                                Err(error) => {
                                    let fault = session.protocol_fault(
                                        &error,
                                        Some(command.event_id),
                                        &frame.captured_at,
                                        action.at_ms,
                                    )?;
                                    files.publish(&fault, "results")?;
                                    events.push(fault);
                                    return Err(error.to_string());
                                }
                            };
                            files.publish_batch(&replies, "results")?;
                            *session = staged;
                            events.extend(replies.iter().cloned());
                            for event in std::iter::once(&command).chain(replies.iter()) {
                                files.consume(event)?;
                                session
                                    .book
                                    .consume(event.event_id)
                                    .map_err(|error| error.to_string())?;
                            }
                            return Ok(());
                        }
                        let mut staged = session.clone();
                        match staged.handle(&command, frame, action.at_ms) {
                            Ok(replies) => {
                                files.publish_batch(&replies, "results")?;
                                *session = staged;
                                events.extend(replies.iter().cloned());
                                for event in std::iter::once(&command).chain(replies.iter()) {
                                    files.consume(event)?;
                                    session
                                        .book
                                        .consume(event.event_id)
                                        .map_err(|error| error.to_string())?;
                                }
                            }
                            Err(error) => {
                                let fault = session.protocol_fault(
                                    &error,
                                    Some(command.event_id),
                                    &frame.captured_at,
                                    action.at_ms,
                                )?;
                                files.publish(&fault, "results")?;
                                if error.code == ProtocolFaultCode::Bounds {
                                    return Err(error.to_string());
                                }
                                events.push(fault);
                            }
                        }
                    } else {
                        session.tick(frame, action.at_ms)?;
                    }
                    if !session.stopped {
                        schedule.collect(session, files, &mut artifacts, frame, action.at_ms)?;
                    }
                    if session.stopped
                        && let Some(artifacts) = &mut artifacts
                    {
                        artifacts.write_peak(&frame.cgroup_peak)?;
                    }
                    Ok(())
                },
            )?;
        }
        require(session.stopped, "replay lacks explicit monitor.stop/drain")?;
        Ok(())
    })();
    if run.is_err() && !session.stopped {
        publish_cancelled(&mut session, &mut files, &last_frame.captured_at, last_ms)?;
        if let Some(artifacts) = &mut artifacts {
            artifacts.write_peak(&last_frame.cgroup_peak)?;
        }
    }
    run?;
    println!(
        "{}",
        String::from_utf8(crate::canonical_json::object_bytes(&events)?)
            .map_err(|e| e.to_string())?
    );
    Ok(())
}

#[cfg(target_os = "linux")]
static CANCELLED: std::sync::atomic::AtomicBool = std::sync::atomic::AtomicBool::new(false);
#[cfg(target_os = "linux")]
extern "C" fn cancel(_signal: i32) {
    CANCELLED.store(true, std::sync::atomic::Ordering::Relaxed);
}
#[cfg(target_os = "linux")]
fn install_cancellation() -> Result<()> {
    CANCELLED.store(false, std::sync::atomic::Ordering::Relaxed);
    // Only the atomic flag changes in the handler; evidence is flushed by the normal loop.
    for signal in [libc::SIGTERM, libc::SIGINT] {
        if unsafe { libc::signal(signal, cancel as *const () as libc::sighandler_t) }
            == libc::SIG_ERR
        {
            return Err(std::io::Error::last_os_error().to_string());
        }
    }
    Ok(())
}
fn cancelled() -> bool {
    #[cfg(target_os = "linux")]
    {
        CANCELLED.load(std::sync::atomic::Ordering::Relaxed)
    }
    #[cfg(not(target_os = "linux"))]
    {
        false
    }
}
fn with_retired_consumed<T>(
    session: &mut Session,
    files: &mut FileTransport,
    consumed: &mut HashSet<uuid::Uuid>,
    now_ms: u64,
    admit: impl FnOnce(&mut Session, &mut FileTransport) -> Result<T>,
) -> Result<T> {
    for id in files.ids("consumed")? {
        if !consumed.insert(id) {
            continue;
        }
        let evidence = files.read(id, "consumed")?;
        // Consumed evidence is the original closed event, not a second protocol shape.
        let direction = if matches!(
            evidence.kind,
            EventKind::HostProbe
                | EventKind::HostTarget
                | EventKind::HostClock
                | EventKind::WorkerRegister
                | EventKind::WindowBegin
                | EventKind::WindowEnd
                | EventKind::WindowAbort
                | EventKind::MonitorStop
        ) {
            "inbox"
        } else {
            "results"
        };
        require(
            files.read(id, direction)? == evidence,
            "consumption differs from original event",
        )?;
        session.book.consume(id).map_err(|e| e.to_string())?;
    }
    // Reclaim validated, expired evidence before admission at this same timestamp.
    let retired = session.retire(now_ms);
    files.remove_retired(&retired)?;
    admit(session, files)
}
fn live(
    workspace: &Path,
    manifest: HostSessionManifest,
    args: &BTreeMap<String, String>,
) -> Result<()> {
    let proc = Path::new(
        args.get("--proc-root")
            .map(String::as_str)
            .unwrap_or("/proc"),
    );
    let cgroup = Path::new(
        args.get("--cgroup-root")
            .map(String::as_str)
            .unwrap_or("/sys/fs/cgroup"),
    );
    let source = LiveCapture::new(
        proc,
        cgroup,
        &manifest.capture_limits,
        manifest.controls.memory_profiling_enabled,
    )?;
    let boot = source.boot_id();
    require(
        boot.value
            .as_ref()
            .and_then(|v| uuid::Uuid::parse_str(v.trim()).ok())
            == Some(manifest.boot_id),
        "monitor readiness unavailable: boot identity differs or cannot be read",
    )?;
    let mut targets = manifest
        .workers
        .iter()
        .map(|v| v.target.clone())
        .collect::<Vec<_>>();
    for server in manifest.workers.iter().filter_map(|v| v.server.as_ref()) {
        if !targets.contains(server) {
            targets.push(server.clone());
        }
        require(
            targets.len() as i64 <= manifest.capture_limits.max_processes,
            "declared resource targets exceed process capture cap",
        )?;
    }
    let mut files = FileTransport::new(workspace, manifest.clone())?;
    let root = artifact_root(&manifest, args)?;
    let mut artifacts = Artifacts::create(
        workspace,
        &root,
        &manifest.limits,
        manifest.controls.memory_profiling_enabled,
    )?;
    let mut session = Session::new(manifest)?;
    let start = Instant::now();
    #[cfg(target_os = "linux")]
    install_cancellation()?;
    let ready = session.ready(&utc_now(), 0)?;
    files.publish(&ready, "results")?;
    let mut schedule = SampleSchedule::new();
    let mut seen = HashMap::new();
    let mut consumed = HashSet::new();
    let mut captures = 0_u64;
    let run = (|| -> Result<()> {
        while !session.stopped {
            let now_ms = start.elapsed().as_millis() as u64;
            if cancelled() {
                publish_cancelled(&mut session, &mut files, &utc_now(), now_ms)?;
                if let Some(artifacts) = &mut artifacts {
                    artifacts.write_peak(&source.peak())?;
                }
                break;
            }
            with_retired_consumed(
                &mut session,
                &mut files,
                &mut consumed,
                now_ms,
                |session, files| {
                    let mut commands = Vec::new();
                    for id in files.ids("inbox")? {
                        let metadata = std::fs::metadata(files.path(id, "inbox")?)
                            .map_err(|e| e.to_string())?;
                        let fingerprint = (
                            metadata.len(),
                            metadata.modified().map_err(|e| e.to_string())?,
                        );
                        if seen.get(&id) == Some(&fingerprint) {
                            continue;
                        }
                        require(
                            seen.len() < session.manifest.limits.max_session_events as usize
                                || seen.contains_key(&id),
                            "inbox history exhausted",
                        )?;
                        let event = files.read(id, "inbox")?;
                        seen.insert(id, fingerprint);
                        commands.push(event);
                    }
                    commands.sort_by(|a, b| {
                        (a.emitter_id.as_str(), a.sequence)
                            .cmp(&(b.emitter_id.as_str(), b.sequence))
                    });
                    for command in commands {
                        if matches!(
                            command.kind,
                            EventKind::HostProbe | EventKind::HostTarget | EventKind::HostClock
                        ) {
                            match session.preflight_host_command(&command, now_ms) {
                                Ok(Some(replies)) => {
                                    files.publish_batch(&replies, "results")?;
                                    continue;
                                }
                                Ok(None) => {}
                                Err(error) => {
                                    let fault = session.protocol_fault(
                                        &error,
                                        Some(command.event_id),
                                        &utc_now(),
                                        now_ms,
                                    )?;
                                    files.publish(&fault, "results")?;
                                    return Err(error.to_string());
                                }
                            }
                            let output =
                                match native_host_output(workspace, session, files, &command, args)
                                {
                                    Ok(value) => value,
                                    Err(error) => {
                                        let native_error = refuse(ProtocolFaultCode::Store, &error);
                                        let fault = session.protocol_fault(
                                            &native_error,
                                            Some(command.event_id),
                                            &utc_now(),
                                            now_ms,
                                        )?;
                                        files.publish(&fault, "results")?;
                                        return Err(error);
                                    }
                                };
                            let mut staged = session.clone();
                            match staged.handle_host(&command, output, now_ms) {
                                Ok(replies) => {
                                    files.publish_batch(&replies, "results")?;
                                    *session = staged;
                                }
                                Err(error) => {
                                    let fault = session.protocol_fault(
                                        &error,
                                        Some(command.event_id),
                                        &utc_now(),
                                        now_ms,
                                    )?;
                                    files.publish(&fault, "results")?;
                                    return Err(error.to_string());
                                }
                            }
                            continue;
                        }
                        require(
                            captures < session.manifest.limits.max_reads as u64,
                            "resource capture budget exhausted",
                        )?;
                        captures += 1;
                        let frame =
                            source.capture(&targets, command.kind == EventKind::MonitorStop);
                        let mut staged = session.clone();
                        match staged.handle(&command, &frame, now_ms) {
                            Ok(replies) => {
                                files.publish_batch(&replies, "results")?;
                                *session = staged;
                            }
                            Err(error) => {
                                let fault = session.protocol_fault(
                                    &error,
                                    Some(command.event_id),
                                    &frame.captured_at,
                                    now_ms,
                                )?;
                                files.publish(&fault, "results")?;
                                return Err(error.to_string());
                            }
                        }
                        if session.stopped
                            && let Some(artifacts) = &mut artifacts
                        {
                            artifacts.write_peak(&frame.cgroup_peak)?;
                        }
                        if session.stopped {
                            break;
                        }
                    }
                    if !session.stopped
                        && (session.needs_tick(now_ms) || schedule.needs_capture(session, now_ms))
                    {
                        require(
                            captures < session.manifest.limits.max_reads as u64,
                            "resource capture budget exhausted",
                        )?;
                        captures += 1;
                        let frame =
                            source.capture(&targets, schedule.needs_capture(session, now_ms));
                        session.tick(&frame, now_ms)?;
                        schedule.collect(session, files, &mut artifacts, &frame, now_ms)?;
                        if session.active_count() > 0 {
                            eprintln!(
                                "host resource heartbeat: {} ms; active={} registered={}",
                                now_ms,
                                session.active_count(),
                                session.registered_count()
                            );
                        }
                    }
                    Ok(())
                },
            )?;
            std::thread::sleep(Duration::from_millis(
                session.manifest.limits.poll_ms as u64,
            ));
        }
        Ok(())
    })();
    if run.is_err() && !session.stopped {
        publish_cancelled(
            &mut session,
            &mut files,
            &utc_now(),
            start.elapsed().as_millis() as u64,
        )?;
        if let Some(artifacts) = &mut artifacts {
            artifacts.write_peak(&source.peak())?;
        }
    }
    run
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Fixture {
        root: PathBuf,
        session: Session,
        files: FileTransport,
        artifacts: Option<Artifacts>,
        schedule: SampleSchedule,
        consumed: HashSet<uuid::Uuid>,
        frame: ResourceFrame,
        ready: HostEvent,
    }
    impl Fixture {
        fn new(name: &str, artifacts_enabled: bool) -> Self {
            Self::with_max_files(name, artifacts_enabled, None)
        }
        fn with_max_files(name: &str, artifacts_enabled: bool, max_files: Option<i64>) -> Self {
            let mut manifest_json: serde_json::Value = serde_json::from_str(include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../tests/fixtures/host-events/manifest.json"
            )))
            .unwrap();
            if let Some(max_files) = max_files {
                manifest_json["limits"]["max_files"] = serde_json::json!(max_files);
            }
            let mut manifest: HostSessionManifest = serde_json::from_value(manifest_json).unwrap();
            manifest.workers.truncate(1);
            manifest.windows.truncate(1);
            manifest.controls.job_sample_interval_seconds =
                manifest.limits.retry_window_ms as f64 / 1000.0;
            assert_eq!(manifest.pending_event_limit().unwrap(), 31);
            let recorded: serde_json::Value = serde_json::from_str(include_str!(concat!(
                env!("CARGO_MANIFEST_DIR"),
                "/../../../tests/fixtures/host-events/resource-windows.json"
            )))
            .unwrap();
            let mut frame: ResourceFrame =
                serde_json::from_value(recorded["replay"]["frames"][0].clone()).unwrap();
            frame.population.value = Some(
                frame
                    .processes
                    .iter()
                    .filter(|p| p.target.pid != 100)
                    .cloned()
                    .collect(),
            );
            let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
                .join("..")
                .join("..")
                .join("var")
                .join(format!("d5-retirement-{name}"));
            if root.exists() {
                std::fs::remove_dir_all(&root).unwrap();
            }
            std::fs::create_dir_all(&root).unwrap();
            let root = root.canonicalize().unwrap();
            let artifacts =
                Artifacts::create(&root, "artifacts", &manifest.limits, artifacts_enabled).unwrap();
            let mut session = Session::new(manifest.clone()).unwrap();
            let mut files = FileTransport::new(&root, manifest).unwrap();
            let ready = session.ready(&frame.captured_at, 0).unwrap();
            files.publish(&ready, "results").unwrap();
            let mut fixture = Self {
                root,
                session,
                files,
                artifacts,
                schedule: SampleSchedule::new(),
                consumed: HashSet::new(),
                frame,
                ready,
            };
            fixture.collect(0).unwrap();
            fixture
        }
        fn collect(&mut self, now_ms: u64) -> Result<()> {
            with_retired_consumed(
                &mut self.session,
                &mut self.files,
                &mut self.consumed,
                now_ms,
                |session, files| {
                    session.tick(&self.frame, now_ms)?;
                    self.schedule
                        .collect(session, files, &mut self.artifacts, &self.frame, now_ms)
                },
            )
        }
        fn open_window(&mut self) -> Vec<HostEvent> {
            let worker = &self.session.manifest.workers[0];
            let mut register = self.ready.clone();
            register.kind = EventKind::WorkerRegister;
            register.event_id = uuid::Uuid::from_u128(1001);
            register.emitter_id = worker.emitter_id.clone();
            register.sequence = 1;
            register.body = EventBody::Worker(WorkerBody {
                target: worker.target.clone(),
                server: worker.server.clone(),
                memory_profiling_enabled: true,
            });
            let mut begin = register.clone();
            begin.kind = EventKind::WindowBegin;
            begin.event_id = uuid::Uuid::from_u128(1002);
            begin.sequence = 2;
            let window = &self.session.manifest.windows[0];
            begin.body = EventBody::Window(WindowBody {
                window_id: window.window_id,
                item_id: window.item_id.clone(),
                target: worker.target.clone(),
                server: worker.server.clone(),
            });
            let mut events = Vec::new();
            for command in [register, begin] {
                self.files.publish(&command, "inbox").unwrap();
                let replies = self.session.handle(&command, &self.frame, 0).unwrap();
                self.files.publish_batch(&replies, "results").unwrap();
                events.push(command);
                events.extend(replies);
            }
            events
        }
    }
    impl Drop for Fixture {
        fn drop(&mut self) {
            self.artifacts.take();
            std::fs::remove_dir_all(&self.root).unwrap();
        }
    }

    #[test]
    fn retry_boundary_retires_consumed_samples_before_next_pair() {
        let mut fixture = Fixture::new("boundary", true);
        let samples = fixture.files.ids("consumed").unwrap();
        assert_eq!(samples.len(), 2);
        let events = fixture.open_window();
        for event in &events[2..] {
            fixture.files.consume(event).unwrap();
        }
        assert_eq!(fixture.session.book.retained(), 7);
        let retry = fixture.session.manifest.limits.retry_window_ms as u64;
        fixture.collect(retry - 1).unwrap();
        assert_eq!(fixture.session.book.retained(), 7);
        for id in &samples {
            assert!(fixture.files.path(*id, "results").unwrap().is_file());
            assert!(fixture.files.path(*id, "consumed").unwrap().is_file());
        }

        fixture.collect(retry).unwrap();
        assert_eq!(fixture.session.book.retained(), 7);
        assert_eq!(fixture.session.book.total_events, 9);
        assert_eq!(fixture.session.book.history_len(), 9);
        assert_eq!(fixture.files.total_events, 9);
        for id in &samples {
            for direction in ["results", "consumed"] {
                assert!(!fixture.files.path(*id, direction).unwrap().exists());
            }
        }
        assert!(
            fixture
                .files
                .path(fixture.ready.event_id, "results")
                .unwrap()
                .is_file()
        );
        for (index, event) in events.iter().enumerate() {
            let direction = if index % 2 == 0 { "inbox" } else { "results" };
            assert_eq!(
                fixture.files.read(event.event_id, direction).unwrap(),
                *event
            );
        }
        assert_eq!(fixture.session.active_count(), 1);
        assert_eq!(
            fixture
                .session
                .handle(&events[2], &fixture.frame, retry)
                .unwrap(),
            vec![events[3].clone()]
        );
    }

    #[test]
    fn unconsumed_samples_cannot_be_reclaimed_for_admission() {
        let mut fixture = Fixture::with_max_files("unconsumed", false, Some(14));
        let samples = fixture.files.ids("results").unwrap();
        fixture.open_window();
        assert_eq!(fixture.session.book.retained(), 7);
        let retry = fixture.session.manifest.limits.retry_window_ms as u64;
        let error = fixture.collect(retry).unwrap_err();
        assert!(error.contains("session total or pending capacity exhausted"));
        for id in samples {
            assert!(fixture.files.path(id, "results").unwrap().is_file());
        }
        assert_eq!(fixture.session.active_count(), 1);
        assert!(fixture.files.ids("consumed").unwrap().is_empty());
        let events = fixture
            .session
            .cancelled(&fixture.frame.captured_at, retry)
            .unwrap();
        fixture.files.publish_batch(&events, "results").unwrap();
        assert_eq!(events.last().unwrap().kind, EventKind::MonitorStopped);
    }

    #[test]
    fn invalid_consumed_bytes_block_retirement_and_admission() {
        let mut fixture = Fixture::new("invalid", true);
        let id = fixture.files.ids("consumed").unwrap()[0];
        let mut altered = fixture.files.read(id, "results").unwrap();
        altered.emitted_at = "2026-10-10T12:00:01Z".to_owned();
        std::fs::write(
            fixture.files.path(id, "consumed").unwrap(),
            crate::canonical_json::row_line(&altered).unwrap(),
        )
        .unwrap();
        fixture.consumed.clear();
        let mut admitted = false;
        let retry = fixture.session.manifest.limits.retry_window_ms as u64;
        let error = with_retired_consumed(
            &mut fixture.session,
            &mut fixture.files,
            &mut fixture.consumed,
            retry,
            |_, _| {
                admitted = true;
                Ok(())
            },
        )
        .unwrap_err();
        assert!(error.contains("consumption differs from original event"));
        assert!(!admitted);
        assert_eq!(fixture.session.book.retained(), 3);
        assert!(fixture.files.path(id, "results").unwrap().is_file());
    }
}
