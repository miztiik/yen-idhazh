//! How are named virtual-source texts read within their operator-owned root and byte cap?

use crate::contracts::events::UnavailableReason;
use crate::contracts::host::{Result, require};
use serde::{Deserialize, Serialize};
use std::io::Read;
use std::path::{Component, Path, PathBuf};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Reading<T> {
    pub value: Option<T>,
    pub reason: Option<UnavailableReason>,
}
impl<T> Reading<T> {
    pub fn found(value: T) -> Self {
        Self {
            value: Some(value),
            reason: None,
        }
    }
    pub fn absent(reason: UnavailableReason) -> Self {
        Self {
            value: None,
            reason: Some(reason),
        }
    }
    pub fn validate(&self) -> Result<()> {
        require(
            self.value.is_some() != self.reason.is_some(),
            "source must have a value or a reason",
        )
    }
    pub fn get(&self) -> std::result::Result<&T, UnavailableReason> {
        self.value
            .as_ref()
            .ok_or(self.reason.unwrap_or(UnavailableReason::Malformed))
    }
}

pub fn read_text(path: &Path, maximum: usize) -> Reading<String> {
    let read = || -> std::io::Result<String> {
        let file = std::fs::File::open(path)?;
        let mut bytes = Vec::new();
        file.take(maximum.saturating_add(1) as u64)
            .read_to_end(&mut bytes)?;
        if bytes.len() > maximum {
            return Err(std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "source exceeds cap",
            ));
        }
        String::from_utf8(bytes)
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))
    };
    match read() {
        Ok(text) => Reading::found(text),
        Err(error) => Reading::absent(match error.kind() {
            std::io::ErrorKind::PermissionDenied => UnavailableReason::PermissionDenied,
            std::io::ErrorKind::NotFound => UnavailableReason::Missing,
            _ => UnavailableReason::Malformed,
        }),
    }
}

pub struct SourceRoot {
    root: PathBuf,
    resolved_root: PathBuf,
    pub maximum: usize,
}
impl SourceRoot {
    pub fn new(root: &Path, maximum: usize) -> Result<Self> {
        require(maximum > 0, "zero source byte cap")?;
        Ok(Self {
            root: root.to_path_buf(),
            resolved_root: std::fs::canonicalize(root).map_err(|e| e.to_string())?,
            maximum,
        })
    }
    pub fn path(&self, relative: &str) -> Result<PathBuf> {
        require(
            !Path::new(relative).is_absolute()
                && Path::new(relative)
                    .components()
                    .all(|c| matches!(c, Component::Normal(_))),
            "virtual-source traversal",
        )?;
        let path = self.root.join(relative);
        if path.exists() {
            let actual = std::fs::canonicalize(&path).map_err(|e| e.to_string())?;
            require(
                actual.starts_with(&self.resolved_root),
                "virtual-source link escapes root",
            )?;
        } else {
            let mut ancestor = path.parent();
            while let Some(parent) = ancestor {
                if parent.exists() {
                    require(
                        std::fs::canonicalize(parent)
                            .map_err(|e| e.to_string())?
                            .starts_with(&self.resolved_root),
                        "virtual-source ancestor escapes root",
                    )?;
                    break;
                }
                ancestor = parent.parent();
            }
        }
        Ok(path)
    }
    pub fn text(&self, relative: &str) -> Reading<String> {
        match self.path(relative) {
            Ok(path) => read_text(&path, self.maximum),
            Err(_) => Reading::absent(UnavailableReason::Malformed),
        }
    }
    pub fn entries(
        &self,
        relative: &str,
        maximum: usize,
    ) -> std::result::Result<Vec<String>, UnavailableReason> {
        let path = self
            .path(relative)
            .map_err(|_| UnavailableReason::Malformed)?;
        let iterator = std::fs::read_dir(path).map_err(|e| {
            if e.kind() == std::io::ErrorKind::PermissionDenied {
                UnavailableReason::PermissionDenied
            } else {
                UnavailableReason::Missing
            }
        })?;
        let mut names = Vec::new();
        for entry in iterator.take(maximum.saturating_add(1)) {
            names.push(
                entry
                    .map_err(|_| UnavailableReason::Malformed)?
                    .file_name()
                    .into_string()
                    .map_err(|_| UnavailableReason::Malformed)?,
            );
        }
        if names.len() > maximum {
            return Err(UnavailableReason::IncompleteCoverage);
        }
        names.sort();
        Ok(names)
    }
}
