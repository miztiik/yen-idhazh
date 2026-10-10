//! Which finite fixture inputs and generated workspace support native producer tests?

#![allow(dead_code)]
use idhazh_host_telemetry::contracts::events::*;
use idhazh_host_telemetry::probe_inputs::{files::Reading, snapshots::ProbeReplay};
use std::path::PathBuf;
use uuid::Uuid;

pub fn workspace(name: &str) -> PathBuf {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("var")
        .join(format!("d3-{name}"));
    if root.exists() {
        std::fs::remove_dir_all(&root).unwrap();
    }
    std::fs::create_dir_all(&root).unwrap();
    root.canonicalize().unwrap()
}
pub fn replay() -> ProbeReplay {
    serde_json::from_str(include_str!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../tests/fixtures/host-events/probe-clock.json"
    )))
    .unwrap()
}
pub fn manifest() -> HostSessionManifest {
    serde_json::from_str(include_str!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../tests/fixtures/host-events/manifest.json"
    )))
    .unwrap()
}
pub fn found(text: &str) -> Reading<String> {
    Reading::found(text.to_owned())
}
pub fn command(
    manifest: &HostSessionManifest,
    kind: EventKind,
    sequence: i64,
    previous: Option<Uuid>,
    target: bool,
) -> HostEvent {
    HostEvent {
        version: manifest.version.clone(),
        kind,
        event_id: Uuid::from_u128(sequence as u128 + 500),
        reply_to: None,
        date: manifest.date.clone(),
        run_id: manifest.run_id.clone(),
        attempt: manifest.attempt,
        job: manifest.job,
        shard: manifest.shard,
        session_id: manifest.session_id,
        emitter_id: manifest.operator_emitter_id.clone(),
        sequence,
        emitted_at: "2026-10-10T12:00:00Z".to_owned(),
        body: EventBody::HostCommand(HostCommandBody {
            controls: manifest.controls.clone(),
            input_names: Vec::new(),
            target: if target {
                Some(ProcessTarget {
                    pid: 100,
                    start_ticks: 800,
                })
            } else {
                None
            },
            previous_result_id: previous,
        }),
    }
}
