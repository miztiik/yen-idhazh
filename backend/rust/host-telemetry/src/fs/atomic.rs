//! How does one file become visible whole without damaging an earlier file?
//!
//! Staging stays in the destination directory. These operations do not promise
//! power-loss durability. Callers own containment and must control the directory:
//! std path checks cannot prevent hostile directory or symlink swaps.

use std::{
    fs::{self, File, OpenOptions},
    io::{self, Write},
    path::{Path, PathBuf},
    sync::atomic::{AtomicU64, Ordering},
};

// This nonce names temporary files only; it is not a ledger identity or clock.
static NEXT_TEMP: AtomicU64 = AtomicU64::new(0);
const MAX_TEMP_ATTEMPTS: usize = 128;

/// Replace a file with complete bytes through a destination-local rename.
///
/// Missing parent directories are created. An error before publication leaves an
/// existing destination unchanged. Destination symlinks are refused, not followed.
pub fn write_atomic_bytes(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let parent = prepare_destination(path)?;
    let mut temporary = stage_bytes(parent, bytes)?;
    refuse_symlink(path)?;
    fs::rename(&temporary.path, path)?;
    temporary.cleanup = false;
    Ok(())
}

/// Publish complete bytes without replacing an existing file.
///
/// Identical existing bytes succeed; different bytes return `AlreadyExists`
/// with a conflict diagnostic. A hard link publishes the staged file atomically,
/// so concurrent writers cannot overwrite the winner. Unsupported hard links
/// fail rather than falling back to a clobbering rename.
///
/// A cleanup error after linking can leave the completed destination present;
/// retrying the same bytes is safe. Destination symlinks are refused, not followed.
pub fn publish_immutable(path: &Path, bytes: &[u8]) -> io::Result<()> {
    let parent = prepare_destination(path)?;
    if identical_existing(path, bytes)? {
        return Ok(());
    }
    let mut temporary = stage_bytes(parent, bytes)?;
    refuse_symlink(path)?;
    match fs::hard_link(&temporary.path, path) {
        Ok(()) => {
            fs::remove_file(&temporary.path)?;
            temporary.cleanup = false;
            Ok(())
        }
        Err(error) if error.kind() == io::ErrorKind::AlreadyExists => {
            if identical_existing(path, bytes)? {
                Ok(())
            } else {
                Err(error)
            }
        }
        Err(error) => Err(error),
    }
}

fn prepare_destination(path: &Path) -> io::Result<&Path> {
    if path.file_name().is_none() {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("destination has no file name: {}", path.display()),
        ));
    }
    refuse_symlink(path)?;
    let parent = path
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
        .unwrap_or_else(|| Path::new("."));
    fs::create_dir_all(parent)?;
    Ok(parent)
}

fn refuse_symlink(path: &Path) -> io::Result<()> {
    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_symlink() => Err(symlink_error(path)),
        Ok(_) => Ok(()),
        Err(error) if error.kind() == io::ErrorKind::NotFound => Ok(()),
        Err(error) => Err(error),
    }
}

fn symlink_error(path: &Path) -> io::Error {
    io::Error::new(
        io::ErrorKind::InvalidInput,
        format!("refusing symlink destination: {}", path.display()),
    )
}

fn identical_existing(path: &Path, bytes: &[u8]) -> io::Result<bool> {
    let metadata = match fs::symlink_metadata(path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(false),
        Err(error) => return Err(error),
    };
    if metadata.file_type().is_symlink() {
        return Err(symlink_error(path));
    }
    if metadata.is_file() && metadata.len() == bytes.len() as u64 && fs::read(path)? == bytes {
        return Ok(true);
    }
    Err(io::Error::new(
        io::ErrorKind::AlreadyExists,
        format!(
            "immutable publication conflict: destination is not a regular file with identical bytes: {}",
            path.display()
        ),
    ))
}

struct TemporaryFile {
    path: PathBuf,
    cleanup: bool,
}

impl Drop for TemporaryFile {
    fn drop(&mut self) {
        // Never sweep a directory: this path was claimed by our create_new.
        if self.cleanup {
            let _ = fs::remove_file(&self.path);
        }
    }
}

fn create_temporary(parent: &Path) -> io::Result<(TemporaryFile, File)> {
    for _ in 0..MAX_TEMP_ATTEMPTS {
        let nonce = NEXT_TEMP
            .fetch_update(Ordering::Relaxed, Ordering::Relaxed, |value| {
                value.checked_add(1)
            })
            .map_err(|_| io::Error::other("atomic temporary-file nonce exhausted"))?;
        let path = parent.join(format!(".idhazh-atomic-{}-{nonce}.tmp", std::process::id()));
        match OpenOptions::new().write(true).create_new(true).open(&path) {
            Ok(file) => {
                return Ok((
                    TemporaryFile {
                        path,
                        cleanup: true,
                    },
                    file,
                ));
            }
            Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
            Err(error) => return Err(error),
        }
    }
    Err(io::Error::new(
        io::ErrorKind::AlreadyExists,
        format!(
            "unable to create an atomic temporary file after {MAX_TEMP_ATTEMPTS} name collisions in {}",
            parent.display()
        ),
    ))
}

fn stage_bytes(parent: &Path, bytes: &[u8]) -> io::Result<TemporaryFile> {
    let (temporary, mut file) = create_temporary(parent)?;
    let result = file.write_all(bytes).and_then(|()| file.flush());
    // Close before publication and cleanup, including on write errors (Windows).
    drop(file);
    result?;
    Ok(temporary)
}
