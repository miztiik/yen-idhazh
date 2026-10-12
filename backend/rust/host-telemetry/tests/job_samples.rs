//! Do emitted native artifacts preserve the Python population, legacy units and runtime status representation?
#[path = "support/resources.rs"]
mod resources;
use idhazh_host_telemetry::{
    contracts::events::*,
    monitor::session::Session,
    probe_inputs::files::Reading,
    producers::job_samples::*,
    sampling::capture::{ReplayAction, ResourceReplay},
    transport::files::FileTransport,
};
use std::process::Command;

#[test]
fn population_is_all_readable_python_not_rust_or_selected_subtree() {
    let mut frame = resources::frames().remove(0);
    let mut unrelated = frame.population.value.as_ref().unwrap()[0].clone();
    unrelated.target.pid = 400;
    unrelated.stat_before.value = Some(
        unrelated
            .stat_before
            .value
            .as_ref()
            .unwrap()
            .replacen("200 ", "400 ", 1),
    );
    unrelated.stat_after = unrelated.stat_before.clone();
    unrelated.status.value = Some("VmRSS: 100 kB\nVmHWM: 120 kB\n".to_owned());
    let mut rust = unrelated.clone();
    rust.comm.value = Some("idhazh-host-telemetry".to_owned());
    frame
        .population
        .value
        .as_mut()
        .unwrap()
        .extend([unrelated, rust]);
    let (record, rows) = sample(&frame, Some(&frame.processes[0].target), true)
        .unwrap()
        .unwrap();
    assert_eq!(record.python_procs, 3);
    assert_eq!(record.python_vmrss_kb, 350);
    assert_eq!(record.python_vmhwm_kb, 420);
    assert_eq!(record.llama_vmrss_kb, Some(400));
    assert_eq!(rows[0].args.as_deref(), Some("-u -m idhazh"));
    assert!(
        !serde_json::to_string(&rows)
            .unwrap()
            .contains("secret-not-exported")
    );
}
#[test]
fn artifacts_are_actual_plain_records_and_memory_off_creates_nothing() {
    let root = resources::workspace("artifacts");
    let m = resources::manifest();
    let frame = resources::frames().remove(0);
    assert!(
        Artifacts::create(&root, "off", &m.limits, false)
            .unwrap()
            .is_none()
    );
    assert!(!root.join("off").exists());
    assert!(sample(&frame, None, false).unwrap().is_none());
    let mut artifacts = Artifacts::create(&root, "on", &m.limits, true)
        .unwrap()
        .unwrap();
    let (record, rows) = sample(&frame, Some(&frame.processes[0].target), true)
        .unwrap()
        .unwrap();
    artifacts.write_sample(&record, &rows).unwrap();
    artifacts
        .write_runtime(&runtime_status(&frame, Some(&frame.processes[0].target), true).unwrap())
        .unwrap();
    artifacts.write_peak(&frame.cgroup_peak).unwrap();
    let raw = std::fs::read(root.join("on").join(LEGACY_JOB_SAMPLE_FILENAME)).unwrap();
    assert_eq!(
        serde_json::from_slice::<LegacyJobSample>(&raw).unwrap(),
        record
    );
    assert!(!String::from_utf8(raw).unwrap().contains("event_id"));
    assert_eq!(
        std::fs::read_to_string(root.join("on").join(RUNTIME_PEAK_FILENAME)).unwrap(),
        "234567\n"
    );
}
#[test]
fn capacity_and_missing_population_never_publish_a_partial_sum() {
    let root = resources::workspace("artifact-caps");
    let mut m = resources::manifest();
    m.limits.max_session_events = 1;
    let mut frame = resources::frames().remove(0);
    let (record, rows) = sample(&frame, None, true).unwrap().unwrap();
    let mut artifacts = Artifacts::create(&root, "cap", &m.limits, true)
        .unwrap()
        .unwrap();
    assert!(artifacts.write_sample(&record, &rows).is_err());
    assert_eq!(
        std::fs::metadata(root.join("cap").join(LEGACY_JOB_SAMPLE_FILENAME))
            .unwrap()
            .len(),
        0
    );
    frame.population = Reading::absent(UnavailableReason::IncompleteCoverage);
    assert!(sample(&frame, None, true).is_err());
}

#[test]
fn retirement_preserves_native_artifact_bytes_and_retry_identity() {
    let root = resources::workspace("sample-retirement");
    let manifest = resources::manifest();
    let frame = resources::frames().remove(0);
    let mut files = FileTransport::new(&root, manifest.clone()).unwrap();
    let mut session = Session::new(manifest.clone()).unwrap();
    let ready = session.ready(&frame.captured_at, 0).unwrap();
    files.publish(&ready, "results").unwrap();
    let mut artifacts = Artifacts::create(&root, "artifacts", &manifest.limits, true)
        .unwrap()
        .unwrap();
    let (record, rows) = sample(&frame, Some(&frame.processes[0].target), true)
        .unwrap()
        .unwrap();
    artifacts.write_sample(&record, &rows).unwrap();
    let mut events = Vec::new();
    for (kind, body) in [
        (
            EventKind::JobSample,
            EventBody::Sample(JobSampleBody { record }),
        ),
        (
            EventKind::ProcessRollcall,
            EventBody::Rollcall(ProcessRollcallBody { records: rows }),
        ),
    ] {
        let event = session
            .observation(kind, body, &frame.captured_at, 0)
            .unwrap();
        files.publish(&event, "results").unwrap();
        files.consume(&event).unwrap();
        assert_eq!(files.read(event.event_id, "consumed").unwrap(), event);
        assert_eq!(files.read(event.event_id, "results").unwrap(), event);
        session.book.consume(event.event_id).unwrap();
        events.push(event);
    }
    let paths = [LEGACY_JOB_SAMPLE_FILENAME, LEGACY_PROCESS_ROLLCALL_FILENAME]
        .map(|name| root.join("artifacts").join(name));
    let before = paths.each_ref().map(|path| std::fs::read(path).unwrap());
    let retry = manifest.limits.retry_window_ms as u64;
    assert!(session.retire(retry - 1).is_empty());
    let retired = session.retire(retry);
    assert_eq!(retired.len(), 2);
    assert!(events.iter().all(|event| retired.contains(&event.event_id)));
    files.remove_retired(&retired).unwrap();
    for (path, bytes) in paths.iter().zip(&before) {
        assert!(!bytes.is_empty());
        assert_eq!(std::fs::read(path).unwrap(), *bytes);
    }
    for event in &events {
        assert!(!files.path(event.event_id, "results").unwrap().exists());
        assert!(!files.path(event.event_id, "consumed").unwrap().exists());
        assert_eq!(
            session.book.check(event, retry).unwrap_err().code,
            ProtocolFaultCode::Retired
        );
        let mut conflict = event.clone();
        conflict.emitted_at = "2026-10-10T12:00:01Z".to_owned();
        assert_eq!(
            session.book.check(&conflict, retry).unwrap_err().code,
            ProtocolFaultCode::Duplicate
        );
    }
    assert_eq!(session.book.retained(), 1);
    assert_eq!(session.book.history_len(), 3);
    assert_eq!(session.book.total_events, 3);
    assert_eq!(files.total_events, 3);
    drop(artifacts);
    std::fs::remove_dir_all(root).unwrap();
}

#[test]
fn replay_retires_expired_samples_without_losing_artifacts_or_protected_evidence() {
    let root = resources::workspace("d5-replay-retirement");
    let mut manifest = resources::manifest();
    manifest.workers.truncate(1);
    manifest.windows.truncate(1);
    assert_eq!(manifest.pending_event_limit().unwrap(), 14);
    assert_eq!(manifest.limits.retry_window_ms, 5000);
    assert_eq!(manifest.limits.max_session_events, 128);
    let interval_ms = (manifest.controls.job_sample_interval_seconds * 1000.0).ceil() as u64;
    let retry_ms = manifest.limits.retry_window_ms as u64;
    assert!(interval_ms > retry_ms);
    manifest.named_inputs = vec![NamedHostInput {
        name: "resource".to_owned(),
        source: CaptureSource::CpuStat,
        relative_path: "captures/resource.json".to_owned(),
    }];
    resources::setup(&root, &manifest);

    let frames = resources::frames();
    let register = resources::command(EventKind::WorkerRegister, 0, 1);
    let begin = resources::command(EventKind::WindowBegin, 0, 2);
    let mut actions = vec![
        ReplayAction {
            frame: 0,
            at_ms: 0,
            event: Some(register.clone()),
        },
        ReplayAction {
            frame: 0,
            at_ms: 0,
            event: Some(begin.clone()),
        },
    ];
    for sample_index in 1..=9 {
        actions.push(ReplayAction {
            frame: 0,
            at_ms: sample_index * interval_ms,
            event: None,
        });
    }
    let protected_at = 9 * interval_ms + retry_ms + 1;
    actions.extend([
        ReplayAction {
            frame: 0,
            at_ms: protected_at,
            event: None,
        },
        ReplayAction {
            frame: 0,
            at_ms: protected_at,
            event: Some(resources::command(EventKind::MonitorStop, 0, 99)),
        },
    ]);
    let replay = ResourceReplay {
        version: manifest.version.clone(),
        frames: frames.clone(),
        actions,
    };
    let input = root
        .join(&manifest.event_root)
        .join("captures")
        .join("resource.json");
    std::fs::create_dir_all(input.parent().unwrap()).unwrap();
    std::fs::write(input, serde_json::to_vec(&replay).unwrap()).unwrap();

    let result = Command::new(env!("CARGO_BIN_EXE_idhazh-host-telemetry"))
        .args([
            "resource-replay",
            "--workspace",
            root.to_str().unwrap(),
            "--manifest",
            "manifest.json",
            "--config",
            "config.json",
            "--snapshot",
            "resource",
            "--artifact-root",
            "artifacts",
        ])
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );

    let events: Vec<HostEvent> = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(
        events.iter().map(|event| event.kind).collect::<Vec<_>>(),
        [
            EventKind::MonitorReady,
            EventKind::WorkerRegistered,
            EventKind::WindowBegun,
            EventKind::WindowResult,
            EventKind::MonitorStopped,
        ]
    );
    assert_eq!(events.len(), 5);
    let register_reply = events
        .iter()
        .find(|event| event.reply_to == Some(register.event_id))
        .unwrap();
    let begin_reply = events
        .iter()
        .find(|event| event.reply_to == Some(begin.event_id))
        .unwrap();
    let mut files = FileTransport::new(&root, manifest.clone()).unwrap();
    assert!(!files.path(register.event_id, "inbox").unwrap().exists());
    assert!(
        !files
            .path(register_reply.event_id, "results")
            .unwrap()
            .exists()
    );
    assert!(
        !files.path(register.event_id, "consumed").unwrap().exists()
            && !files
                .path(register_reply.event_id, "consumed")
                .unwrap()
                .exists()
    );
    assert!(
        files.path(begin.event_id, "inbox").unwrap().is_file(),
        "the active window command must remain protected past retry expiry"
    );
    assert!(
        files
            .path(begin_reply.event_id, "results")
            .unwrap()
            .is_file()
    );
    assert!(
        files.path(begin.event_id, "consumed").unwrap().is_file()
            && files
                .path(begin_reply.event_id, "consumed")
                .unwrap()
                .is_file()
    );
    assert!(
        files.path(events[0].event_id, "results").unwrap().is_file()
            && !files.path(events[0].event_id, "consumed").unwrap().exists(),
        "unconsumed readiness evidence must not be retired"
    );
    for id in files.ids("results").unwrap() {
        let event = files.read(id, "results").unwrap();
        assert!(!matches!(
            event.kind,
            EventKind::JobSample | EventKind::ProcessRollcall
        ));
    }

    let (expected_sample, expected_rollcall) =
        sample(&frames[0], manifest.workers[0].server.as_ref(), true)
            .unwrap()
            .unwrap();
    let artifact_root = root.join("artifacts");
    let samples = std::fs::read_to_string(artifact_root.join(LEGACY_JOB_SAMPLE_FILENAME)).unwrap();
    let samples = samples
        .lines()
        .map(|line| serde_json::from_str::<LegacyJobSample>(line).unwrap())
        .collect::<Vec<_>>();
    assert_eq!(samples.len(), 10);
    assert!(samples.iter().all(|sample| sample == &expected_sample));
    assert!(events.len() + 3 + samples.len() * 2 <= manifest.limits.max_session_events as usize);
    let rollcall =
        std::fs::read_to_string(artifact_root.join(LEGACY_PROCESS_ROLLCALL_FILENAME)).unwrap();
    let rollcall = rollcall
        .lines()
        .map(|line| serde_json::from_str::<LegacyProcessRollcall>(line).unwrap())
        .collect::<Vec<_>>();
    assert_eq!(rollcall.len(), 10 * expected_rollcall.len());
    assert_eq!(
        rollcall,
        expected_rollcall
            .into_iter()
            .cycle()
            .take(rollcall.len())
            .collect::<Vec<_>>()
    );
    assert!(
        std::fs::read_to_string(artifact_root.join(RUNTIME_STATUS_FILENAME))
            .unwrap()
            .lines()
            .count()
            >= samples.len()
    );
    assert_eq!(
        std::fs::read_to_string(artifact_root.join(RUNTIME_PEAK_FILENAME)).unwrap(),
        format!("{}\n", frames[0].cgroup_peak.value.as_ref().unwrap().trim())
    );
    std::fs::remove_dir_all(root).unwrap();
}
