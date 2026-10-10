pub use idhazh_host_telemetry::contracts;
#[path = "../src/ledger/paths.rs"]
mod paths;

use contracts::file_envelope::Format;
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};
use uuid::Uuid;

fn file_id() -> Uuid {
    Uuid::parse_str("01a125af-2e7b-8945-899b-fa46f230ac97").unwrap()
}

fn prefix(parts: &[&str]) -> Vec<String> {
    parts.iter().map(|v| (*v).to_owned()).collect()
}

fn raw() -> String {
    paths::raw_path(
        &prefix(&["host-fingerprint"]),
        "2026-10-10",
        file_id(),
        Format::Parquet,
    )
    .unwrap()
}

struct Generated {
    root: PathBuf,
    workspace: PathBuf,
}

impl Generated {
    fn new(label: &str) -> Self {
        static SEQUENCE: AtomicU64 = AtomicU64::new(0);
        let clock = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        let root = Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("var")
            .join("d11-paths-tests")
            .join(format!(
                "{label}-{}-{clock}-{}",
                std::process::id(),
                SEQUENCE.fetch_add(1, Ordering::Relaxed)
            ));
        // Exclusive creation means cleanup can only remove this test's directory.
        fs::create_dir_all(root.parent().unwrap()).unwrap();
        fs::create_dir(&root).unwrap();
        let workspace = root.join("workspace");
        fs::create_dir(&workspace).unwrap();
        Self { root, workspace }
    }

    fn native(&self, target: &str, relative: &str) -> PathBuf {
        let mut result = self.workspace.clone();
        for part in target.split('/').chain(relative.split('/')) {
            result.push(part);
        }
        result
    }
}

impl Drop for Generated {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.root).expect("remove only this test's generated tree");
    }
}

#[test]
fn exact_raw_host_paths_support_both_formats_and_nested_trial_prefixes() {
    assert_eq!(
        raw(),
        "raw/host-fingerprint/2026/10/10/01a125af-2e7b-8945-899b-fa46f230ac97.parquet"
    );
    assert_eq!(
        paths::raw_path(
            &prefix(&["trial", "case-1", "host-fingerprint"]),
            "2024-02-29",
            file_id(),
            Format::Json,
        )
        .unwrap(),
        "raw/trial/case-1/host-fingerprint/2024/02/29/01a125af-2e7b-8945-899b-fa46f230ac97.json"
    );
    assert!(
        paths::raw_path(
            &prefix(&["COM10", ".trial", "host-fingerprint"]),
            "2026-10-10",
            file_id(),
            Format::Json,
        )
        .is_ok()
    );
}

#[test]
fn unsafe_prefixes_noncalendar_days_and_wrong_uuid_kinds_are_refused() {
    for parts in [
        vec![],
        vec!["other-ledger"],
        vec!["host-fingerprint", "extra"],
        vec!["..", "host-fingerprint"],
        vec![".", "host-fingerprint"],
        vec!["a/b", "host-fingerprint"],
        vec!["a\\b", "host-fingerprint"],
        vec!["", "host-fingerprint"],
        vec!["CON", "host-fingerprint"],
        vec!["nul.parquet", "host-fingerprint"],
        vec!["com1", "host-fingerprint"],
        vec!["LPT9.log", "host-fingerprint"],
        vec!["trial.", "host-fingerprint"],
        vec!["trial ", "host-fingerprint"],
        vec!["C:", "host-fingerprint"],
        vec!["x\n", "host-fingerprint"],
        vec!["x\0", "host-fingerprint"],
    ] {
        assert!(
            paths::raw_path(&prefix(&parts), "2026-10-10", file_id(), Format::Parquet).is_err(),
            "{parts:?}"
        );
    }
    for day in [
        "2026-02-29",
        "2026-04-31",
        "0000-01-01",
        "2026-1-01",
        "2026-10-10\n",
    ] {
        assert!(
            paths::raw_path(&prefix(&["host-fingerprint"]), day, file_id(), Format::Json).is_err()
        );
    }
    assert!(
        paths::raw_path(
            &prefix(&["host-fingerprint"]),
            "2026-10-10",
            Uuid::parse_str("4f918a28-1fa6-5125-98d6-98e1cf8e1d15").unwrap(),
            Format::Json,
        )
        .is_err()
    );
    let overlong = "x".repeat(513);
    assert!(
        paths::raw_path(
            &prefix(&[&overlong, "host-fingerprint"]),
            "2026-10-10",
            file_id(),
            Format::Json,
        )
        .is_err()
    );
}

#[test]
fn resolution_permits_missing_descendants_but_creates_nothing() {
    let generated = Generated::new("missing");
    let relative = paths::raw_path(
        &prefix(&["trial", "case-1", "host-fingerprint"]),
        "2024-02-29",
        file_id(),
        Format::Json,
    )
    .unwrap();
    let workspace = fs::canonicalize(&generated.workspace).unwrap();
    let mut expected = workspace.join("runs").join("state");
    for part in relative.split('/') {
        expected.push(part);
    }
    assert_eq!(
        paths::resolve(&generated.workspace, "runs/state", &relative).unwrap(),
        expected
    );
    assert!(!generated.workspace.join("runs").exists());
    fs::create_dir_all(generated.workspace.join("runs").join("state")).unwrap();
    assert_eq!(
        paths::resolve(&generated.workspace, "runs/state", &relative).unwrap(),
        expected
    );
    assert!(
        !generated
            .workspace
            .join("runs")
            .join("state")
            .join("raw")
            .exists()
    );
}

#[test]
fn resolution_refuses_drive_traversal_controls_reserved_names_and_nonraw_grammar() {
    let generated = Generated::new("grammar");
    for root in [
        "",
        ".",
        "..",
        "../state",
        "/state",
        "C:/state",
        "C:state",
        "\\\\server\\share",
        "state\\raw",
        "state/../outside",
        "state//trial",
        "state/",
        "state/CON",
        "state/LPT1.txt",
        "state/trial.",
        "state/trial ",
        "state/\0",
        "state/\n",
    ] {
        assert!(
            paths::resolve(&generated.workspace, root, &raw()).is_err(),
            "{root:?}"
        );
    }
    let valid = raw();
    for bad in [
        valid.replace("raw/", "compact/"),
        valid.replace("raw/", "history/"),
        valid.replace("raw/", "/raw/"),
        valid.replace("raw/", "raw/../raw/"),
        valid.replace("raw/", "raw//"),
        valid.replace("raw/", "raw/CON/"),
        valid.replace("host-fingerprint", "other-ledger"),
        valid.replace("/2026/10/10/", "/2026/02/29/"),
        valid.replace("/2026/10/10/", "/2026/10/"),
        valid.replace(".parquet", ".jsonl"),
        valid.replace(".parquet", ".parquet."),
        valid.replace("01a125af", "01A125AF"),
        valid.replace(
            "01a125af-2e7b-8945-899b-fa46f230ac97",
            "4f918a28-1fa6-5125-98d6-98e1cf8e1d15",
        ),
        valid.replace('/', "\\"),
        format!("{valid}\n"),
    ] {
        assert!(
            paths::resolve(&generated.workspace, "state", &bad).is_err(),
            "{bad:?}"
        );
    }
    assert!(!generated.workspace.join("state").exists());
}

#[test]
fn existing_files_are_resolved_without_writes_and_wrong_component_types_fail() {
    let generated = Generated::new("existing");
    let destination = generated.native("state", &raw());
    fs::create_dir_all(destination.parent().unwrap()).unwrap();
    fs::write(&destination, b"unchanged generated bytes").unwrap();
    assert_eq!(
        paths::resolve(&generated.workspace, "state", &raw()).unwrap(),
        fs::canonicalize(&destination).unwrap()
    );
    assert_eq!(
        fs::read(&destination).unwrap(),
        b"unchanged generated bytes"
    );
    fs::remove_file(&destination).unwrap();
    fs::create_dir(&destination).unwrap();
    assert!(paths::resolve(&generated.workspace, "state", &raw()).is_err());
    fs::write(generated.workspace.join("root-file"), b"not a directory").unwrap();
    assert!(paths::resolve(&generated.workspace, "root-file", &raw()).is_err());
    assert!(paths::resolve(&generated.workspace.join("root-file"), "state", &raw()).is_err());
    assert!(paths::resolve(&generated.workspace.join("missing"), "state", &raw()).is_err());
    fs::create_dir(generated.workspace.join("another-state")).unwrap();
    fs::write(
        generated.workspace.join("another-state").join("raw"),
        b"not a directory",
    )
    .unwrap();
    assert!(paths::resolve(&generated.workspace, "another-state", &raw()).is_err());
    #[cfg(windows)]
    {
        let upper_raw = generated.workspace.join("case-state").join("RAW");
        fs::create_dir_all(&upper_raw).unwrap();
        let resolved = paths::resolve(&generated.workspace, "case-state", &raw()).unwrap();
        assert!(resolved.starts_with(fs::canonicalize(&upper_raw).unwrap()));
    }
}

#[cfg(unix)]
fn directory_link(target: &Path, link: &Path) {
    std::os::unix::fs::symlink(target, link).unwrap();
}

#[cfg(windows)]
fn directory_link(target: &Path, link: &Path) {
    match std::os::windows::fs::symlink_dir(target, link) {
        Ok(()) => {}
        Err(error) if error.raw_os_error() == Some(1314) => {
            eprintln!(
                "Windows refused directory symlink creation (native error 1314: required \
                 privilege not held). Testing a real directory junction instead."
            );
            let quote = |path: &Path| {
                // Windows PowerShell's junction constructor does not accept the
                // verbatim prefix returned by std::fs::canonicalize.
                path.to_str()
                    .unwrap()
                    .trim_start_matches(r"\\?\")
                    .replace('\'', "''")
            };
            let command = format!(
                "$ErrorActionPreference = 'Stop'; New-Item -ItemType Junction \
                 -Path '{}' -Target '{}' | Out-Null",
                quote(link),
                quote(target),
            );
            let result = std::process::Command::new("powershell.exe")
                .args(["-NoProfile", "-NonInteractive", "-Command"])
                .arg(command)
                .output()
                .unwrap();
            assert!(
                result.status.success(),
                "real junction creation failed: {}",
                String::from_utf8_lossy(&result.stderr)
            );
        }
        Err(error) => panic!("native directory symlink creation failed: {error}"),
    }
}

#[cfg(any(unix, windows))]
fn unlink_directory(link: &Path) {
    #[cfg(unix)]
    fs::remove_file(link).unwrap();
    #[cfg(windows)]
    fs::remove_dir(link).unwrap();
}

#[test]
#[cfg(any(unix, windows))]
fn real_symlinks_or_junctions_cannot_escape_workspace_target_or_raw_tier() {
    let generated = Generated::new("escaping-links");
    let outside = fs::canonicalize(&generated.root).unwrap().join("outside");
    fs::create_dir(&outside).unwrap();
    let state = generated.workspace.join("state");
    directory_link(&outside, &state);
    assert!(paths::resolve(&generated.workspace, "state", &raw()).is_err());
    unlink_directory(&state);
    fs::create_dir(&state).unwrap();
    let raw_root = state.join("raw");
    directory_link(&outside, &raw_root);
    assert!(paths::resolve(&generated.workspace, "state", &raw()).is_err());
    unlink_directory(&raw_root);
    let compact = fs::canonicalize(&state).unwrap().join("compact");
    fs::create_dir(&compact).unwrap();
    directory_link(&compact, &raw_root);
    assert!(paths::resolve(&generated.workspace, "state", &raw()).is_err());
    unlink_directory(&raw_root);
    fs::create_dir(&raw_root).unwrap();
    let ledger = raw_root.join("host-fingerprint");
    directory_link(&outside, &ledger);
    assert!(paths::resolve(&generated.workspace, "state", &raw()).is_err());
    unlink_directory(&ledger);
    fs::create_dir(&ledger).unwrap();
    directory_link(&outside, &ledger.join("2026"));
    assert!(paths::resolve(&generated.workspace, "state", &raw()).is_err());
    unlink_directory(&ledger.join("2026"));
}

#[test]
#[cfg(any(unix, windows))]
fn real_links_within_the_raw_root_remain_contained() {
    let generated = Generated::new("internal-links");
    let raw_root = generated.workspace.join("state").join("raw");
    let held = raw_root.join("held");
    fs::create_dir_all(&held).unwrap();
    let held = fs::canonicalize(held).unwrap();
    let trial = raw_root.join("trial");
    directory_link(&held, &trial);
    let relative = paths::raw_path(
        &prefix(&["trial", "host-fingerprint"]),
        "2026-10-10",
        file_id(),
        Format::Json,
    )
    .unwrap();
    let expected = held
        .join("host-fingerprint")
        .join("2026")
        .join("10")
        .join("10")
        .join(format!("{}.json", file_id()));
    assert_eq!(
        paths::resolve(&generated.workspace, "state", &relative).unwrap(),
        expected
    );
    assert!(!held.join("host-fingerprint").exists());
    unlink_directory(&trial);
}

#[test]
#[cfg(unix)]
fn dangling_links_and_escaping_leaf_file_symlinks_are_not_missing_paths() {
    let generated = Generated::new("leaf-links");
    let state = generated.workspace.join("state");
    fs::create_dir(&state).unwrap();
    std::os::unix::fs::symlink(generated.root.join("missing"), state.join("raw")).unwrap();
    assert!(paths::resolve(&generated.workspace, "state", &raw()).is_err());
    fs::remove_file(state.join("raw")).unwrap();
    let outside_file = generated.root.join("outside-file");
    fs::write(&outside_file, b"outside").unwrap();
    let destination = generated.native("state", &raw());
    fs::create_dir_all(destination.parent().unwrap()).unwrap();
    std::os::unix::fs::symlink(fs::canonicalize(&outside_file).unwrap(), &destination).unwrap();
    assert!(paths::resolve(&generated.workspace, "state", &raw()).is_err());
    assert_eq!(fs::read(outside_file).unwrap(), b"outside");
}
