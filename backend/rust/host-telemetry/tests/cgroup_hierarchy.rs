//! Do raw structural root records distinguish actual roots from namespace-hidden ancestry?

mod support;
use idhazh_host_telemetry::contracts::{events::*, host::QuotaState};
use idhazh_host_telemetry::probe_inputs::{
    allowance::{self, TargetCapture},
    cpu,
    files::Reading,
    hierarchy::{self, Lookup},
    snapshots,
};
use support::found;

fn target() -> TargetCapture {
    support::replay().attempts.remove(0).target_before.unwrap()
}
fn root(target: &mut TargetCapture) -> &mut hierarchy::RootEvidence {
    target
        .constraints
        .value
        .as_mut()
        .unwrap()
        .last_mut()
        .unwrap()
        .root_evidence
        .as_mut()
        .unwrap()
}
#[test]
fn same_slash_mount_and_namespace_context_do_not_prove_hidden_ancestry() {
    let limits = support::manifest().capture_limits;
    let actual = target();
    assert_eq!(
        allowance::quota(&actual, &limits).unwrap(),
        (Some(0.5), QuotaState::Finite)
    );
    let mut hidden = actual.clone();
    root(&mut hidden).marker = root(&mut hidden).cgroup_procs.clone();
    assert_eq!(hidden.cgroup, actual.cgroup);
    assert_eq!(hidden.mountinfo, actual.mountinfo);
    assert_eq!(hidden.source_context, actual.source_context);
    assert_eq!(
        allowance::quota(&hidden, &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
    for row in hidden
        .constraints
        .value
        .as_mut()
        .unwrap()
        .iter_mut()
        .filter(|r| !r.root)
    {
        row.quota = found("max 100000");
    }
    assert_eq!(
        allowance::quota(&hidden, &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
    for row in hidden
        .constraints
        .value
        .as_mut()
        .unwrap()
        .iter_mut()
        .filter(|r| !r.root)
    {
        row.quota = found("50000 100000");
    }
    assert_eq!(
        allowance::quota(&hidden, &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
}
#[test]
fn finite_ancestor_and_unlimited_require_positive_complete_root_coverage() {
    let limits = support::manifest().capture_limits;
    let mut t = target();
    let rows = t.constraints.value.as_mut().unwrap();
    rows[0].quota = found("max 100000");
    rows[1].quota = found("25000 100000");
    assert_eq!(
        allowance::quota(&t, &limits).unwrap(),
        (Some(0.25), QuotaState::Finite)
    );
    t.constraints.value.as_mut().unwrap()[1].quota = found("max 100000");
    assert_eq!(
        allowance::quota(&t, &limits).unwrap(),
        (None, QuotaState::Unlimited)
    );
    t.constraints.value.as_mut().unwrap()[2].root_evidence = None;
    assert_eq!(
        allowance::quota(&t, &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
}
#[test]
fn missing_denied_wrong_filesystem_substituted_mount_and_wrong_core_entry_refuse() {
    let limits = support::manifest().capture_limits;
    for mode in 0..9 {
        let mut t = target();
        let expected = match mode {
            0 => {
                root(&mut t).marker = Lookup::Failed(UnavailableReason::Missing);
                UnavailableReason::Missing
            }
            1 => {
                root(&mut t).marker = Lookup::Failed(UnavailableReason::PermissionDenied);
                UnavailableReason::PermissionDenied
            }
            2 => {
                root(&mut t)
                    .directory
                    .value
                    .as_mut()
                    .unwrap()
                    .filesystem_type = 0x01021994;
                UnavailableReason::IncompleteCoverage
            }
            3 => {
                root(&mut t).directory.value.as_mut().unwrap().mount_id += 1;
                UnavailableReason::IncompleteCoverage
            }
            4 => {
                root(&mut t).directory.value.as_mut().unwrap().minor += 1;
                UnavailableReason::IncompleteCoverage
            }
            5 => {
                root(&mut t).cgroup_procs = Lookup::ExactEnoent;
                UnavailableReason::IncompleteCoverage
            }
            6 => {
                if let Lookup::Present(p) = &mut root(&mut t).cgroup_procs {
                    p.regular = false;
                }
                UnavailableReason::IncompleteCoverage
            }
            7 => {
                if let Lookup::Present(p) = &mut root(&mut t).cgroup_procs {
                    p.identity.device += 1;
                }
                UnavailableReason::IncompleteCoverage
            }
            _ => {
                root(&mut t).selected_mount.mountpoint = "/other".to_owned();
                UnavailableReason::IncompleteCoverage
            }
        };
        assert_eq!(allowance::quota(&t, &limits), Err(expected), "mode {mode}");
    }
}
#[test]
fn unaligned_namespace_or_filesystem_root_and_legacy_absent_evidence_refuse() {
    let limits = support::manifest().capture_limits;
    for mode in 0..5 {
        let mut t = target();
        if mode == 4 {
            t.source_context = Reading::absent(UnavailableReason::IncompleteCoverage);
        } else {
            let c = t.source_context.value.as_mut().unwrap();
            match mode {
                0 => c.target_cgroupns.inode += 1,
                1 => c.target_mountns.inode += 1,
                2 => c.target_root.device += 1,
                _ => c.source_root.inode += 1,
            }
        }
        assert_eq!(
            allowance::quota(&t, &limits),
            Err(UnavailableReason::IncompleteCoverage)
        );
    }
    let mut legacy = serde_json::to_value(target()).unwrap();
    legacy.as_object_mut().unwrap().remove("source_context");
    for r in legacy["constraints"]["value"].as_array_mut().unwrap() {
        r.as_object_mut().unwrap().remove("root_evidence");
        r.as_object_mut().unwrap().remove("subtree_control");
    }
    let t: TargetCapture = serde_json::from_value(legacy).unwrap();
    assert_eq!(
        allowance::quota(&t, &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
}
#[test]
fn covering_mount_rows_missing_scope_and_bound_exhaustion_refuse() {
    let limits = support::manifest().capture_limits;
    let mut t = target();
    t.mountinfo = found(
        "29 23 0:26 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n40 29 0:40 / /sys/fs/cgroup/slice rw - tmpfs tmpfs rw\n",
    );
    assert_eq!(
        allowance::quota(&t, &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
    t = target();
    t.constraints.value.as_mut().unwrap().remove(1);
    assert_eq!(
        allowance::quota(&t, &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
    let mut bounded = limits.clone();
    bounded.max_cgroup_ancestors = 2;
    assert_eq!(
        allowance::quota(&target(), &bounded),
        Err(UnavailableReason::IncompleteCoverage)
    );
    bounded = limits;
    bounded.max_mount_entries = 1;
    t.mountinfo = found(
        "29 23 0:26 / /sys/fs/cgroup rw - cgroup2 cgroup rw\n1 0 0:1 / / rw - tmpfs tmpfs rw\n",
    );
    assert_eq!(
        allowance::quota(&t, &bounded),
        Err(UnavailableReason::IncompleteCoverage)
    );
}
#[test]
fn v1_release_agent_metadata_is_required_even_for_a_finite_visible_quota() {
    let limits = support::manifest().capture_limits;
    let mut t = target();
    t.cgroup = found("4:cpu:/slice/job\n");
    t.mountinfo = found("29 23 0:26 / /cpu rw - cgroup cgroup rw,cpu\n");
    let scopes =
        allowance::scopes(t.cgroup.get().unwrap(), t.mountinfo.get().unwrap(), &limits).unwrap();
    let original = t.constraints.value.as_ref().unwrap()[0].clone();
    t.constraints = Reading::found(
        scopes
            .iter()
            .map(|s| {
                let mut row = original.clone();
                row.controller = s.controller;
                row.directory = s.directory.clone();
                row.root = s.root;
                row.root_evidence = support::recorded_root(s);
                row.quota = found(if s.root { "-1" } else { "75000" });
                row.period = found("100000");
                row
            })
            .collect(),
    );
    assert_eq!(
        allowance::quota(&t, &limits).unwrap(),
        (Some(0.75), QuotaState::Finite)
    );
    root(&mut t).marker = Lookup::ExactEnoent;
    assert_eq!(
        allowance::quota(&t, &limits),
        Err(UnavailableReason::IncompleteCoverage)
    );
}
#[test]
fn partition_target_effective_mask_ignores_empty_or_disjoint_parent_masks_and_changes() {
    let limits = support::manifest().capture_limits;
    for parent in ["", "3", "1,4-6"] {
        let mut capture = support::replay().attempts.remove(0);
        let a = capture.target_before.as_mut().unwrap();
        a.constraints.value.as_mut().unwrap()[1].cpuset = found(parent);
        a.constraints.value.as_mut().unwrap()[2].cpuset = found("");
        capture.target_after = capture.target_before.clone();
        assert_eq!(
            allowance::allowed(
                capture.target_before.as_ref().unwrap(),
                &[0, 2, 3, 7],
                &limits
            )
            .unwrap(),
            2
        );
        capture
            .target_after
            .as_mut()
            .unwrap()
            .constraints
            .value
            .as_mut()
            .unwrap()[1]
            .cpuset = found("6");
        assert!(
            snapshots::stable(&capture),
            "upstream v2 partition masks do not constrain this target"
        );
    }
}
#[test]
fn absent_nonroot_interfaces_need_parent_subtree_applicability_and_inherit_nearest_effective_mask()
{
    let limits = support::manifest().capture_limits;
    let mut t = target();
    let rows = t.constraints.value.as_mut().unwrap();
    rows[0].quota = Reading::absent(UnavailableReason::Missing);
    rows[0].cpuset = Reading::absent(UnavailableReason::Missing);
    rows[1].subtree_control = found("");
    rows[0].controllers = found("");
    rows[1].quota = found("25000 100000");
    rows[1].cpuset = found("2,7");
    assert_eq!(
        allowance::quota(&t, &limits).unwrap(),
        (Some(0.25), QuotaState::Finite)
    );
    assert_eq!(
        allowance::cpuset(&t, &[0, 2, 3, 7], &limits).unwrap(),
        [2, 7]
    );
    t.constraints.value.as_mut().unwrap()[1].subtree_control =
        Reading::absent(UnavailableReason::Missing);
    assert_eq!(
        allowance::quota(&t, &limits),
        Err(UnavailableReason::Missing)
    );
    assert_eq!(
        allowance::cpuset(&t, &[0, 2, 3, 7], &limits),
        Err(UnavailableReason::Missing)
    );
    t.constraints.value.as_mut().unwrap()[1].subtree_control = found("cpu cpuset");
    t.constraints.value.as_mut().unwrap()[0].controllers = found("cpu cpuset");
    assert_eq!(
        allowance::quota(&t, &limits),
        Err(UnavailableReason::Missing)
    );
    assert_eq!(
        allowance::cpuset(&t, &[0, 2, 3, 7], &limits),
        Err(UnavailableReason::Missing)
    );
}
#[test]
fn verified_unavailable_controller_cannot_hide_a_denied_nonroot_interface() {
    let limits = support::manifest().capture_limits;
    let mut absent = target();
    for row in absent.constraints.value.as_mut().unwrap() {
        row.controllers = found("");
        row.subtree_control = found("");
        row.quota = Reading::absent(UnavailableReason::Missing);
        row.cpuset = Reading::absent(UnavailableReason::Missing);
    }
    assert_eq!(
        allowance::quota(&absent, &limits).unwrap(),
        (None, QuotaState::Unlimited)
    );
    assert_eq!(
        allowance::cpuset(&absent, &[0, 2, 3, 7], &limits).unwrap(),
        [0, 2, 3, 7]
    );
    absent.constraints.value.as_mut().unwrap()[0].quota =
        Reading::absent(UnavailableReason::PermissionDenied);
    assert_eq!(
        allowance::quota(&absent, &limits),
        Err(UnavailableReason::PermissionDenied)
    );
}
#[test]
fn changing_context_root_proof_or_quota_retries_then_diagnoses_snapshot_changed() {
    let limits = support::manifest().capture_limits;
    for mode in 0..3 {
        let mut replay = support::replay();
        let unchanged = replay.attempts[0].clone();
        let after = replay.attempts[0].target_after.as_mut().unwrap();
        match mode {
            0 => {
                after
                    .source_context
                    .value
                    .as_mut()
                    .unwrap()
                    .target_mountns
                    .inode += 1
            }
            1 => root(after).directory.value.as_mut().unwrap().identity.inode += 1,
            _ => after.constraints.value.as_mut().unwrap()[0].quota = found("75000 100000"),
        }
        assert!(!snapshots::stable(&replay.attempts[0]));
        replay.attempts.push(unchanged.clone());
        assert_eq!(replay.selected(&limits).unwrap(), &unchanged);
        replay.attempts[1] = replay.attempts[0].clone();
        let selected = replay.selected(&limits).unwrap();
        let mut row =
            serde_json::from_str(r#"{"date":"2026-10-10","run_id":"2026-10-10-17","shard":0}"#)
                .unwrap();
        let mut diag = cpu::measure(&mut row, selected, &limits);
        cpu::target(
            &mut row,
            &mut diag,
            selected,
            &ProcessTarget {
                pid: 100,
                start_ticks: 800,
            },
            "2026-10-10T12:00:01Z",
            &limits,
        );
        assert_eq!(row.cpu_quota_state, Some(QuotaState::Unavailable));
        assert_eq!(
            diag.source(CaptureSource::Quota).unwrap().reason,
            Some(UnavailableReason::SnapshotChanged)
        );
        assert_eq!(row.cpu_logical_processors, Some(4));
    }
}

#[cfg(target_os = "linux")]
#[test]
fn actual_linux_descriptors_and_root_markers_are_replayed_without_synthetic_kernel_proof() {
    use std::path::Path;
    let limits = support::manifest().capture_limits;
    let pid = std::process::id();
    let stat = std::fs::read_to_string(format!("/proc/{pid}/stat")).unwrap();
    let selected = ProcessTarget {
        pid: i64::from(pid),
        start_ticks: allowance::start_ticks(&stat).unwrap(),
    };
    let roots = snapshots::LiveRoots {
        proc: Path::new("/proc"),
        cpu: Path::new("/sys/devices/system/cpu"),
        namespace: Path::new("/"),
    };
    let context = hierarchy::context(&roots, &selected);
    context.get().unwrap().aligned().unwrap();
    let capture = snapshots::live(&roots, Some(&selected), &limits).unwrap();
    snapshots::validate_capture(&capture, &limits).unwrap();
    let target = capture.target_before.as_ref().unwrap();
    assert_eq!(target.source_context, context);
    let encoded = serde_json::to_vec(&capture).unwrap();
    let replay: snapshots::CpuCapture = serde_json::from_slice(&encoded).unwrap();
    assert_eq!(capture, replay);
    assert_eq!(
        allowance::quota(target, &limits),
        allowance::quota(replay.target_before.as_ref().unwrap(), &limits)
    );
    if let Ok(scopes) = allowance::scopes(
        target.cgroup.get().unwrap(),
        target.mountinfo.get().unwrap(),
        &limits,
    ) {
        let rows = target.constraints.get().unwrap();
        for (scope, row) in scopes.iter().zip(rows).filter(|(s, _)| s.root) {
            let proof = row
                .root_evidence
                .as_ref()
                .expect("live root probe must retain evidence");
            let metadata = proof.directory.get().unwrap();
            assert_eq!(
                metadata.filesystem_type,
                if scope.controller == allowance::Controller::V2 {
                    hierarchy::CGROUP2_SUPER_MAGIC
                } else {
                    hierarchy::CGROUP_SUPER_MAGIC
                }
            );
            let marker_path = Path::new(&scope.directory).join(
                if scope.controller == allowance::Controller::V2 {
                    "cgroup.events"
                } else {
                    "release_agent"
                },
            );
            let marker = std::fs::symlink_metadata(marker_path);
            assert_eq!(
                matches!(proof.marker, Lookup::ExactEnoent),
                marker
                    .as_ref()
                    .is_err_and(|e| e.raw_os_error() == Some(libc::ENOENT))
            );
            if hierarchy::verify_root(scope, proof).is_err() {
                assert!(allowance::quota(target, &limits).is_err());
            }
        }
    } else {
        assert!(allowance::quota(target, &limits).is_err());
    }
}
