//! Do real named process reads preserve identity, units and the independent memory-off boundary?
#[path = "support/resources.rs"]
mod resources;
use idhazh_host_telemetry::{
    contracts::events::*, probe_inputs::files::Reading, sampling::process::*,
};

#[test]
fn reads_generated_files_with_bracketed_commands_and_exact_units() {
    let root = resources::workspace("process-units");
    let frame = &resources::frames()[0];
    resources::write_frame(&root, frame, true);
    let sampler = ProcessSampler::new(&root, 4096, 64).unwrap();
    let v = sampler.sample(&frame.processes[0].target, true, true);
    assert_eq!(v.identity.value, Some(frame.processes[0].target.clone()));
    assert_eq!(v.rss.value, Some(400 * 1024));
    assert_eq!(v.hwm.value, Some(500 * 1024));
    assert_eq!(v.anon.value, Some(80 * 1024));
    assert_eq!(v.faults.value, Some(40));
    assert_eq!(v.legacy_status.value.unwrap()["VmRSS"], "400 kB");
}
#[test]
fn off_never_opens_status_and_does_not_extract_malformed_fault_field() {
    let root = resources::workspace("process-off");
    let mut frame = resources::frames().remove(0);
    frame.processes[0].stat_before.value = Some(
        frame.processes[0]
            .stat_before
            .value
            .as_ref()
            .unwrap()
            .replacen(" 40 ", " not-a-fault ", 1),
    );
    resources::write_frame(&root, &frame, false);
    let sampler = ProcessSampler::new(&root, 4096, 64).unwrap();
    let v = sampler.sample(&frame.processes[0].target, false, true);
    assert!(v.identity.value.is_some());
    assert_eq!(v.rss.reason, Some(UnavailableReason::Disabled));
    assert_eq!(v.faults.reason, Some(UnavailableReason::Disabled));
    assert_eq!(
        sampler.population(false).reason,
        Some(UnavailableReason::Disabled)
    );
}
#[test]
fn refuses_start_reuse_and_races_and_reports_real_exits() {
    let mut texts = resources::frames()[0].processes[0].clone();
    texts.stat_after.value = Some(
        texts
            .stat_after
            .value
            .as_ref()
            .unwrap()
            .replace(" 800\n", " 801\n"),
    );
    assert_eq!(
        reduce(&texts, true, true).rss.reason,
        Some(UnavailableReason::PidReused)
    );
    texts.stat_after = Reading::absent(UnavailableReason::Missing);
    assert_eq!(
        reduce(&texts, true, true).identity.reason,
        Some(UnavailableReason::PidExited)
    );
    let root = resources::workspace("process-exit");
    assert_eq!(
        ProcessSampler::new(&root, 4096, 64)
            .unwrap()
            .identity(100)
            .reason,
        Some(UnavailableReason::PidExited)
    );
}
#[test]
fn bounds_and_denied_source_are_not_truncated_valid_readings() {
    let root = resources::workspace("process-bounds");
    resources::write_frame(&root, &resources::frames()[0], true);
    std::fs::remove_file(root.join("100").join("status")).unwrap();
    std::fs::create_dir(root.join("100").join("status")).unwrap();
    let sampler = ProcessSampler::new(&root, 4096, 1).unwrap();
    assert!(
        sampler
            .sample(&resources::window(0).server.unwrap(), true, true)
            .rss
            .value
            .is_none()
    );
    assert_eq!(
        sampler.population(true).reason,
        Some(UnavailableReason::IncompleteCoverage)
    );
    assert!(
        ProcessSampler::new(&root, 8, 64)
            .unwrap()
            .identity(100)
            .value
            .is_none()
    );
}
#[test]
fn malformed_fields_and_overflow_remain_null() {
    assert_eq!(
        kilobytes(
            &Reading::found("VmRSS: 9223372036854775808 kB\n".to_owned()),
            "VmRSS"
        )
        .value,
        None
    );
    assert_eq!(
        bytes(
            &Reading::found("VmRSS: 9223372036854775807 kB\n".to_owned()),
            "VmRSS"
        )
        .value,
        None
    );
    assert_eq!(
        identity(&Reading::found("100 (x) Z 0\n".to_owned()), 100).reason,
        Some(UnavailableReason::PidExited)
    );
}
#[cfg(not(target_os = "linux"))]
#[test]
fn unsupported_live_procfs_is_truthfully_unavailable() {
    let root = resources::workspace("nonlinux-proc");
    assert!(
        ProcessSampler::new(&root, 4096, 64)
            .unwrap()
            .sample(&resources::window(0).target, true, true)
            .identity
            .value
            .is_none()
    );
}
