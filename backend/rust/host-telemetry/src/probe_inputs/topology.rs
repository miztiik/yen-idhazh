//! Which complete visible online topology establishes physical and logical processor counts?

use crate::contracts::events::{HostCaptureLimits, UnavailableReason};
use crate::probe_inputs::files::Reading;
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub type Observation<T> = std::result::Result<T, UnavailableReason>;
pub fn cpu_list(text: &str, limits: &HostCaptureLimits) -> Observation<Vec<i64>> {
    let mut ids = BTreeSet::new();
    let text = text.trim();
    if text.is_empty() {
        return Err(UnavailableReason::Malformed);
    }
    for part in text.split(',') {
        let parts: Vec<_> = part.split('-').collect();
        if parts.is_empty()
            || parts.len() > 2
            || parts
                .iter()
                .any(|p| p.is_empty() || !p.bytes().all(|b| b.is_ascii_digit()))
        {
            return Err(UnavailableReason::Malformed);
        }
        let start: i64 = parts[0].parse().map_err(|_| UnavailableReason::Malformed)?;
        let end = if parts.len() == 2 {
            parts[1].parse().map_err(|_| UnavailableReason::Malformed)?
        } else {
            start
        };
        if start > end || end > limits.max_cpu_id || end - start >= limits.max_cpu_ids {
            return Err(UnavailableReason::Malformed);
        }
        for id in start..=end {
            if !ids.insert(id) || ids.len() as i64 > limits.max_cpu_ids {
                return Err(UnavailableReason::Malformed);
            }
        }
    }
    Ok(ids.into_iter().collect())
}

pub fn online(
    text: &Reading<String>,
    inventory: &Reading<String>,
    limits: &HostCaptureLimits,
) -> Observation<Vec<i64>> {
    let ids = cpu_list(text.get()?, limits)?;
    let visible = cpu_list(inventory.get()?, limits)?;
    if ids.iter().any(|id| visible.binary_search(id).is_err()) {
        return Err(UnavailableReason::IncompleteCoverage);
    }
    Ok(ids)
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CpuTopology {
    pub id: i64,
    pub package: Reading<String>,
    pub core: Reading<String>,
    pub thread_siblings: Reading<String>,
    pub package_siblings: Reading<String>,
}
pub fn physical(
    ids: &[i64],
    entries: &[CpuTopology],
    limits: &HostCaptureLimits,
) -> Observation<i64> {
    if ids.is_empty() {
        return Err(UnavailableReason::IncompleteCoverage);
    }
    let mut rows = BTreeMap::new();
    for entry in entries {
        let integer = |text: &Reading<String>| -> Observation<i64> {
            let value = text.get()?.trim();
            if value.is_empty() || !value.bytes().all(|b| b.is_ascii_digit()) {
                return Err(UnavailableReason::Malformed);
            }
            value.parse().map_err(|_| UnavailableReason::Malformed)
        };
        let package = integer(&entry.package)?;
        let core = integer(&entry.core)?;
        let filter = |list: Vec<i64>| {
            list.into_iter()
                .filter(|id| ids.binary_search(id).is_ok())
                .collect::<BTreeSet<_>>()
        };
        let threads = filter(cpu_list(entry.thread_siblings.get()?, limits)?);
        let packages = filter(cpu_list(entry.package_siblings.get()?, limits)?);
        if ids.binary_search(&entry.id).is_err()
            || !threads.contains(&entry.id)
            || !packages.contains(&entry.id)
            || rows
                .insert(entry.id, (package, core, threads, packages))
                .is_some()
        {
            return Err(UnavailableReason::Malformed);
        }
    }
    if rows.len() != ids.len() {
        return Err(UnavailableReason::IncompleteCoverage);
    }
    for (&id, (package, core, threads, packages)) in &rows {
        let expected_threads = rows
            .iter()
            .filter(|(_, r)| r.0 == *package && r.1 == *core)
            .map(|(&id, _)| id)
            .collect();
        let expected_package = rows
            .iter()
            .filter(|(_, r)| r.0 == *package)
            .map(|(&id, _)| id)
            .collect();
        if *threads != expected_threads || *packages != expected_package || !threads.contains(&id) {
            return Err(UnavailableReason::Malformed);
        }
    }
    Ok(rows
        .values()
        .map(|r| (r.0, r.1))
        .collect::<BTreeSet<_>>()
        .len() as i64)
}
