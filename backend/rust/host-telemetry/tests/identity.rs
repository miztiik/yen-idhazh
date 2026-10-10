pub use idhazh_host_telemetry::{canonical_json, contracts};
#[path = "../src/ledger/filenames.rs"]
mod filenames;
#[path = "../src/ledger/identity.rs"]
mod identity;

use contracts::file_envelope::HostWriterIdentity;
use contracts::host::{
    CorrectedHostFingerprintRow, HOST_PRODUCER, HostStoredRow, QuotaState, ServerJob, Validate,
};
use serde_json::json;

fn writer(attempt: i64) -> HostWriterIdentity {
    serde_json::from_value(json!({
        "run_id": "2026-10-10-42", "attempt": attempt, "job": "work", "shard": 0,
        "producer": HOST_PRODUCER, "git_sha": "a".repeat(40)
    }))
    .unwrap()
}

fn host() -> CorrectedHostFingerprintRow {
    let mut row: CorrectedHostFingerprintRow = serde_json::from_value(json!({
        "date": "2026-10-10", "run_id": "2026-10-10-42", "shard": 0,
        "cpu_vendor": "GenuineIntel", "cpu_logical_processors": 4, "cpu_physical_cores": 2,
        "cpu_observed_mhz": 1200.0, "measured_at": "2026-10-10T12:00:00Z"
    }))
    .unwrap();
    row.fingerprint = row.fingerprint_v2().unwrap();
    row.fingerprint_version = Some(2);
    row.validate().unwrap();
    row
}

#[test]
fn stamping_preserves_every_cell_and_only_adds_missing_rank() {
    let row = host();
    let original = canonical_json::rows_bytes(std::slice::from_ref(&row)).unwrap();
    let stored = identity::stamp(&row, &writer(2)).unwrap();
    assert_eq!(stored.host, row);
    assert_eq!(stored.ledger, "host-fingerprint");
    assert_eq!(stored.covers, row.date);
    assert_eq!(stored.attempt, 2);
    assert_eq!(
        stored.unit_id.to_string(),
        "4f918a28-1fa6-5125-98d6-98e1cf8e1d15"
    );
    assert_eq!(
        canonical_json::rows_bytes(std::slice::from_ref(&row)).unwrap(),
        original
    );
    assert_eq!(identity::preserve(&stored, &writer(2)).unwrap(), stored);
    let mut legacy = row.clone();
    legacy.fingerprint_version = Some(1);
    legacy.fingerprint = Some("0123456789abcdef".to_owned());
    assert_eq!(identity::stamp(&legacy, &writer(2)).unwrap().host, legacy);
}

#[test]
fn foreign_invocations_producers_invalid_rows_and_existing_ranks_are_refused() {
    let row = host();
    for foreign in [
        HostWriterIdentity {
            run_id: "2026-10-10-43".to_owned(),
            ..writer(2)
        },
        HostWriterIdentity {
            job: ServerJob::Runtime,
            ..writer(2)
        },
        HostWriterIdentity {
            shard: 1,
            ..writer(2)
        },
        HostWriterIdentity {
            producer: "idhazh_rust.ledger.parquet".to_owned(),
            ..writer(2)
        },
        HostWriterIdentity {
            attempt: 0,
            ..writer(2)
        },
        HostWriterIdentity {
            git_sha: "BAD".to_owned(),
            ..writer(2)
        },
    ] {
        assert!(identity::stamp(&row, &foreign).is_err());
    }
    let mut invalid = row.clone();
    invalid.date = "2026-02-29".to_owned();
    assert!(identity::stamp(&invalid, &writer(2)).is_err());
    invalid = row.clone();
    invalid.cpu_observed_mhz = Some(f64::NAN);
    assert!(identity::stamp(&invalid, &writer(2)).is_err());
    let stored = identity::stamp(&row, &writer(2)).unwrap();
    assert!(identity::preserve(&stored, &writer(3)).is_err());
    let mut foreign = stored.clone();
    foreign.unit_id = uuid::Uuid::nil();
    assert!(identity::preserve(&foreign, &writer(2)).is_err());
    let mut wrong_day = stored.clone();
    wrong_day.covers = "2026-10-09".to_owned();
    assert!(identity::preserve(&wrong_day, &writer(2)).is_err());
    let mut wrong_ledger = stored;
    wrong_ledger.ledger = "item-health".to_owned();
    assert!(identity::preserve(&wrong_ledger, &writer(2)).is_err());
}

#[test]
fn probe_target_clock_share_units_but_changed_files_need_an_actual_clock() {
    let probe = host();
    let mut target = probe.clone();
    target.cpu_allowed_processors = Some(3);
    target.cpu_quota_cores = Some(0.5);
    target.cpu_quota_state = Some(QuotaState::Finite);
    target.cpu_target_measured_at = Some("2026-10-10T12:00:01Z".to_owned());
    let mut clock = target.clone();
    clock.job_seconds = Some(3);
    clock.model_load_ms = Some(1.25);
    clock.server_prompt_tokens = Some(17);
    clock.server_prompt_seconds = Some(0.2);
    let a = identity::stamp(&probe, &writer(1)).unwrap();
    let b = identity::stamp(&target, &writer(1)).unwrap();
    let c = identity::stamp(&clock, &writer(2)).unwrap();
    assert_eq!(a.unit_id, b.unit_id);
    assert_eq!(a.unit_id, c.unit_id);
    assert_eq!(a.host.fingerprint, c.host.fingerprint);
    assert_eq!(a.host.measured_at, c.host.measured_at);
    // Different payloads alone cannot change a file ID at the same write clock.
    assert_eq!(
        filenames::file_id(a.unit_id, a.attempt, 1791633600123).unwrap(),
        filenames::file_id(b.unit_id, b.attempt, 1791633600123).unwrap()
    );
    assert_ne!(
        filenames::file_id(a.unit_id, a.attempt, 1791633600123).unwrap(),
        filenames::file_id(c.unit_id, c.attempt, 1791633600123).unwrap()
    );
}

#[test]
fn highest_attempts_and_order_do_not_depend_on_input_order() {
    let row = host();
    let first = identity::stamp(&row, &writer(1)).unwrap();
    let mut newer_host = row.clone();
    newer_host.job_seconds = Some(9);
    let newest = identity::stamp(&newer_host, &writer(3)).unwrap();
    let mut prior_day = row.clone();
    prior_day.date = "2024-02-29".to_owned();
    let prior = identity::stamp(&prior_day, &writer(2)).unwrap();
    let other_writer = HostWriterIdentity {
        shard: 1,
        ..writer(2)
    };
    let other_host = CorrectedHostFingerprintRow { shard: 1, ..row };
    let other = identity::stamp(&other_host, &other_writer).unwrap();
    let mut rows = vec![
        first,
        newest.clone(),
        other.clone(),
        newest.clone(),
        prior.clone(),
    ];
    let expected = vec![prior, newest, other];
    assert_eq!(identity::settle(&rows).unwrap(), expected);
    rows.reverse();
    assert_eq!(identity::settle(&rows).unwrap(), expected);
    assert!(identity::settle(&[]).unwrap().is_empty());
}

#[test]
fn equal_rank_conflicts_cannot_be_hidden_by_input_order_or_later_attempts() {
    let row = host();
    let first = identity::stamp(&row, &writer(1)).unwrap();
    let mut changed: HostStoredRow = first.clone();
    changed.host.job_seconds = Some(3);
    let later = identity::stamp(&row, &writer(2)).unwrap();
    for rows in [
        vec![first.clone(), changed.clone()],
        vec![changed.clone(), first.clone()],
        vec![first.clone(), changed, later],
    ] {
        assert!(identity::settle(&rows).is_err());
    }
    let mut positive_zero = first.clone();
    positive_zero.host.boot_seconds = Some(0.0);
    let mut negative_zero = positive_zero.clone();
    negative_zero.host.boot_seconds = Some(-0.0);
    assert!(identity::settle(&[positive_zero, negative_zero]).is_err());
    let mut invalid = first;
    invalid.attempt = 0;
    assert!(identity::settle(&[invalid]).is_err());
}
