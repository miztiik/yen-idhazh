use idhazh_host_telemetry::{
    config::{CodecConfig, Lifecycle},
    contracts::{file_envelope::*, host::*},
    ledger::{identity, store},
};
use serde_json::json;
use std::{
    fs,
    path::{Path, PathBuf},
    process::Command,
    time::Duration,
};
use uuid::Uuid;

struct TestRoot(PathBuf);
impl TestRoot {
    fn new(name: &str) -> Self {
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../..")
            .join(format!(
                "backend/var/d11-store/{name}-{}",
                std::process::id()
            ));
        if root.exists() {
            fs::remove_dir_all(&root).unwrap();
        }
        fs::create_dir_all(&root).unwrap();
        Self(root)
    }
}
impl Drop for TestRoot {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.0).unwrap();
    }
}
fn writer() -> HostWriterIdentity {
    serde_json::from_value(json!({
        "run_id":"2026-10-10-42","attempt":2,"job":"work","shard":0,
        "producer":HOST_PRODUCER,"git_sha":"a".repeat(40)
    }))
    .unwrap()
}
fn rows() -> Vec<HostStoredRow> {
    ["2026-10-08", "2026-10-09", "2026-10-10"]
        .iter()
        .map(|date| {
            let row: CorrectedHostFingerprintRow = serde_json::from_value(json!({
                "date":date,"run_id":"2026-10-10-42","shard":0
            }))
            .unwrap();
            identity::stamp(&row, &writer()).unwrap()
        })
        .collect()
}
fn prepare(
    root: &Path,
    rows: &[HostStoredRow],
    lifecycle: Lifecycle,
) -> Result<Option<store::PreparedWrite>> {
    store::prepare(
        root,
        store::WriteRequest {
            target_root: "state",
            prefix: &["host-fingerprint".to_owned()],
            publication_identity: &writer(),
            rows,
            codec: &CodecConfig {
                format: Format::Json,
                compression: Compression::None,
            },
            lifecycle,
            event_id: Uuid::from_u128(0xaaaaaaaaaaaa4aaa8aaaaaaaaaaaaaaa),
            written_at_ms: 1791633600123,
        },
    )
}
#[test]
fn empty_and_paused_retired_write_no_files() {
    let root = TestRoot::new("gates");
    assert!(prepare(&root.0, &[], Lifecycle::Active).unwrap().is_none());
    for lifecycle in [Lifecycle::Paused, Lifecycle::Retired] {
        assert!(prepare(&root.0, &rows(), lifecycle).unwrap().is_none());
    }
    assert!(!root.0.join("state").exists());
}
#[test]
fn invalid_last_group_and_duplicate_day_refuse_before_any_write() {
    let root = TestRoot::new("invalid");
    let mut invalid = rows();
    invalid[2].host.date = "2026-02-30".to_owned();
    assert!(prepare(&root.0, &invalid, Lifecycle::Active).is_err());
    let mut duplicate = rows();
    duplicate.push(duplicate[0].clone());
    assert!(prepare(&root.0, &duplicate, Lifecycle::Active).is_err());
    assert!(!root.0.join("state").exists());
}
#[test]
fn all_groups_prepared_then_partial_failure_retains_completed_bytes() {
    let root = TestRoot::new("partial");
    let prepared = prepare(&root.0, &rows(), Lifecycle::Active)
        .unwrap()
        .unwrap();
    let blocked = root.0.join("state/raw/host-fingerprint/2026/10/10");
    fs::create_dir_all(blocked.parent().unwrap()).unwrap();
    fs::write(&blocked, b"unrelated obstruction").unwrap();
    let failure = store::publish(&prepared).unwrap_err();
    assert_eq!(failure.completed.len(), 2);
    for file in &failure.completed {
        assert!(root.0.join(&file.relative_path).is_file());
    }
    assert_eq!(fs::read(&blocked).unwrap(), b"unrelated obstruction");
    fs::remove_file(&blocked).unwrap();
    let files = store::publish(&prepared).unwrap();
    assert_eq!(files.len(), 3);
    assert_eq!(&files[..2], &failure.completed);
    assert_eq!(store::publish(&prepared).unwrap(), files);
}
#[test]
fn conflicting_destination_is_never_replaced_and_successor_needs_actual_clock() {
    let root = TestRoot::new("conflict");
    let prepared = prepare(&root.0, &rows(), Lifecycle::Active)
        .unwrap()
        .unwrap();
    let files = store::publish(&prepared).unwrap();
    let path = root.0.join(&files[0].relative_path);
    fs::write(&path, b"conflict").unwrap();
    assert!(store::publish(&prepared).unwrap_err().completed.is_empty());
    assert_eq!(fs::read(&path).unwrap(), b"conflict");
    let mut successor = prepared.plan().clone();
    successor.files[0].rows[0].host.job_seconds = Some(12);
    assert!(store::prepare_plan(&root.0, successor).is_err());
    let now = store::actual_millis_after(None, Duration::ZERO).unwrap();
    assert!(store::actual_millis_after(Some(now), Duration::from_millis(100)).unwrap() > now);
    assert!(store::actual_millis_after(Some(i64::MAX), Duration::ZERO).is_err());
}

#[test]
fn whole_row_successors_preserve_probe_and_require_strictly_later_milliseconds() {
    let root = TestRoot::new("successor");
    let mut rows = rows();
    let original = prepare(&root.0, &rows, Lifecycle::Active).unwrap().unwrap();
    rows[0].host.job_seconds = Some(12);
    let event_id = Uuid::from_u128(0xbbbbbbbbbbbb4bbb8bbbbbbbbbbbbbbb);
    let codec = CodecConfig {
        format: Format::Json,
        compression: Compression::None,
    };
    let identity = writer();
    let prefix = ["host-fingerprint".to_owned()];
    let request = |clock| store::WriteRequest {
        target_root: "state",
        prefix: &prefix,
        publication_identity: &identity,
        rows: &rows,
        codec: &codec,
        lifecycle: Lifecycle::Active,
        event_id,
        written_at_ms: clock,
    };
    assert!(store::prepare_successor(&root.0, request(1791633600123), original.plan()).is_err());
    let next = store::prepare_successor(&root.0, request(1791633600124), original.plan())
        .unwrap()
        .unwrap();
    assert_eq!(&next.plan().files[1..], &original.plan().files[1..]);
    store::publish(&original).unwrap();
    store::publish(&next).unwrap();
    assert!(root.0.join("state").is_dir());
}
#[test]
fn actual_store_files_are_retained_for_independent_python_verification() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..");
    let evidence = root.join("backend/var/d11-rust-tests");
    if evidence.exists() {
        fs::remove_dir_all(&evidence).unwrap();
    }
    let output = Command::new(env!("CARGO_BIN_EXE_storage-fixture"))
        .current_dir(&root)
        .args([
            "tests/fixtures/host-events/storage-parity.json",
            "backend/var/d11-rust-tests",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    fs::write(
        root.join("backend/var/d11-rust-tests/proofs.json"),
        &output.stdout,
    )
    .unwrap();
    let proofs: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(proofs.as_array().unwrap().len(), 4);
}
