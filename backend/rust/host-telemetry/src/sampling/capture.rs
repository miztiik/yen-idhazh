//! Which bounded live or recorded source texts back one resource capture?

use crate::contracts::events::*;
use crate::probe_inputs::files::{Reading, read_text};
use crate::sampling::{
    machine,
    process::{self, ProcessSampler, ProcessTexts},
};
use crate::windows::reduce::{Snapshot, absent_server};
use crate::{Result, Validate};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResourceFrame {
    pub captured_at: String,
    pub proc_stat: Reading<String>,
    pub loadavg: Reading<String>,
    pub meminfo: Reading<String>,
    pub processes: Vec<ProcessTexts>,
    pub population: Reading<Vec<ProcessTexts>>,
    pub cgroup_current: Reading<String>,
    pub cgroup_peak: Reading<String>,
}
impl ResourceFrame {
    pub fn validate(&self, limits: &HostCaptureLimits) -> Result<()> {
        crate::contracts::host::timestamp(&self.captured_at)?;
        crate::contracts::host::require(
            self.processes.len() as i64 <= limits.max_processes
                && self
                    .population
                    .value
                    .as_ref()
                    .is_none_or(|v| v.len() as i64 <= limits.max_processes),
            "resource process capture exceeds cap",
        )?;
        let text = |v: &Reading<String>, cap: i64| -> Result<()> {
            v.validate()?;
            crate::contracts::host::require(
                v.value.as_ref().is_none_or(|v| v.len() as i64 <= cap),
                "resource text exceeds cap",
            )
        };
        for v in [&self.proc_stat, &self.loadavg, &self.meminfo] {
            text(v, limits.max_proc_text_bytes)?;
        }
        self.population.validate()?;
        let mut seen = std::collections::HashSet::new();
        for p in &self.processes {
            crate::contracts::host::require(seen.insert(p.target.pid), "duplicate resource PID")?;
        }
        for p in self
            .processes
            .iter()
            .chain(self.population.value.iter().flatten())
        {
            p.target.validate()?;
            for v in [
                &p.stat_before,
                &p.stat_after,
                &p.status,
                &p.comm,
                &p.exe,
                &p.cmdline,
            ] {
                text(v, limits.max_proc_text_bytes)?;
            }
        }
        text(&self.cgroup_current, limits.max_sysfs_text_bytes)?;
        text(&self.cgroup_peak, limits.max_sysfs_text_bytes)
    }
    pub fn snapshot(&self, window: &WindowBody, memory: bool, endpoints: bool) -> Snapshot {
        let process = |target: &ProcessTarget| {
            self.processes
                .iter()
                .find(|v| &v.target == target)
                .map(|v| process::reduce(v, memory, endpoints))
                .unwrap_or_else(|| {
                    process::ProcessReading::unavailable(UnavailableReason::PidExited, memory)
                })
        };
        Snapshot {
            captured_at: self.captured_at.clone(),
            machine: machine::reduce(&self.proc_stat, &self.loadavg, &self.meminfo, memory),
            worker: process(&window.target),
            server: window
                .server
                .as_ref()
                .map(process)
                .unwrap_or_else(|| absent_server(memory)),
        }
    }
}

pub struct LiveCapture {
    processes: ProcessSampler,
    machine: machine::MachineSampler,
    cgroup: PathBuf,
    sysfs_cap: usize,
    memory: bool,
}
impl LiveCapture {
    pub fn new(
        proc_root: &Path,
        cgroup: &Path,
        limits: &HostCaptureLimits,
        memory: bool,
    ) -> Result<Self> {
        limits.validate()?;
        Ok(Self {
            processes: ProcessSampler::new(
                proc_root,
                limits.max_proc_text_bytes as usize,
                limits.max_processes as usize,
            )?,
            machine: machine::MachineSampler::new(proc_root, limits.max_proc_text_bytes as usize)?,
            cgroup: cgroup.to_owned(),
            sysfs_cap: limits.max_sysfs_text_bytes as usize,
            memory,
        })
    }
    pub fn capture(&self, targets: &[ProcessTarget], population: bool) -> ResourceFrame {
        let (proc_stat, loadavg, meminfo) = self.machine.texts(self.memory);
        let disabled = || Reading::absent(UnavailableReason::Disabled);
        let cgroup_current = if self.memory && population {
            let v2 = read_text(&self.cgroup.join("memory.current"), self.sysfs_cap);
            if v2.reason == Some(UnavailableReason::Missing) {
                read_text(
                    &self.cgroup.join("memory").join("memory.usage_in_bytes"),
                    self.sysfs_cap,
                )
            } else {
                v2
            }
        } else {
            disabled()
        };
        ResourceFrame {
            captured_at: utc_now(),
            proc_stat,
            loadavg,
            meminfo,
            processes: targets
                .iter()
                .map(|v| self.processes.texts(v, self.memory, false))
                .collect(),
            population: if population {
                self.processes.population(self.memory)
            } else {
                Reading::absent(UnavailableReason::Missing)
            },
            cgroup_current,
            cgroup_peak: if self.memory && population {
                read_text(&self.cgroup.join("memory.peak"), self.sysfs_cap)
            } else {
                disabled()
            },
        }
    }
    pub fn boot_id(&self) -> Reading<String> {
        read_text(
            &self
                .processes
                .root
                .join("sys")
                .join("kernel")
                .join("random")
                .join("boot_id"),
            self.sysfs_cap,
        )
    }
    pub fn peak(&self) -> Reading<String> {
        if self.memory {
            read_text(&self.cgroup.join("memory.peak"), self.sysfs_cap)
        } else {
            Reading::absent(UnavailableReason::Disabled)
        }
    }
}

pub fn utc_now() -> String {
    let time: chrono::DateTime<chrono::Utc> = std::time::SystemTime::now().into();
    time.to_rfc3339_opts(chrono::SecondsFormat::Secs, true)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReplayAction {
    pub frame: usize,
    pub at_ms: u64,
    pub event: Option<HostEvent>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ResourceReplay {
    pub version: String,
    pub frames: Vec<ResourceFrame>,
    pub actions: Vec<ReplayAction>,
}
impl ResourceReplay {
    pub fn from_bytes(raw: &[u8], manifest: &HostSessionManifest) -> Result<Self> {
        crate::contracts::host::require(
            raw.len() as i64 <= manifest.capture_limits.max_log_bytes,
            "resource replay exceeds input cap",
        )?;
        let value: Self = serde_json::from_slice(raw).map_err(|e| e.to_string())?;
        crate::contracts::host::require(
            value.version == default_version(),
            "unknown resource replay version",
        )?;
        crate::contracts::host::require(
            value.frames.len() as i64 <= manifest.limits.max_session_events
                && value.actions.len() as i64 <= manifest.limits.max_session_events,
            "resource replay count exceeds cap",
        )?;
        for frame in &value.frames {
            frame.validate(&manifest.capture_limits)?;
        }
        for action in &value.actions {
            crate::contracts::host::require(
                action.frame < value.frames.len(),
                "resource replay frame out of bounds",
            )?;
            if let Some(event) = &action.event {
                event.validate()?;
            }
        }
        crate::contracts::host::require(
            value.actions.windows(2).all(|v| v[0].at_ms <= v[1].at_ms),
            "replay monotonic time reversed",
        )?;
        Ok(value)
    }
}
