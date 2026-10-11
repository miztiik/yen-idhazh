//! Do machine samples preserve existing CPU arithmetic and avoid every memory read when off?
#[path = "support/resources.rs"]
mod resources;
use idhazh_host_telemetry::{
    contracts::events::UnavailableReason, probe_inputs::files::Reading, sampling::machine::*,
};

#[test]
fn cpu_delta_uses_real_recorded_runner_texts() {
    let a = Reading::found(
        include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../tests/fixtures/runtime/2026-08-30-probe-proc-stat-at-start.txt"
        ))
        .to_owned(),
    );
    let b = Reading::found(
        include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../tests/fixtures/runtime/2026-08-30-probe-proc-stat-at-end.txt"
        ))
        .to_owned(),
    );
    let value = shares(&cpu_ticks(&a), &cpu_ticks(&b)).value.unwrap();
    assert!(value.busy >= 0.0 && value.busy <= 100.0);
    assert!(value.steal.is_some());
}
#[test]
fn generated_machine_reads_keep_zero_swap_distinct_from_missing() {
    let root = resources::workspace("machine-units");
    resources::write_frame(&root, &resources::frames()[0], true);
    let v = MachineSampler::new(&root, 4096).unwrap().sample(true);
    assert_eq!(v.available.value, Some(800 * 1024));
    assert_eq!(v.swap_total.value, Some(0));
    assert_eq!(v.load.value, Some(0.25));
}
#[test]
fn memory_directory_denial_does_not_block_cpu_or_load_when_off() {
    let root = resources::workspace("machine-off");
    resources::write_frame(&root, &resources::frames()[0], false);
    let v = MachineSampler::new(&root, 4096).unwrap().sample(false);
    assert!(v.cpu.value.is_some());
    assert_eq!(v.load.value, Some(0.25));
    assert_eq!(v.available.reason, Some(UnavailableReason::Disabled));
}
#[test]
fn malformed_counter_reset_missing_steal_and_guest_semantics() {
    let a = cpu_ticks(&Reading::found("cpu 10 0 10 80\n".to_owned()));
    let b = cpu_ticks(&Reading::found("cpu 20 0 20 160\n".to_owned()));
    let result = shares(&a, &b).value.unwrap();
    assert_eq!(result.busy, 20.0);
    assert_eq!(result.steal, None);
    assert!(shares(&b, &a).value.is_none());
    let a = cpu_ticks(&Reading::found("cpu 10 0 10 80 0 0 0 0 5 0\n".to_owned()));
    let b = cpu_ticks(&Reading::found("cpu 20 0 20 160 0 0 0 0 10 0\n".to_owned()));
    assert_eq!(shares(&a, &b).value.unwrap().busy, 20.0);
    assert!(load(&Reading::found("nan 0\n".to_owned())).value.is_none());
    assert!(
        cpu_ticks(&Reading::found("cpu 1 nope\n".to_owned()))
            .value
            .is_none()
    );
}

#[test]
fn decimal_half_percentages_match_python_binary_float_rounding() {
    let a = cpu_ticks(&Reading::found("cpu 0 0 0 0 0 0 0 0\n".to_owned()));
    for (busy, idle, expected) in [(107, 3893, 2.67), (45, 3955, 1.12), (115, 3885, 2.88)] {
        let b = cpu_ticks(&Reading::found(format!("cpu {busy} 0 0 {idle} 0 0 0 0\n")));
        assert_eq!(shares(&a, &b).value.unwrap().busy, expected);
    }
}
