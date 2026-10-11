//! Which bounded before/after capture preserves source evidence and detects a moving CPU snapshot?

use crate::contracts::events::{HostCaptureLimits, ProcessTarget, UnavailableReason};
use crate::contracts::host::{Result, require};
use crate::probe_inputs::{
    allowance::{self, TargetCapture},
    files::{Reading, SourceRoot},
    frequency::FrequencyPolicy,
    hierarchy,
    topology::{self, CpuTopology},
};
use serde::{Deserialize, Serialize};
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuCapture {
    pub online_before: Reading<String>,
    pub online_after: Reading<String>,
    pub inventory: Reading<String>,
    pub cpuinfo: Reading<String>,
    pub topology: Vec<CpuTopology>,
    pub policies: Reading<Vec<FrequencyPolicy>>,
    pub target_before: Option<TargetCapture>,
    pub target_after: Option<TargetCapture>,
    pub cache_bytes: Reading<i64>,
    pub uptime: Reading<String>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ProbeReplay {
    pub attempts: Vec<CpuCapture>,
    pub placement_json: Reading<String>,
    pub runner_name: Option<String>,
    pub captured_at: String,
    pub written_at_ms: i64,
}
impl ProbeReplay {
    pub fn selected(&self, limits: &HostCaptureLimits) -> Result<&CpuCapture> {
        require(
            !self.attempts.is_empty()
                && self.attempts.len() as i64 <= limits.max_snapshot_retries + 1,
            "capture retry count exceeds bound",
        )?;
        for attempt in &self.attempts {
            validate_capture(attempt, limits)?;
        }
        Ok(self
            .attempts
            .iter()
            .find(|v| stable(v))
            .unwrap_or_else(|| self.attempts.last().expect("nonempty")))
    }
}

pub struct LiveRoots<'a> {
    pub proc: &'a Path,
    pub cpu: &'a Path,
    pub namespace: &'a Path,
}
pub fn capture(
    roots: &LiveRoots<'_>,
    target: Option<&ProcessTarget>,
    limits: &HostCaptureLimits,
    recorded_affinity: Option<&Reading<Vec<i64>>>,
) -> Result<CpuCapture> {
    limits.validate()?;
    let proc = SourceRoot::new(roots.proc, limits.max_proc_text_bytes as usize)?;
    let cpu = SourceRoot::new(roots.cpu, limits.max_sysfs_text_bytes as usize)?;
    let namespace = SourceRoot::new(roots.namespace, limits.max_sysfs_text_bytes as usize)?;
    let online_before = cpu.text("online");
    let inventory = cpu.text("present");
    let target_capture = || {
        target.map(|target| {
            let source_context = if roots.proc == Path::new("/proc") {
                hierarchy::context(roots, target)
            } else {
                hierarchy::missing_context()
            };
            let cgroup = proc.text(&format!("{}/cgroup", target.pid));
            let mountinfo = proc.text(&format!("{}/mountinfo", target.pid));
            let constraints = match cgroup.get().and_then(|cg| {
                mountinfo
                    .get()
                    .and_then(|mi| allowance::scopes(cg, mi, limits))
            }) {
                Ok(scopes) => Reading::found(if roots.proc == Path::new("/proc") {
                    hierarchy::constraints(roots.namespace, &scopes, namespace.maximum)
                } else {
                    allowance::capture_constraints(&namespace, &scopes)
                }),
                Err(reason) => Reading::absent(reason),
            };
            let stat = proc.text(&format!("{}/stat", target.pid));
            let start_ticks = match stat.get().and_then(|s| allowance::start_ticks(s)) {
                Ok(v) => Reading::found(v),
                Err(UnavailableReason::Missing) => Reading::absent(UnavailableReason::PidExited),
                Err(r) => Reading::absent(r),
            };
            let source_context_after = if roots.proc == Path::new("/proc") {
                hierarchy::context(roots, target)
            } else {
                hierarchy::missing_context()
            };
            TargetCapture {
                start_ticks,
                cgroup,
                mountinfo,
                affinity: recorded_affinity
                    .cloned()
                    .unwrap_or_else(|| allowance::affinity(target, limits)),
                constraints,
                source_context: if source_context == source_context_after {
                    source_context
                } else {
                    Reading::absent(UnavailableReason::SnapshotChanged)
                },
            }
        })
    };
    let target_before = target_capture();
    let ids = topology::online(&online_before, &inventory, limits).unwrap_or_default();
    let entries = ids
        .iter()
        .map(|id| {
            let read = |name| cpu.text(&format!("cpu{id}/topology/{name}"));
            CpuTopology {
                id: *id,
                package: read("physical_package_id"),
                core: read("core_id"),
                thread_siblings: read("thread_siblings_list"),
                package_siblings: read("core_siblings_list"),
            }
        })
        .collect();
    let policies = match cpu.entries("cpufreq", limits.max_cpu_ids as usize) {
        Ok(names) => {
            let mut entries = Vec::new();
            for name in names {
                if !name
                    .strip_prefix("policy")
                    .is_some_and(|v| !v.is_empty() && v.bytes().all(|b| b.is_ascii_digit()))
                {
                    continue;
                }
                entries.push(FrequencyPolicy {
                    cpus: cpu.text(&format!("cpufreq/{name}/related_cpus")),
                    maximum_khz: cpu.text(&format!("cpufreq/{name}/cpuinfo_max_freq")),
                    name,
                });
            }
            Reading::found(entries)
        }
        Err(r) => Reading::absent(r),
    };
    let cpuinfo = proc.text("cpuinfo");
    let cache_bytes = cache(&cpu, limits.max_cpu_ids as usize);
    let uptime = proc.text("uptime");
    let target_after = target_capture();
    let online_after = cpu.text("online");
    Ok(CpuCapture {
        online_before,
        online_after,
        inventory,
        cpuinfo,
        topology: entries,
        policies,
        target_before,
        target_after,
        cache_bytes,
        uptime,
    })
}

pub fn cache(cpu: &SourceRoot, entry_cap: usize) -> Reading<i64> {
    let entries = match cpu.entries("cpu0/cache", entry_cap) {
        Ok(v) => v,
        Err(r) => return Reading::absent(r),
    };
    for name in entries {
        let level = cpu.text(&format!("cpu0/cache/{name}/level"));
        if level.value.as_deref().map(str::trim) != Some("3") {
            continue;
        }
        let size = cpu.text(&format!("cpu0/cache/{name}/size"));
        let Ok(raw) = size.get() else {
            return Reading::absent(size.reason.unwrap_or(UnavailableReason::Missing));
        };
        let raw = raw.trim();
        let (number, multiple) = if let Some(v) = raw.strip_suffix('K') {
            (v, 1024)
        } else if let Some(v) = raw.strip_suffix('M') {
            (v, 1024 * 1024)
        } else {
            (raw, 1)
        };
        let value = number
            .parse::<i64>()
            .ok()
            .and_then(|v| v.checked_mul(multiple))
            .filter(|v| *v > 0);
        return value
            .map(Reading::found)
            .unwrap_or_else(|| Reading::absent(UnavailableReason::Malformed));
    }
    Reading::absent(UnavailableReason::Missing)
}
pub fn stable(capture: &CpuCapture) -> bool {
    capture.online_before == capture.online_after
        && match (&capture.target_before, &capture.target_after) {
            (Some(a), Some(b)) => {
                a.source_context.reason != Some(UnavailableReason::SnapshotChanged)
                    && b.source_context.reason != Some(UnavailableReason::SnapshotChanged)
                    && a.start_ticks == b.start_ticks
                    && a.cgroup == b.cgroup
                    && a.mountinfo == b.mountinfo
                    && a.affinity == b.affinity
                    && allowance::constraints_stable(a, b, true)
                    && allowance::constraints_stable(a, b, false)
            }
            (None, None) => true,
            _ => false,
        }
}
pub fn live(
    roots: &LiveRoots<'_>,
    target: Option<&ProcessTarget>,
    limits: &HostCaptureLimits,
) -> Result<CpuCapture> {
    let mut result = capture(roots, target, limits, None)?;
    for _ in 0..limits.max_snapshot_retries {
        if stable(&result) {
            break;
        }
        result = capture(roots, target, limits, None)?;
    }
    Ok(result)
}

pub fn validate_capture(c: &CpuCapture, limits: &HostCaptureLimits) -> Result<()> {
    fn text(reading: &Reading<String>, cap: i64) -> Result<()> {
        reading.validate()?;
        require(
            reading.value.as_ref().is_none_or(|v| v.len() as i64 <= cap),
            "capture text exceeds bound",
        )
    }
    require(
        c.topology.len() as i64 <= limits.max_cpu_ids,
        "capture topology exceeds bound",
    )?;
    for text in [&c.online_before, &c.online_after, &c.inventory] {
        text.validate()?;
        require(
            text.value
                .as_ref()
                .is_none_or(|v| v.len() as i64 <= limits.max_sysfs_text_bytes),
            "capture text exceeds bound",
        )?;
    }
    text(&c.cpuinfo, limits.max_proc_text_bytes)?;
    text(&c.uptime, limits.max_proc_text_bytes)?;
    c.cache_bytes.validate()?;
    require(
        c.cache_bytes.value.is_none_or(|v| v > 0),
        "invalid captured cache bytes",
    )?;
    for entry in &c.topology {
        require(
            entry.id >= 0 && entry.id <= limits.max_cpu_id,
            "captured topology ID exceeds bound",
        )?;
        for source in [
            &entry.package,
            &entry.core,
            &entry.thread_siblings,
            &entry.package_siblings,
        ] {
            text(source, limits.max_sysfs_text_bytes)?;
        }
    }
    c.policies.validate()?;
    if let Some(policies) = &c.policies.value {
        require(
            policies.len() as i64 <= limits.max_cpu_ids,
            "captured policies exceed bound",
        )?;
        for policy in policies {
            require(policy.name.len() <= 128, "policy name exceeds bound")?;
            text(&policy.cpus, limits.max_sysfs_text_bytes)?;
            text(&policy.maximum_khz, limits.max_sysfs_text_bytes)?;
        }
    }
    for target in [&c.target_before, &c.target_after].into_iter().flatten() {
        target.start_ticks.validate()?;
        require(
            target.start_ticks.value.is_none_or(|v| v >= 0),
            "negative captured start ticks",
        )?;
        text(&target.cgroup, limits.max_proc_text_bytes)?;
        text(&target.mountinfo, limits.max_proc_text_bytes)?;
        target.affinity.validate()?;
        require(
            target
                .affinity
                .value
                .as_ref()
                .is_none_or(|v| v.len() as i64 <= limits.max_cpu_ids),
            "captured affinity exceeds bound",
        )?;
        target.constraints.validate()?;
        target.source_context.validate()?;
        if let Some(rows) = &target.constraints.value {
            require(
                rows.len() as i64 <= limits.max_cgroup_ancestors.saturating_mul(3),
                "captured ancestry exceeds bound",
            )?;
            for row in rows {
                require(
                    row.directory.len() as i64 <= limits.max_proc_text_bytes,
                    "captured cgroup path exceeds bound",
                )?;
                require(
                    row.root || row.root_evidence.is_none(),
                    "root proof on nonroot scope",
                )?;
                if let Some(evidence) = &row.root_evidence {
                    evidence.directory.validate()?;
                    require(
                        evidence.selected_mount.root.len() as i64 <= limits.max_proc_text_bytes
                            && evidence.selected_mount.mountpoint.len() as i64
                                <= limits.max_proc_text_bytes,
                        "root proof path exceeds bound",
                    )?;
                }
                for source in [
                    &row.controllers,
                    &row.cpuset,
                    &row.quota,
                    &row.period,
                    &row.subtree_control,
                ] {
                    text(source, limits.max_sysfs_text_bytes)?;
                }
            }
        }
    }
    Ok(())
}

use crate::contracts::host::Validate;
