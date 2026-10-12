use idhazh_host_telemetry::config::*;
use idhazh_host_telemetry::contracts::file_envelope::*;
use idhazh_host_telemetry::contracts::host::*;

#[test]
fn real_configuration_bounds_controls_and_override() {
    let bytes = include_bytes!("../../../../config/host-telemetry-experiment.json");
    let config = ExperimentConfig::from_bytes(bytes, 65536).unwrap();
    assert!(config.controls.memory_profiling_enabled);
    assert!(
        !config
            .effective_controls(Some(false))
            .memory_profiling_enabled
    );
    assert_eq!(config.effective_controls(None), config.controls);
    assert_eq!(memory_profiling_override(None).unwrap(), None);
    assert_eq!(memory_profiling_override(Some("on")).unwrap(), Some(true));
    assert_eq!(memory_profiling_override(Some("off")).unwrap(), Some(false));
    for invalid in ["true", "false", "1", "yes", "OFF"] {
        assert!(memory_profiling_override(Some(invalid)).is_err());
    }
    assert!(ExperimentConfig::from_bytes(bytes, 1).is_err());
    let mut data: serde_json::Value = serde_json::from_slice(bytes).unwrap();
    data["controls"]["memory_profiling_enabled"] = serde_json::json!("false");
    assert!(serde_json::from_value::<ExperimentConfig>(data).is_err());
    let mut config = config;
    config.limits.max_concurrent_windows = config.limits.max_windows + 1;
    assert!(config.validate().is_err());
}

#[test]
fn native_configuration_rejects_migration_and_unknown_sections() {
    let bytes = include_bytes!("../../../../config/host-telemetry-experiment.json");
    for field in ["history_migration_limits", "unknown_section"] {
        let mut data: serde_json::Value = serde_json::from_slice(bytes).unwrap();
        data[field] = serde_json::json!({"max_roots": 4});
        let bytes = serde_json::to_vec(&data).unwrap();
        let error = ExperimentConfig::from_bytes(&bytes, 65536).unwrap_err();
        assert!(
            error.contains(&format!("unknown field `{field}`")),
            "{error}"
        );
    }
}

#[test]
fn all_formats_compressions_and_lifecycle_are_explicit() {
    for format in ["parquet", "json"] {
        for compression in ["none", "snappy", "zstd"] {
            let config: CodecConfig = serde_json::from_value(
                serde_json::json!({"format":format,"compression":compression}),
            )
            .unwrap();
            assert_eq!(
                config.effective_compression(),
                if format == "json" {
                    Compression::None
                } else {
                    config.compression
                }
            );
        }
    }
    for field in ["format", "compression"] {
        let mut data = serde_json::json!({"format":"parquet","compression":"none"});
        data[field] = serde_json::json!("unknown");
        assert!(serde_json::from_value::<CodecConfig>(data).is_err());
    }
    for job in [ServerJob::Work, ServerJob::Migrate, ServerJob::History] {
        assert!(admits_raw(Lifecycle::Active, job));
        assert!(!admits_raw(Lifecycle::Paused, job));
        assert!(!admits_raw(Lifecycle::Retired, job));
    }
}
