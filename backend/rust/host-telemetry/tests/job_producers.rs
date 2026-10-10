//! Do probe, first target and closing clocks publish real whole files with one ranked identity?

mod support;
use idhazh_host_telemetry::{
    config::{CodecConfig, Lifecycle},
    contracts::{events::*, file_envelope::*},
    probe_inputs::placement,
    producers::{
        job_clock,
        job_probe::{self, Publication},
        target_probe,
    },
    receipts,
};
use std::fs;
use uuid::Uuid;

#[test]
fn whole_native_files_and_receipts_preserve_hardware_across_target_and_clock() {
    for (label, format, compression) in [
        ("json", Format::Json, Compression::None),
        ("none", Format::Parquet, Compression::None),
        ("snappy", Format::Parquet, Compression::Snappy),
        ("zstd", Format::Parquet, Compression::Zstd),
    ] {
        let workspace = support::workspace(&format!("job-{label}"));
        let mut manifest = support::manifest();
        manifest.cpu_target = None;
        manifest.cpu_target_role = TargetRole::Unselected;
        let replay = support::replay();
        let capture = &replay.attempts[0];
        let where_ = placement::recorded(replay.placement_json.value.as_ref().unwrap().as_bytes());
        let probe = support::command(&manifest, EventKind::HostProbe, 1, None, false);
        let result = job_probe::probe(
            &manifest,
            &probe,
            capture,
            &where_,
            replay.runner_name.clone(),
            "2026-10-10T12:00:00Z",
            2,
        )
        .unwrap();
        assert_eq!(result.row.cpu_quota_state, None);
        assert_eq!(result.row.cpu_allowed_processors, None);
        assert_eq!(result.row.memcpy_probe_mib, Some(0));
        assert_eq!(result.row.boot_seconds, Some(12345.75));
        let identity = HostWriterIdentity {
            run_id: manifest.run_id.clone(),
            attempt: 1,
            job: manifest.job,
            shard: 0,
            producer: "telemetry.silicon".to_owned(),
            git_sha: manifest.git_sha.clone(),
        };
        let prefix = vec!["host-fingerprint".to_owned()];
        let codec = CodecConfig {
            format,
            compression,
        };
        let limits = receipts::ReceiptLimits {
            max_files: 64,
            max_file_bytes: 1048576,
            max_total_bytes: 16777216,
            max_document_bytes: 262144,
        };
        let mut publication = Publication {
            workspace: &workspace,
            target_root: "output/state",
            evidence_root: "evidence",
            prefix: &prefix,
            identity: &identity,
            codec: &codec,
            lifecycle: Lifecycle::Active,
            event_id: probe.event_id,
            written_at_ms: replay.written_at_ms,
            limits: &limits,
        };
        let initial = job_probe::publish(&publication, result, None)
            .unwrap()
            .unwrap();
        let old_bytes =
            fs::read(workspace.join(initial.completion.receipt.writes.keys().next().unwrap()))
                .unwrap();
        let target = support::command(
            &manifest,
            EventKind::HostTarget,
            2,
            Some(Uuid::from_u128(1001)),
            true,
        );
        let enriched = target_probe::enrich(
            &manifest,
            &target,
            Uuid::from_u128(1001),
            &initial.result,
            &initial.plan,
            capture,
            "2026-10-10T12:00:01Z",
        )
        .unwrap();
        assert_eq!(enriched.row.fingerprint, initial.result.row.fingerprint);
        assert_eq!(enriched.row.measured_at, initial.result.row.measured_at);
        assert_eq!(enriched.row.cpu_allowed_processors, Some(2));
        publication.event_id = target.event_id;
        publication.written_at_ms += 1;
        let selected = job_probe::publish(&publication, enriched, Some(&initial.plan))
            .unwrap()
            .unwrap();
        let frozen = target_probe::enrich(
            &manifest,
            &target,
            Uuid::from_u128(1001),
            &initial.result,
            &initial.plan,
            capture,
            "2026-10-10T12:00:01Z",
        )
        .unwrap();
        assert_eq!(frozen.row.cpu_quota_cores, Some(0.5));
        let clock = support::command(
            &manifest,
            EventKind::HostClock,
            3,
            Some(Uuid::from_u128(1002)),
            false,
        );
        let closed = job_clock::enrich(
            &manifest,
            &clock,
            Uuid::from_u128(1002),
            &selected.result,
            &selected.plan,
            job_clock::ClockInputs {
                start: Some("2026-10-10T12:00:00Z"),
                finish: "2026-10-10T12:00:42Z",
                log: Some(include_str!(concat!(
                    env!("CARGO_MANIFEST_DIR"),
                    "/../../../tests/fixtures/runtime/2026-08-29-3-shard-0.server-head.txt"
                ))),
                metrics: Some(include_str!(concat!(
                    env!("CARGO_MANIFEST_DIR"),
                    "/../../../tests/fixtures/runtime/2026-08-26-5-shard-0.prom"
                ))),
            },
        )
        .unwrap();
        publication.event_id = clock.event_id;
        publication.written_at_ms += 1;
        let final_ = job_probe::publish(&publication, closed, Some(&selected.plan))
            .unwrap()
            .unwrap();
        assert_eq!(final_.result.row.job_seconds, Some(42));
        assert_eq!(final_.result.row.model_load_ms, Some(3797.64));
        assert_eq!(
            final_.result.row.cpu_target_measured_at,
            Some("2026-10-10T12:00:01Z".to_owned())
        );
        assert_eq!(final_.result.cpu, selected.result.cpu);
        assert_eq!(
            initial.plan.files[0].envelope.unit_id,
            final_.plan.files[0].envelope.unit_id
        );
        assert_eq!(
            fs::read(workspace.join(initial.completion.receipt.writes.keys().next().unwrap()))
                .unwrap(),
            old_bytes
        );
        let retried = job_probe::publish(&publication, final_.result.clone(), Some(&final_.plan))
            .unwrap()
            .unwrap();
        assert_eq!(retried.completion, final_.completion);
        fs::write(
            workspace.join("final-result.json"),
            serde_json::to_vec(&final_.result).unwrap(),
        )
        .unwrap();
        fs::write(
            workspace.join("final-plan.json"),
            serde_json::to_vec(&final_.plan).unwrap(),
        )
        .unwrap();
        fs::write(
            workspace.join("final-completion.json"),
            serde_json::to_vec(&final_.completion).unwrap(),
        )
        .unwrap();
    }
}
#[test]
fn conflicting_target_and_foreign_attempt_are_refused_before_publication() {
    let mut manifest = support::manifest();
    manifest.cpu_target = None;
    manifest.cpu_target_role = TargetRole::Unselected;
    let mut command = support::command(&manifest, EventKind::HostTarget, 1, None, true);
    if let EventBody::HostCommand(body) = &mut command.body {
        body.target = Some(ProcessTarget {
            pid: 200,
            start_ticks: 900,
        });
    }

    assert!(job_probe::validate_command(&manifest, &command).is_err());
    command.attempt = 2;
    assert!(job_probe::validate_command(&manifest, &command).is_err());
}

#[test]
fn memory_off_does_not_disable_the_separately_selected_real_copy() {
    let manifest = support::manifest();
    let mut command = support::command(&manifest, EventKind::HostProbe, 1, None, true);
    if let EventBody::HostCommand(body) = &mut command.body {
        body.controls.memory_profiling_enabled = false;
        body.controls.memcpy_enabled = true;
        body.controls.memcpy_probe_mib = 1;
    }
    let mut replay = support::replay();
    replay.attempts[0].cache_bytes =
        idhazh_host_telemetry::probe_inputs::files::Reading::absent(UnavailableReason::Missing);
    let result = job_probe::probe(
        &manifest,
        &command,
        &replay.attempts[0],
        &placement::Placement::default(),
        None,
        "2026-10-10T12:00:00Z",
        2,
    )
    .unwrap();
    assert_eq!(result.row.memcpy_probe_mib, Some(1));
    assert!(result.row.memcpy_gib_s.unwrap() > 0.0);
    assert_eq!(result.row.cpu_allowed_processors, Some(2));
}
