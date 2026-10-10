//! Where may named raw host and evidence files go inside a filesystem workspace?

use crate::contracts::file_envelope::Format;
use crate::contracts::host::{Result, day, rel_path, require};
use std::fs;
use std::io::ErrorKind;
use std::path::{Path, PathBuf};
use uuid::{Uuid, Variant};

fn segment(value: &str) -> Result<()> {
    rel_path(value)?;
    require(
        !value.contains('/') && !value.ends_with('.') && !value.ends_with(' '),
        "path requires one canonical segment without a trailing dot or space",
    )?;
    let stem = value.split('.').next().unwrap_or("").to_ascii_uppercase();
    let numbered_device = stem
        .strip_prefix("COM")
        .or_else(|| stem.strip_prefix("LPT"))
        .is_some_and(|n| n.len() == 1 && matches!(n.as_bytes()[0], b'1'..=b'9'));
    require(
        !matches!(stem.as_str(), "CON" | "PRN" | "AUX" | "NUL") && !numbered_device,
        "Windows reserved device path segment",
    )
}

fn segments(value: &str) -> Result<Vec<&str>> {
    rel_path(value)?;
    let parts = value.split('/').collect::<Vec<_>>();
    for part in &parts {
        segment(part)?;
    }
    Ok(parts)
}

pub fn raw_path(prefix: &[String], covers: &str, file_id: Uuid, format: Format) -> Result<String> {
    require(
        prefix.last().is_some_and(|v| v == "host-fingerprint"),
        "host prefix must end in host-fingerprint",
    )?;
    for part in prefix {
        segment(part)?;
    }
    day(covers)?;
    require(
        file_id.get_version_num() == 8 && file_id.get_variant() == Variant::RFC4122,
        "raw filename requires RFC UUID8",
    )?;
    let suffix = match format {
        Format::Parquet => "parquet",
        Format::Json => "json",
    };
    let result = format!(
        "raw/{}/{}/{}.{}",
        prefix.join("/"),
        covers.replace('-', "/"),
        file_id,
        suffix
    );
    rel_path(&result)?;
    Ok(result)
}

fn raw_segments(relative_path: &str) -> Result<Vec<&str>> {
    let parts = segments(relative_path)?;
    require(
        parts.len() >= 6 && parts[0] == "raw",
        "only generated raw host file paths can be resolved",
    )?;
    let day_start = parts.len() - 4;
    let prefix = parts[1..day_start]
        .iter()
        .map(|v| (*v).to_owned())
        .collect::<Vec<_>>();
    let covers = parts[day_start..day_start + 3].join("-");
    let (name, suffix) = parts[parts.len() - 1]
        .rsplit_once('.')
        .ok_or("raw file requires a format suffix")?;
    let format = match suffix {
        "parquet" => Format::Parquet,
        "json" => Format::Json,
        _ => return Err("unsupported raw host file suffix".to_owned()),
    };
    let file_id = Uuid::parse_str(name).map_err(|_| "invalid raw file UUID")?;
    require(
        raw_path(&prefix, &covers, file_id, format)? == relative_path,
        "raw path is not canonical generated grammar",
    )?;
    Ok(parts)
}

fn descend(parent: &Path, part: &str, boundary: &Path, directory: bool) -> Result<PathBuf> {
    let candidate = parent.join(part);
    match fs::symlink_metadata(&candidate) {
        Ok(original) => {
            require(
                directory || !original.file_type().is_symlink(),
                "file destination cannot be a symlink",
            )?;
            // Canonicalization follows both Unix symlinks and Windows junctions.
            // A dangling link is an error, not a missing directory to create.
            let resolved = fs::canonicalize(&candidate)
                .map_err(|_| format!("cannot resolve existing path component {part}"))?;
            require(
                resolved.starts_with(boundary),
                "path component escapes its declared filesystem root",
            )?;
            let metadata = fs::metadata(&resolved)
                .map_err(|_| format!("cannot inspect resolved path component {part}"))?;
            require(
                if directory {
                    metadata.is_dir()
                } else {
                    metadata.is_file()
                },
                "existing path component has the wrong filesystem type",
            )?;
            Ok(resolved)
        }
        Err(error) if error.kind() == ErrorKind::NotFound => Ok(candidate),
        Err(_) => Err(format!("cannot inspect path component {part}")),
    }
}

/// Resolve one named evidence document, never a directory listing.
#[allow(
    dead_code,
    reason = "The raw-path fixture also compiles this source as its own module."
)]
pub fn resolve_document(workspace: &Path, relative_path: &str) -> Result<PathBuf> {
    resolve_named(workspace, relative_path, false)
}

#[allow(
    dead_code,
    reason = "The raw-path fixture also compiles this source as its own module."
)]
pub fn resolve_directory(workspace: &Path, relative_path: &str) -> Result<PathBuf> {
    resolve_named(workspace, relative_path, true)
}

fn resolve_named(workspace: &Path, relative_path: &str, directory: bool) -> Result<PathBuf> {
    let parts = segments(relative_path)?;
    let workspace = fs::canonicalize(workspace)
        .map_err(|_| "workspace must be an existing resolvable directory")?;
    require(workspace.is_dir(), "workspace must be a directory")?;
    let mut resolved = workspace.clone();
    for (index, part) in parts.iter().enumerate() {
        resolved = descend(
            &resolved,
            part,
            &workspace,
            directory || index + 1 != parts.len(),
        )?;
    }
    Ok(resolved)
}

/// Resolve existing components without creating missing descendants.
///
/// This checks ordinary filesystem containment, not concurrent hostile renames.
/// The store must call it before atomic publication; receipts grant no authority.
pub fn resolve(workspace: &Path, target_root: &str, relative_path: &str) -> Result<PathBuf> {
    let target_parts = segments(target_root)?;
    let raw_parts = raw_segments(relative_path)?;
    let workspace = fs::canonicalize(workspace)
        .map_err(|_| "workspace must be an existing resolvable directory")?;
    require(workspace.is_dir(), "workspace must be a directory")?;
    let mut target = workspace.clone();
    for part in target_parts {
        target = descend(&target, part, &workspace, true)?;
    }
    let mut resolved = descend(&target, "raw", &target, true)?;
    let raw_name = resolved.file_name().and_then(|v| v.to_str()).unwrap_or("");
    // Resolve real directory casing on Windows, but do not admit a raw-root
    // link into compact or another sibling as a new raw tier.
    require(
        resolved.parent() == Some(target.as_path())
            && if cfg!(windows) {
                raw_name.eq_ignore_ascii_case("raw")
            } else {
                raw_name == "raw"
            },
        "raw root escapes the declared raw tier",
    )?;
    let raw_boundary = resolved.clone();
    for (index, part) in raw_parts.iter().enumerate().skip(1) {
        resolved = descend(&resolved, part, &raw_boundary, index + 1 != raw_parts.len())?;
    }
    Ok(resolved)
}
