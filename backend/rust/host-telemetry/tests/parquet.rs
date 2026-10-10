use idhazh_host_telemetry::{
    canonical_json::sha256, codec::parquet, contracts::file_envelope::Compression,
    contracts::write_plan::HostWritePlan,
};
use std::{path::Path, process::Command};

#[test]
fn actual_native_all_compressions_roundtrip_and_corruption() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..");
    let output = Command::new(env!("CARGO_BIN_EXE_codec-fixture"))
        .current_dir(&root)
        .args([
            "render",
            "tests/fixtures/host-events/file-parity.json",
            "backend/var/d10-rust-tests/parquet",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let proofs: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    std::fs::write(
        root.join("backend/var/d10-rust-tests/parquet/proofs.json"),
        &output.stdout,
    )
    .unwrap();
    for proof in proofs.as_array().unwrap().iter().skip(1) {
        let plan: HostWritePlan = serde_json::from_value(proof["plan"].clone()).unwrap();
        let file = &plan.files[0];
        let bytes = std::fs::read(root.join(&plan.target_root).join(&file.relative_path)).unwrap();
        assert_eq!(sha256(&bytes), proof["physical_sha256"].as_str().unwrap());
        let (env, rows) = parquet::read(&bytes, 1048576).unwrap();
        assert_eq!(env, file.envelope);
        assert_eq!(rows, file.rows);
        assert!(parquet::read(&bytes, 1).is_err());
        assert!(parquet::read(&bytes[..bytes.len() - 4], 1048576).is_err());
        if env.compression == Compression::None {
            let mut nonfinite = bytes.clone();
            let offsets = bytes
                .windows(8)
                .enumerate()
                .filter_map(|(offset, value)| (value == (-0.0_f64).to_le_bytes()).then_some(offset))
                .collect::<Vec<_>>();
            assert!(!offsets.is_empty());
            for offset in offsets {
                nonfinite[offset..offset + 8].copy_from_slice(&f64::NAN.to_le_bytes());
            }
            assert!(
                parquet::read(&nonfinite, 1048576)
                    .unwrap_err()
                    .contains("nonfinite float")
            );
            let mut mismatched = bytes.clone();
            let offset = bytes.windows(4).position(|value| value == b"none").unwrap();
            mismatched[offset..offset + 4].copy_from_slice(b"zstd");
            assert!(
                parquet::read(&mismatched, 1048576)
                    .unwrap_err()
                    .contains("compression/footer mismatch")
            );
        }
        if let Some(offset) = bytes.windows(6).position(|v| v == b"Native") {
            let mut corrupted = bytes.clone();
            corrupted[offset] = b'M';
            assert!(parquet::read(&corrupted, 1048576).is_err());
        }
        let mut foreign = file.envelope.clone();
        foreign.identity.shard = 1;
        assert!(parquet::render(&file.rows, &foreign).is_err());
        let mut legacy = file.rows.clone();
        legacy[0].host.fingerprint_version = Some(1);
        let mut legacy_envelope = file.envelope.clone();
        legacy_envelope.content_sha256 =
            sha256(&idhazh_host_telemetry::canonical_json::rows_bytes(&legacy).unwrap());
        assert!(parquet::render(&legacy, &legacy_envelope).is_err());
        let mut empty = file.envelope.clone();
        empty.content_sha256 = sha256(b"");
        let bytes = parquet::render(&[], &empty).unwrap();
        let (env, rows) = parquet::read(&bytes, 1048576).unwrap();
        assert_eq!(env, empty);
        assert!(rows.is_empty());
        let mut forged = file.envelope.clone();
        forged.writer_version = "made-up".to_owned();
        assert!(parquet::render(&file.rows, &forged).is_err());
    }
}
