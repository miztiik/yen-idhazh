//! Which selected task's visible affinity, cpuset ancestry and CPU quota constrain its execution?

use crate::contracts::events::{HostCaptureLimits, ProcessTarget, UnavailableReason};
use crate::contracts::host::QuotaState;
use crate::probe_inputs::{
    files::{Reading, SourceRoot},
    hierarchy::{self, CgroupSourceContext, MountIdentity, RootEvidence},
    topology::{Observation, cpu_list},
};
use serde::{Deserialize, Serialize};
use std::collections::BTreeSet;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Controller {
    V2,
    Cpu,
    Cpuset,
}
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Scope {
    pub controller: Controller,
    pub directory: String,
    pub root: bool,
    pub mount: MountIdentity,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Constraint {
    pub controller: Controller,
    pub directory: String,
    pub root: bool,
    pub controllers: Reading<String>,
    pub cpuset: Reading<String>,
    pub quota: Reading<String>,
    pub period: Reading<String>,
    #[serde(default = "hierarchy::missing_text")]
    pub subtree_control: Reading<String>,
    #[serde(default)]
    pub root_evidence: Option<RootEvidence>,
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TargetCapture {
    pub start_ticks: Reading<i64>,
    pub cgroup: Reading<String>,
    pub mountinfo: Reading<String>,
    pub affinity: Reading<Vec<i64>>,
    pub constraints: Reading<Vec<Constraint>>,
    #[serde(default = "hierarchy::missing_context")]
    pub source_context: Reading<CgroupSourceContext>,
}

fn decoded_path(raw: &str) -> Observation<String> {
    let mut result = String::new();
    let mut chars = raw.chars();
    while let Some(c) = chars.next() {
        if c != '\\' {
            result.push(c);
            continue;
        }
        let code: String = chars.by_ref().take(3).collect();
        result.push(match code.as_str() {
            "040" => ' ',
            "011" => '\t',
            "012" => '\n',
            "134" => '\\',
            _ => return Err(UnavailableReason::Malformed),
        });
    }
    if !result.starts_with('/')
        || result.split('/').any(|s| matches!(s, "." | ".."))
        || result.contains('\\')
        || result.contains('\0')
    {
        return Err(UnavailableReason::Malformed);
    }
    Ok(result)
}

pub fn scopes(
    cgroup: &str,
    mountinfo: &str,
    limits: &HostCaptureLimits,
) -> Observation<Vec<Scope>> {
    let mut memberships = Vec::new();
    let mut membership_keys = BTreeSet::new();
    for line in cgroup.lines() {
        let cells: Vec<_> = line.splitn(3, ':').collect();
        if cells.len() != 3 || cells[0].parse::<u64>().is_err() {
            return Err(UnavailableReason::Malformed);
        }
        let path = decoded_path(cells[2])?;
        for controller in cells[1].split(',') {
            let kind = match controller {
                "" if cells[0] == "0" => Some(Controller::V2),
                "cpu" => Some(Controller::Cpu),
                "cpuset" => Some(Controller::Cpuset),
                _ => None,
            };
            if let Some(kind) = kind {
                if !membership_keys.insert(controller.to_owned()) {
                    return Err(UnavailableReason::Malformed);
                }
                memberships.push((kind, path.clone()));
            }
        }
    }
    if cgroup.trim().is_empty() {
        return Err(UnavailableReason::Malformed);
    }
    let lines: Vec<_> = mountinfo.lines().collect();
    if lines.len() as i64 > limits.max_mount_entries {
        return Err(UnavailableReason::IncompleteCoverage);
    }
    let mut mounts = Vec::new();
    let mut all_mounts = Vec::new();
    for line in lines {
        let Some((left, right)) = line.split_once(" - ") else {
            return Err(UnavailableReason::Malformed);
        };
        let before: Vec<_> = left.split_whitespace().collect();
        let after: Vec<_> = right.split_whitespace().collect();
        if before.len() < 6 || after.len() < 3 {
            return Err(UnavailableReason::Malformed);
        }
        let id = before[0]
            .parse()
            .map_err(|_| UnavailableReason::Malformed)?;
        let (major, minor) = before[2]
            .split_once(':')
            .ok_or(UnavailableReason::Malformed)?;
        let identity = MountIdentity {
            id,
            major: major.parse().map_err(|_| UnavailableReason::Malformed)?,
            minor: minor.parse().map_err(|_| UnavailableReason::Malformed)?,
            root: decoded_path(before[3])?,
            mountpoint: decoded_path(before[4])?,
        };
        all_mounts.push(identity.clone());
        let kinds = match after[0] {
            "cgroup2" => vec![Controller::V2],
            "cgroup" => after[2]
                .split(',')
                .filter_map(|name| match name {
                    "cpu" => Some(Controller::Cpu),
                    "cpuset" => Some(Controller::Cpuset),
                    _ => None,
                })
                .collect(),
            _ => continue,
        };
        for kind in kinds {
            mounts.push((kind, identity.clone()));
        }
    }
    let mut result = Vec::new();
    for (kind, membership) in &memberships {
        let applicable: Vec<_> = mounts.iter().filter(|m| m.0 == *kind).collect();
        // A mount rooted below '/' hides ancestors, even if its own leaf is readable.
        if applicable.len() != 1 || applicable[0].1.root != "/" {
            return Err(UnavailableReason::IncompleteCoverage);
        }
        let selected = &applicable[0].1;
        let mountpoint = selected.mountpoint.trim_end_matches('/');
        let segments: Vec<_> = membership.split('/').filter(|s| !s.is_empty()).collect();
        if segments.len() as i64 + 1 > limits.max_cgroup_ancestors {
            return Err(UnavailableReason::IncompleteCoverage);
        }
        for count in (0..=segments.len()).rev() {
            let directory = if count == 0 {
                selected.mountpoint.clone()
            } else {
                format!("{mountpoint}/{}", segments[..count].join("/"))
            };
            let within = |path: &str, root: &str| {
                path == root
                    || root == "/"
                    || path.strip_prefix(root).is_some_and(|v| v.starts_with('/'))
            };
            if all_mounts.iter().any(|m| {
                m.id != selected.id
                    && within(&m.mountpoint, &selected.mountpoint)
                    && within(&directory, &m.mountpoint)
            }) {
                return Err(UnavailableReason::IncompleteCoverage);
            }
            result.push(Scope {
                controller: *kind,
                directory,
                root: count == 0,
                mount: selected.clone(),
            });
        }
    }
    if mounts
        .iter()
        .any(|m| !memberships.iter().any(|v| v.0 == m.0))
    {
        return Err(UnavailableReason::IncompleteCoverage);
    }
    Ok(result)
}

pub fn capture_constraints(root: &SourceRoot, scopes: &[Scope]) -> Vec<Constraint> {
    scopes
        .iter()
        .map(|scope| {
            let read = |name| {
                root.text(&format!(
                    "{}/{name}",
                    scope.directory.trim_start_matches('/')
                ))
            };
            Constraint {
                controller: scope.controller,
                directory: scope.directory.clone(),
                root: scope.root,
                controllers: read("cgroup.controllers"),
                cpuset: read(if scope.controller == Controller::V2 {
                    "cpuset.cpus.effective"
                } else {
                    "cpuset.cpus"
                }),
                quota: read(if scope.controller == Controller::V2 {
                    "cpu.max"
                } else {
                    "cpu.cfs_quota_us"
                }),
                period: read("cpu.cfs_period_us"),
                subtree_control: read("cgroup.subtree_control"),
                root_evidence: None,
            }
        })
        .collect()
}

pub fn start_ticks(text: &str) -> Observation<i64> {
    let (_, rest) = text.rsplit_once(") ").ok_or(UnavailableReason::Malformed)?;
    let ticks = rest
        .split_whitespace()
        .nth(19)
        .ok_or(UnavailableReason::Malformed)?;
    ticks
        .parse::<i64>()
        .ok()
        .filter(|v| *v >= 0)
        .ok_or(UnavailableReason::Malformed)
}

pub fn identity(capture: &TargetCapture, target: &ProcessTarget) -> Observation<()> {
    if *capture.start_ticks.get()? != target.start_ticks {
        return Err(UnavailableReason::PidReused);
    }
    Ok(())
}
pub fn affinity(target: &ProcessTarget, limits: &HostCaptureLimits) -> Reading<Vec<i64>> {
    #[cfg(target_os = "linux")]
    {
        let result = || -> Observation<Vec<i64>> {
            let pid = i32::try_from(target.pid).map_err(|_| UnavailableReason::Malformed)?;
            let bits = usize::try_from(limits.max_cpu_id)
                .map_err(|_| UnavailableReason::Malformed)?
                .checked_add(1)
                .ok_or(UnavailableReason::Malformed)?;
            let words = bits.div_ceil(usize::BITS as usize);
            let mut mask = vec![0usize; words];
            // Linux accepts a dynamically sized CPU bitset; libc supplies the kernel interface.
            let status = unsafe {
                libc::sched_getaffinity(
                    pid,
                    mask.len() * size_of::<usize>(),
                    mask.as_mut_ptr().cast(),
                )
            };
            if status != 0 {
                return Err(match std::io::Error::last_os_error().raw_os_error() {
                    Some(libc::ESRCH) => UnavailableReason::PidExited,
                    Some(libc::EPERM | libc::EACCES) => UnavailableReason::PermissionDenied,
                    _ => UnavailableReason::IncompleteCoverage,
                });
            }
            let mut ids = Vec::new();
            for id in 0..bits {
                if mask[id / usize::BITS as usize] & (1usize << (id % usize::BITS as usize)) != 0 {
                    ids.push(id as i64);
                }
            }
            if ids.is_empty() || ids.len() as i64 > limits.max_cpu_ids {
                return Err(UnavailableReason::Malformed);
            }
            Ok(ids)
        };
        match result() {
            Ok(v) => Reading::found(v),
            Err(r) => Reading::absent(r),
        }
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = (target, limits);
        Reading::absent(UnavailableReason::Missing)
    }
}

fn verified_constraints<'a>(
    capture: &'a TargetCapture,
    limits: &HostCaptureLimits,
) -> Observation<&'a Vec<Constraint>> {
    capture
        .source_context
        .validate()
        .map_err(|_| UnavailableReason::Malformed)?;
    capture.source_context.get()?.aligned()?;
    let expected = scopes(capture.cgroup.get()?, capture.mountinfo.get()?, limits)?;
    let rows = capture.constraints.get()?;
    if expected.is_empty()
        || expected.len() != rows.len()
        || expected.iter().zip(rows).any(|(a, b)| {
            a.controller != b.controller || a.directory != b.directory || a.root != b.root
        })
    {
        return Err(UnavailableReason::IncompleteCoverage);
    }
    for (scope, row) in expected.iter().zip(rows) {
        if scope.root {
            hierarchy::verify_root(
                scope,
                row.root_evidence
                    .as_ref()
                    .ok_or(UnavailableReason::IncompleteCoverage)?,
            )?;
        } else if row.root_evidence.is_some() {
            return Err(UnavailableReason::IncompleteCoverage);
        }
    }
    Ok(rows)
}
fn v2_available(rows: &[Constraint], name: &str) -> Observation<bool> {
    let root = rows
        .iter()
        .find(|r| r.controller == Controller::V2 && r.root)
        .ok_or(UnavailableReason::IncompleteCoverage)?;
    let enabled = root
        .controllers
        .get()?
        .split_whitespace()
        .any(|v| v == name);
    if !enabled
        && rows
            .iter()
            .filter(|r| r.controller == Controller::V2)
            .any(|r| {
                if name == "cpu" {
                    r.quota.value.is_some()
                } else {
                    r.cpuset.value.is_some()
                }
            })
    {
        return Err(UnavailableReason::Malformed);
    }
    if !enabled {
        for row in rows
            .iter()
            .filter(|r| r.controller == Controller::V2 && !r.root)
        {
            let reading = if name == "cpu" {
                &row.quota
            } else {
                &row.cpuset
            };
            if reading.reason != Some(UnavailableReason::Missing) {
                return Err(reading.reason.unwrap_or(UnavailableReason::Malformed));
            }
        }
    }
    Ok(enabled)
}
fn v2_applicable(rows: &[Constraint], index: usize, name: &str) -> Observation<bool> {
    let row = &rows[index];
    if !v2_available(rows, name)? {
        return Ok(false);
    }
    if row.root {
        return Ok(true);
    }
    let parent = rows
        .get(index + 1)
        .filter(|p| p.controller == Controller::V2)
        .ok_or(UnavailableReason::IncompleteCoverage)?;
    let enabled = parent
        .subtree_control
        .get()?
        .split_whitespace()
        .any(|v| v == name);
    let present = if name == "cpu" {
        row.quota.value.is_some()
    } else {
        row.cpuset.value.is_some()
    };
    let available_here = row.controllers.get()?.split_whitespace().any(|v| v == name);
    if enabled != available_here {
        return Err(UnavailableReason::IncompleteCoverage);
    }
    if !enabled && present {
        return Err(UnavailableReason::Malformed);
    }
    if !enabled {
        let reading = if name == "cpu" {
            &row.quota
        } else {
            &row.cpuset
        };
        if reading.reason != Some(UnavailableReason::Missing) {
            return Err(reading.reason.unwrap_or(UnavailableReason::Malformed));
        }
    }
    Ok(enabled)
}
fn cpuset_indices(rows: &[Constraint]) -> Observation<Vec<usize>> {
    let mut result = Vec::new();
    let mut v2_found = false;
    for (index, row) in rows.iter().enumerate() {
        if row.controller == Controller::Cpuset
            || (row.controller == Controller::V2
                && !v2_found
                && v2_applicable(rows, index, "cpuset")?)
        {
            result.push(index);
            v2_found |= row.controller == Controller::V2;
        }
    }
    Ok(result)
}
pub fn constraints_stable(before: &TargetCapture, after: &TargetCapture, quota: bool) -> bool {
    if before.source_context != after.source_context {
        return false;
    }
    match (&before.constraints.value, &after.constraints.value) {
        (Some(a), Some(b)) if a.len() == b.len() => {
            let selected = if quota {
                Ok(Vec::new())
            } else {
                cpuset_indices(a)
            };
            let selected_after = if quota {
                Ok(Vec::new())
            } else {
                cpuset_indices(b)
            };
            if selected != selected_after {
                return false;
            }
            a.iter().zip(b).enumerate().all(|(index, (a, b))| {
                a.controller == b.controller
                    && a.directory == b.directory
                    && a.root == b.root
                    && a.root_evidence == b.root_evidence
                    && a.controllers == b.controllers
                    && a.subtree_control == b.subtree_control
                    && if quota {
                        a.quota == b.quota && a.period == b.period
                    } else if selected
                        .as_ref()
                        .is_ok_and(|indices| !indices.contains(&index))
                    {
                        true
                    } else {
                        a.cpuset == b.cpuset
                    }
            })
        }
        _ => before.constraints == after.constraints,
    }
}
pub fn cpuset(
    capture: &TargetCapture,
    ids: &[i64],
    limits: &HostCaptureLimits,
) -> Observation<Vec<i64>> {
    let rows = verified_constraints(capture, limits)?;
    let mut allowed: BTreeSet<_> = ids.iter().copied().collect();
    let mut descendant: Option<(Controller, BTreeSet<i64>)> = None;
    let mut v1_mask_found = false;
    for index in cpuset_indices(rows)? {
        let row = &rows[index];
        let text = row.cpuset.get()?;
        if row.controller == Controller::Cpuset && text.trim().is_empty() {
            continue;
        }
        let set: BTreeSet<_> = cpu_list(text, limits)?.into_iter().collect();
        if row.controller == Controller::Cpuset {
            v1_mask_found = true;
        }
        if row.controller == Controller::Cpuset
            && let Some((kind, child)) = &descendant
            && *kind == row.controller
            && !child.is_subset(&set)
        {
            return Err(UnavailableReason::Malformed);
        }
        descendant = Some((row.controller, set.clone()));
        allowed = allowed.intersection(&set).copied().collect();
    }
    if allowed.is_empty()
        || (rows.iter().any(|r| r.controller == Controller::Cpuset) && !v1_mask_found)
    {
        return Err(UnavailableReason::Malformed);
    }
    Ok(allowed.into_iter().collect())
}
pub fn allowed(
    capture: &TargetCapture,
    ids: &[i64],
    limits: &HostCaptureLimits,
) -> Observation<i64> {
    let mask = capture.affinity.get()?;
    if mask.is_empty()
        || mask.len() as i64 > limits.max_cpu_ids
        || mask.windows(2).any(|v| v[0] >= v[1])
        || mask.iter().any(|v| *v < 0 || *v > limits.max_cpu_id)
    {
        return Err(UnavailableReason::Malformed);
    }
    let effective = cpuset(capture, ids, limits)?;
    let count = effective
        .iter()
        .filter(|id| mask.binary_search(id).is_ok())
        .count();
    if count == 0 {
        return Err(UnavailableReason::Malformed);
    }
    Ok(count as i64)
}
fn positive_integer(text: &str) -> Observation<i64> {
    if text.is_empty() || !text.bytes().all(|b| b.is_ascii_digit()) {
        return Err(UnavailableReason::Malformed);
    }
    text.parse::<i64>()
        .ok()
        .filter(|v| *v > 0)
        .ok_or(UnavailableReason::Malformed)
}
pub fn quota(
    capture: &TargetCapture,
    limits: &HostCaptureLimits,
) -> Observation<(Option<f64>, QuotaState)> {
    let rows = verified_constraints(capture, limits)?;
    let mut minimum: Option<f64> = None;
    for (index, row) in rows.iter().enumerate() {
        if row.controller == Controller::Cpuset
            || (row.controller == Controller::V2 && !v2_applicable(rows, index, "cpu")?)
        {
            continue;
        }
        // The hierarchy root has no cpu.max file on Linux; it cannot be throttled.
        if row.controller == Controller::V2
            && row.root
            && row.quota.reason == Some(UnavailableReason::Missing)
        {
            continue;
        }
        let raw = row.quota.get()?.trim();
        let (value, period) = if row.controller == Controller::V2 {
            let fields: Vec<_> = raw.split_whitespace().collect();
            if fields.len() != 2 {
                return Err(UnavailableReason::Malformed);
            }
            (fields[0], positive_integer(fields[1])?)
        } else {
            (raw, positive_integer(row.period.get()?.trim())?)
        };
        if (row.controller == Controller::V2 && value == "max")
            || (row.controller == Controller::Cpu && value == "-1")
        {
            continue;
        }
        let ratio = positive_integer(value)? as f64 / period as f64;
        minimum = Some(minimum.map_or(ratio, |old| old.min(ratio)));
    }
    Ok((
        minimum,
        if minimum.is_some() {
            QuotaState::Finite
        } else {
            QuotaState::Unlimited
        },
    ))
}
