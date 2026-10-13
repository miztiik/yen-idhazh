//! Which unchanged legacy job records and runtime memory artifacts follow these observations?

use crate::contracts::events::*;
use crate::contracts::host::require;
use crate::probe_inputs::files::Reading;
use crate::sampling::{
    capture::ResourceFrame,
    process::{kilobytes, reduce},
};
use crate::{Result, Validate};
use std::{
    fs::{File, OpenOptions},
    io::Write,
    path::Path,
};

pub const RUNTIME_STATUS_FILENAME: &str = "server-rss-samples.jsonl";
pub const RUNTIME_PEAK_FILENAME: &str = "cgroup-memory-peak.txt";
// The legacy runtime sampler wakes once per second, independently of item/job cadences.
pub const RUNTIME_INTERVAL_MS: u64 = 1000;

pub fn sample(
    frame: &ResourceFrame,
    server: Option<&ProcessTarget>,
    memory: bool,
) -> Result<Option<(LegacyJobSample, Vec<LegacyProcessRollcall>)>> {
    if !memory {
        return Ok(None);
    }
    let population = frame
        .population
        .get()
        .map_err(|v| format!("Python population unavailable: {v:?}"))?;
    let ts = chrono::DateTime::parse_from_rfc3339(&frame.captured_at)
        .map_err(|e| e.to_string())?
        .with_timezone(&chrono::Utc)
        .format("%Y-%m-%dT%H:%M:%SZ")
        .to_string();
    let mut rows = Vec::new();
    for texts in population {
        if !texts
            .comm
            .value
            .as_ref()
            .is_some_and(|v| v.trim().starts_with("python"))
        {
            continue;
        }
        let captured = reduce(texts, true, false);
        if captured.identity.value.is_none() {
            continue;
        }
        let Some(resident) = kilobytes(&texts.status, "VmRSS").value else {
            continue;
        };
        let args = texts.cmdline.value.as_ref().map(|v| {
            let fields = v
                .split('\0')
                .filter(|v| !v.is_empty())
                .skip(1)
                .take(3)
                .collect::<Vec<_>>()
                .join(" ");
            fields.split_whitespace().collect::<Vec<_>>().join(" ")
        });
        rows.push(LegacyProcessRollcall {
            ts: ts.clone(),
            pid: texts.target.pid,
            comm: texts.comm.value.as_ref().unwrap().trim().to_owned(),
            vmrss_kb: resident,
            vmhwm_kb: kilobytes(&texts.status, "VmHWM").value,
            exe: texts.exe.value.clone(),
            args,
        });
    }
    rows.sort_by_key(|v| v.pid.to_string());
    let sum = |hwm: bool| -> Result<i64> {
        rows.iter().try_fold(0_i64, |sum, row| {
            let value = if hwm {
                row.vmhwm_kb.filter(|v| *v != 0).unwrap_or(row.vmrss_kb)
            } else {
                row.vmrss_kb
            };
            sum.checked_add(value)
                .ok_or_else(|| "Python population total overflows".to_owned())
        })
    };
    let server_status = server
        .and_then(|target| frame.processes.iter().find(|v| &v.target == target))
        .filter(|v| reduce(v, true, false).identity.value.is_some())
        .map(|v| &v.status);
    let missing = Reading::absent(UnavailableReason::Missing);
    let record = LegacyJobSample {
        ts,
        llama_vmrss_kb: kilobytes(server_status.unwrap_or(&missing), "VmRSS").value,
        llama_vmhwm_kb: kilobytes(server_status.unwrap_or(&missing), "VmHWM").value,
        python_vmrss_kb: sum(false)?,
        python_procs: rows.len() as i64,
        python_vmhwm_kb: sum(true)?,
        mem_total_kb: kilobytes(&frame.meminfo, "MemTotal").value,
        mem_available_kb: kilobytes(&frame.meminfo, "MemAvailable").value,
        committed_as_kb: kilobytes(&frame.meminfo, "Committed_AS").value,
        cgroup_current_bytes: frame.cgroup_current.value.as_ref().and_then(|v| {
            let v = v.trim();
            if v.is_empty() || !v.bytes().all(|v| v.is_ascii_digit()) {
                None
            } else {
                v.parse().ok()
            }
        }),
    };
    record.validate()?;
    for row in &rows {
        row.validate()?;
    }
    Ok(Some((record, rows)))
}

pub fn runtime_status(
    frame: &ResourceFrame,
    server: Option<&ProcessTarget>,
    memory: bool,
) -> Option<std::collections::BTreeMap<String, String>> {
    if !memory {
        return None;
    }
    let target = server?;
    let reading = frame
        .processes
        .iter()
        .find(|v| &v.target == target)
        .map(|v| reduce(v, true, false));
    Some(
        reading
            .and_then(|v| v.legacy_status.value)
            .unwrap_or_default(),
    )
}

pub struct Artifacts {
    sample: File,
    rollcall: File,
    runtime: File,
    peak_path: std::path::PathBuf,
    bytes: u64,
    records: u64,
    max_bytes: u64,
    max_records: u64,
}
impl Artifacts {
    pub fn create(
        workspace: &Path,
        root: &str,
        limits: &HostEventLimits,
        memory: bool,
    ) -> Result<Option<Self>> {
        if !memory {
            return Ok(None);
        }
        require(
            !root
                .split('/')
                .any(|v| matches!(v, "state" | "raw" | "compact" | "public")),
            "artifact root aliases persistent state",
        )?;
        let resolved = crate::ledger::paths::resolve_directory(workspace, root)?;
        std::fs::create_dir_all(&resolved).map_err(|e| e.to_string())?;
        let open = |name| -> Result<File> {
            let path =
                crate::ledger::paths::resolve_document(workspace, &format!("{root}/{name}"))?;
            OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(path)
                .map_err(|e| e.to_string())
        };
        Ok(Some(Self {
            sample: open(LEGACY_JOB_SAMPLE_FILENAME)?,
            rollcall: open(LEGACY_PROCESS_ROLLCALL_FILENAME)?,
            runtime: open(RUNTIME_STATUS_FILENAME)?,
            peak_path: resolved.join(RUNTIME_PEAK_FILENAME),
            bytes: 0,
            records: 0,
            max_bytes: limits.max_session_bytes as u64,
            max_records: limits.max_session_events as u64,
        }))
    }
    pub fn write_sample(
        &mut self,
        record: &LegacyJobSample,
        rows: &[LegacyProcessRollcall],
    ) -> Result<()> {
        let a = crate::canonical_json::row_line(
            &serde_json::to_value(record).map_err(|e| e.to_string())?,
        )?;
        let mut b = Vec::new();
        for row in rows {
            b.extend(crate::canonical_json::row_line(
                &serde_json::to_value(row).map_err(|e| e.to_string())?,
            )?);
        }
        self.reserve(a.len() + b.len(), rows.len() + 1)?;
        self.sample
            .write_all(&a)
            .and_then(|_| self.sample.flush())
            .map_err(|e| e.to_string())?;
        self.rollcall
            .write_all(&b)
            .and_then(|_| self.rollcall.flush())
            .map_err(|e| e.to_string())
    }
    pub fn write_runtime(
        &mut self,
        status: &std::collections::BTreeMap<String, String>,
    ) -> Result<()> {
        let raw = crate::canonical_json::row_line(
            &serde_json::to_value(status).map_err(|e| e.to_string())?,
        )?;
        self.reserve(raw.len(), 1)?;
        self.runtime
            .write_all(&raw)
            .and_then(|_| self.runtime.flush())
            .map_err(|e| e.to_string())
    }
    pub fn write_peak(&mut self, peak: &Reading<String>) -> Result<()> {
        if let Some(value) = &peak.value {
            let raw = format!("{}\n", value.trim());
            self.reserve(raw.len(), 1)?;
            crate::fs::atomic::publish_immutable(&self.peak_path, raw.as_bytes())
                .map_err(|e| e.to_string())?;
        }
        Ok(())
    }
    fn reserve(&mut self, bytes: usize, records: usize) -> Result<()> {
        require(
            self.bytes.saturating_add(bytes as u64) <= self.max_bytes
                && self.records.saturating_add(records as u64) <= self.max_records,
            "legacy artifact capacity exhausted",
        )?;
        self.bytes += bytes as u64;
        self.records += records as u64;
        Ok(())
    }
}
