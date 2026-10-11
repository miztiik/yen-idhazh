//! Which finite resource captures and real generated proc files support resource tests?
#![allow(dead_code)]
use idhazh_host_telemetry::{Validate, contracts::events::*, sampling::capture::*};
use std::path::{Path, PathBuf};
use uuid::Uuid;

pub fn fixture() -> serde_json::Value {
    serde_json::from_str(include_str!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../tests/fixtures/host-events/resource-windows.json"
    )))
    .unwrap()
}
pub fn frames() -> Vec<ResourceFrame> {
    let mut frames: Vec<ResourceFrame> =
        serde_json::from_value(fixture()["replay"]["frames"].clone()).unwrap();
    for frame in &mut frames {
        frame.population.value = Some(
            frame
                .processes
                .iter()
                .filter(|v| v.target.pid != 100)
                .cloned()
                .collect(),
        );
    }
    frames
}
pub fn manifest() -> HostSessionManifest {
    serde_json::from_str(include_str!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../tests/fixtures/host-events/manifest.json"
    )))
    .unwrap()
}
pub fn workspace(name: &str) -> PathBuf {
    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("var")
        .join(format!("d4-{name}"));
    if path.exists() {
        std::fs::remove_dir_all(&path).unwrap();
    }
    std::fs::create_dir_all(&path).unwrap();
    path.canonicalize().unwrap()
}
pub fn window(index: usize) -> WindowBody {
    let m = manifest();
    WindowBody {
        window_id: m.windows[index].window_id,
        item_id: m.windows[index].item_id.clone(),
        target: m.workers[index].target.clone(),
        server: m.workers[index].server.clone(),
    }
}
pub fn command(kind: EventKind, worker: usize, sequence: i64) -> HostEvent {
    let m = manifest();
    let body = match kind {
        EventKind::WorkerRegister => EventBody::Worker(WorkerBody {
            target: m.workers[worker].target.clone(),
            server: m.workers[worker].server.clone(),
            memory_profiling_enabled: m.controls.memory_profiling_enabled,
        }),
        EventKind::WindowBegin | EventKind::WindowEnd => EventBody::Window(window(worker)),
        EventKind::WindowAbort => EventBody::Abort(WindowAbortBody {
            window: window(worker),
            reason: AbortReason::Cancelled,
        }),
        EventKind::MonitorStop => EventBody::Stop(StopBody {
            reason: StopReason::Completed,
        }),
        _ => unreachable!(),
    };
    let event = HostEvent {
        version: m.version,
        kind,
        event_id: Uuid::from_u128(1000 + worker as u128 * 100 + sequence as u128),
        reply_to: None,
        date: m.date,
        run_id: m.run_id,
        attempt: m.attempt,
        job: m.job,
        shard: m.shard,
        session_id: m.session_id,
        emitter_id: if kind == EventKind::MonitorStop {
            m.operator_emitter_id
        } else {
            m.workers[worker].emitter_id.clone()
        },
        sequence,
        emitted_at: "2026-10-10T12:00:00Z".to_owned(),
        body,
    };
    event.validate().unwrap();
    event
}
pub fn write_frame(root: &Path, frame: &ResourceFrame, memory: bool) {
    std::fs::create_dir_all(root).unwrap();
    for (name, text) in [
        ("stat", &frame.proc_stat),
        ("loadavg", &frame.loadavg),
        ("meminfo", &frame.meminfo),
    ] {
        let path = root.join(name);
        if name == "meminfo" && !memory {
            if path.is_file() {
                std::fs::remove_file(&path).unwrap();
            }
            std::fs::create_dir_all(&path).unwrap();
        } else if let Some(text) = &text.value {
            std::fs::write(path, text).unwrap();
        }
    }
    for p in &frame.processes {
        let entry = root.join(p.target.pid.to_string());
        std::fs::create_dir_all(&entry).unwrap();
        std::fs::write(entry.join("stat"), p.stat_before.value.as_ref().unwrap()).unwrap();
        for (leaf, text) in [
            ("status", &p.status),
            ("comm", &p.comm),
            ("cmdline", &p.cmdline),
        ] {
            let path = entry.join(leaf);
            if !memory && leaf == "status" {
                if path.is_file() {
                    std::fs::remove_file(&path).unwrap();
                }
                std::fs::create_dir_all(&path).unwrap();
            } else if let Some(text) = &text.value {
                std::fs::write(path, text).unwrap();
            }
        }
    }
}
pub fn setup(root: &Path, m: &HostSessionManifest) {
    std::fs::write(root.join("manifest.json"), serde_json::to_vec(m).unwrap()).unwrap();
    let mut config: serde_json::Value = serde_json::from_str(include_str!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../config/host-telemetry-experiment.json"
    )))
    .unwrap();
    config["controls"] = serde_json::to_value(&m.controls).unwrap();
    config["limits"] = serde_json::to_value(&m.limits).unwrap();
    config["capture_limits"] = serde_json::to_value(&m.capture_limits).unwrap();
    std::fs::write(
        root.join("config.json"),
        serde_json::to_vec(&config).unwrap(),
    )
    .unwrap();
}
