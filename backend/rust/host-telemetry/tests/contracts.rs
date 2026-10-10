use idhazh_host_telemetry::contracts::events::*;
use idhazh_host_telemetry::contracts::file_envelope::*;
use idhazh_host_telemetry::contracts::host::*;
use idhazh_host_telemetry::contracts::write_plan::*;
use serde_json::json;
use std::path::Path;
use std::process::Command;

#[test]
fn corrected_defaults_and_numeric_refusals() {
    let minimal = json!({"date":"2026-10-10","run_id":"2026-10-10-42","shard":0});
    let row: CorrectedHostFingerprintRow = serde_json::from_value(minimal.clone()).unwrap();
    assert_eq!(row.version, VERSION);
    assert_eq!(row.job, ServerJob::Work);
    assert_eq!(row.flags, "");
    assert_eq!(row.cpu_physical_cores, None);
    assert_eq!(row.fingerprint_v2().unwrap(), None);
    for (key, value) in [
        ("shard", json!(true)),
        ("shard", json!("1")),
        ("shard", json!(1.2)),
        ("shard", json!(u64::MAX)),
        ("cpu_physical_cores", json!(0)),
        ("version", json!("2026-09-20")),
        ("cores", json!(2)),
    ] {
        let mut bad = minimal.clone();
        bad[key] = value;
        assert!(
            serde_json::from_value::<CorrectedHostFingerprintRow>(bad).is_err(),
            "{key}"
        );
    }
}
#[test]
fn target_fingerprint_and_identity_predicates() {
    let mut row: CorrectedHostFingerprintRow = serde_json::from_value(
        json!({"date":"2026-10-10","run_id":"2026-10-10-42","shard":0,"cpu_vendor":"GenuineIntel"}),
    )
    .unwrap();
    row.fingerprint = row.fingerprint_v2().unwrap();
    row.fingerprint_version = Some(2);
    row.validate().unwrap();
    let fingerprint = row.fingerprint.clone();
    row.cpu_logical_processors = Some(4);
    row.cpu_physical_cores = Some(2);
    row.cpu_observed_mhz = Some(1000.0);
    assert_eq!(row.fingerprint_v2().unwrap(), fingerprint);
    row.cpu_allowed_processors = Some(3);
    assert!(row.validate().is_err());
    row.cpu_target_measured_at = Some("2026-10-10T12:00:01Z".to_owned());
    row.cpu_quota_state = Some(QuotaState::Unlimited);
    row.validate().unwrap();
    row.cpu_quota_cores = Some(0.5);
    assert!(row.validate().is_err());
    row.cpu_quota_state = Some(QuotaState::Finite);
    row.validate().unwrap();
    row.cpu_physical_cores = Some(5);
    assert!(row.validate().is_err());
    let unit = host_unit_id(&row.date, &row.run_id, row.job, row.shard).unwrap();
    assert_eq!(unit.get_version_num(), 5);
    assert_eq!(
        host_file_id(unit, 2, 1791633600123)
            .unwrap()
            .get_version_num(),
        8
    );
    assert!(host_file_id(unit, 0, 1791633600123).is_err());
}
#[test]
fn closed_events_and_required_nullable_fields() {
    let event = json!({"kind":"monitor.ready","event_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","reply_to":null,"date":"2026-10-10","run_id":"2026-10-10-42","attempt":1,"job":"work","shard":0,"session_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb","emitter_id":"monitor","sequence":1,"emitted_at":"2026-10-10T12:00:00Z","body":{"boot_id":"cccccccc-cccc-4ccc-8ccc-cccccccccccc","supported_version":VERSION}});
    let valid: HostEvent = serde_json::from_value(event.clone()).unwrap();
    valid.validate().unwrap();
    for (key, value) in [
        ("kind", json!("unknown")),
        ("sequence", json!(false)),
        ("sequence", json!(0)),
        ("reply_to", json!("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")),
        ("extra", json!(1)),
    ] {
        let mut bad = event.clone();
        bad[key] = value;
        assert!(serde_json::from_value::<HostEvent>(bad).is_err());
    }
    let mut missing = event;
    missing.as_object_mut().unwrap().remove("reply_to");
    assert!(serde_json::from_value::<HostEvent>(missing).is_err());
    assert!(serde_json::from_value::<ProcessTarget>(json!({"pid":0,"start_ticks":0})).is_err());
    assert!(
        serde_json::from_value::<StoppedBody>(json!({"drained":1,"aborted_window_ids":[]}))
            .is_err()
    );
}
#[test]
fn immutable_plans_metadata_and_completion_membership() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..");
    let result = Command::new(env!("CARGO_BIN_EXE_codec-fixture"))
        .current_dir(&root)
        .args([
            "render",
            "tests/fixtures/host-events/file-parity.json",
            "backend/var/d10-rust-tests/contracts",
        ])
        .output()
        .unwrap();
    assert!(
        result.status.success(),
        "{}",
        String::from_utf8_lossy(&result.stderr)
    );
    let proofs: serde_json::Value = serde_json::from_slice(&result.stdout).unwrap();
    let plan: HostWritePlan = serde_json::from_value(proofs[0]["plan"].clone()).unwrap();
    let completion: HostWriteCompletion =
        serde_json::from_value(proofs[0]["completion"].clone()).unwrap();
    plan.validate_successor(&plan).unwrap();
    completion.validate_plan(&plan, true).unwrap();
    let mut changed = plan.clone();
    changed.event_id = uuid::Uuid::nil();
    assert!(changed.validate_successor(&plan).is_err());
    let metadata = plan.files[0].envelope.metadata().unwrap();
    assert_eq!(metadata.attempt, "02");
    assert_eq!(metadata.shard, "00");
    assert_eq!(metadata.envelope().unwrap(), plan.files[0].envelope);
    let mut bad = serde_json::to_value(&metadata).unwrap();
    bad["surprise"] = json!("bad");
    assert!(serde_json::from_value::<EnvelopeMetadata>(bad).is_err());
    let mut partial = completion;
    partial.receipt.writes.clear();
    partial.validate_plan(&plan, false).unwrap();
    assert!(partial.validate_plan(&plan, true).is_err());
}
