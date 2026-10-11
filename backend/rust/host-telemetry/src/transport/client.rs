//! How does a caller wait finitely for ACK/result evidence and clean up only its known monitor PID?

use crate::Result;
use crate::contracts::events::*;
use crate::transport::files::FileTransport;
use crate::windows::reduce::incomplete;
use std::time::{Duration, Instant};

pub fn await_result(
    files: &mut FileTransport,
    command: Option<&HostEvent>,
) -> Result<serde_json::Value> {
    if let Some(command) = command {
        files.check_command(command)?;
    }
    let start = Instant::now();
    let timeout = if command.is_some() {
        files.manifest.limits.ack_timeout_ms
    } else {
        files.manifest.limits.readiness_timeout_ms
    };
    let mut seen = std::collections::HashSet::new();
    loop {
        let mut selected = None;
        for id in files.ids("results")? {
            if !seen.insert(id) {
                continue;
            }
            let event = files.read(id, "results")?;
            if event.reply_to.is_none()
                && let EventBody::Fault(fault) = &event.body
            {
                return Err(format!("monitor protocol fault: {:?}", fault.code));
            }
            let matches = match command {
                Some(command) => event.reply_to == Some(command.event_id),
                None => event.kind == EventKind::MonitorReady,
            };
            if matches {
                if let EventBody::Fault(fault) = &event.body {
                    return Err(format!("monitor protocol fault: {:?}", fault.code));
                }
                if selected.is_none() {
                    selected = Some(event);
                }
            }
        }
        // A matching success is not final until every already-listed result was validated.
        if let Some(event) = selected {
            if let Some(command) = command {
                let expected = match command.kind {
                    EventKind::WorkerRegister => EventKind::WorkerRegistered,
                    EventKind::WindowBegin => EventKind::WindowBegun,
                    EventKind::WindowEnd | EventKind::WindowAbort => EventKind::WindowResult,
                    EventKind::MonitorStop => EventKind::MonitorStopped,
                    _ => return Err("unsupported ACK command".to_owned()),
                };
                crate::contracts::host::require(
                    event.kind == expected,
                    "reply kind contradicts triggering command",
                )?;
                let expected_window = match &command.body {
                    EventBody::Window(v) => Some(v),
                    EventBody::Abort(v) => Some(&v.window),
                    _ => None,
                };
                let actual_window = match &event.body {
                    EventBody::Begun(v) => Some(&v.window),
                    EventBody::WindowResult(v) => Some(&v.window),
                    _ => None,
                };
                crate::contracts::host::require(
                    expected_window == actual_window,
                    "reply names another window/target",
                )?;
                if let (EventBody::Worker(a), EventBody::Worker(b)) = (&command.body, &event.body) {
                    crate::contracts::host::require(
                        a == b,
                        "registration ACK names another worker",
                    )?;
                }
            }
            files.consume(&event)?;
            if let Some(command) = command {
                files.consume(command)?;
            }
            return serde_json::to_value(event).map_err(|e| e.to_string());
        }
        if start.elapsed() >= Duration::from_millis(timeout as u64) {
            if let Some(command) = command {
                let window = match &command.body {
                    EventBody::Window(v) => Some(v),
                    EventBody::Abort(v) => Some(&v.window),
                    _ => None,
                };
                if let Some(window) = window {
                    return serde_json::to_value(incomplete(
                        window.clone(),
                        None,
                        files.manifest.controls.memory_profiling_enabled,
                        UnavailableReason::TimedOut,
                    ))
                    .map_err(|e| e.to_string());
                }
            }
            return Err(
                "monitor unavailable: timed_out awaiting readiness or registration/shutdown ACK"
                    .to_owned(),
            );
        }
        std::thread::sleep(Duration::from_millis(files.manifest.limits.poll_ms as u64));
    }
}

#[cfg(target_os = "linux")]
pub fn cleanup_known_pid(
    target: &ProcessTarget,
    proc_root: &std::path::Path,
    limits: &HostEventLimits,
    capture: &HostCaptureLimits,
) -> Result<()> {
    use std::os::fd::{AsRawFd, FromRawFd, OwnedFd};
    crate::contracts::host::require(
        std::fs::canonicalize(proc_root).map_err(|e| e.to_string())?
            == std::fs::canonicalize("/proc").map_err(|e| e.to_string())?,
        "cleanup requires genuine live procfs, not recorded/generated PID evidence",
    )?;
    let sampler = crate::sampling::process::ProcessSampler::new(
        proc_root,
        capture.max_proc_text_bytes as usize,
        capture.max_processes as usize,
    )?;
    let verify = || -> Result<bool> {
        let identity = sampler.identity(target.pid);
        match identity.get() {
            Ok(actual) if actual == target => Ok(true),
            Ok(_) => Err("cleanup refuses reused monitor PID".to_owned()),
            Err(UnavailableReason::PidExited) => Ok(false),
            Err(e) => Err(format!("cleanup identity unavailable: {e:?}")),
        }
    };
    if !verify()? {
        return Ok(());
    }
    let pid = i32::try_from(target.pid).map_err(|e| e.to_string())?;
    let descriptor = unsafe { libc::syscall(libc::SYS_pidfd_open, pid, 0) };
    if descriptor < 0 {
        return Err(std::io::Error::last_os_error().to_string());
    }
    let descriptor = unsafe { OwnedFd::from_raw_fd(descriptor as i32) };
    if !verify()? {
        return Ok(());
    }
    let signal = |signal| unsafe {
        libc::syscall(
            libc::SYS_pidfd_send_signal,
            descriptor.as_raw_fd(),
            signal,
            std::ptr::null::<libc::siginfo_t>(),
            0,
        )
    };
    // The pinned task cannot become a different task if its numeric PID is reused.
    if signal(libc::SIGTERM) != 0 {
        return Err(std::io::Error::last_os_error().to_string());
    }
    let start = Instant::now();
    while start.elapsed() < Duration::from_millis(limits.drain_timeout_ms as u64) {
        if !verify()? {
            return Ok(());
        }
        std::thread::sleep(Duration::from_millis(limits.poll_ms as u64));
    }
    if verify()? && signal(libc::SIGKILL) != 0 {
        return Err(std::io::Error::last_os_error().to_string());
    }
    Ok(())
}
#[cfg(not(target_os = "linux"))]
pub fn cleanup_known_pid(
    _target: &ProcessTarget,
    _proc_root: &std::path::Path,
    _limits: &HostEventLimits,
    _capture: &HostCaptureLimits,
) -> Result<()> {
    Err("cleanup unavailable: procfs PID/start-tick identity requires Linux".to_owned())
}
