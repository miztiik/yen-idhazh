//! Do compiled native monitors honor ACKs, overlap, shutdown and real Linux process cancellation?
#[path = "support/resources.rs"]
mod resources;
use idhazh_host_telemetry::{
    contracts::events::*, monitor::session::Session, sampling::capture::*, transport::files::*,
};
use std::{
    path::Path,
    process::{Child, Command},
    time::{Duration, Instant},
};

#[test]
fn overlap_ack_order_duplicate_and_shutdown_drain() {
    let mut m = resources::manifest();
    m.controls.resource_interval_seconds = 1.0;
    let frames = resources::frames();
    let mut session = Session::new(m).unwrap();
    session.ready(&frames[0].captured_at, 0).unwrap();
    let early = resources::command(EventKind::WindowBegin, 0, 2);
    assert!(session.handle(&early, &frames[0], 0).is_err());
    for worker in 0..2 {
        session
            .handle(
                &resources::command(EventKind::WorkerRegister, worker, 1),
                &frames[0],
                0,
            )
            .unwrap();
        let command = resources::command(EventKind::WindowBegin, worker, 2);
        let first = session
            .handle(&command, &frames[worker], worker as u64 * 1000)
            .unwrap();
        let repeated = session
            .handle(&command, &frames[worker], worker as u64 * 1000)
            .unwrap();
        assert_eq!(first, repeated);
    }
    assert_eq!(session.active_count(), 2);
    session.tick(&frames[2], 2000).unwrap();
    let result = session
        .handle(
            &resources::command(EventKind::WindowEnd, 0, 3),
            &frames[3],
            3000,
        )
        .unwrap();
    assert_eq!(result[0].kind, EventKind::WindowResult);
    let stop = resources::command(EventKind::MonitorStop, 0, 99);
    let result = session.handle(&stop, &frames[3], 3000).unwrap();
    assert_eq!(result.len(), 2);
    assert_eq!(result[0].kind, EventKind::WindowResult);
    assert_eq!(result[1].kind, EventKind::MonitorStopped);
    assert_eq!(session.active_count(), 0);
    assert!(session.stopped);
}
#[test]
fn foreign_start_abort_and_capacity_faults_leave_state_unchanged() {
    let mut m = resources::manifest();
    m.limits.max_concurrent_windows = 1;
    let frame = resources::frames().remove(0);
    let mut session = Session::new(m).unwrap();
    session.ready(&frame.captured_at, 0).unwrap();
    for worker in 0..2 {
        session
            .handle(
                &resources::command(EventKind::WorkerRegister, worker, 1),
                &frame,
                0,
            )
            .unwrap();
    }
    let mut foreign = resources::command(EventKind::WindowBegin, 0, 2);
    if let EventBody::Window(body) = &mut foreign.body {
        body.target.start_ticks += 1;
    }
    assert_eq!(
        session.handle(&foreign, &frame, 1).unwrap_err().code,
        ProtocolFaultCode::Target
    );
    session
        .handle(&resources::command(EventKind::WindowBegin, 0, 2), &frame, 1)
        .unwrap();
    assert_eq!(
        session
            .handle(&resources::command(EventKind::WindowBegin, 1, 2), &frame, 1)
            .unwrap_err()
            .code,
        ProtocolFaultCode::Bounds
    );
    assert_eq!(session.active_count(), 1);
    let result = session
        .handle(&resources::command(EventKind::WindowAbort, 0, 3), &frame, 2)
        .unwrap();
    let EventBody::WindowResult(body) = &result[0].body else {
        panic!()
    };
    assert_eq!(body.status, WindowStatus::Incomplete);
}

#[test]
fn memory_off_end_reuse_is_a_protocol_fault_and_cancel_has_stopped_evidence() {
    let mut m = resources::manifest();
    m.controls.memory_profiling_enabled = false;
    let mut frames = resources::frames();
    let mut session = Session::new(m).unwrap();
    session.ready(&frames[0].captured_at, 0).unwrap();
    let mut register = resources::command(EventKind::WorkerRegister, 0, 1);
    if let EventBody::Worker(body) = &mut register.body {
        body.memory_profiling_enabled = false;
    }
    session.handle(&register, &frames[0], 0).unwrap();
    session
        .handle(
            &resources::command(EventKind::WindowBegin, 0, 2),
            &frames[0],
            0,
        )
        .unwrap();
    frames[3].processes[0].stat_after.value = Some(
        frames[3].processes[0]
            .stat_after
            .value
            .as_ref()
            .unwrap()
            .replace(" 800\n", " 801\n"),
    );
    assert_eq!(
        session
            .handle(
                &resources::command(EventKind::WindowEnd, 0, 3),
                &frames[3],
                3000
            )
            .unwrap_err()
            .code,
        ProtocolFaultCode::Target
    );
    assert_eq!(session.active_count(), 1);
    let events = session.cancelled(&frames[3].captured_at, 3000).unwrap();
    assert_eq!(events.len(), 2);
    let EventBody::WindowResult(body) = &events[0].body else {
        panic!()
    };
    assert_eq!(body.status, WindowStatus::Incomplete);
    assert_eq!(events[1].kind, EventKind::MonitorStopped);
}

#[test]
fn compiled_binary_replays_real_files_and_retains_closed_events_and_legacy_bytes() {
    let root = resources::workspace("native-replay");
    let mut m = resources::manifest();
    m.controls.resource_interval_seconds = 1.0;
    m.named_inputs = vec![NamedHostInput {
        name: "resource".to_owned(),
        source: CaptureSource::CpuStat,
        relative_path: "captures/resource.json".to_owned(),
    }];
    resources::setup(&root, &m);
    let mut actions = Vec::new();
    for worker in 0..2 {
        actions.push(ReplayAction {
            frame: 0,
            at_ms: 0,
            event: Some(resources::command(EventKind::WorkerRegister, worker, 1)),
        });
        actions.push(ReplayAction {
            frame: 0,
            at_ms: 0,
            event: Some(resources::command(EventKind::WindowBegin, worker, 2)),
        });
    }
    actions.extend([
        ReplayAction {
            frame: 1,
            at_ms: 1000,
            event: None,
        },
        ReplayAction {
            frame: 2,
            at_ms: 2000,
            event: None,
        },
    ]);
    for worker in 0..2 {
        actions.push(ReplayAction {
            frame: 3,
            at_ms: 3000,
            event: Some(resources::command(EventKind::WindowEnd, worker, 3)),
        });
    }
    actions.push(ReplayAction {
        frame: 3,
        at_ms: 3000,
        event: Some(resources::command(EventKind::MonitorStop, 0, 99)),
    });
    let replay = ResourceReplay {
        version: m.version.clone(),
        frames: resources::frames(),
        actions,
    };
    let input = root
        .join(&m.event_root)
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
    let files = FileTransport::new(&root, m).unwrap();
    for event in &events {
        assert_eq!(
            decode_event(&std::fs::read(files.path(event.event_id, "results").unwrap()).unwrap())
                .unwrap(),
            *event
        );
    }
    assert_eq!(
        events
            .iter()
            .filter(|v| v.kind == EventKind::WindowResult)
            .count(),
        2
    );
    assert!(root.join("artifacts").join("rss-samples.jsonl").is_file());
    assert_eq!(
        std::fs::read_to_string(root.join("artifacts").join("server-rss-samples.jsonl"))
            .unwrap()
            .lines()
            .count(),
        4
    );
    std::fs::write(root.join("native-proof.json"), &result.stdout).unwrap();
}

#[test]
fn job_sampling_stops_at_target_exit_without_losing_window_cpu_and_load() {
    let root = resources::workspace("job-exit");
    let mut m = resources::manifest();
    m.named_inputs = vec![NamedHostInput {
        name: "resource".to_owned(),
        source: CaptureSource::CpuStat,
        relative_path: "captures/resource.json".to_owned(),
    }];
    resources::setup(&root, &m);
    let mut frames = resources::frames();
    frames[3].processes.remove(0);
    let replay = ResourceReplay {
        version: m.version.clone(),
        frames,
        actions: vec![
            ReplayAction {
                frame: 0,
                at_ms: 0,
                event: Some(resources::command(EventKind::WorkerRegister, 0, 1)),
            },
            ReplayAction {
                frame: 0,
                at_ms: 0,
                event: Some(resources::command(EventKind::WindowBegin, 0, 2)),
            },
            ReplayAction {
                frame: 3,
                at_ms: 16000,
                event: Some(resources::command(EventKind::WindowEnd, 0, 3)),
            },
            ReplayAction {
                frame: 3,
                at_ms: 16000,
                event: Some(resources::command(EventKind::MonitorStop, 0, 99)),
            },
        ],
    };
    let input = root
        .join(&m.event_root)
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
    assert!(String::from_utf8_lossy(&result.stderr).contains("\"reason\":\"pid_exited\""));
    assert_eq!(
        std::fs::read_to_string(root.join("artifacts").join(LEGACY_JOB_SAMPLE_FILENAME))
            .unwrap()
            .lines()
            .count(),
        1
    );
    let events: Vec<HostEvent> = serde_json::from_slice(&result.stdout).unwrap();
    let EventBody::WindowResult(body) = &events
        .iter()
        .find(|v| v.kind == EventKind::WindowResult)
        .unwrap()
        .body
    else {
        panic!()
    };
    assert_eq!(body.status, WindowStatus::Complete);
    assert_eq!(body.cells.cpu_busy_pct, Some(50.0));
    assert_eq!(body.cells.load_1m, Some(1.25));
    assert_eq!(body.cells.llama_rss_bytes, None);
}

struct OwnedChild(Child);
impl Drop for OwnedChild {
    fn drop(&mut self) {
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}
fn start_monitor(root: &Path, proc_root: &Path, cgroup_root: &Path) -> OwnedChild {
    OwnedChild(
        Command::new(env!("CARGO_BIN_EXE_idhazh-host-telemetry"))
            .args([
                "monitor",
                "--workspace",
                root.to_str().unwrap(),
                "--manifest",
                "manifest.json",
                "--config",
                "config.json",
                "--proc-root",
                proc_root.to_str().unwrap(),
                "--cgroup-root",
                cgroup_root.to_str().unwrap(),
                "--artifact-root",
                "artifacts",
            ])
            .stderr(std::fs::File::create(root.join("monitor.log")).unwrap())
            .spawn()
            .unwrap(),
    )
}
fn wait_kind(files: &mut FileTransport, kind: EventKind) -> HostEvent {
    let start = Instant::now();
    let mut seen = std::collections::HashSet::new();
    while start.elapsed() < Duration::from_secs(10) {
        for id in files.ids("results").unwrap() {
            if !seen.insert(id) {
                continue;
            }
            let event = match files.read(id, "results") {
                Ok(event) => event,
                Err(error)
                    if error.contains("No such file") || error.contains("cannot find the file") =>
                {
                    continue;
                }
                Err(error) => panic!("failed to read result evidence: {error}"),
            };
            if event.kind == kind {
                return event;
            }
        }
        std::thread::sleep(Duration::from_millis(5));
    }
    panic!("missing {kind:?}");
}

#[test]
fn real_monitor_keeps_twelve_file_shutdown_evidence_after_consumption_refusal() {
    let root = resources::workspace("live-consume-stop");
    let mut m = resources::manifest();
    m.workers.truncate(1);
    m.windows.truncate(1);
    m.limits.max_concurrent_windows = 1;
    m.limits.max_files = 12;
    m.limits.retry_window_ms = 60_000;
    m.limits.poll_ms = 5;
    m.controls.memory_profiling_enabled = false;
    resources::setup(&root, &m);
    let proc = root.join("proc");
    let cgroup = root.join("cgroup");
    resources::write_frame(&proc, &resources::frames()[0], false);
    std::fs::create_dir_all(&cgroup).unwrap();
    let boot = proc.join("sys").join("kernel").join("random");
    std::fs::create_dir_all(&boot).unwrap();
    std::fs::write(boot.join("boot_id"), m.boot_id.to_string()).unwrap();
    let mut files = FileTransport::new(&root, m.clone()).unwrap();
    let mut child = start_monitor(&root, &proc, &cgroup);
    let ready = wait_kind(&mut files, EventKind::MonitorReady);
    files.consume(&ready).unwrap();
    let mut register = resources::command(EventKind::WorkerRegister, 0, 1);
    if let EventBody::Worker(body) = &mut register.body {
        body.memory_profiling_enabled = false;
    }
    files.publish(&register, "inbox").unwrap();
    let registered = wait_kind(&mut files, EventKind::WorkerRegistered);
    files.consume(&registered).unwrap();
    files.consume(&register).unwrap();
    let begin = resources::command(EventKind::WindowBegin, 0, 2);
    files.publish(&begin, "inbox").unwrap();
    let begun = wait_kind(&mut files, EventKind::WindowBegun);
    for event in [&begun, &begin] {
        assert!(files.consume(event).unwrap_err().contains("capacity"));
        assert!(!files.path(event.event_id, "consumed").unwrap().exists());
    }
    let stop = resources::command(EventKind::MonitorStop, 0, 99);
    files.publish(&stop, "inbox").unwrap();
    let stopped = wait_kind(&mut files, EventKind::MonitorStopped);
    assert_eq!(stopped.reply_to, Some(stop.event_id));
    let EventBody::Stopped(body) = &stopped.body else {
        panic!()
    };
    assert!(body.drained);
    assert_eq!(
        body.aborted_window_ids,
        vec![resources::window(0).window_id]
    );
    let result = wait_kind(&mut files, EventKind::WindowResult);
    let EventBody::WindowResult(body) = result.body else {
        panic!()
    };
    assert_eq!(body.status, WindowStatus::Incomplete);
    assert_eq!(files.ids("inbox").unwrap().len(), 3);
    assert_eq!(files.ids("results").unwrap().len(), 5);
    assert_eq!(files.ids("consumed").unwrap().len(), 3);
    assert!(child.0.wait().unwrap().success());
    assert!(!root.join("artifacts").exists());
}

#[test]
fn too_small_ordinary_capacity_emits_fault_and_stopped_instead_of_partial_shutdown() {
    let root = resources::workspace("live-ordinary-full");
    let mut m = resources::manifest();
    m.workers.truncate(1);
    m.windows.truncate(1);
    m.limits.max_concurrent_windows = 1;
    m.limits.max_files = 6;
    m.limits.poll_ms = 5;
    m.controls.memory_profiling_enabled = false;
    resources::setup(&root, &m);
    let proc = root.join("proc");
    let cgroup = root.join("cgroup");
    resources::write_frame(&proc, &resources::frames()[0], false);
    std::fs::create_dir_all(&cgroup).unwrap();
    let boot = proc.join("sys").join("kernel").join("random");
    std::fs::create_dir_all(&boot).unwrap();
    std::fs::write(boot.join("boot_id"), m.boot_id.to_string()).unwrap();
    let mut files = FileTransport::new(&root, m).unwrap();
    let mut child = start_monitor(&root, &proc, &cgroup);
    let ready = wait_kind(&mut files, EventKind::MonitorReady);
    let mut register = resources::command(EventKind::WorkerRegister, 0, 1);
    if let EventBody::Worker(body) = &mut register.body {
        body.memory_profiling_enabled = false;
    }
    files.publish(&register, "inbox").unwrap();
    let fault = wait_kind(&mut files, EventKind::ProtocolFault);
    assert_eq!(fault.reply_to, Some(register.event_id));
    let EventBody::Fault(body) = fault.body else {
        panic!()
    };
    assert_eq!(body.code, ProtocolFaultCode::Bounds);
    let stopped = wait_kind(&mut files, EventKind::MonitorStopped);
    assert_eq!(stopped.reply_to, Some(ready.event_id));
    let EventBody::Stopped(body) = stopped.body else {
        panic!()
    };
    assert!(body.drained);
    assert!(body.aborted_window_ids.is_empty());
    assert!(!child.0.wait().unwrap().success());
    assert_eq!(files.ids("results").unwrap().len(), 3);
}
#[test]
fn actual_file_monitor_completes_with_memory_denied_cpu_identity_and_heartbeat_live() {
    let root = resources::workspace("live-off");
    let mut m = resources::manifest();
    m.controls.memory_profiling_enabled = false;
    m.controls.resource_interval_seconds = 0.01;
    m.limits.poll_ms = 5;
    resources::setup(&root, &m);
    let proc = root.join("proc");
    let cgroup = root.join("cgroup");
    resources::write_frame(&proc, &resources::frames()[0], false);
    std::fs::create_dir_all(&cgroup).unwrap();
    for name in ["memory.current", "memory.peak"] {
        std::fs::create_dir(cgroup.join(name)).unwrap();
    }
    #[cfg(target_os = "linux")]
    {
        use std::os::unix::ffi::OsStrExt;
        let mut denied = vec![
            proc.join("meminfo"),
            cgroup.join("memory.current"),
            cgroup.join("memory.peak"),
        ];
        denied.extend(
            resources::frames()[0]
                .processes
                .iter()
                .map(|v| proc.join(v.target.pid.to_string()).join("status")),
        );
        for path in denied {
            std::fs::remove_dir(&path).unwrap();
            let name = std::ffi::CString::new(path.as_os_str().as_bytes()).unwrap();
            // A single memory-specific open would block this real monitor until the test deadline.
            assert_eq!(unsafe { libc::mkfifo(name.as_ptr(), 0o600) }, 0);
        }
    }
    let boot = proc.join("sys").join("kernel").join("random");
    std::fs::create_dir_all(&boot).unwrap();
    std::fs::write(boot.join("boot_id"), m.boot_id.to_string()).unwrap();
    let mut files = FileTransport::new(&root, m).unwrap();
    let mut child = start_monitor(&root, &proc, &cgroup);
    wait_kind(&mut files, EventKind::MonitorReady);
    let mut register = resources::command(EventKind::WorkerRegister, 0, 1);
    if let EventBody::Worker(body) = &mut register.body {
        body.memory_profiling_enabled = false;
    }
    files.publish(&register, "inbox").unwrap();
    wait_kind(&mut files, EventKind::WorkerRegistered);
    files
        .publish(&resources::command(EventKind::WindowBegin, 0, 2), "inbox")
        .unwrap();
    wait_kind(&mut files, EventKind::WindowBegun);
    let closing = &resources::frames()[3];
    std::fs::write(proc.join("stat"), closing.proc_stat.value.as_ref().unwrap()).unwrap();
    std::fs::write(
        proc.join("loadavg"),
        closing.loadavg.value.as_ref().unwrap(),
    )
    .unwrap();
    for process in &closing.processes {
        std::fs::write(
            proc.join(process.target.pid.to_string()).join("stat"),
            process.stat_after.value.as_ref().unwrap(),
        )
        .unwrap();
    }
    std::thread::sleep(Duration::from_millis(30));
    files
        .publish(&resources::command(EventKind::WindowEnd, 0, 3), "inbox")
        .unwrap();
    let result = wait_kind(&mut files, EventKind::WindowResult);
    let EventBody::WindowResult(body) = result.body else {
        panic!()
    };
    assert_eq!(body.cells.cpu_busy_pct, Some(50.0));
    assert_eq!(body.cells.load_1m, Some(1.25));
    assert_eq!(body.cells.python_rss_bytes, None);
    assert!(
        body.unavailable
            .iter()
            .all(|v| v.reason == UnavailableReason::Disabled)
    );
    files
        .publish(&resources::command(EventKind::MonitorStop, 0, 99), "inbox")
        .unwrap();
    wait_kind(&mut files, EventKind::MonitorStopped);
    assert!(child.0.wait().unwrap().success());
    assert!(!root.join("artifacts").exists());
    assert!(
        std::fs::read_to_string(root.join("monitor.log"))
            .unwrap()
            .contains("heartbeat")
    );
}

#[test]
fn live_job_target_reuse_emits_a_fault_and_drains_the_open_window() {
    let root = resources::workspace("live-job-reuse");
    let mut m = resources::manifest();
    m.controls.job_sample_interval_seconds = 5.0;
    m.limits.poll_ms = 5;
    resources::setup(&root, &m);
    let proc = root.join("proc");
    let cgroup = root.join("cgroup");
    let frame = resources::frames().remove(0);
    resources::write_frame(&proc, &frame, true);
    std::fs::create_dir_all(&cgroup).unwrap();
    let boot = proc.join("sys").join("kernel").join("random");
    std::fs::create_dir_all(&boot).unwrap();
    std::fs::write(boot.join("boot_id"), m.boot_id.to_string()).unwrap();
    let mut files = FileTransport::new(&root, m).unwrap();
    let mut child = start_monitor(&root, &proc, &cgroup);
    wait_kind(&mut files, EventKind::MonitorReady);
    files
        .publish(
            &resources::command(EventKind::WorkerRegister, 0, 1),
            "inbox",
        )
        .unwrap();
    wait_kind(&mut files, EventKind::WorkerRegistered);
    files
        .publish(&resources::command(EventKind::WindowBegin, 0, 2), "inbox")
        .unwrap();
    wait_kind(&mut files, EventKind::WindowBegun);
    std::fs::write(
        proc.join("100").join("stat"),
        frame.processes[0]
            .stat_before
            .value
            .as_ref()
            .unwrap()
            .replace(" 800\n", " 801\n"),
    )
    .unwrap();
    let fault = wait_kind(&mut files, EventKind::ProtocolFault);
    let EventBody::Fault(body) = fault.body else {
        panic!()
    };
    assert_eq!(body.code, ProtocolFaultCode::Target);
    let window = wait_kind(&mut files, EventKind::WindowResult);
    let EventBody::WindowResult(body) = window.body else {
        panic!()
    };
    assert_eq!(body.status, WindowStatus::Incomplete);
    wait_kind(&mut files, EventKind::MonitorStopped);
    assert!(!child.0.wait().unwrap().success());
    let end = resources::command(EventKind::WindowEnd, 0, 3);
    let error =
        idhazh_host_telemetry::transport::client::await_result(&mut files, Some(&end)).unwrap_err();
    assert!(error.contains("protocol fault: Target"));
}

#[cfg(target_os = "linux")]
#[test]
fn pidfd_cleanup_refuses_foreign_start_and_terminates_only_the_owned_task() {
    use idhazh_host_telemetry::{
        sampling::process::ProcessSampler, transport::client::cleanup_known_pid,
    };
    let mut child = OwnedChild(
        Command::new("python3")
            .args(["-c", "import time; time.sleep(30)"])
            .spawn()
            .unwrap(),
    );
    let m = resources::manifest();
    let sampler = ProcessSampler::new(Path::new("/proc"), 262144, 256).unwrap();
    let target = sampler.identity(child.0.id() as i64).value.unwrap();
    let mut foreign = target.clone();
    foreign.start_ticks += 1;
    assert!(cleanup_known_pid(&foreign, Path::new("/proc"), &m.limits, &m.capture_limits).is_err());
    assert!(child.0.try_wait().unwrap().is_none());
    cleanup_known_pid(&target, Path::new("/proc"), &m.limits, &m.capture_limits).unwrap();
    child.0.wait().unwrap();
}

#[cfg(target_os = "linux")]
#[test]
fn real_linux_python_exit_and_signal_cancellation_retains_incomplete_window() {
    use idhazh_host_telemetry::sampling::process::ProcessSampler;
    let root = resources::workspace("linux-cancel");
    let mut python = OwnedChild(
        Command::new("python3")
            .args(["-c", "import time; time.sleep(30)"])
            .spawn()
            .unwrap(),
    );
    let sampler = ProcessSampler::new(Path::new("/proc"), 262144, 256).unwrap();
    let target = sampler.identity(python.0.id() as i64).value.unwrap();
    let actual = sampler.sample(&target, true, true);
    assert!(actual.rss.value.is_some());
    let mut m = resources::manifest();
    m.workers.truncate(1);
    m.windows.truncate(1);
    m.workers[0].target = target.clone();
    m.workers[0].server = None;
    m.cpu_target = Some(target.clone());
    m.cpu_target_role = TargetRole::PythonWorker;
    m.controls.memory_profiling_enabled = false;
    m.limits.poll_ms = 5;
    m.boot_id = uuid::Uuid::parse_str(
        std::fs::read_to_string("/proc/sys/kernel/random/boot_id")
            .unwrap()
            .trim(),
    )
    .unwrap();
    resources::setup(&root, &m);
    let mut files = FileTransport::new(&root, m).unwrap();
    let mut child = start_monitor(&root, Path::new("/proc"), Path::new("/sys/fs/cgroup"));
    wait_kind(&mut files, EventKind::MonitorReady);
    let mut command = resources::command(EventKind::WorkerRegister, 0, 1);
    if let EventBody::Worker(body) = &mut command.body {
        body.target = target.clone();
        body.server = None;
        body.memory_profiling_enabled = false;
    }
    files.publish(&command, "inbox").unwrap();
    wait_kind(&mut files, EventKind::WorkerRegistered);
    let mut begin = resources::command(EventKind::WindowBegin, 0, 2);
    if let EventBody::Window(body) = &mut begin.body {
        body.target = target.clone();
        body.server = None;
    }
    files.publish(&begin, "inbox").unwrap();
    wait_kind(&mut files, EventKind::WindowBegun);
    assert_eq!(unsafe { libc::kill(child.0.id() as i32, libc::SIGTERM) }, 0);
    assert!(child.0.wait().unwrap().success());
    let event = wait_kind(&mut files, EventKind::WindowResult);
    let EventBody::WindowResult(body) = event.body else {
        panic!()
    };
    assert_eq!(body.status, WindowStatus::Incomplete);
    python.0.kill().unwrap();
    python.0.wait().unwrap();
    assert_eq!(
        sampler.identity(target.pid).reason,
        Some(UnavailableReason::PidExited)
    );
}

#[test]
fn actual_live_memory_on_monitor_exports_legacy_files_and_endpoint_window() {
    let root = resources::workspace("live-on");
    let mut m = resources::manifest();
    m.limits.poll_ms = 5;
    resources::setup(&root, &m);
    let proc = root.join("proc");
    let cgroup = root.join("cgroup");
    let frames = resources::frames();
    resources::write_frame(&proc, &frames[0], true);
    std::fs::create_dir_all(&cgroup).unwrap();
    std::fs::write(cgroup.join("memory.current"), "123456\n").unwrap();
    std::fs::write(cgroup.join("memory.peak"), "234567\n").unwrap();
    let boot = proc.join("sys").join("kernel").join("random");
    std::fs::create_dir_all(&boot).unwrap();
    std::fs::write(boot.join("boot_id"), m.boot_id.to_string()).unwrap();
    let mut files = FileTransport::new(&root, m).unwrap();
    let mut child = start_monitor(&root, &proc, &cgroup);
    wait_kind(&mut files, EventKind::MonitorReady);
    let sample = wait_kind(&mut files, EventKind::JobSample);
    let EventBody::Sample(body) = sample.body else {
        panic!()
    };
    assert_eq!(body.record.python_procs, 2);
    assert_eq!(body.record.python_vmrss_kb, 250);
    files
        .publish(
            &resources::command(EventKind::WorkerRegister, 0, 1),
            "inbox",
        )
        .unwrap();
    wait_kind(&mut files, EventKind::WorkerRegistered);
    files
        .publish(&resources::command(EventKind::WindowBegin, 0, 2), "inbox")
        .unwrap();
    wait_kind(&mut files, EventKind::WindowBegun);
    resources::write_frame(&proc, &frames[3], true);
    files
        .publish(&resources::command(EventKind::WindowEnd, 0, 3), "inbox")
        .unwrap();
    let event = wait_kind(&mut files, EventKind::WindowResult);
    let EventBody::WindowResult(body) = event.body else {
        panic!()
    };
    assert_eq!(body.cells.cpu_busy_pct, Some(50.0));
    assert_eq!(body.cells.python_rss_bytes, Some(300 * 1024));
    files
        .publish(&resources::command(EventKind::MonitorStop, 0, 99), "inbox")
        .unwrap();
    wait_kind(&mut files, EventKind::MonitorStopped);
    assert!(child.0.wait().unwrap().success());
    let sample: LegacyJobSample = serde_json::from_slice(
        &std::fs::read(root.join("artifacts").join(LEGACY_JOB_SAMPLE_FILENAME)).unwrap(),
    )
    .unwrap();
    assert_eq!(sample.python_procs, 2);
    assert_eq!(
        std::fs::read_to_string(root.join("artifacts").join("cgroup-memory-peak.txt")).unwrap(),
        "234567\n"
    );
}
