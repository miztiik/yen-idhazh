//! Do bounded reductions reproduce whole-window means, endpoint HWM and periodic extrema independently?
#[path = "support/resources.rs"]
mod resources;
use idhazh_host_telemetry::{Validate, contracts::events::*, windows::reduce::*};

#[test]
fn exact_existing_cells_from_periodic_fixture() {
    let frames = resources::frames();
    let w = resources::window(0);
    let mut reducer =
        WindowReducer::new(w.clone(), frames[0].snapshot(&w, true, true), true).unwrap();
    for frame in &frames[1..3] {
        reducer.note(&frame.snapshot(&w, true, false));
    }
    let result = reducer.close(frames[3].snapshot(&w, true, true)).unwrap();
    assert_eq!(
        serde_json::to_value(&result.cells).unwrap(),
        resources::fixture()["expected_periodic"]
    );
    assert!(result.unavailable.is_empty());
    assert_eq!(result.cells.llama_rss_peak_bytes, Some(500 * 1024));
}
#[test]
fn endpoint_only_cpu_extrema_and_headroom_match_endpoints() {
    let frames = resources::frames();
    let w = resources::window(0);
    let reducer = WindowReducer::new(w.clone(), frames[0].snapshot(&w, true, true), true).unwrap();
    let result = reducer.close(frames[3].snapshot(&w, true, true)).unwrap();
    assert_eq!(result.cells.cpu_busy_max, Some(50.0));
    assert_eq!(result.cells.cpu_busy_min, Some(50.0));
    assert_eq!(result.cells.os_mem_available_min_bytes, Some(750 * 1024));
}
#[test]
fn off_and_abort_are_typed_nulls_not_stale_or_zero() {
    let frames = resources::frames();
    let w = resources::window(0);
    let reducer =
        WindowReducer::new(w.clone(), frames[0].snapshot(&w, false, true), false).unwrap();
    let result = reducer.close(frames[3].snapshot(&w, false, true)).unwrap();
    result.validate().unwrap();
    assert_eq!(result.status, WindowStatus::Complete);
    assert_eq!(result.cells.cpu_busy_pct, Some(50.0));
    assert_eq!(result.cells.python_rss_bytes, None);
    assert!(
        result
            .unavailable
            .iter()
            .all(|v| v.reason == UnavailableReason::Disabled)
    );
    let result = incomplete(w, None, false, UnavailableReason::TimedOut);
    result.validate().unwrap();
    assert!(result.cells.availability().into_iter().all(|v| !v.0));
}
#[test]
fn fault_reset_and_target_exit_are_diagnosed() {
    let mut frames = resources::frames();
    let w = resources::window(0);
    frames[3].processes[0].stat_after.value = Some(
        frames[3].processes[0]
            .stat_after
            .value
            .as_ref()
            .unwrap()
            .replace(" 49 ", " 1 "),
    );
    let result = WindowReducer::new(w.clone(), frames[0].snapshot(&w, true, true), true)
        .unwrap()
        .close(frames[3].snapshot(&w, true, true))
        .unwrap();
    assert_eq!(result.cells.llama_major_faults, None);
    assert!(
        result
            .unavailable
            .iter()
            .any(|v| v.source == CaptureSource::MajorFaults)
    );
}
#[test]
fn a_long_window_stores_running_statistics_not_samples() {
    let frames = resources::frames();
    let w = resources::window(0);
    let mut reducer =
        WindowReducer::new(w.clone(), frames[0].snapshot(&w, true, true), true).unwrap();
    let initial_size = std::mem::size_of_val(&reducer);
    for _ in 0..10_000 {
        reducer.note(&frames[1].snapshot(&w, true, false));
    }
    assert_eq!(std::mem::size_of_val(&reducer), initial_size);
    assert_eq!(reducer.samples, 10_000);
}
