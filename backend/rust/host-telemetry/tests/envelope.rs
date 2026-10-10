use idhazh_host_telemetry::{
    canonical_json::{rows_bytes, sha256},
    config::CodecConfig,
    contracts::{file_envelope::*, host::*},
    ledger::{envelope, identity},
};
use serde_json::json;

#[test]
fn exact_native_metadata_is_logical_not_physical_identity() {
    let row: CorrectedHostFingerprintRow = serde_json::from_value(json!({
        "date":"2026-10-10","run_id":"2026-10-10-42","shard":0
    }))
    .unwrap();
    let writer: HostWriterIdentity = serde_json::from_value(json!({
        "run_id":row.run_id,"attempt":2,"job":"work","shard":0,
        "producer":HOST_PRODUCER,"git_sha":"a".repeat(40)
    }))
    .unwrap();
    let stored = identity::stamp(&row, &writer).unwrap();
    for format in [Format::Json, Format::Parquet] {
        let codec = CodecConfig {
            format,
            compression: Compression::Snappy,
        };
        let env = envelope::build(&stored, &writer, &codec, 1791633600123).unwrap();
        assert_eq!(
            env.content_sha256,
            sha256(&rows_bytes(std::slice::from_ref(&stored)).unwrap())
        );
        assert!(env.writer.native());
        assert_eq!(env.writer.format(), format);
        assert_eq!(env.compression, codec.effective_compression());
        let metadata = serde_json::to_value(env.metadata().unwrap()).unwrap();
        assert_eq!(metadata.as_object().unwrap().len(), 18);
        assert!(
            metadata
                .as_object()
                .unwrap()
                .values()
                .all(|v| v.is_string())
        );
        assert!(metadata.get("period").is_none() && metadata.get("built_from").is_none());
        let bytes = match format {
            Format::Json => {
                idhazh_host_telemetry::codec::jsonl::render(std::slice::from_ref(&stored), &env)
            }
            Format::Parquet => {
                idhazh_host_telemetry::codec::parquet::render(std::slice::from_ref(&stored), &env)
            }
        }
        .unwrap();
        assert_ne!(env.content_sha256, sha256(&bytes));
    }
    let mut conflict = stored.clone();
    conflict.attempt = 1;
    assert!(
        envelope::build(
            &conflict,
            &writer,
            &CodecConfig {
                format: Format::Json,
                compression: Compression::None,
            },
            1791633600123
        )
        .is_err()
    );
}
