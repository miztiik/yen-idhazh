//! What does the named process hold, without following an exited or reused PID?

use crate::contracts::events::{ProcessTarget, UnavailableReason};
use crate::probe_inputs::files::{Reading, SourceRoot};
use crate::{Result, Validate};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, PartialEq)]
pub struct ProcessReading {
    pub identity: Reading<ProcessTarget>,
    pub rss: Reading<i64>,
    pub hwm: Reading<i64>,
    pub anon: Reading<i64>,
    pub faults: Reading<i64>,
    pub legacy_status: Reading<std::collections::BTreeMap<String, String>>,
}

pub fn kilobytes(text: &Reading<String>, key: &str) -> Reading<i64> {
    let text = match text.get() {
        Ok(v) => v,
        Err(e) => return Reading::absent(e),
    };
    let mut result = None;
    for line in text.lines() {
        let Some((name, rest)) = line.split_once(':') else {
            continue;
        };
        if name.trim() != key {
            continue;
        }
        let value = rest.split_whitespace().next().unwrap_or("");
        if !value.is_empty() && value.bytes().all(|v| v.is_ascii_digit()) {
            result = value.parse::<i64>().ok();
        }
    }
    result.map_or_else(
        || Reading::absent(UnavailableReason::Malformed),
        Reading::found,
    )
}

pub fn bytes(text: &Reading<String>, key: &str) -> Reading<i64> {
    let kb = kilobytes(text, key);
    match kb.get() {
        Ok(v) => v.checked_mul(1024).map_or_else(
            || Reading::absent(UnavailableReason::Malformed),
            Reading::found,
        ),
        Err(e) => Reading::absent(e),
    }
}

/// Identity deliberately does not parse the fault or RSS fields of stat.
pub fn identity(stat: &Reading<String>, pid: i64) -> Reading<ProcessTarget> {
    let text = match stat.get() {
        Ok(v) => v,
        Err(UnavailableReason::Missing) => {
            return Reading::absent(UnavailableReason::PidExited);
        }
        Err(e) => return Reading::absent(e),
    };
    let parsed = || -> Option<ProcessTarget> {
        let (prefix, rest) = text.rsplit_once(')')?;
        let reported = prefix.split_whitespace().next()?.parse::<i64>().ok()?;
        if reported != pid || !prefix.contains('(') {
            return None;
        }
        let cells = rest.split_whitespace().collect::<Vec<_>>();
        if matches!(cells.first().copied(), Some("Z" | "X" | "x")) {
            return None;
        }
        let start_ticks = cells.get(19)?.parse::<i64>().ok()?;
        let target = ProcessTarget { pid, start_ticks };
        target.validate().ok()?;
        Some(target)
    };
    if text
        .rsplit_once(')')
        .is_some_and(|(_, rest)| matches!(rest.split_whitespace().next(), Some("Z" | "X" | "x")))
    {
        return Reading::absent(UnavailableReason::PidExited);
    }
    parsed().map_or_else(
        || Reading::absent(UnavailableReason::Malformed),
        Reading::found,
    )
}

pub fn major_faults(stat: &Reading<String>) -> Reading<i64> {
    let text = match stat.get() {
        Ok(v) => v,
        Err(e) => return Reading::absent(e),
    };
    let value = text
        .rsplit_once(')')
        .and_then(|(_, rest)| rest.split_whitespace().nth(9))
        .filter(|v| !v.is_empty() && v.bytes().all(|b| b.is_ascii_digit()))
        .and_then(|v| v.parse::<i64>().ok());
    value.map_or_else(
        || Reading::absent(UnavailableReason::Malformed),
        Reading::found,
    )
}

impl ProcessReading {
    pub fn unavailable(reason: UnavailableReason, memory: bool) -> Self {
        let memory_reason = if memory {
            reason
        } else {
            UnavailableReason::Disabled
        };
        Self {
            identity: Reading::absent(reason),
            rss: Reading::absent(memory_reason),
            hwm: Reading::absent(memory_reason),
            anon: Reading::absent(memory_reason),
            faults: Reading::absent(memory_reason),
            legacy_status: Reading::absent(memory_reason),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ProcessTexts {
    pub target: ProcessTarget,
    pub stat_before: Reading<String>,
    pub stat_after: Reading<String>,
    pub status: Reading<String>,
    pub comm: Reading<String>,
    pub exe: Reading<String>,
    pub cmdline: Reading<String>,
}

pub fn reduce(texts: &ProcessTexts, memory: bool, faults: bool) -> ProcessReading {
    let before = identity(&texts.stat_before, texts.target.pid);
    let after = identity(&texts.stat_after, texts.target.pid);
    for value in [&before, &after] {
        match value.get() {
            Err(e) => return ProcessReading::unavailable(e, memory),
            Ok(v) if v != &texts.target => {
                return ProcessReading::unavailable(UnavailableReason::PidReused, memory);
            }
            _ => {}
        }
    }
    if !memory {
        let mut result = ProcessReading::unavailable(UnavailableReason::Disabled, false);
        result.identity = before;
        return result;
    }
    let mut status = std::collections::BTreeMap::new();
    if let Ok(text) = texts.status.get() {
        for line in text.lines() {
            if line.starts_with("VmRSS:") || line.starts_with("VmHWM:") {
                let (key, value) = line.split_once(':').unwrap();
                status.insert(key.to_owned(), value.trim().to_owned());
            }
        }
    }
    ProcessReading {
        identity: before,
        rss: bytes(&texts.status, "VmRSS"),
        hwm: bytes(&texts.status, "VmHWM"),
        anon: bytes(&texts.status, "RssAnon"),
        faults: if faults {
            major_faults(&texts.stat_after)
        } else {
            Reading::absent(UnavailableReason::Missing)
        },
        legacy_status: match texts.status.get() {
            Ok(_) => Reading::found(status),
            Err(e) => Reading::absent(e),
        },
    }
}

pub struct ProcessSampler {
    pub root: PathBuf,
    source: SourceRoot,
    pub max_processes: usize,
}
impl ProcessSampler {
    pub fn new(root: &Path, max_text: usize, max_processes: usize) -> Result<Self> {
        crate::contracts::host::require(max_processes > 0, "zero process cap")?;
        Ok(Self {
            root: root.to_owned(),
            source: SourceRoot::new(root, max_text)?,
            max_processes,
        })
    }
    pub fn identity(&self, pid: i64) -> Reading<ProcessTarget> {
        identity(&self.source.text(&format!("{pid}/stat")), pid)
    }
    pub fn texts(&self, target: &ProcessTarget, memory: bool, population: bool) -> ProcessTexts {
        let stat_before = self.source.text(&format!("{}/stat", target.pid));
        let valid = identity(&stat_before, target.pid).value.as_ref() == Some(target);
        let read = |leaf: &str| {
            if memory && valid {
                self.source.text(&format!("{}/{leaf}", target.pid))
            } else {
                Reading::absent(if memory {
                    UnavailableReason::PidReused
                } else {
                    UnavailableReason::Disabled
                })
            }
        };
        let status = read("status");
        let comm = if population {
            read("comm")
        } else {
            Reading::absent(UnavailableReason::Missing)
        };
        let cmdline = if population {
            read("cmdline")
        } else {
            Reading::absent(UnavailableReason::Missing)
        };
        // exe is metadata, not a followed source file; it may name a path outside procfs.
        let exe = if memory && valid && population {
            match std::fs::read_link(self.root.join(target.pid.to_string()).join("exe")) {
                Ok(v) => Reading::found(v.to_string_lossy().replace('\\', "/")),
                Err(_) => Reading::absent(UnavailableReason::Missing),
            }
        } else {
            Reading::absent(UnavailableReason::Disabled)
        };
        ProcessTexts {
            target: target.clone(),
            stat_before,
            status,
            comm,
            exe,
            cmdline,
            stat_after: self.source.text(&format!("{}/stat", target.pid)),
        }
    }
    pub fn sample(&self, target: &ProcessTarget, memory: bool, faults: bool) -> ProcessReading {
        reduce(&self.texts(target, memory, false), memory, faults)
    }
    pub fn population(&self, memory: bool) -> Reading<Vec<ProcessTexts>> {
        if !memory {
            return Reading::absent(UnavailableReason::Disabled);
        }
        let entries = match std::fs::read_dir(&self.root) {
            Ok(v) => v,
            Err(e) => {
                return Reading::absent(if e.kind() == std::io::ErrorKind::PermissionDenied {
                    UnavailableReason::PermissionDenied
                } else {
                    UnavailableReason::Missing
                });
            }
        };
        let mut names = Vec::new();
        for entry in entries.take(self.max_processes.saturating_add(1)) {
            let Ok(entry) = entry else {
                return Reading::absent(UnavailableReason::Malformed);
            };
            names.push(entry.file_name().to_string_lossy().into_owned());
        }
        if names.len() > self.max_processes {
            return Reading::absent(UnavailableReason::IncompleteCoverage);
        }
        names.sort();
        let mut result = Vec::new();
        for name in names {
            if !name.bytes().all(|v| v.is_ascii_digit()) {
                continue;
            }
            let Ok(pid) = name.parse::<i64>() else {
                continue;
            };
            let comm = self.source.text(&format!("{pid}/comm"));
            if !comm
                .value
                .as_ref()
                .is_some_and(|v| v.trim().starts_with("python"))
            {
                continue;
            }
            if let Some(target) = self.identity(pid).value {
                result.push(self.texts(&target, true, true));
            }
        }
        Reading::found(result)
    }
}
