use idhazh_host_telemetry::canonical_json::*;

#[test]
fn ascii_sorted_compact_surrogate_pairs_lf_and_hash() {
    let value = serde_json::json!({"z":null,"a":"\u{03bb}\u{1f680}\n\t\u{007f}","n":-0.0});
    let bytes = row_line(&value).unwrap();
    assert_eq!(
        bytes,
        br#"{"a":"\u03bb\ud83d\ude80\n\t\u007f","n":-0.0,"z":null}"#
            .iter()
            .copied()
            .chain([b'\n'])
            .collect::<Vec<_>>()
    );
    assert!(bytes.is_ascii());
    assert_eq!(
        sha256(b""),
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    );
    assert_eq!(
        sha256(&rows_bytes(&[value.clone(), value]).unwrap()),
        sha256(&[bytes.clone(), bytes].concat())
    );
}
#[test]
fn python_notation_thresholds_and_nonfinite_refusal() {
    for (value, expected) in [
        (0.0, "0.0"),
        (-0.0, "-0.0"),
        (1e-5, "1e-05"),
        (1e-4, "0.0001"),
        (1e15, "1000000000000000.0"),
        (1e16, "1e+16"),
        (1e20, "1e+20"),
        (f64::from_bits(1), "5e-324"),
        (1.25, "1.25"),
        (-1e-7, "-1e-07"),
    ] {
        assert_eq!(float_text(value).unwrap(), expected);
    }
    for value in [f64::NAN, f64::INFINITY, f64::NEG_INFINITY] {
        assert!(float_text(value).is_err());
        assert!(object_bytes(&value).is_err());
        assert!(object_bytes(&vec![Some(value)]).is_err());
    }
}
