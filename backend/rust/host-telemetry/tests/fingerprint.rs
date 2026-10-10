//! Do independently recorded identity bytes and hardware sources produce the declared fingerprints?

mod support;
use idhazh_host_telemetry::{
    canonical_json, contracts::host::CorrectedHostFingerprintRow, fingerprint,
};
use serde_json::{Value, json};

#[test]
fn exact_versioned_vectors_and_nonhardware_invariance() {
    let vectors: Value = serde_json::from_str(include_str!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../tests/fixtures/host-events/fingerprint-versions.json"
    )))
    .unwrap();
    for vector in vectors["vectors"].as_array().unwrap() {
        assert_eq!(
            &canonical_json::sha256(vector["v1_preimage"].as_str().unwrap().as_bytes())[..16],
            vector["v1"]
        );
        let mut facts = vector["facts"].clone();
        facts.as_object_mut().unwrap().remove("cores");
        facts.as_object_mut().unwrap().remove("threads");
        facts["date"] = json!("2026-10-10");
        facts["run_id"] = json!("2026-10-10-17");
        facts["shard"] = json!(0);
        let mut row: CorrectedHostFingerprintRow = serde_json::from_value(facts).unwrap();
        assert_eq!(
            row.fingerprint_v2().unwrap(),
            vector["v2"].as_str().map(str::to_owned)
        );
        row.cpu_physical_cores = Some(64);
        row.cpu_logical_processors = Some(128);
        row.cpu_observed_mhz = Some(999.0);
        row.cpu_reported_max_mhz = Some(5000.0);
        row.microcode = Some("changed".to_owned());
        assert_eq!(
            row.fingerprint_v2().unwrap(),
            vector["v2"].as_str().map(str::to_owned)
        );
    }
}
#[test]
fn hardware_only_uses_watched_flags_and_never_invents_empty_identity() {
    let mut row: CorrectedHostFingerprintRow =
        serde_json::from_value(json!({"date":"2026-10-10","run_id":"2026-10-10-17","shard":0}))
            .unwrap();
    fingerprint::hardware(&mut row, None, None).unwrap();
    assert_eq!(
        (row.fingerprint.clone(), row.fingerprint_version),
        (None, None)
    );
    let replay = support::replay();
    fingerprint::hardware(
        &mut row,
        replay.attempts[0].cpuinfo.value.as_deref(),
        Some(33554432),
    )
    .unwrap();
    assert_eq!(
        row.flags,
        "amx_bf16 amx_int8 amx_tile avx2 avx512_bf16 avx512f f16c fma sse4_2"
    );
    assert_eq!(row.cpu_model_number, Some(207));
    assert_eq!(row.fingerprint_version, Some(2));
    let before = row.fingerprint.clone();
    fingerprint::hardware(
        &mut row,
        replay.attempts[0].cpuinfo.value.as_deref(),
        Some(33554432),
    )
    .unwrap();
    assert_eq!(row.fingerprint, before);
}
