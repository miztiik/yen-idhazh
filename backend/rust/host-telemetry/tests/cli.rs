//! Does the real native CLI replay named sources into retained atomic results and files?

mod support;
use idhazh_host_telemetry::{contracts::events::*, probe_inputs::snapshots::ProbeReplay};
use std::io::{BufRead, BufReader, Read};
use std::process::Command;
use uuid::Uuid;

#[test]
fn native_replay_uses_the_real_producer_and_refuses_conflicting_retries() {
    native_replay_check();
}
fn native_replay_check() {
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
    native_replay_finish(workspace, manifest, command);
}
#[test]
fn killed_cli_resumes_intent_plan_publication_receipt_and_result_without_recapture() {
    for codec in ["json", "none", "snappy", "zstd"] {
        for boundary in [
            "intended-result",
            "plan",
            "publication",
            "receipt",
            "result",
        ] {
            let workspace = support::workspace(&format!("cli-killed-{codec}-{boundary}"));
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
            for (name, value) in [
                ("manifest.json", serde_json::to_vec(&manifest).unwrap()),
                ("command.json", serde_json::to_vec(&command).unwrap()),
                (
                    "capture.json",
                    serde_json::to_vec(&support::replay()).unwrap(),
                ),
            ] {
                std::fs::write(workspace.join(name), value).unwrap();
            }
            std::fs::write(
                workspace.join("config.json"),
                include_bytes!(concat!(
                    env!("CARGO_MANIFEST_DIR"),
                    "/../../../config/host-telemetry-experiment.json"
                )),
            )
            .unwrap();
            let call = || {
                let mut process = Command::new(env!("CARGO_BIN_EXE_idhazh-host-telemetry"));
                process.args([
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
                    if codec == "json" { "json" } else { "parquet" },
                    "--compression",
                    if codec == "json" { "none" } else { codec },
                    "--result-id",
                    "00000000-0000-0000-0000-000000002001",
                ]);
                process
            };
            let mut child = call()
                .env("IDHAZH_HOST_CHECKPOINT", boundary)
                .stdout(std::process::Stdio::piped())
                .stderr(std::process::Stdio::piped())
                .spawn()
                .unwrap();
            let stderr = child.stderr.take().unwrap();
            let (sent, received) = std::sync::mpsc::channel();
            let reader = std::thread::spawn(move || {
                let mut line = String::new();
                BufReader::new(stderr).read_line(&mut line).unwrap();
                let _ = sent.send(line);
            });
            let line = received.recv_timeout(std::time::Duration::from_secs(60));
            child.kill().unwrap();
            child.wait().unwrap();
            reader.join().unwrap();
            let mut stdout = String::new();
            child
                .stdout
                .take()
                .unwrap()
                .read_to_string(&mut stdout)
                .unwrap();
            assert!(
                stdout.is_empty(),
                "a stopped invocation must not announce completion"
            );
            assert_eq!(
                line.expect("CLI checkpoint deadline").trim(),
                format!("host checkpoint: {boundary}")
            );
            let result_name = format!(
                "{}/results/00000000-0000-0000-0000-000000002001.json",
                manifest.event_root
            );
            assert_eq!(workspace.join(&result_name).exists(), boundary == "result");
            let receipt_name = format!(
                "{}/writes/{}.completed-1.json",
                manifest.event_root, command.event_id
            );
            assert_eq!(
                workspace.join(receipt_name).exists(),
                matches!(boundary, "receipt" | "result")
            );
            let retained_name = format!(
                "{}/writes/{}.intent.json",
                manifest.event_root, command.event_id
            );
            let intent_bytes = std::fs::read(workspace.join(retained_name)).unwrap();
            let intent: serde_json::Value = serde_json::from_slice(&intent_bytes).unwrap();
            let plan: idhazh_host_telemetry::contracts::write_plan::HostWritePlan =
                serde_json::from_value(intent["plan"].clone()).unwrap();
            let raw = workspace
                .join(&plan.target_root)
                .join(&plan.files[0].relative_path);
            let published = raw.exists().then(|| std::fs::read(&raw).unwrap());
            std::fs::remove_file(workspace.join("capture.json")).unwrap();
            let output = call().output().unwrap();
            assert!(
                output.status.success(),
                "{}",
                String::from_utf8_lossy(&output.stderr)
            );
            let result_bytes = std::fs::read(workspace.join(&result_name)).unwrap();
            let event: HostEvent = serde_json::from_slice(&result_bytes).unwrap();
            assert_eq!(serde_json::to_value(&event).unwrap(), intent["event"]);
            if let Some(before) = published {
                assert_eq!(std::fs::read(&raw).unwrap(), before);
            }
            let limits = idhazh_host_telemetry::receipts::ReceiptLimits {
                max_files: 4,
                max_file_bytes: 1048576,
                max_total_bytes: 4194304,
                max_document_bytes: 1048576,
            };
            let evidence = format!("{}/writes", manifest.event_root);
            let prepared = idhazh_host_telemetry::receipts::load_plan(
                &workspace,
                &idhazh_host_telemetry::receipts::plan_path(&evidence, &plan),
                &evidence,
                &limits,
            )
            .unwrap();
            let completion =
                idhazh_host_telemetry::receipts::recover(&prepared, &evidence, &limits).unwrap();
            completion.validate_plan(&plan, true).unwrap();
            assert!(prepared.verify_existing(0).unwrap().is_some());
            fn files(path: &std::path::Path) -> Vec<std::path::PathBuf> {
                let mut result = Vec::new();
                for entry in std::fs::read_dir(path).unwrap() {
                    let entry = entry.unwrap().path();
                    if entry.is_dir() {
                        result.extend(files(&entry));
                    } else {
                        result.push(entry);
                    }
                }
                result.sort();
                result
            }
            assert_eq!(
                files(&workspace.join(&plan.target_root)),
                std::slice::from_ref(&raw)
            );
            let before: Vec<_> = files(&workspace)
                .into_iter()
                .map(|p| {
                    let bytes = std::fs::read(&p).unwrap();
                    (p, bytes)
                })
                .collect();
            assert!(call().output().unwrap().status.success());
            assert!(
                before
                    .iter()
                    .all(|(p, bytes)| std::fs::read(p).unwrap() == *bytes)
            );
            assert_eq!(files(&workspace).len(), before.len());
            command.sequence += 1;
            std::fs::write(
                workspace.join("command.json"),
                serde_json::to_vec(&command).unwrap(),
            )
            .unwrap();
            assert!(!call().output().unwrap().status.success());
            assert_eq!(
                std::fs::read(workspace.join(result_name)).unwrap(),
                result_bytes
            );
        }
    }
}
fn native_replay_finish(
    workspace: std::path::PathBuf,
    manifest: HostSessionManifest,
    mut command: HostEvent,
) {
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
