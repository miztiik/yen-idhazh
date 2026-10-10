use idhazh_host_telemetry::{
    canonical_json::{object_bytes, rows_bytes, sha256},
    config::{CodecConfig, Lifecycle},
    contracts::{file_envelope::*, host::*, write_plan::*},
    ledger::{identity, paths, store},
    receipts::{self, Checkpoint, ReceiptLimits},
};
use serde_json::{Value, json};
use std::{
    fs,
    path::{Path, PathBuf},
    process::{Command, Output},
    sync::atomic::{AtomicU64, Ordering},
};
use uuid::Uuid;

struct TestRoot {
    workspace: PathBuf,
    root: PathBuf,
    relative: String,
}
impl TestRoot {
    fn new(name: &str) -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        let workspace = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..");
        let relative = format!(
            "backend/var/d12-native/{name}-{}-{}",
            std::process::id(),
            NEXT.fetch_add(1, Ordering::Relaxed),
        );
        let root = workspace.join(&relative);
        if root.exists() {
            fs::remove_dir_all(&root).unwrap();
        }
        fs::create_dir_all(&root).unwrap();
        Self {
            workspace,
            root,
            relative,
        }
    }
    fn evidence(&self) -> String {
        format!("{}/evidence", self.relative)
    }
    fn prepared(&self, format: Format, compression: Compression) -> store::PreparedWrite {
        let publisher = publisher();
        store::prepare(
            &self.workspace,
            store::WriteRequest {
                target_root: &format!("{}/state", self.relative),
                prefix: &["trial".to_owned(), "host-fingerprint".to_owned()],
                publication_identity: &publisher,
                rows: &rows(),
                codec: &CodecConfig {
                    format,
                    compression,
                },
                lifecycle: Lifecycle::Active,
                event_id: Uuid::from_u128(0xaaaaaaaaaaaa4aaa8aaaaaaaaaaaaaaa),
                written_at_ms: 1791633600123,
            },
        )
        .unwrap()
        .unwrap()
    }
    fn document(&self, relative: &str, value: &impl serde::Serialize) {
        let path = self.workspace.join(relative);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        let mut bytes = object_bytes(value).unwrap();
        bytes.push(b'\n');
        fs::write(path, bytes).unwrap();
    }
    fn input(&self, plan: &HostWritePlan) -> String {
        let path = format!("{}/input.plan.json", self.relative);
        self.document(&path, plan);
        path
    }
    fn fixture(&self, args: &[&str]) -> Output {
        Command::new(env!("CARGO_BIN_EXE_receipts-fixture"))
            .current_dir(&self.workspace)
            .args(args)
            .output()
            .unwrap()
    }
    fn retained(&self, plan: &HostWritePlan) -> String {
        receipts::plan_path(&self.evidence(), plan)
    }
    fn snapshot(&self, plan: &HostWritePlan, count: usize) -> String {
        receipts::completion_path(&self.evidence(), plan, count)
    }
    fn target(&self, plan: &HostWritePlan, index: usize) -> PathBuf {
        self.workspace
            .join(&plan.target_root)
            .join(&plan.files[index].relative_path)
    }
}
impl Drop for TestRoot {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.root).expect("remove only this test's generated artifact root");
    }
}

fn publisher() -> HostWriterIdentity {
    serde_json::from_value(json!({
        "run_id":"2026-10-10-42","attempt":2,"job":"work","shard":0,
        "producer":"utilities.host-fixture","git_sha":"a".repeat(40)
    }))
    .unwrap()
}
fn rows() -> Vec<HostStoredRow> {
    let mut logical = publisher();
    logical.producer = HOST_PRODUCER.to_owned();
    ["2026-10-08", "2026-10-09", "2026-10-10"]
        .iter()
        .map(|day| {
            let mut row: CorrectedHostFingerprintRow = serde_json::from_value(json!({
                "date":day,"run_id":"2026-10-10-42","shard":0,
                "cpu_model":"Native receipt \u{00e9}vidence","cpu_vendor":"GenuineIntel",
                "cpu_physical_cores":2,"cpu_logical_processors":4,
                "cpu_observed_mhz":2400.25,"cpu_reported_max_mhz":3200.0,
                "measured_at":"2026-10-10T12:00:00Z"
            }))
            .unwrap();
            row.fingerprint = row.fingerprint_v2().unwrap();
            row.fingerprint_version = Some(2);
            identity::stamp(&row, &logical).unwrap()
        })
        .collect()
}
fn limits() -> ReceiptLimits {
    ReceiptLimits {
        max_files: 3,
        max_file_bytes: 1_048_576,
        max_total_bytes: 3_145_728,
        max_document_bytes: 262_144,
    }
}
fn assert_completion(
    root: &TestRoot,
    plan: &HostWritePlan,
    completion: &HostWriteCompletion,
    count: usize,
) {
    completion
        .validate_plan(plan, count == plan.files.len())
        .unwrap();
    assert_eq!(completion.receipt.writes.len(), count);
    assert_eq!(
        completion.receipt.identity.producer,
        "utilities.host-fixture"
    );
    for file in &plan.files {
        assert_eq!(file.envelope.identity.producer, HOST_PRODUCER);
        let relative = format!("{}/{}", plan.target_root, file.relative_path);
        if let Some(hash) = completion.receipt.writes.get(&relative) {
            let bytes =
                store::read_bounded(&root.workspace.join(&relative), limits().max_file_bytes)
                    .unwrap();
            assert_eq!(*hash, sha256(&bytes));
            assert_ne!(*hash, sha256(&rows_bytes(&file.rows).unwrap()));
        }
    }
}
fn parse_success(output: Output) -> (HostWritePlan, HostWriteCompletion) {
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let proof: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert!(proof.get("error").is_none(), "{proof}");
    (
        serde_json::from_value(proof["plan"].clone()).unwrap(),
        serde_json::from_value(proof["completion"].clone()).unwrap(),
    )
}

#[test]
fn exact_bytes_in_all_codecs_have_immutable_cumulative_receipts_and_identical_retries() {
    for (name, format, compression) in [
        ("json", Format::Json, Compression::None),
        ("none", Format::Parquet, Compression::None),
        ("snappy", Format::Parquet, Compression::Snappy),
        ("zstd", Format::Parquet, Compression::Zstd),
    ] {
        let root = TestRoot::new(name);
        let prepared = root.prepared(format, compression);
        let plan = prepared.plan();
        let mut stages = Vec::new();
        let completion =
            receipts::write_observed(&prepared, &root.evidence(), &limits(), &mut |stage| {
                stages.push(stage);
                Ok(())
            })
            .unwrap();
        assert_completion(&root, plan, &completion, 3);
        assert_eq!(stages[0], Checkpoint::PlanPersisted);
        for index in 0..3 {
            assert_eq!(
                &stages[1 + index * 4..5 + index * 4],
                &[
                    Checkpoint::BeforeFilePublish(index),
                    Checkpoint::FilePublished(index),
                    Checkpoint::BeforeReceiptPersist(index),
                    Checkpoint::ReceiptPersisted(index),
                ]
            );
            let snapshot: HostWriteCompletion = serde_json::from_slice(
                &fs::read(root.workspace.join(root.snapshot(plan, index + 1))).unwrap(),
            )
            .unwrap();
            assert_completion(&root, plan, &snapshot, index + 1);
        }
        let retained_before = fs::read(root.workspace.join(root.retained(plan))).unwrap();
        let last_before = fs::read(root.workspace.join(root.snapshot(plan, 3))).unwrap();
        let replay = receipts::load_plan(
            &root.workspace,
            &root.retained(plan),
            &root.evidence(),
            &limits(),
        )
        .unwrap();
        assert_eq!(replay.plan(), plan);
        assert_eq!(
            receipts::recover(&replay, &root.evidence(), &limits()).unwrap(),
            completion
        );
        assert_eq!(
            receipts::write(&replay, &root.evidence(), &limits()).unwrap(),
            completion
        );
        assert_eq!(
            fs::read(root.workspace.join(root.retained(plan))).unwrap(),
            retained_before
        );
        assert_eq!(
            fs::read(root.workspace.join(root.snapshot(plan, 3))).unwrap(),
            last_before
        );
    }
}

#[test]
fn real_multiday_process_exit_at_each_checkpoint_recovers_only_completed_targets() {
    for (name, format, compression) in [
        ("json", Format::Json, Compression::None),
        ("none", Format::Parquet, Compression::None),
        ("snappy", Format::Parquet, Compression::Snappy),
        ("zstd", Format::Parquet, Compression::Zstd),
    ] {
        for (stage, count, receipt_count) in [
            ("plan", 0, 0),
            ("before-file-0", 0, 0),
            ("after-file-0", 1, 0),
            ("before-receipt-0", 1, 0),
            ("after-receipt-0", 1, 1),
            ("before-file-1", 1, 1),
            ("after-file-1", 2, 1),
            ("before-receipt-1", 2, 1),
            ("after-receipt-1", 2, 2),
        ] {
            let root = TestRoot::new(&format!("stop-{name}-{stage}"));
            let prepared = root.prepared(format, compression);
            let plan = prepared.plan();
            let input = root.input(plan);
            let evidence = root.evidence();
            let output = root.fixture(&["write", &input, &evidence, "--interrupt-after", stage]);
            assert_eq!(
                output.status.code(),
                Some(70),
                "{}",
                String::from_utf8_lossy(&output.stderr)
            );
            assert!(root.workspace.join(root.retained(plan)).is_file());
            for index in 0..3 {
                assert_eq!(root.target(plan, index).is_file(), index < count, "{stage}");
                assert_eq!(
                    root.workspace
                        .join(root.snapshot(plan, index + 1))
                        .is_file(),
                    index < receipt_count,
                    "{stage}"
                );
            }
            // A foreign file in the same day is not scanned, adopted or changed.
            let foreign = root
                .target(plan, 0)
                .parent()
                .unwrap()
                .join("unplanned.json");
            fs::create_dir_all(foreign.parent().unwrap()).unwrap();
            fs::write(&foreign, b"unrelated").unwrap();
            let retained = root.retained(plan);
            let (recovered_plan, recovered) =
                parse_success(root.fixture(&["recover", &retained, &evidence]));
            assert_eq!(&recovered_plan, plan);
            assert_completion(&root, plan, &recovered, count);
            for index in count..3 {
                assert!(
                    !root.target(plan, index).exists(),
                    "recovery must not publish unfinished files"
                );
            }
            let (_, retried) = parse_success(root.fixture(&["retry", &retained, &evidence]));
            assert_completion(&root, plan, &retried, 3);
            assert_eq!(fs::read(&foreign).unwrap(), b"unrelated");
            assert_eq!(
                receipts::recover(&prepared, &evidence, &limits()).unwrap(),
                retried
            );
        }
    }
}

#[test]
fn missing_later_receipt_never_erases_an_earlier_completion() {
    let root = TestRoot::new("missing-receipt");
    let prepared = root.prepared(Format::Json, Compression::None);
    let complete = receipts::write(&prepared, &root.evidence(), &limits()).unwrap();
    let first_before = fs::read(root.workspace.join(root.snapshot(prepared.plan(), 1))).unwrap();
    fs::remove_file(root.workspace.join(root.snapshot(prepared.plan(), 3))).unwrap();
    fs::remove_file(root.workspace.join(root.snapshot(prepared.plan(), 2))).unwrap();
    assert_eq!(
        receipts::recover(&prepared, &root.evidence(), &limits()).unwrap(),
        complete
    );
    assert_eq!(
        fs::read(root.workspace.join(root.snapshot(prepared.plan(), 1))).unwrap(),
        first_before
    );
    assert!(
        root.workspace
            .join(root.snapshot(prepared.plan(), 3))
            .is_file()
    );
}

#[test]
fn prior_receipt_promising_missing_file_refuses_instead_of_retrying_it() {
    let root = TestRoot::new("missing-promised");
    let prepared = root.prepared(Format::Parquet, Compression::Snappy);
    receipts::write(&prepared, &root.evidence(), &limits()).unwrap();
    fs::remove_file(root.target(prepared.plan(), 1)).unwrap();
    let failure = receipts::recover(&prepared, &root.evidence(), &limits()).unwrap_err();
    assert!(
        failure.message.contains("promises a missing file"),
        "{}",
        failure.message
    );
    assert!(receipts::write(&prepared, &root.evidence(), &limits()).is_err());
    assert!(!root.target(prepared.plan(), 1).exists());
}

#[test]
fn corrupt_foreign_canonical_hash_and_non_cumulative_prior_receipts_refuse() {
    for kind in [
        "event",
        "identity",
        "membership",
        "logical-hash",
        "count",
        "drop",
        "corrupt",
    ] {
        let root = TestRoot::new(kind);
        let prepared = root.prepared(Format::Json, Compression::None);
        let plan = prepared.plan();
        let completion = receipts::write(&prepared, &root.evidence(), &limits()).unwrap();
        let path = root.snapshot(plan, if kind == "drop" { 2 } else { 3 });
        if kind == "corrupt" {
            fs::write(root.workspace.join(&path), b"{truncated").unwrap();
        } else {
            let mut forged = completion.clone();
            match kind {
                "event" => forged.event_id = Uuid::from_u128(0xbbbbbbbbbbbb4bbb8bbbbbbbbbbbbbbb),
                "identity" => forged.receipt.identity.git_sha = "b".repeat(40),
                "membership" => {
                    forged.receipt.writes.pop_first();
                    forged
                        .receipt
                        .writes
                        .insert(format!("{}/foreign.json", plan.target_root), "0".repeat(64));
                }
                "logical-hash" => {
                    forged.receipt.writes.insert(
                        format!("{}/{}", plan.target_root, plan.files[0].relative_path),
                        plan.files[0].envelope.content_sha256.clone(),
                    );
                }
                "count" => {
                    forged.receipt.writes.pop_first();
                }
                "drop" => {
                    forged.receipt.writes.pop_first();
                }
                _ => unreachable!(),
            }
            root.document(&path, &forged);
        }
        assert!(
            receipts::recover(&prepared, &root.evidence(), &limits()).is_err(),
            "{kind}"
        );
        assert!(
            receipts::write(&prepared, &root.evidence(), &limits()).is_err(),
            "{kind}"
        );
        for index in 0..3 {
            assert!(prepared.verify_existing(index).unwrap().is_some());
        }
    }
}

#[test]
fn corrupt_actual_bytes_same_path_foreign_content_and_inaccessible_types_are_not_unfinished() {
    for (name, format, compression) in [
        ("json", Format::Json, Compression::None),
        ("none", Format::Parquet, Compression::None),
        ("snappy", Format::Parquet, Compression::Snappy),
        ("zstd", Format::Parquet, Compression::Zstd),
    ] {
        let root = TestRoot::new(&format!("corrupt-{name}"));
        let prepared = root.prepared(format, compression);
        let input = root.input(prepared.plan());
        let evidence = root.evidence();
        assert_eq!(
            root.fixture(&[
                "write",
                &input,
                &evidence,
                "--interrupt-after",
                "after-file-0"
            ])
            .status
            .code(),
            Some(70)
        );
        let path = root.target(prepared.plan(), 0);
        let mut bytes = fs::read(&path).unwrap();
        bytes[0] ^= 1;
        fs::write(&path, &bytes).unwrap();
        assert!(receipts::recover(&prepared, &evidence, &limits()).is_err());
        assert!(receipts::write(&prepared, &evidence, &limits()).is_err());
        assert_eq!(fs::read(&path).unwrap(), bytes);
        assert!(!root.target(prepared.plan(), 1).exists());
        fs::write(&path, b"same path, unrelated content").unwrap();
        assert!(receipts::recover(&prepared, &evidence, &limits()).is_err());
        fs::remove_file(&path).unwrap();
        fs::create_dir(&path).unwrap();
        assert!(prepared.verify_existing(0).is_err());
        assert!(receipts::recover(&prepared, &evidence, &limits()).is_err());
    }
}

#[test]
fn immutable_plan_conflicts_foreign_retained_names_and_invalid_last_group_refuse() {
    let root = TestRoot::new("plan-refusal");
    let prepared = root.prepared(Format::Json, Compression::None);
    let input = root.input(prepared.plan());
    let evidence = root.evidence();
    assert_eq!(
        root.fixture(&["write", &input, &evidence, "--interrupt-after", "plan"])
            .status
            .code(),
        Some(70)
    );
    let mut changed = prepared.plan().clone();
    changed.publication_identity.producer = "utilities.other-invocation".to_owned();
    let changed = store::prepare_plan(&root.workspace, changed).unwrap();
    assert!(
        receipts::write(&changed, &evidence, &limits())
            .unwrap_err()
            .message
            .contains("immutable evidence")
    );
    assert!(!root.target(prepared.plan(), 0).exists());
    let retained_path = root.retained(prepared.plan());
    let mut foreign = prepared.plan().clone();
    foreign.event_id = Uuid::from_u128(0xbbbbbbbbbbbb4bbb8bbbbbbbbbbbbbbb);
    root.document(&retained_path, &foreign);
    assert!(receipts::load_plan(&root.workspace, &retained_path, &evidence, &limits()).is_err());
    assert!(receipts::recover(&prepared, &evidence, &limits()).is_err());
    let mut corrupt = serde_json::to_value(prepared.plan()).unwrap();
    corrupt["files"][2]["rows"][0]["cpu_logical_processors"] = json!(0);
    root.document(&input, &corrupt);
    assert!(!root.fixture(&["write", &input, &evidence]).status.success());
    assert!(!root.target(prepared.plan(), 0).exists());
}

#[test]
fn same_file_identity_with_changed_rows_and_corrupt_or_stale_retained_plans_refuse() {
    let root = TestRoot::new("same-identity");
    let prepared = root.prepared(Format::Json, Compression::None);
    let completion = receipts::write(&prepared, &root.evidence(), &limits()).unwrap();
    let first_before = fs::read(root.target(prepared.plan(), 0)).unwrap();
    let mut conflicting = prepared.plan().clone();
    conflicting.files[0].rows[0].host.job_seconds = Some(12);
    conflicting.files[0].envelope.content_sha256 =
        sha256(&rows_bytes(&conflicting.files[0].rows).unwrap());
    assert_eq!(
        conflicting.files[0].envelope.file_id,
        prepared.plan().files[0].envelope.file_id
    );
    let conflicting = store::prepare_plan(&root.workspace, conflicting).unwrap();
    assert!(receipts::write(&conflicting, &root.evidence(), &limits()).is_err());
    assert_eq!(
        fs::read(root.target(prepared.plan(), 0)).unwrap(),
        first_before
    );
    assert_eq!(
        receipts::recover(&prepared, &root.evidence(), &limits()).unwrap(),
        completion
    );

    let retained = root.retained(prepared.plan());
    let mut stale = prepared.plan().clone();
    stale.publication_identity.git_sha = "b".repeat(40);
    for file in &mut stale.files {
        file.envelope.identity.git_sha = "b".repeat(40);
    }
    stale.validate().unwrap();
    root.document(&retained, &stale);
    assert!(receipts::recover(&prepared, &root.evidence(), &limits()).is_err());
    fs::write(root.workspace.join(&retained), b"{corrupt").unwrap();
    assert!(receipts::load_plan(&root.workspace, &retained, &root.evidence(), &limits()).is_err());
    fs::write(
        root.workspace.join(&retained),
        vec![b' '; limits().max_document_bytes + 1],
    )
    .unwrap();
    assert!(receipts::load_plan(&root.workspace, &retained, &root.evidence(), &limits()).is_err());
}

#[test]
fn later_io_failure_and_observer_failure_preserve_actual_completed_evidence() {
    let root = TestRoot::new("partial-io");
    let prepared = root.prepared(Format::Json, Compression::None);
    let mut callback_completion = 0;
    let failure = receipts::write_observed(&prepared, &root.evidence(), &limits(), &mut |stage| {
        if stage == Checkpoint::BeforeFilePublish(1) {
            let blocked = root.target(prepared.plan(), 1).parent().unwrap().to_owned();
            fs::write(blocked, b"real obstruction").unwrap();
        }
        if let Checkpoint::ReceiptPersisted(_) = stage {
            callback_completion += 1;
        }
        Ok(())
    })
    .unwrap_err();
    assert_eq!(callback_completion, 1);
    assert_completion(&root, prepared.plan(), &failure.completion, 1);
    assert!(
        root.workspace
            .join(root.snapshot(prepared.plan(), 1))
            .is_file()
    );
    assert!(!root.target(prepared.plan(), 2).exists());

    let root = TestRoot::new("observer-error");
    let prepared = root.prepared(Format::Parquet, Compression::Zstd);
    let failure = receipts::write_observed(&prepared, &root.evidence(), &limits(), &mut |stage| {
        require(
            stage != Checkpoint::FilePublished(0),
            "observer requested a real stop",
        )
    })
    .unwrap_err();
    assert_eq!(failure.message, "observer requested a real stop");
    assert_completion(&root, prepared.plan(), &failure.completion, 1);
    assert_eq!(
        receipts::recover(&prepared, &root.evidence(), &limits()).unwrap(),
        failure.completion
    );
}

#[test]
fn receipt_io_failure_after_publication_reports_bytes_and_real_recovery_repairs_missing_receipt() {
    let root = TestRoot::new("receipt-io");
    let prepared = root.prepared(Format::Parquet, Compression::None);
    let snapshot = root.workspace.join(root.snapshot(prepared.plan(), 1));
    let failure = receipts::write_observed(&prepared, &root.evidence(), &limits(), &mut |stage| {
        if stage == Checkpoint::BeforeReceiptPersist(0) {
            fs::create_dir(&snapshot).unwrap();
        }
        Ok(())
    })
    .unwrap_err();
    assert!(
        failure.message.contains("filesystem type"),
        "{}",
        failure.message
    );
    assert_completion(&root, prepared.plan(), &failure.completion, 1);
    assert!(!root.target(prepared.plan(), 1).exists());
    fs::remove_dir(&snapshot).unwrap();
    assert_eq!(
        receipts::recover(&prepared, &root.evidence(), &limits()).unwrap(),
        failure.completion
    );
    assert!(snapshot.is_file());
}

#[test]
fn positive_limits_and_separate_evidence_roots_are_checked_before_target_io() {
    let root = TestRoot::new("limits");
    let prepared = root.prepared(Format::Json, Compression::None);
    for bounded in [
        ReceiptLimits {
            max_files: 0,
            ..limits()
        },
        ReceiptLimits {
            max_file_bytes: 0,
            ..limits()
        },
        ReceiptLimits {
            max_total_bytes: 0,
            ..limits()
        },
        ReceiptLimits {
            max_document_bytes: 0,
            ..limits()
        },
        ReceiptLimits {
            max_files: 2,
            ..limits()
        },
        ReceiptLimits {
            max_file_bytes: 1,
            ..limits()
        },
        ReceiptLimits {
            max_total_bytes: 1,
            ..limits()
        },
        ReceiptLimits {
            max_document_bytes: 1,
            ..limits()
        },
    ] {
        assert!(receipts::write(&prepared, &root.evidence(), &bounded).is_err());
    }
    for evidence in [
        prepared.plan().target_root.clone(),
        format!("{}/raw/evidence", prepared.plan().target_root),
        root.relative.clone(),
        "state/evidence".to_owned(),
        "raw/evidence".to_owned(),
        format!("{}/CON", root.relative),
    ] {
        assert!(
            receipts::write(&prepared, &evidence, &limits()).is_err(),
            "{evidence}"
        );
    }
    #[cfg(windows)]
    for evidence in [
        format!("{}/STATE/evidence", root.relative),
        "STATE/evidence".to_owned(),
        "RAW/evidence".to_owned(),
    ] {
        assert!(
            receipts::write(&prepared, &evidence, &limits()).is_err(),
            "{evidence}"
        );
    }
    assert!(!root.workspace.join(&prepared.plan().target_root).exists());
    assert!(!root.workspace.join(root.retained(prepared.plan())).exists());
}

#[cfg(unix)]
fn directory_link(target: &Path, link: &Path) {
    std::os::unix::fs::symlink(target, link).unwrap();
}
#[cfg(windows)]
fn directory_link(target: &Path, link: &Path) {
    match std::os::windows::fs::symlink_dir(target, link) {
        Ok(()) => {}
        Err(error) if error.raw_os_error() == Some(1314) => {
            eprintln!(
                "Directory symlinks unavailable (Windows error 1314); testing a real junction."
            );
            let quote = |path: &Path| {
                path.to_str()
                    .unwrap()
                    .trim_start_matches(r"\\?\")
                    .replace('\'', "''")
            };
            let output = Command::new("powershell.exe").args(["-NoProfile", "-NonInteractive", "-Command"])
                .arg(format!(
                    "$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path '{}' -Target '{}' | Out-Null",
                    quote(link), quote(target),
                )).output().unwrap();
            assert!(
                output.status.success(),
                "{}",
                String::from_utf8_lossy(&output.stderr)
            );
        }
        Err(error) => panic!("real directory link failed: {error}"),
    }
}
#[cfg(any(unix, windows))]
fn unlink_directory(link: &Path) {
    #[cfg(unix)]
    fs::remove_file(link).unwrap();
    #[cfg(windows)]
    fs::remove_dir(link).unwrap();
}

#[test]
#[cfg(any(unix, windows))]
fn real_evidence_root_aliases_and_escaping_document_parents_refuse() {
    let root = TestRoot::new("links");
    let prepared = root.prepared(Format::Json, Compression::None);
    let state = root.workspace.join(&prepared.plan().target_root);
    fs::create_dir_all(&state).unwrap();
    let evidence = root.root.join("evidence");
    directory_link(&fs::canonicalize(&state).unwrap(), &evidence);
    assert!(receipts::write(&prepared, &root.evidence(), &limits()).is_err());
    unlink_directory(&evidence);
    assert!(!root.target(prepared.plan(), 0).exists());

    let workspace = root.root.join("workspace");
    let outside = root.root.join("outside");
    fs::create_dir(&workspace).unwrap();
    fs::create_dir(&outside).unwrap();
    let link = workspace.join("evidence");
    directory_link(&fs::canonicalize(&outside).unwrap(), &link);
    assert!(paths::resolve_document(&workspace, "evidence/plan.json").is_err());
    unlink_directory(&link);

    for reserved in ["state", "raw"] {
        let backing = workspace.join(format!("real-{reserved}"));
        fs::create_dir(&backing).unwrap();
        let reserved_path = workspace.join(reserved);
        directory_link(&fs::canonicalize(&backing).unwrap(), &reserved_path);
        let mut plan = prepared.plan().clone();
        plan.target_root = "different-target".to_owned();
        let isolated = store::prepare_plan(&workspace, plan).unwrap();
        assert!(receipts::write(&isolated, &format!("{reserved}/evidence"), &limits()).is_err());
        assert!(
            receipts::write(&isolated, &format!("real-{reserved}/evidence"), &limits()).is_err()
        );
        assert!(!backing.join("evidence").exists());
        unlink_directory(&reserved_path);
    }
}

#[test]
#[cfg(any(unix, windows))]
fn leaf_document_and_planned_file_links_are_explicitly_refused_not_followed() {
    let root = TestRoot::new("leaf-link");
    let prepared = root.prepared(Format::Json, Compression::None);
    let input = root.input(prepared.plan());
    let evidence = root.evidence();
    assert_eq!(
        root.fixture(&["write", &input, &evidence, "--interrupt-after", "plan"])
            .status
            .code(),
        Some(70)
    );
    let retained = root.workspace.join(root.retained(prepared.plan()));
    let real = root.root.join("original-plan.json");
    fs::rename(&retained, &real).unwrap();
    #[cfg(unix)]
    std::os::unix::fs::symlink(&real, &retained).unwrap();
    #[cfg(windows)]
    let retained_is_directory_link = match std::os::windows::fs::symlink_file(&real, &retained) {
        Ok(()) => false,
        Err(error) if error.raw_os_error() == Some(1314) => {
            eprintln!(
                "Leaf file symlinks unavailable (Windows error 1314); testing a leaf junction refusal."
            );
            directory_link(&fs::canonicalize(&root.root).unwrap(), &retained);
            true
        }
        Err(error) => panic!("real file symlink failed: {error}"),
    };
    assert!(paths::resolve_document(&root.workspace, &root.retained(prepared.plan())).is_err());
    assert!(receipts::recover(&prepared, &evidence, &limits()).is_err());
    #[cfg(unix)]
    fs::remove_file(&retained).unwrap();
    #[cfg(windows)]
    if retained_is_directory_link {
        fs::remove_dir(&retained).unwrap();
    } else {
        fs::remove_file(&retained).unwrap();
    }
    fs::rename(&real, &retained).unwrap();
    let destination = root.target(prepared.plan(), 0);
    fs::create_dir_all(destination.parent().unwrap()).unwrap();
    #[cfg(unix)]
    std::os::unix::fs::symlink(&real, &destination).unwrap();
    #[cfg(windows)]
    {
        directory_link(&fs::canonicalize(&root.root).unwrap(), &destination);
    }
    assert!(prepared.verify_existing(0).is_err());
    assert!(receipts::recover(&prepared, &evidence, &limits()).is_err());
    #[cfg(unix)]
    fs::remove_file(&destination).unwrap();
    #[cfg(windows)]
    fs::remove_dir(&destination).unwrap();
}
