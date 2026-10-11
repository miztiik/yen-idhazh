//! Are recorded server clocks, Prometheus counters and UTC elapsed times unchanged?

use idhazh_host_telemetry::producers::job_clock::{elapsed, model_load_ms, prompt_totals};
const LOG: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../tests/fixtures/runtime/2026-08-29-3-shard-0.server-head.txt"
));
const METRICS: &str = include_str!(concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../tests/fixtures/runtime/2026-08-26-5-shard-0.prom"
));
#[test]
fn captured_server_formats_are_decoded_exactly() {
    assert_eq!(model_load_ms(LOG), Some(3797.64));
    let totals = prompt_totals(METRICS).unwrap();
    assert_eq!(totals, (Some(30538), Some(2795.15)));
    assert_eq!(
        elapsed(Some("2026-10-09T23:59:58Z"), "2026-10-10T00:00:04Z").unwrap(),
        Some(6)
    );
    assert_eq!(elapsed(None, "2026-10-10T00:00:04Z").unwrap(), None);
}
#[test]
fn renamed_missing_fractional_nonfinite_and_backward_readings_are_not_zero() {
    assert_eq!(model_load_ms("renamed"), None);
    assert_eq!(prompt_totals("# absent\n").unwrap(), (None, None));
    for text in [
        "llamacpp:prompt_tokens_total 2.5",
        "llamacpp:prompt_tokens_total NaN",
        "llamacpp:prompt_seconds_total inf",
        "llamacpp:prompt_tokens_total 9223372036854775808",
    ] {
        assert!(prompt_totals(text).is_err());
    }
    assert!(elapsed(Some("2026-10-10T00:00:05Z"), "2026-10-10T00:00:04Z").is_err());
    assert!(elapsed(Some("2026-10-10T00:00:04+02:00"), "2026-10-10T00:00:04Z").is_err());
    assert_eq!(
        model_load_ms(
            "00.00.000.100 load_model: loading model\n00.00.001.115 llama_server: model loaded"
        ),
        Some(1.015)
    );
}
