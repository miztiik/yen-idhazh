use idhazh_host_telemetry::ledger::schema::*;

#[test]
fn explicit_order_types_and_nullable_empty_schema() {
    let columns = columns_for("host-fingerprint", "2026-10-10").unwrap();
    assert_eq!(columns.len(), 40);
    assert_eq!(columns[0].name, "version");
    assert_eq!(columns[5].name, "fingerprint");
    assert_eq!(columns[6].name, "fingerprint_version");
    assert_eq!(columns[16].r#type, ColumnType::Float64);
    assert!(columns[16].nullable);
    assert_eq!(columns[36].name, "ledger");
    assert_eq!(columns[39].name, "unit_id");
    let names = columns
        .iter()
        .map(|v| v.name)
        .collect::<std::collections::HashSet<_>>();
    assert_eq!(names.len(), columns.len());
    assert!(!names.contains("cores"));
    assert!(!names.contains("mhz_max"));
    assert!(columns_for("unknown", "2026-10-10").is_err());
    assert!(columns_for("host-fingerprint", "2026-09-20").is_err());
}
