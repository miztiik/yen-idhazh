//! Which closed commands, results and session declarations may an instrument exchange?

use super::host::*;
use super::write_plan::{HostWriteCompletion, HostWritePlan};
use serde::{Deserialize, Serialize};
use std::collections::HashSet;
use uuid::Uuid;

macro_rules! vocabulary {
    ($name:ident {$($variant:ident => $text:literal),* $(,)?}) => {
        #[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
        pub enum $name { $(#[serde(rename = $text)] $variant),* }
    };
}
vocabulary!(CaptureSource {
    Online => "sysfs.online", Topology => "sysfs.topology", Cpuinfo => "proc.cpuinfo",
    Cpufreq => "sysfs.cpufreq", Affinity => "sched.affinity", Cpuset => "cgroup.cpuset",
    Quota => "cgroup.cpu_quota", CpuStat => "proc.stat", Load => "proc.loadavg",
    ServerMemory => "proc.server_status", WorkerMemory => "proc.worker_status",
    MachineMemory => "proc.meminfo", MajorFaults => "proc.major_faults",
    JobMemory => "proc.python_population", ClockLog => "clock.log", BootId => "proc.boot_id",
});
vocabulary!(UnavailableReason {
    Missing => "missing", Malformed => "malformed", PermissionDenied => "permission_denied",
    PidExited => "pid_exited", PidReused => "pid_reused", Disabled => "disabled",
    TimedOut => "timed_out", SnapshotChanged => "snapshot_changed",
    IncompleteCoverage => "incomplete_coverage",
});
vocabulary!(CoverageStatus { Complete => "complete", Partial => "partial", Unavailable => "unavailable" });
vocabulary!(WindowStatus { Complete => "complete", Incomplete => "incomplete" });
vocabulary!(TargetRole { ModelServer => "model_server", PythonWorker => "python_worker", Unselected => "unselected" });
vocabulary!(AbortReason { Cancelled => "cancelled", WorkFailed => "work_failed", InstrumentFailed => "instrument_failed" });
vocabulary!(StopReason { Completed => "completed", Cancelled => "cancelled", Failed => "failed" });
vocabulary!(HostCommandKind { Probe => "host.probe", Target => "host.target", Clock => "host.clock" });
vocabulary!(ProtocolFaultCode {
    Identity => "identity_conflict", Duplicate => "duplicate_conflict", Order => "sequence_order",
    State => "invalid_state", Target => "target_conflict", Bounds => "limit_exhausted",
    Retired => "retired_event", Store => "store_failure",
});
vocabulary!(EventKind {
    MonitorReady => "monitor.ready", HostProbe => "host.probe", HostTarget => "host.target",
    HostClock => "host.clock", HostResult => "host.result", WorkerRegister => "worker.register",
    WorkerRegistered => "worker.registered", WindowBegin => "window.begin",
    WindowBegun => "window.begun", WindowEnd => "window.end", WindowAbort => "window.abort",
    WindowResult => "window.result", MonitorStop => "monitor.stop", MonitorStopped => "monitor.stopped",
    InstrumentSkipped => "instrument.skipped", ProtocolFault => "protocol.fault",
    WritePlan => "host.write.plan", WriteCompleted => "host.write.completed",
    JobSample => "job.sample", ProcessRollcall => "process.rollcall",
});
fn unique<T: Eq + std::hash::Hash>(values: impl IntoIterator<Item = T>) -> Result<()> {
    let mut seen = HashSet::new();
    for value in values {
        require(seen.insert(value), "duplicate identity or source")?;
    }
    Ok(())
}
contract!(ProcessTarget {
    pid: i64,
    start_ticks: i64
});
impl Validate for ProcessTarget {
    fn validate(&self) -> Result<()> {
        positive(self.pid)?;
        nonnegative(self.start_ticks)
    }
}

contract!(HostEventLimits {
    max_manifest_bytes: i64,
    max_command_bytes: i64,
    max_result_bytes: i64,
    max_files: i64,
    max_session_events: i64,
    max_session_bytes: i64,
    max_read_bytes: i64,
    max_reads: i64,
    max_workers: i64,
    max_windows: i64,
    max_concurrent_windows: i64,
    retry_window_ms: i64,
    poll_ms: i64,
    readiness_timeout_ms: i64,
    ack_timeout_ms: i64,
    drain_timeout_ms: i64,
});
impl Validate for HostEventLimits {
    fn validate(&self) -> Result<()> {
        for value in [
            self.max_manifest_bytes,
            self.max_command_bytes,
            self.max_result_bytes,
            self.max_files,
            self.max_session_events,
            self.max_session_bytes,
            self.max_read_bytes,
            self.max_reads,
            self.max_workers,
            self.max_windows,
            self.max_concurrent_windows,
            self.retry_window_ms,
            self.poll_ms,
            self.readiness_timeout_ms,
            self.ack_timeout_ms,
            self.drain_timeout_ms,
        ] {
            positive(value)?;
        }
        require(
            self.max_concurrent_windows <= self.max_windows,
            "concurrency exceeds window cap",
        )?;
        require(
            self.max_command_bytes.max(self.max_result_bytes) <= self.max_session_bytes,
            "event exceeds session bytes",
        )
    }
}
contract!(HostCaptureLimits {
    max_proc_text_bytes: i64,
    max_sysfs_text_bytes: i64,
    max_cpu_id: i64,
    max_cpu_ids: i64,
    max_cgroup_ancestors: i64,
    max_mount_entries: i64,
    max_processes: i64,
    max_log_bytes: i64,
    max_snapshot_retries: i64,
});
impl Validate for HostCaptureLimits {
    fn validate(&self) -> Result<()> {
        for value in [
            self.max_proc_text_bytes,
            self.max_sysfs_text_bytes,
            self.max_cpu_ids,
            self.max_cgroup_ancestors,
            self.max_mount_entries,
            self.max_processes,
            self.max_log_bytes,
        ] {
            positive(value)?;
        }
        nonnegative(self.max_cpu_id)?;
        require(
            (0..=1).contains(&self.max_snapshot_retries),
            "snapshot retries exceed one",
        )
    }
}
contract!(CollectionControls {
    #[serde(default = "default_true")]
    memory_profiling_enabled: bool,
    resource_interval_seconds: f64,
    job_sample_interval_seconds: f64,
    memcpy_enabled: bool,
    memcpy_probe_mib: i64,
    memcpy_passes: i64,
});
impl Validate for CollectionControls {
    fn validate(&self) -> Result<()> {
        finite(self.resource_interval_seconds, 0.0, false)?;
        finite(self.job_sample_interval_seconds, 0.0, true)?;
        positive(self.memcpy_probe_mib)?;
        positive(self.memcpy_passes)
    }
}
contract!(UnavailableDiagnostic {
    source: CaptureSource,
    reason: UnavailableReason
});
impl Validate for UnavailableDiagnostic {
    fn validate(&self) -> Result<()> {
        Ok(())
    }
}
contract!(NamedHostInput {
    name: String,
    source: CaptureSource,
    relative_path: String
});
impl Validate for NamedHostInput {
    fn validate(&self) -> Result<()> {
        token(&self.name)?;
        rel_path(&self.relative_path)
    }
}
contract!(ExpectedWorker { emitter_id: String, target: ProcessTarget, #[serde(default)] server: Option<ProcessTarget> });
impl Validate for ExpectedWorker {
    fn validate(&self) -> Result<()> {
        token(&self.emitter_id)?;
        self.target.validate()?;
        if let Some(v) = &self.server {
            v.validate()?;
        }
        Ok(())
    }
}
contract!(ExpectedWindow {
    window_id: Uuid,
    item_id: String,
    emitter_id: String
});
fn item_id(value: &str) -> Result<()> {
    pattern(
        value,
        r"^[a-z0-9]+(-[a-z0-9]+)*-([0-9]{2,}|[0-9a-hjkmnp-tv-z]{16})$",
        "invalid item_id",
    )
}
impl Validate for ExpectedWindow {
    fn validate(&self) -> Result<()> {
        item_id(&self.item_id)?;
        token(&self.emitter_id)
    }
}
pub use super::host::default_version;
contract!(HostSessionManifest {
    #[serde(default = "default_version")] version: String,
    date: String, run_id: String, attempt: i64, job: ServerJob, shard: i64, git_sha: String,
    session_id: Uuid, operator_emitter_id: String, monitor_emitter_id: String, boot_id: Uuid,
    event_root: String, output_roots: Vec<String>, named_inputs: Vec<NamedHostInput>,
    workers: Vec<ExpectedWorker>, windows: Vec<ExpectedWindow>,
    #[serde(default)] cpu_target: Option<ProcessTarget>,
    cpu_target_role: TargetRole, controls: CollectionControls,
    limits: HostEventLimits, capture_limits: HostCaptureLimits,
});
impl Validate for HostSessionManifest {
    fn validate(&self) -> Result<()> {
        require(self.version == VERSION, "unknown session version")?;
        day(&self.date)?;
        run_id(&self.run_id)?;
        positive(self.attempt)?;
        nonnegative(self.shard)?;
        hex(&self.git_sha, 40)?;
        self.controls.validate()?;
        self.limits.validate()?;
        self.capture_limits.validate()?;
        token(&self.operator_emitter_id)?;
        token(&self.monitor_emitter_id)?;
        rel_path(&self.event_root)?;
        require(
            self.event_root
                == format!(
                    "backend/var/host-events/{}/{}/{}/{}/{}",
                    self.run_id,
                    self.attempt,
                    job_text(self.job),
                    self.shard,
                    self.session_id
                ),
            "event root contradicts session",
        )?;
        require(!self.output_roots.is_empty(), "empty output roots")?;
        for root in &self.output_roots {
            rel_path(root)?;
        }
        require(
            self.workers.len() as i64 <= self.limits.max_workers
                && self.windows.len() as i64 <= self.limits.max_windows,
            "declared workers/windows exceed caps",
        )?;
        for worker in &self.workers {
            worker.validate()?;
        }
        for window in &self.windows {
            window.validate()?;
        }
        for input in &self.named_inputs {
            input.validate()?;
        }
        unique(
            self.workers
                .iter()
                .map(|v| &v.emitter_id)
                .chain([&self.operator_emitter_id, &self.monitor_emitter_id]),
        )?;
        unique(self.windows.iter().map(|v| v.window_id))?;
        require(
            self.windows
                .iter()
                .all(|w| self.workers.iter().any(|v| v.emitter_id == w.emitter_id)),
            "undeclared window worker",
        )?;
        unique(self.named_inputs.iter().map(|v| &v.name))?;
        unique(self.named_inputs.iter().map(|v| &v.relative_path))?;
        unique(&self.output_roots)?;
        require(
            self.cpu_target.is_none() == (self.cpu_target_role == TargetRole::Unselected),
            "target role contradicts target",
        )?;
        let servers = self
            .workers
            .iter()
            .filter_map(|v| v.server.as_ref())
            .collect::<Vec<_>>();
        require(
            servers.iter().all(|v| Some(*v) == servers.first().copied()),
            "workers disagree on server",
        )?;
        require(
            servers.is_empty() || self.cpu_target_role != TargetRole::PythonWorker,
            "server job must select server",
        )?;
        if let Some(target) = &self.cpu_target {
            target.validate()?;
            require(
                self.workers.iter().any(|w| match self.cpu_target_role {
                    TargetRole::ModelServer => w.server.as_ref() == Some(target),
                    _ => &w.target == target,
                }),
                "target is not a declared worker/server",
            )?;
        }
        Ok(())
    }
}
impl HostSessionManifest {
    pub fn pending_event_limit(&self) -> Result<i64> {
        (self.workers.len() as i64)
            .checked_mul(4)
            .and_then(|v| v.checked_add(self.limits.max_concurrent_windows))
            .and_then(|v| v.checked_add(8))
            .ok_or("pending event limit overflow".to_owned())
    }
}
contract!(SourceCoverage { source: CaptureSource, status: CoverageStatus, expected: i64, observed: i64, #[serde(default)] reason: Option<UnavailableReason> });
impl Validate for SourceCoverage {
    fn validate(&self) -> Result<()> {
        nonnegative(self.expected)?;
        nonnegative(self.observed)?;
        require(self.observed <= self.expected, "observed exceeds expected")?;
        match self.status {
            CoverageStatus::Complete => require(
                self.expected > 0 && self.observed == self.expected && self.reason.is_none(),
                "complete source lacks full coverage",
            )?,
            _ => require(
                self.reason.is_some(),
                "partial/unavailable source needs reason",
            )?,
        }
        require(
            self.status != CoverageStatus::Unavailable || self.observed == 0,
            "unavailable source contains observations",
        )
    }
}
pub const CPU_SOURCES: [CaptureSource; 7] = [
    CaptureSource::Online,
    CaptureSource::Topology,
    CaptureSource::Cpuinfo,
    CaptureSource::Cpufreq,
    CaptureSource::Affinity,
    CaptureSource::Cpuset,
    CaptureSource::Quota,
];
contract!(CpuDiagnostics { online_cpu_ids: Vec<i64>, sources: Vec<SourceCoverage>, #[serde(default)] target: Option<ProcessTarget> });
impl Validate for CpuDiagnostics {
    fn validate(&self) -> Result<()> {
        for v in &self.online_cpu_ids {
            nonnegative(*v)?;
        }
        require(
            self.online_cpu_ids.windows(2).all(|v| v[0] < v[1]),
            "online IDs must be ordered unique",
        )?;
        unique(self.sources.iter().map(|v| v.source))?;
        require(
            self.sources.len() == 7 && self.sources.iter().all(|v| CPU_SOURCES.contains(&v.source)),
            "CPU requires seven exact sources",
        )?;
        for v in &self.sources {
            v.validate()?;
            require(
                v.reason != Some(UnavailableReason::Disabled),
                "CPU cannot be disabled by memory switch",
            )?;
        }
        let online = self.source(CaptureSource::Online)?;
        if !self.online_cpu_ids.is_empty() || online.status == CoverageStatus::Complete {
            require(
                online.status == CoverageStatus::Complete
                    && online.observed == self.online_cpu_ids.len() as i64,
                "inventory coverage mismatch",
            )?;
        }
        if let Some(v) = &self.target {
            v.validate()?;
        }
        Ok(())
    }
}
impl CpuDiagnostics {
    pub fn source(&self, name: CaptureSource) -> Result<&SourceCoverage> {
        self.sources
            .iter()
            .find(|v| v.source == name)
            .ok_or("missing source".to_owned())
    }
}
contract!(HostWindowCells {
    #[serde(default)] cpu_busy_pct: Option<f64>, #[serde(default)] cpu_busy_max: Option<f64>,
    #[serde(default)] cpu_busy_min: Option<f64>, #[serde(default)] cpu_steal_pct: Option<f64>,
    #[serde(default)] load_1m: Option<f64>,
    #[serde(default)] llama_rss_bytes: Option<i64>, #[serde(default)] llama_rss_anon_bytes: Option<i64>,
    #[serde(default)] llama_rss_peak_bytes: Option<i64>, #[serde(default)] llama_major_faults: Option<i64>,
    #[serde(default)] python_rss_bytes: Option<i64>, #[serde(default)] python_rss_anon_bytes: Option<i64>,
    #[serde(default)] os_mem_available_bytes: Option<i64>, #[serde(default)] os_mem_total_bytes: Option<i64>,
    #[serde(default)] os_mem_cached_bytes: Option<i64>, #[serde(default)] os_swap_free_bytes: Option<i64>,
    #[serde(default)] os_swap_total_bytes: Option<i64>, #[serde(default)] os_mem_available_min_bytes: Option<i64>,
});
impl Validate for HostWindowCells {
    fn validate(&self) -> Result<()> {
        for v in [
            self.cpu_busy_pct,
            self.cpu_busy_max,
            self.cpu_busy_min,
            self.cpu_steal_pct,
        ]
        .into_iter()
        .flatten()
        {
            finite(v, 0.0, false)?;
            require(v <= 100.0, "CPU percentage exceeds 100")?;
        }
        if let Some(v) = self.load_1m {
            finite(v, 0.0, false)?;
        }
        for v in [
            self.llama_rss_bytes,
            self.llama_rss_anon_bytes,
            self.llama_rss_peak_bytes,
            self.llama_major_faults,
            self.python_rss_bytes,
            self.python_rss_anon_bytes,
            self.os_mem_available_bytes,
            self.os_mem_total_bytes,
            self.os_mem_cached_bytes,
            self.os_swap_free_bytes,
            self.os_swap_total_bytes,
            self.os_mem_available_min_bytes,
        ]
        .into_iter()
        .flatten()
        {
            nonnegative(v)?;
        }
        Ok(())
    }
}
impl HostWindowCells {
    pub fn availability(&self) -> [(bool, CaptureSource); 17] {
        use CaptureSource::*;
        [
            (self.cpu_busy_pct.is_some(), CpuStat),
            (self.cpu_busy_max.is_some(), CpuStat),
            (self.cpu_busy_min.is_some(), CpuStat),
            (self.cpu_steal_pct.is_some(), CpuStat),
            (self.load_1m.is_some(), Load),
            (self.llama_rss_bytes.is_some(), ServerMemory),
            (self.llama_rss_anon_bytes.is_some(), ServerMemory),
            (self.llama_rss_peak_bytes.is_some(), ServerMemory),
            (self.llama_major_faults.is_some(), MajorFaults),
            (self.python_rss_bytes.is_some(), WorkerMemory),
            (self.python_rss_anon_bytes.is_some(), WorkerMemory),
            (self.os_mem_available_bytes.is_some(), MachineMemory),
            (self.os_mem_total_bytes.is_some(), MachineMemory),
            (self.os_mem_cached_bytes.is_some(), MachineMemory),
            (self.os_swap_free_bytes.is_some(), MachineMemory),
            (self.os_swap_total_bytes.is_some(), MachineMemory),
            (self.os_mem_available_min_bytes.is_some(), MachineMemory),
        ]
    }
}
contract!(LegacyJobSample {
    ts: String,
    #[serde(deserialize_with="required_nullable")] llama_vmrss_kb: Option<i64>,
    #[serde(deserialize_with="required_nullable")] llama_vmhwm_kb: Option<i64>,
    python_vmrss_kb: i64, python_procs: i64, python_vmhwm_kb: i64,
    #[serde(deserialize_with="required_nullable")] mem_total_kb: Option<i64>,
    #[serde(deserialize_with="required_nullable")] mem_available_kb: Option<i64>,
    #[serde(deserialize_with="required_nullable")] committed_as_kb: Option<i64>,
    #[serde(deserialize_with="required_nullable")] cgroup_current_bytes: Option<i64>,
});
impl Validate for LegacyJobSample {
    fn validate(&self) -> Result<()> {
        timestamp(&self.ts)?;
        for v in [
            self.llama_vmrss_kb,
            self.llama_vmhwm_kb,
            Some(self.python_vmrss_kb),
            Some(self.python_procs),
            Some(self.python_vmhwm_kb),
            self.mem_total_kb,
            self.mem_available_kb,
            self.committed_as_kb,
            self.cgroup_current_bytes,
        ]
        .into_iter()
        .flatten()
        {
            nonnegative(v)?;
        }
        Ok(())
    }
}
contract!(LegacyProcessRollcall {
    ts:String,pid:i64,comm:String,vmrss_kb:i64,
    #[serde(deserialize_with="required_nullable")] vmhwm_kb:Option<i64>,
    #[serde(deserialize_with="required_nullable")] exe:Option<String>,
    #[serde(deserialize_with="required_nullable")] args:Option<String>,
});
impl Validate for LegacyProcessRollcall {
    fn validate(&self) -> Result<()> {
        timestamp(&self.ts)?;
        positive(self.pid)?;
        nonnegative(self.vmrss_kb)?;
        if let Some(v) = self.vmhwm_kb {
            nonnegative(v)?;
        }
        Ok(())
    }
}
pub const LEGACY_JOB_SAMPLE_FILENAME: &str = "rss-samples.jsonl";
pub const LEGACY_PROCESS_ROLLCALL_FILENAME: &str = "python-procs.jsonl";
contract!(MonitorReadyBody {
    boot_id: Uuid,
    supported_version: String
});
impl Validate for MonitorReadyBody {
    fn validate(&self) -> Result<()> {
        require(
            self.supported_version == VERSION,
            "unsupported monitor version",
        )
    }
}
contract!(HostCommandBody {controls:CollectionControls,input_names:Vec<String>,#[serde(default)] target:Option<ProcessTarget>,#[serde(default)] previous_result_id:Option<Uuid>});
impl Validate for HostCommandBody {
    fn validate(&self) -> Result<()> {
        self.controls.validate()?;
        for v in &self.input_names {
            token(v)?;
        }
        unique(&self.input_names)?;
        if let Some(v) = &self.target {
            v.validate()?;
        }
        Ok(())
    }
}
contract!(WorkerBody {target:ProcessTarget,#[serde(default)] server:Option<ProcessTarget>,#[serde(default="default_true")] memory_profiling_enabled:bool});
impl Validate for WorkerBody {
    fn validate(&self) -> Result<()> {
        self.target.validate()?;
        if let Some(v) = &self.server {
            v.validate()?;
        }
        Ok(())
    }
}
contract!(WindowBody {window_id:Uuid,item_id:String,target:ProcessTarget,#[serde(default)] server:Option<ProcessTarget>});
impl Validate for WindowBody {
    fn validate(&self) -> Result<()> {
        item_id(&self.item_id)?;
        self.target.validate()?;
        if let Some(v) = &self.server {
            v.validate()?;
        }
        Ok(())
    }
}
contract!(WindowBegunBody {
    #[serde(flatten)]
    window: WindowBody,
    captured_at: String
});
impl Validate for WindowBegunBody {
    fn validate(&self) -> Result<()> {
        self.window.validate()?;
        timestamp(&self.captured_at)
    }
}
contract!(WindowAbortBody {
    #[serde(flatten)]
    window: WindowBody,
    reason: AbortReason
});
impl Validate for WindowAbortBody {
    fn validate(&self) -> Result<()> {
        self.window.validate()
    }
}
contract!(WindowResultBody {
    #[serde(flatten)] window:WindowBody,status:WindowStatus,
    #[serde(deserialize_with="required_nullable")] opened_at:Option<String>,
    #[serde(deserialize_with="required_nullable")] closed_at:Option<String>,
    #[serde(default="default_true")] memory_profiling_enabled:bool,
    cells:HostWindowCells,unavailable:Vec<UnavailableDiagnostic>,
});
impl Validate for WindowResultBody {
    fn validate(&self) -> Result<()> {
        self.window.validate()?;
        self.cells.validate()?;
        unique(self.unavailable.iter().map(|v| v.source))?;
        for v in [&self.opened_at, &self.closed_at].into_iter().flatten() {
            timestamp(v)?;
        }
        let endpoints = self.opened_at.is_some() && self.closed_at.is_some();
        require(
            self.status != WindowStatus::Complete || endpoints,
            "complete window lacks endpoints",
        )?;
        if let (Some(a), Some(b)) = (&self.opened_at, &self.closed_at) {
            require(b >= a, "closing precedes opening")?;
        }
        let cells = self.cells.availability();
        require(
            self.unavailable
                .iter()
                .all(|v| cells.iter().any(|(_, s)| s == &v.source)),
            "not a window source",
        )?;
        for (present, source) in cells {
            let reason = self
                .unavailable
                .iter()
                .find(|v| v.source == source)
                .map(|v| v.reason);
            require(endpoints || !present, "endpointless window has cells")?;
            require(present || reason.is_some(), "null cell needs typed reason")?;
            if !self.memory_profiling_enabled
                && matches!(
                    source,
                    CaptureSource::ServerMemory
                        | CaptureSource::WorkerMemory
                        | CaptureSource::MachineMemory
                        | CaptureSource::MajorFaults
                )
            {
                require(
                    !present && reason == Some(UnavailableReason::Disabled),
                    "memory-off cell contradicts disabled",
                )?;
            }
        }
        require(
            !self.memory_profiling_enabled
                || !self
                    .unavailable
                    .iter()
                    .any(|v| v.reason == UnavailableReason::Disabled),
            "enabled instrument claims disabled",
        )
    }
}
contract!(HostResultBody {row:CorrectedHostFingerprintRow,cpu:CpuDiagnostics,completion_event_ids:Vec<Uuid>});
impl Validate for HostResultBody {
    fn validate(&self) -> Result<()> {
        self.row.validate()?;
        self.cpu.validate()?;
        require(
            !self.completion_event_ids.is_empty(),
            "missing completed evidence",
        )?;
        unique(&self.completion_event_ids)?;
        use CaptureSource::*;
        let complete = |source| -> Result<bool> {
            Ok(self.cpu.source(source)?.status == CoverageStatus::Complete)
        };
        if let Some(logical) = self.row.cpu_logical_processors {
            require(
                complete(Online)? && logical == self.cpu.online_cpu_ids.len() as i64,
                "logical count/evidence mismatch",
            )?;
        }
        for (present, source) in [
            (self.row.cpu_logical_processors.is_some(), Online),
            (self.row.cpu_physical_cores.is_some(), Topology),
            (self.row.cpu_observed_mhz.is_some(), Cpuinfo),
            (self.row.cpu_reported_max_mhz.is_some(), Cpufreq),
            (self.row.cpu_allowed_processors.is_some(), Affinity),
        ] {
            require(
                present || !complete(source)?,
                "null reading claims complete source",
            )?;
        }
        for source in [Topology, Cpuinfo, Cpufreq] {
            require(
                self.cpu.source(source)?.expected == self.cpu.online_cpu_ids.len() as i64,
                "coverage inventory mismatch",
            )?;
        }
        for (present, source) in [
            (self.row.cpu_physical_cores.is_some(), Topology),
            (self.row.cpu_reported_max_mhz.is_some(), Cpufreq),
            (self.row.cpu_allowed_processors.is_some(), Affinity),
        ] {
            if present {
                require(
                    complete(source)? && self.cpu.source(source)?.observed > 0,
                    "reading lacks complete coverage",
                )?;
                if matches!(source, Topology | Cpufreq) {
                    require(
                        !self.cpu.online_cpu_ids.is_empty() && complete(Online)?,
                        "reading lacks online inventory",
                    )?;
                }
            }
        }
        require(
            self.row.cpu_allowed_processors.is_none() || complete(Cpuset)?,
            "allowed count lacks cpuset evidence",
        )?;
        if self.row.cpu_observed_mhz.is_some() {
            let source = self.cpu.source(Cpuinfo)?;
            require(
                source.observed > 0 && source.status != CoverageStatus::Unavailable,
                "frequency lacks observations",
            )?;
        }
        require(
            self.row.cpu_target_measured_at.is_none() == self.cpu.target.is_none(),
            "target PID/time mismatch",
        )?;
        let quota = matches!(
            self.row.cpu_quota_state,
            Some(QuotaState::Finite | QuotaState::Unlimited)
        );
        require(
            quota == complete(Quota)?,
            "quota state/ancestor evidence mismatch",
        )
    }
}
contract!(StopBody { reason: StopReason });
impl Validate for StopBody {
    fn validate(&self) -> Result<()> {
        Ok(())
    }
}
contract!(StoppedBody {drained:bool,aborted_window_ids:Vec<Uuid>});
impl Validate for StoppedBody {
    fn validate(&self) -> Result<()> {
        require(self.drained, "stopped must be drained")?;
        unique(&self.aborted_window_ids)
    }
}
contract!(InstrumentSkippedBody {command_kind:HostCommandKind,unavailable:Vec<UnavailableDiagnostic>,#[serde(default)] completion_event_ids:Vec<Uuid>});
impl Validate for InstrumentSkippedBody {
    fn validate(&self) -> Result<()> {
        require(!self.unavailable.is_empty(), "skipped needs reason")
    }
}
contract!(ProtocolFaultBody {code:ProtocolFaultCode,#[serde(deserialize_with="required_nullable")] related_event_id:Option<Uuid>});
impl Validate for ProtocolFaultBody {
    fn validate(&self) -> Result<()> {
        Ok(())
    }
}
contract!(JobSampleBody {
    record: LegacyJobSample
});
impl Validate for JobSampleBody {
    fn validate(&self) -> Result<()> {
        self.record.validate()
    }
}
contract!(ProcessRollcallBody {records:Vec<LegacyProcessRollcall>});
impl Validate for ProcessRollcallBody {
    fn validate(&self) -> Result<()> {
        for v in &self.records {
            v.validate()?;
        }
        unique(self.records.iter().map(|v| v.pid))?;
        require(
            self.records
                .iter()
                .all(|v| self.records.first().is_none_or(|first| v.ts == first.ts)),
            "rollcall mixes captures",
        )
    }
}
contract!(WritePlanBody {
    plan: HostWritePlan
});
impl Validate for WritePlanBody {
    fn validate(&self) -> Result<()> {
        self.plan.validate()
    }
}
contract!(WriteCompletedBody {
    completion: HostWriteCompletion
});
impl Validate for WriteCompletedBody {
    fn validate(&self) -> Result<()> {
        self.completion.validate()
    }
}

#[derive(Debug, Clone, PartialEq, Serialize)]
#[serde(untagged)]
pub enum EventBody {
    Ready(MonitorReadyBody),
    HostCommand(HostCommandBody),
    HostResult(Box<HostResultBody>),
    Worker(WorkerBody),
    Window(WindowBody),
    Begun(WindowBegunBody),
    Abort(WindowAbortBody),
    WindowResult(Box<WindowResultBody>),
    Stop(StopBody),
    Stopped(StoppedBody),
    Skipped(InstrumentSkippedBody),
    Fault(ProtocolFaultBody),
    Plan(WritePlanBody),
    Completed(WriteCompletedBody),
    Sample(JobSampleBody),
    Rollcall(ProcessRollcallBody),
}
impl EventBody {
    fn decode(kind: EventKind, value: serde_json::Value) -> Result<Self> {
        fn parse<T: serde::de::DeserializeOwned>(value: serde_json::Value) -> Result<T> {
            serde_json::from_value(value).map_err(|e| e.to_string())
        }
        use EventKind::*;
        Ok(match kind {
            MonitorReady => Self::Ready(parse(value)?),
            HostProbe | HostTarget | HostClock => Self::HostCommand(parse(value)?),
            HostResult => Self::HostResult(parse(value)?),
            WorkerRegister | WorkerRegistered => Self::Worker(parse(value)?),
            WindowBegin | WindowEnd => Self::Window(parse(value)?),
            WindowBegun => Self::Begun(parse(value)?),
            WindowAbort => Self::Abort(parse(value)?),
            WindowResult => Self::WindowResult(parse(value)?),
            MonitorStop => Self::Stop(parse(value)?),
            MonitorStopped => Self::Stopped(parse(value)?),
            InstrumentSkipped => Self::Skipped(parse(value)?),
            ProtocolFault => Self::Fault(parse(value)?),
            WritePlan => Self::Plan(parse(value)?),
            WriteCompleted => Self::Completed(parse(value)?),
            JobSample => Self::Sample(parse(value)?),
            ProcessRollcall => Self::Rollcall(parse(value)?),
        })
    }
}
impl Validate for EventBody {
    fn validate(&self) -> Result<()> {
        match self {
            Self::Ready(v) => v.validate(),
            Self::HostCommand(v) => v.validate(),
            Self::HostResult(v) => v.validate(),
            Self::Worker(v) => v.validate(),
            Self::Window(v) => v.validate(),
            Self::Begun(v) => v.validate(),
            Self::Abort(v) => v.validate(),
            Self::WindowResult(v) => v.validate(),
            Self::Stop(v) => v.validate(),
            Self::Stopped(v) => v.validate(),
            Self::Skipped(v) => v.validate(),
            Self::Fault(v) => v.validate(),
            Self::Plan(v) => v.validate(),
            Self::Completed(v) => v.validate(),
            Self::Sample(v) => v.validate(),
            Self::Rollcall(v) => v.validate(),
        }
    }
}
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct HostEvent {
    pub version: String,
    pub kind: EventKind,
    pub event_id: Uuid,
    pub reply_to: Option<Uuid>,
    pub date: String,
    pub run_id: String,
    pub attempt: i64,
    pub job: ServerJob,
    pub shard: i64,
    pub session_id: Uuid,
    pub emitter_id: String,
    pub sequence: i64,
    pub emitted_at: String,
    pub body: EventBody,
}
impl<'de> Deserialize<'de> for HostEvent {
    fn deserialize<D: serde::Deserializer<'de>>(
        deserializer: D,
    ) -> std::result::Result<Self, D::Error> {
        #[derive(Deserialize)]
        #[serde(deny_unknown_fields)]
        struct Wire {
            #[serde(default = "default_version")]
            version: String,
            kind: EventKind,
            event_id: Uuid,
            #[serde(deserialize_with = "required_nullable")]
            reply_to: Option<Uuid>,
            date: String,
            run_id: String,
            attempt: i64,
            job: ServerJob,
            shard: i64,
            session_id: Uuid,
            emitter_id: String,
            sequence: i64,
            emitted_at: String,
            body: serde_json::Value,
        }
        let w = Wire::deserialize(deserializer)?;
        let body = EventBody::decode(w.kind, w.body).map_err(serde::de::Error::custom)?;
        let result = Self {
            version: w.version,
            kind: w.kind,
            event_id: w.event_id,
            reply_to: w.reply_to,
            date: w.date,
            run_id: w.run_id,
            attempt: w.attempt,
            job: w.job,
            shard: w.shard,
            session_id: w.session_id,
            emitter_id: w.emitter_id,
            sequence: w.sequence,
            emitted_at: w.emitted_at,
            body,
        };
        result.validate().map_err(serde::de::Error::custom)?;
        Ok(result)
    }
}
impl Validate for HostEvent {
    fn validate(&self) -> Result<()> {
        require(self.version == VERSION, "unknown event version")?;
        day(&self.date)?;
        run_id(&self.run_id)?;
        positive(self.attempt)?;
        nonnegative(self.shard)?;
        positive(self.sequence)?;
        token(&self.emitter_id)?;
        timestamp(&self.emitted_at)?;
        self.body.validate()?;
        // Re-selecting the closed body also checks directly constructed events.
        EventBody::decode(
            self.kind,
            serde_json::to_value(&self.body).map_err(|e| e.to_string())?,
        )?;
        use EventKind::*;
        let no_reply = matches!(
            self.kind,
            HostProbe
                | HostTarget
                | HostClock
                | WorkerRegister
                | WindowBegin
                | WindowEnd
                | WindowAbort
                | MonitorStop
                | MonitorReady
                | JobSample
                | ProcessRollcall
        );
        if no_reply {
            require(self.reply_to.is_none(), "command/observation cannot reply")?;
        } else if self.kind != ProtocolFault {
            require(self.reply_to.is_some(), "result requires triggering event")?;
        }
        if let EventBody::HostResult(body) = &self.body {
            require(
                body.row.date == self.date
                    && body.row.run_id == self.run_id
                    && body.row.job == self.job
                    && body.row.shard == self.shard,
                "host result/event identity mismatch",
            )?;
        }
        Ok(())
    }
}
