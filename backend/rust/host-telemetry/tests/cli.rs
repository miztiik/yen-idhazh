//! Does the real native CLI replay named sources into retained atomic results and files?

mod support;
use idhazh_host_telemetry::{contracts::events::*, probe_inputs::snapshots::ProbeReplay};
use std::process::Command;
use uuid::Uuid;

#[test]
fn native_replay_uses_the_real_producer_and_refuses_conflicting_retries() {
    let workspace = support::workspace("cli");
    let mut manifest = support::manifest();
    manifest.named_inputs = vec![NamedHostInput {
        name: "snapshot".to_owned(),
        source: CaptureSource::Cpuinfo,
        relative_path: "capture.json".to_owned(),
    }];
    let mut command = support::command(&manifest, EventKind::HostProbe, 1, None, true);
    if let EventBody::HostCommand(body) = &mut command.body {
        body.input_names = vec!["snapshot".to_owned()];
    }
    std::fs::write(
        workspace.join("manifest.json"),
        serde_json::to_vec(&manifest).unwrap(),
    )
    .unwrap();
    std::fs::write(
        workspace.join("command.json"),
        serde_json::to_vec(&command).unwrap(),
    )
    .unwrap();
    let replay: ProbeReplay = support::replay();
    std::fs::write(
        workspace.join("capture.json"),
        serde_json::to_vec(&replay).unwrap(),
    )
    .unwrap();
    std::fs::write(
        workspace.join("config.json"),
        include_bytes!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../config/host-telemetry-experiment.json"
        )),
    )
    .unwrap();
    let call = || {
        Command::new(env!("CARGO_BIN_EXE_idhazh-host-telemetry"))
            .args([
                "probe",
                "--workspace",
                workspace.to_str().unwrap(),
                "--manifest",
                "manifest.json",
                "--command",
                "command.json",
                "--config",
                "config.json",
                "--snapshot",
                "snapshot",
                "--cache-multiple",
                "2",
                "--format",
                "json",
                "--result-id",
                "00000000-0000-0000-0000-000000002001",
            ])
            .output()
            .unwrap()
    };
    let output = call();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let name = String::from_utf8(output.stdout).unwrap();
    let bytes = std::fs::read(workspace.join(name.trim())).unwrap();
    let result: HostEvent = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(result.event_id, Uuid::from_u128(0x2001));
    let EventBody::HostResult(body) = result.body else {
        panic!("not a result")
    };
    assert_eq!(body.row.cpu_quota_cores, Some(0.5));
    assert_eq!(body.row.cpu_logical_processors, Some(4));
    std::fs::remove_file(workspace.join("capture.json")).unwrap();
    assert!(
        call().status.success(),
        "retry must not reread absent capture"
    );
    assert_eq!(std::fs::read(workspace.join(name.trim())).unwrap(), bytes);
    command.sequence = 2;
    std::fs::write(
        workspace.join("command.json"),
        serde_json::to_vec(&command).unwrap(),
    )
    .unwrap();
    assert!(!call().status.success());
}
