use idhazh_host_telemetry::{
    canonical_json::{row_line, sha256},
    codec::jsonl,
    contracts::write_plan::HostWritePlan,
};
use std::{path::Path, process::Command};

#[test]
fn actual_envelope_first_canonical_rows_and_truncation() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../..");
    let output = Command::new(env!("CARGO_BIN_EXE_codec-fixture"))
        .current_dir(&root)
        .args([
            "render",
            "tests/fixtures/host-events/file-parity.json",
            "backend/var/d10-rust-tests/jsonl",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let proofs: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    let plan: HostWritePlan = serde_json::from_value(proofs[0]["plan"].clone()).unwrap();
    let file = &plan.files[0];
    let bytes = std::fs::read(root.join(&plan.target_root).join(&file.relative_path)).unwrap();
    assert!(bytes.is_ascii());
    assert_eq!(bytes.iter().filter(|v| **v == b'\n').count(), 2);
    let (env, rows) = jsonl::read(&bytes, 1048576).unwrap();
    assert_eq!(env, file.envelope);
    assert_eq!(rows, file.rows);
    assert!(bytes.ends_with(&row_line(&file.rows[0]).unwrap()));
    assert!(jsonl::read(&bytes[..bytes.len() - 1], 1048576).is_err());
    assert!(jsonl::read(&bytes, 1).is_err());
    assert!(jsonl::read(b"{}\n{}\n", 100).is_err());
    let mut foreign = file.envelope.clone();
    foreign.identity.shard = 1;
    assert!(jsonl::render(&file.rows, &foreign).is_err());
    let mut corrupted = bytes.clone();
    let offset = corrupted.windows(6).position(|v| v == b"Native").unwrap();
    corrupted[offset] = b'M';
    assert!(jsonl::read(&corrupted, 1048576).is_err());
    let mut empty = env;
    empty.content_sha256 = sha256(b"");
    let bytes = jsonl::render(&[], &empty).unwrap();
    assert!(jsonl::read(&bytes, 1048576).unwrap().1.is_empty());
    let unordered = vec![file.rows[0].clone(), file.rows[0].clone()];
    empty.content_sha256 =
        sha256(&idhazh_host_telemetry::canonical_json::rows_bytes(&unordered).unwrap());
    assert_eq!(
        jsonl::read(&jsonl::render(&unordered, &empty).unwrap(), 1048576)
            .unwrap()
            .1,
        unordered
    );
}
