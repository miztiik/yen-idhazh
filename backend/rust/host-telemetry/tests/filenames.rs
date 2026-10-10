pub use idhazh_host_telemetry::contracts;
#[path = "../src/ledger/filenames.rs"]
mod filenames;

use contracts::host::ServerJob;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use uuid::{Uuid, Variant};

#[test]
fn exact_python_uuid5_namespace_and_host_seeds() {
    // These vectors come from the named Python ledger filename owner.
    for (covers, run, job, shard, expected) in [
        (
            "2026-10-10",
            "2026-10-10-42",
            ServerJob::Work,
            0,
            "4f918a28-1fa6-5125-98d6-98e1cf8e1d15",
        ),
        (
            "2024-02-29",
            "2026-10-10-42",
            ServerJob::RunTasks,
            123,
            "7d7329b3-61e2-5708-ab3a-3edd5a495d12",
        ),
        (
            "2026-10-10",
            "2026-10-10-0042",
            ServerJob::SaveCouncilResults,
            i64::MAX,
            "bfed04d8-8bd4-5a14-9282-99060cb0dcc9",
        ),
    ] {
        let unit = filenames::unit_id(covers, run, job, shard).unwrap();
        assert_eq!(unit.to_string(), expected);
        assert_eq!(unit.get_version_num(), 5);
        assert_eq!(unit.get_variant(), Variant::RFC4122);
    }
}

#[test]
fn exact_python_uuid8_vectors_keep_clock_hash_bits_and_low_48_bit_mask() {
    let unit = Uuid::parse_str("4f918a28-1fa6-5125-98d6-98e1cf8e1d15").unwrap();
    for (attempt, clock, expected) in [
        (1, 0, "00000000-0000-8abb-b12a-c107e1bc1736"),
        (2, 1791633600123, "01a125af-2e7b-8945-899b-fa46f230ac97"),
        (2, 1791633600124, "01a125af-2e7c-807a-a7e3-a871758d41cb"),
        (i64::MAX, i64::MAX, "ffffffff-ffff-88b4-8dce-a9a155f56e20"),
        (1, 1_i64 << 48, "00000000-0000-8220-afcb-bb09c17885c5"),
    ] {
        let file = filenames::file_id(unit, attempt, clock).unwrap();
        assert_eq!(file.to_string(), expected);
        assert_eq!(file.get_version_num(), 8);
        assert_eq!(file.get_variant(), Variant::RFC4122);
        assert_eq!(file.as_u128() >> 80, (clock as u128) & ((1 << 48) - 1));
    }
}

#[test]
fn invalid_scalars_calendar_days_and_non_rfc_units_are_refused() {
    for covers in [
        "2026-02-29",
        "2026-04-31",
        "0000-01-01",
        "2026-1-01",
        "2026-10-10\n",
    ] {
        assert!(filenames::unit_id(covers, "2026-10-10-42", ServerJob::Work, 0).is_err());
    }
    for run in [
        "",
        "2026-02-29-42",
        "2026-10-10",
        "2026-10-10--1",
        "2026-10-10-42\n",
        "2026-10-10-42|operator",
    ] {
        assert!(filenames::unit_id("2026-10-10", run, ServerJob::Work, 0).is_err());
    }
    assert!(filenames::unit_id("2026-10-10", "2026-10-10-42", ServerJob::Work, -1).is_err());
    let unit = filenames::unit_id("2026-10-10", "2026-10-10-42", ServerJob::Work, 0).unwrap();
    for (bad_unit, attempt, clock) in [
        (unit, 0, 0),
        (unit, -1, 0),
        (unit, 1, -1),
        (Uuid::nil(), 1, 0),
        (Uuid::from_u128(unit.as_u128() & !(3 << 62)), 1, 0),
    ] {
        assert!(filenames::file_id(bad_unit, attempt, clock).is_err());
    }
}

fn actual_ms() -> i64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis()
        .try_into()
        .unwrap()
}

#[test]
fn actual_millisecond_ordering_and_same_clock_collision_rules() {
    let unit = filenames::unit_id("2026-10-10", "2026-10-10-42", ServerJob::Work, 0).unwrap();
    let other_unit = filenames::unit_id("2026-10-10", "2026-10-10-42", ServerJob::Work, 1).unwrap();
    let clock = actual_ms();
    let file = filenames::file_id(unit, 1, clock).unwrap();
    assert_eq!(file, filenames::file_id(unit, 1, clock).unwrap());
    assert_ne!(file, filenames::file_id(unit, 2, clock).unwrap());
    assert_ne!(file, filenames::file_id(other_unit, 1, clock).unwrap());
    let started = Instant::now();
    let later = loop {
        let observed = actual_ms();
        if observed > clock {
            break observed;
        }
        assert!(
            started.elapsed() < Duration::from_secs(2),
            "write clock did not advance"
        );
        std::thread::sleep(Duration::from_millis(1));
    };
    let later_file = filenames::file_id(unit, 1, later).unwrap();
    assert!(file < later_file);
    assert!(file.to_string() < later_file.to_string());
    assert_eq!(file.as_u128() >> 80, clock as u128);
    assert_eq!(later_file.as_u128() >> 80, later as u128);
}
