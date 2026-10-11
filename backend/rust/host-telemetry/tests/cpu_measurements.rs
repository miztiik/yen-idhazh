//! Do independent OS edge cases preserve valid CPU readings and diagnose incomplete constraints?

mod support;
use idhazh_host_telemetry::contracts::{events::*, host::*};
use idhazh_host_telemetry::probe_inputs::{
    allowance::{self, Controller},
    cpu,
    files::Reading,
    frequency, topology,
};
use support::found;

fn row() -> CorrectedHostFingerprintRow {
    serde_json::from_str(r#"{"date":"2026-10-10","run_id":"2026-10-10-17","shard":0,"measured_at":"2026-10-10T12:00:00Z"}"#).unwrap()
}
#[test]
fn sparse_smt_multiple_sockets_partial_frequency_and_fractional_quota() {
    let replay = support::replay();
    let c = &replay.attempts[0];
    let limits = support::manifest().capture_limits;
    let mut row = row();
    let mut diag = cpu::measure(&mut row, c, &limits);
    assert_eq!(diag.online_cpu_ids, [0, 2, 3, 7]);
    assert_eq!(
        (row.cpu_physical_cores, row.cpu_logical_processors),
        (Some(3), Some(4))
    );
    assert_eq!(row.cpu_observed_mhz, Some(2400.0));
    assert_eq!(row.cpu_reported_max_mhz, Some(3600.0));
    assert_eq!(
        (
            diag.source(CaptureSource::Cpuinfo).unwrap().observed,
            diag.source(CaptureSource::Cpuinfo).unwrap().status
        ),
        (3, CoverageStatus::Partial)
    );
    cpu::target(
        &mut row,
        &mut diag,
        c,
        &ProcessTarget {
            pid: 100,
            start_ticks: 800,
        },
        "2026-10-10T12:00:01Z",
        &limits,
    );
    assert_eq!(row.cpu_allowed_processors, Some(2));
    assert_eq!(row.cpu_quota_cores, Some(0.5));
    assert_eq!(row.cpu_quota_state, Some(QuotaState::Finite));
    HostResultBody {
        row,
        cpu: diag,
        completion_event_ids: vec![uuid::Uuid::from_u128(1)],
    }
    .validate()
    .unwrap();
}
#[test]
fn cpulists_reject_duplicate_overlapping_out_of_inventory_and_overflow() {
    let limits = support::manifest().capture_limits;
    for text in [
        "0,0",
        "0-2,2-3",
        "3-2",
        "-1",
        "1-",
        "4096",
        "0-999999999999999999999",
        "true",
        "1.5",
        "0, 2",
        "",
    ] {
        assert!(topology::cpu_list(text, &limits).is_err(), "{text}");
    }
    assert!(topology::online(&found("0,9"), &found("0-7"), &limits).is_err());
    let mut bounded = limits.clone();
    bounded.max_cpu_ids = 2;
    assert!(topology::cpu_list("0-3", &bounded).is_err());
}
#[test]
fn topology_is_complete_nonnegative_and_consistent_not_a_clock_count() {
    let mut c = support::replay().attempts.remove(0);
    let limits = support::manifest().capture_limits;
    c.cpuinfo = found("processor : 0\ncpu MHz : nan\n");
    let mut r = row();
    cpu::measure(&mut r, &c, &limits);
    assert_eq!(
        (
            r.cpu_physical_cores,
            r.cpu_logical_processors,
            r.cpu_observed_mhz
        ),
        (Some(3), Some(4), None)
    );
    for mode in 0..5 {
        let mut c = c.clone();
        match mode {
            0 => {
                c.topology.pop();
            }
            1 => c.topology[0].package = found("-1"),
            2 => c.topology[1].thread_siblings = found("2"),
            3 => {
                c.topology.push(c.topology[0].clone());
            }
            _ => c.topology[0].package_siblings = found("0,7"),
        }
        cpu::measure(&mut r, &c, &limits);
        assert_eq!(r.cpu_physical_cores, None);
        assert_eq!(r.cpu_logical_processors, Some(4));
    }
}
#[test]
fn frequency_rejects_duplicates_nonfinite_and_incomplete_hardware_policies() {
    let c = support::replay().attempts.remove(0);
    let limits = support::manifest().capture_limits;
    for text in [
        "processor : 0\ncpu MHz : 2000\nprocessor : 0\ncpu MHz : 3000\n",
        "processor : x\ncpu MHz : 2000\n",
    ] {
        assert!(frequency::observed(&found(text), &[0, 2, 3, 7]).is_err());
    }
    assert_eq!(frequency::observed(&found("processor : 0\ncpu MHz : 2000\nprocessor : 2\ncpu MHz : inf\nprocessor : 7\ncpu MHz : -1"),&[0,2,3,7]).unwrap(),(Some(2000.0),1));
    for mode in 0..4 {
        let mut policies = c.policies.clone();
        let p = policies.value.as_mut().unwrap();
        match mode {
            0 => {
                p.pop();
            }
            1 => p[1].cpus = found("0 7"),
            2 => p[0].maximum_khz = found("NaN"),
            _ => p[0].maximum_khz = found("0"),
        }
        assert!(frequency::reported(&policies, &[0, 2, 3, 7], &limits).is_err());
    }
}
#[test]
fn v2_nested_unlimited_missing_and_hidden_ancestry_are_distinct() {
    let c = support::replay().attempts.remove(0);
    let limits = support::manifest().capture_limits;
    let base = c.target_before.unwrap();
    let mut target = base.clone();
    target.constraints.value.as_mut().unwrap()[1].quota = found("25000 100000");
    assert_eq!(
        allowance::quota(&target, &limits).unwrap(),
        (Some(0.25), QuotaState::Finite)
    );
    for entry in target
        .constraints
        .value
        .as_mut()
        .unwrap()
        .iter_mut()
        .filter(|v| !v.root)
    {
        entry.quota = found("max 100000");
    }
    assert_eq!(
        allowance::quota(&target, &limits).unwrap(),
        (None, QuotaState::Unlimited)
    );
    for text in ["0 100000", "max 0", "max", "-1 100000", "50000.5 100000"] {
        target.constraints.value.as_mut().unwrap()[0].quota = found(text);
        assert!(allowance::quota(&target, &limits).is_err());
    }
    target = base.clone();
    target.constraints.value.as_mut().unwrap()[1].quota =
        Reading::absent(UnavailableReason::PermissionDenied);
    assert_eq!(
        allowance::quota(&target, &limits),
        Err(UnavailableReason::PermissionDenied)
    );
    target = base;
    target.mountinfo = found("29 23 0:26 /slice /sys/fs/cgroup rw - cgroup2 cgroup rw\n");
    assert_eq!(
        allowance::quota(&target, &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
}
#[test]
fn v1_inherits_empty_cpuset_and_takes_minimum_fractional_quota_across_all_ancestors() {
    let c = support::replay().attempts.remove(0);
    let limits = support::manifest().capture_limits;
    let mut target = c.target_before.unwrap();
    target.cgroup = found("4:cpu,cpuacct:/slice/job\n3:cpuset:/slice/job\n");
    target.mountinfo = found(
        "29 23 0:26 / /sys/fs/cpu rw - cgroup cgroup rw,cpu,cpuacct\n30 23 0:27 / /sys/fs/cpuset rw - cgroup cgroup rw,cpuset\n",
    );
    let scopes = allowance::scopes(
        target.cgroup.value.as_ref().unwrap(),
        target.mountinfo.value.as_ref().unwrap(),
        &limits,
    )
    .unwrap();
    let original = target.constraints.value.unwrap()[0].clone();
    target.constraints = Reading::found(
        scopes
            .into_iter()
            .map(|s| {
                let mut r = original.clone();
                r.root_evidence = support::recorded_root(&s);
                r.controller = s.controller;
                r.directory = s.directory;
                r.root = s.root;
                r.cpuset = found(if r.root {
                    "0-7"
                } else if r.directory.ends_with("job") {
                    ""
                } else {
                    "0,2,7"
                });
                r.quota = found(if r.root {
                    "-1"
                } else if r.directory.ends_with("job") {
                    "150000"
                } else {
                    "75000"
                });
                r.period = found("100000");
                r
            })
            .collect(),
    );
    assert_eq!(
        allowance::allowed(&target, &[0, 2, 3, 7], &limits).unwrap(),
        2
    );
    assert_eq!(
        allowance::quota(&target, &limits).unwrap(),
        (Some(0.75), QuotaState::Finite)
    );
    assert!(
        target
            .constraints
            .value
            .as_ref()
            .unwrap()
            .iter()
            .any(|r| r.controller == Controller::Cpuset)
    );
    for r in target.constraints.value.as_mut().unwrap() {
        r.quota = found("-1");
    }
    assert_eq!(
        allowance::quota(&target, &limits).unwrap(),
        (None, QuotaState::Unlimited)
    );
}
#[test]
fn verified_absent_controllers_are_unrestricted_but_empty_masks_are_not() {
    let c = support::replay().attempts.remove(0);
    let limits = support::manifest().capture_limits;
    let mut target = c.target_before.unwrap();
    target.cgroup = found("1:name=systemd:/job\n");
    target.mountinfo = found("1 0 0:1 / / rw - tmpfs tmpfs rw\n");
    target.constraints = Reading::found(vec![]);
    assert_eq!(
        allowance::allowed(&target, &[0, 2, 3, 7], &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
    assert_eq!(
        allowance::quota(&target, &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
    target.affinity = Reading::found(vec![1]);
    assert!(allowance::allowed(&target, &[0, 2, 3, 7], &limits).is_err());
}
#[test]
fn hotplug_affinity_races_and_pid_reuse_do_not_erase_independent_hardware_or_quota() {
    let base = support::replay().attempts.remove(0);
    let limits = support::manifest().capture_limits;
    for mode in 0..4 {
        let mut c = base.clone();
        let mut r = row();
        let mut diag = cpu::measure(&mut r, &c, &limits);
        match mode {
            0 => c.online_after = found("0,2-3"),
            1 => c.target_after.as_mut().unwrap().affinity = Reading::found(vec![2]),
            2 => c.target_after.as_mut().unwrap().start_ticks = Reading::found(801),
            _ => {
                c.target_after
                    .as_mut()
                    .unwrap()
                    .constraints
                    .value
                    .as_mut()
                    .unwrap()[0]
                    .quota = found("75000 100000")
            }
        }
        cpu::target(
            &mut r,
            &mut diag,
            &c,
            &ProcessTarget {
                pid: 100,
                start_ticks: 800,
            },
            "2026-10-10T12:00:01Z",
            &limits,
        );
        assert_eq!(r.cpu_logical_processors, Some(4));
        if mode < 2 {
            assert_eq!(r.cpu_allowed_processors, None);
            assert_eq!(r.cpu_quota_cores, Some(0.5));
        }
        if mode == 2 {
            assert_eq!(r.cpu_quota_state, Some(QuotaState::Unavailable));
            assert_eq!(
                diag.source(CaptureSource::Quota).unwrap().reason,
                Some(UnavailableReason::PidReused)
            );
        }
        if mode == 3 {
            assert_eq!(r.cpu_allowed_processors, Some(2));
            assert_eq!(r.cpu_quota_cores, None);
        }
    }
}

#[test]
fn hybrid_quota_and_cpuset_constraints_both_apply_and_empty_inheritance_is_not_unrestricted() {
    let capture = support::replay().attempts.remove(0);
    let limits = support::manifest().capture_limits;
    let mut target = capture.target_before.unwrap();
    target.cgroup = found("0::/slice/job\n4:cpu:/job\n3:cpuset:/job\n");
    target.mountinfo = found(
        "29 23 0:26 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n30 23 0:27 / /cpu rw - cgroup cgroup rw,cpu\n31 23 0:28 / /cpuset rw - cgroup cgroup rw,cpuset\n",
    );
    let expected = allowance::scopes(
        target.cgroup.value.as_ref().unwrap(),
        target.mountinfo.value.as_ref().unwrap(),
        &limits,
    )
    .unwrap();
    let original = target.constraints.value.as_ref().unwrap()[0].clone();
    let mut rows = target.constraints.value.clone().unwrap();
    for scope in expected
        .into_iter()
        .filter(|s| s.controller != Controller::V2)
    {
        let mut row = original.clone();
        row.root_evidence = support::recorded_root(&scope);
        row.controller = scope.controller;
        row.directory = scope.directory;
        row.root = scope.root;
        row.quota = found(if row.root { "-1" } else { "12500" });
        row.period = found("100000");
        row.cpuset = found("0,2,7");
        rows.push(row);
    }
    target.constraints = Reading::found(rows);
    assert_eq!(
        allowance::quota(&target, &limits).unwrap(),
        (Some(0.125), QuotaState::Finite)
    );
    assert_eq!(
        allowance::allowed(&target, &[0, 2, 3, 7], &limits).unwrap(),
        2
    );
    for row in target
        .constraints
        .value
        .as_mut()
        .unwrap()
        .iter_mut()
        .filter(|r| r.controller == Controller::Cpuset)
    {
        row.cpuset = found("");
    }
    assert!(allowance::allowed(&target, &[0, 2, 3, 7], &limits).is_err());
    target.constraints.value.as_mut().unwrap()[0].cpuset = found("0,1,2,7");
    assert!(allowance::allowed(&target, &[0, 2, 3, 7], &limits).is_err());
}

#[test]
fn one_bounded_retry_can_recover_but_another_race_nulls_only_affected_sources() {
    let mut replay = support::replay();
    let limits = support::manifest().capture_limits;
    let stable = replay.attempts[0].clone();
    replay.attempts[0].online_after = found("0,2,3");
    replay.attempts.push(stable.clone());
    assert_eq!(replay.selected(&limits).unwrap(), &stable);
    replay.attempts[1].online_after = found("0,2,3");
    let selected = replay.selected(&limits).unwrap();
    let mut r = row();
    let mut diag = cpu::measure(&mut r, selected, &limits);
    cpu::target(
        &mut r,
        &mut diag,
        selected,
        &ProcessTarget {
            pid: 100,
            start_ticks: 800,
        },
        "2026-10-10T12:00:01Z",
        &limits,
    );
    assert_eq!(r.cpu_logical_processors, None);
    assert_eq!(r.cpu_physical_cores, None);
    assert_eq!(r.cpu_observed_mhz, None);
    assert_eq!(r.cpu_reported_max_mhz, None);
    assert_eq!(r.cpu_quota_cores, Some(0.5));
    assert_eq!(
        diag.source(CaptureSource::Online).unwrap().reason,
        Some(UnavailableReason::SnapshotChanged)
    );
    replay.attempts.push(stable);
    assert!(replay.selected(&limits).is_err());
}
