//! How do one window's endpoints and bounded running extrema become the existing HostCells?

use crate::contracts::events::*;
use crate::probe_inputs::files::Reading;
use crate::sampling::{
    machine::{MachineReading, shares},
    process::ProcessReading,
};
use crate::{Result, Validate};
use std::collections::BTreeMap;

#[derive(Debug, Clone)]
pub struct Snapshot {
    pub captured_at: String,
    pub machine: MachineReading,
    pub worker: ProcessReading,
    pub server: ProcessReading,
}
#[derive(Clone)]
pub struct WindowReducer {
    pub window: WindowBody,
    pub opened_at: String,
    memory: bool,
    first: Snapshot,
    previous: MachineReading,
    busy_min: Option<f64>,
    busy_max: Option<f64>,
    headroom_min: Option<i64>,
    pub samples: u64,
}
fn min<T: PartialOrd + Copy>(a: Option<T>, b: Option<T>) -> Option<T> {
    match (a, b) {
        (Some(a), Some(b)) => Some(if a < b { a } else { b }),
        (a, b) => a.or(b),
    }
}
fn max<T: PartialOrd + Copy>(a: Option<T>, b: Option<T>) -> Option<T> {
    match (a, b) {
        (Some(a), Some(b)) => Some(if a > b { a } else { b }),
        (a, b) => a.or(b),
    }
}
impl WindowReducer {
    pub fn new(window: WindowBody, first: Snapshot, memory: bool) -> Result<Self> {
        window.validate()?;
        crate::contracts::host::timestamp(&first.captured_at)?;
        let headroom_min = if memory {
            first.machine.available.value
        } else {
            None
        };
        Ok(Self {
            window,
            opened_at: first.captured_at.clone(),
            memory,
            previous: first.machine.clone(),
            first,
            busy_min: None,
            busy_max: None,
            headroom_min,
            samples: 0,
        })
    }
    pub fn note(&mut self, reading: &Snapshot) {
        if let Some(v) = shares(&self.previous.cpu, &reading.machine.cpu).value {
            self.busy_min = min(self.busy_min, Some(v.busy));
            self.busy_max = max(self.busy_max, Some(v.busy));
        }
        if self.memory {
            self.headroom_min = min(self.headroom_min, reading.machine.available.value);
        }
        self.previous = reading.machine.clone();
        self.samples = self.samples.saturating_add(1);
    }
    pub fn close(self, last: Snapshot) -> Result<WindowResultBody> {
        let shared = shares(&self.first.machine.cpu, &last.machine.cpu);
        let busy = shared.value.map(|v| v.busy);
        let steal = shared.value.and_then(|v| v.steal);
        let mut cells: HostWindowCells = serde_json::from_str("{}").map_err(|e| e.to_string())?;
        cells.cpu_busy_pct = busy;
        cells.cpu_busy_min = min(self.busy_min, busy);
        cells.cpu_busy_max = max(self.busy_max, busy);
        cells.cpu_steal_pct = steal;
        cells.load_1m = last.machine.load.value;
        if self.memory {
            cells.llama_rss_bytes = last.server.rss.value;
            cells.llama_rss_anon_bytes = last.server.anon.value;
            cells.llama_rss_peak_bytes = max(self.first.server.hwm.value, last.server.hwm.value);
            cells.llama_major_faults =
                match (self.first.server.faults.value, last.server.faults.value) {
                    (Some(a), Some(b)) if b >= a => Some(b - a),
                    _ => None,
                };
            cells.python_rss_bytes = last.worker.rss.value;
            cells.python_rss_anon_bytes = last.worker.anon.value;
            cells.os_mem_available_bytes = last.machine.available.value;
            cells.os_mem_total_bytes = last.machine.total.value;
            cells.os_mem_cached_bytes = last.machine.cached.value;
            cells.os_swap_free_bytes = last.machine.swap_free.value;
            cells.os_swap_total_bytes = last.machine.swap_total.value;
            cells.os_mem_available_min_bytes = min(self.headroom_min, last.machine.available.value);
        }
        let mut reasons = BTreeMap::new();
        let mut reason = |source, fallback| {
            reasons.entry(source as u8).or_insert((source, fallback));
        };
        if cells.cpu_busy_pct.is_none() || cells.cpu_steal_pct.is_none() {
            reason(
                CaptureSource::CpuStat,
                shared
                    .reason
                    .unwrap_or(UnavailableReason::IncompleteCoverage),
            );
        }
        if cells.load_1m.is_none() {
            reason(
                CaptureSource::Load,
                last.machine
                    .load
                    .reason
                    .unwrap_or(UnavailableReason::Malformed),
            );
        }
        for (present, source) in cells.availability() {
            if present {
                continue;
            }
            let fallback = if !self.memory
                && matches!(
                    source,
                    CaptureSource::ServerMemory
                        | CaptureSource::WorkerMemory
                        | CaptureSource::MachineMemory
                        | CaptureSource::MajorFaults
                ) {
                UnavailableReason::Disabled
            } else {
                match source {
                    CaptureSource::ServerMemory => last
                        .server
                        .identity
                        .reason
                        .or(last.server.rss.reason)
                        .or(last.server.anon.reason)
                        .or(last.server.hwm.reason),
                    CaptureSource::WorkerMemory => last
                        .worker
                        .identity
                        .reason
                        .or(last.worker.rss.reason)
                        .or(last.worker.anon.reason),
                    CaptureSource::MachineMemory => last
                        .machine
                        .available
                        .reason
                        .or(last.machine.total.reason)
                        .or(last.machine.cached.reason)
                        .or(last.machine.swap_free.reason)
                        .or(last.machine.swap_total.reason),
                    CaptureSource::MajorFaults => last
                        .server
                        .identity
                        .reason
                        .or(last.server.faults.reason)
                        .or(self.first.server.faults.reason),
                    _ => None,
                }
                .unwrap_or(UnavailableReason::SnapshotChanged)
            };
            reason(source, fallback);
        }
        let body = WindowResultBody {
            window: self.window,
            status: WindowStatus::Complete,
            opened_at: Some(self.opened_at),
            closed_at: Some(last.captured_at),
            memory_profiling_enabled: self.memory,
            cells,
            unavailable: reasons
                .into_values()
                .map(|(source, reason)| UnavailableDiagnostic { source, reason })
                .collect(),
        };
        body.validate()?;
        Ok(body)
    }
    pub fn abort(self, reason: UnavailableReason) -> WindowResultBody {
        incomplete(self.window, Some(self.opened_at), self.memory, reason)
    }
}
pub fn incomplete(
    window: WindowBody,
    opened_at: Option<String>,
    memory: bool,
    reason: UnavailableReason,
) -> WindowResultBody {
    let sources = [
        CaptureSource::CpuStat,
        CaptureSource::Load,
        CaptureSource::ServerMemory,
        CaptureSource::WorkerMemory,
        CaptureSource::MachineMemory,
        CaptureSource::MajorFaults,
    ];
    WindowResultBody {
        window,
        status: WindowStatus::Incomplete,
        opened_at,
        closed_at: None,
        memory_profiling_enabled: memory,
        cells: serde_json::from_str("{}").expect("closed nullable cells"),
        unavailable: sources
            .into_iter()
            .map(|source| UnavailableDiagnostic {
                source,
                reason: if !memory
                    && !matches!(source, CaptureSource::CpuStat | CaptureSource::Load)
                {
                    UnavailableReason::Disabled
                } else {
                    reason
                },
            })
            .collect(),
    }
}

pub fn absent_server(memory: bool) -> ProcessReading {
    ProcessReading::unavailable(UnavailableReason::Missing, memory)
}
pub fn missing<T>() -> Reading<T> {
    Reading::absent(UnavailableReason::Missing)
}
