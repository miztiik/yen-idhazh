//! Do emitted native artifacts preserve the Python population, legacy units and runtime status representation?
#[path = "support/resources.rs"]
mod resources;
use idhazh_host_telemetry::{
    contracts::events::*, probe_inputs::files::Reading, producers::job_samples::*,
};

#[test]
fn population_is_all_readable_python_not_rust_or_selected_subtree() {
    let mut frame = resources::frames().remove(0);
    let mut unrelated = frame.population.value.as_ref().unwrap()[0].clone();
    unrelated.target.pid = 400;
    unrelated.stat_before.value = Some(
        unrelated
            .stat_before
            .value
            .as_ref()
            .unwrap()
            .replacen("200 ", "400 ", 1),
    );
    unrelated.stat_after = unrelated.stat_before.clone();
    unrelated.status.value = Some("VmRSS: 100 kB\nVmHWM: 120 kB\n".to_owned());
    let mut rust = unrelated.clone();
    rust.comm.value = Some("idhazh-host-telemetry".to_owned());
    frame
        .population
        .value
        .as_mut()
        .unwrap()
        .extend([unrelated, rust]);
    let (record, rows) = sample(&frame, Some(&frame.processes[0].target), true)
        .unwrap()
        .unwrap();
    assert_eq!(record.python_procs, 3);
    assert_eq!(record.python_vmrss_kb, 350);
    assert_eq!(record.python_vmhwm_kb, 420);
    assert_eq!(record.llama_vmrss_kb, Some(400));
    assert_eq!(rows[0].args.as_deref(), Some("-u -m idhazh"));
    assert!(
        !serde_json::to_string(&rows)
            .unwrap()
            .contains("secret-not-exported")
    );
}
#[test]
fn artifacts_are_actual_plain_records_and_memory_off_creates_nothing() {
    let root = resources::workspace("artifacts");
    let m = resources::manifest();
    let frame = resources::frames().remove(0);
    assert!(
        Artifacts::create(&root, "off", &m.limits, false)
            .unwrap()
            .is_none()
    );
    assert!(!root.join("off").exists());
    assert!(sample(&frame, None, false).unwrap().is_none());
    let mut artifacts = Artifacts::create(&root, "on", &m.limits, true)
        .unwrap()
        .unwrap();
    let (record, rows) = sample(&frame, Some(&frame.processes[0].target), true)
        .unwrap()
        .unwrap();
    artifacts.write_sample(&record, &rows).unwrap();
    artifacts
        .write_runtime(&runtime_status(&frame, Some(&frame.processes[0].target), true).unwrap())
        .unwrap();
    artifacts.write_peak(&frame.cgroup_peak).unwrap();
    let raw = std::fs::read(root.join("on").join(LEGACY_JOB_SAMPLE_FILENAME)).unwrap();
    assert_eq!(
        serde_json::from_slice::<LegacyJobSample>(&raw).unwrap(),
        record
    );
    assert!(!String::from_utf8(raw).unwrap().contains("event_id"));
    assert_eq!(
        std::fs::read_to_string(root.join("on").join(RUNTIME_PEAK_FILENAME)).unwrap(),
        "234567\n"
    );
}
#[test]
fn capacity_and_missing_population_never_publish_a_partial_sum() {
    let root = resources::workspace("artifact-caps");
    let mut m = resources::manifest();
    m.limits.max_session_events = 1;
    let mut frame = resources::frames().remove(0);
    let (record, rows) = sample(&frame, None, true).unwrap().unwrap();
    let mut artifacts = Artifacts::create(&root, "cap", &m.limits, true)
        .unwrap()
        .unwrap();
    assert!(artifacts.write_sample(&record, &rows).is_err());
    assert_eq!(
        std::fs::metadata(root.join("cap").join(LEGACY_JOB_SAMPLE_FILENAME))
            .unwrap()
            .len(),
        0
    );
    frame.population = Reading::absent(UnavailableReason::IncompleteCoverage);
    assert!(sample(&frame, None, true).is_err());
}
