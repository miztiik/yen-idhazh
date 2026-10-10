//! Which observed samples and fully covered hardware policies establish the two frequency readings?

use crate::contracts::events::{HostCaptureLimits, UnavailableReason};
use crate::probe_inputs::{
    files::Reading,
    topology::{Observation, cpu_list},
};
use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, BTreeSet};

pub fn positive_float(text: &str) -> Option<f64> {
    text.trim()
        .parse::<f64>()
        .ok()
        .filter(|v| v.is_finite() && *v > 0.0)
}
pub fn cpuinfo_records(text: &str) -> Observation<Vec<BTreeMap<String, String>>> {
    let mut records = Vec::new();
    let mut current = BTreeMap::new();
    for line in text.lines() {
        let Some((key, value)) = line.split_once(':') else {
            continue;
        };
        let key = key.trim();
        if key == "processor" && current.contains_key("processor") {
            records.push(std::mem::take(&mut current));
        }
        if current
            .insert(key.to_owned(), value.trim().to_owned())
            .is_some()
        {
            return Err(UnavailableReason::Malformed);
        }
    }
    if !current.is_empty() {
        records.push(current);
    }
    Ok(records)
}
pub fn observed(text: &Reading<String>, ids: &[i64]) -> Observation<(Option<f64>, usize)> {
    let records = cpuinfo_records(text.get()?)?;
    let mut seen = BTreeSet::new();
    let mut values = Vec::new();
    for row in records {
        let id = row.get("processor").ok_or(UnavailableReason::Malformed)?;
        if id.is_empty() || !id.bytes().all(|b| b.is_ascii_digit()) {
            return Err(UnavailableReason::Malformed);
        }
        let id: i64 = id.parse().map_err(|_| UnavailableReason::Malformed)?;
        if !seen.insert(id) {
            return Err(UnavailableReason::Malformed);
        }
        if ids.binary_search(&id).is_ok()
            && let Some(value) = row.get("cpu MHz").and_then(|s| positive_float(s))
        {
            values.push(value);
        }
    }
    let mean = if values.is_empty() {
        None
    } else {
        // Dividing each term avoids overflow when a finite captured sample is very large.
        Some(values.iter().map(|v| v / values.len() as f64).sum::<f64>())
    };
    Ok((mean.filter(|v| v.is_finite() && *v > 0.0), values.len()))
}
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct FrequencyPolicy {
    pub name: String,
    pub cpus: Reading<String>,
    pub maximum_khz: Reading<String>,
}
pub fn reported(
    policies: &Reading<Vec<FrequencyPolicy>>,
    ids: &[i64],
    limits: &HostCaptureLimits,
) -> Observation<f64> {
    let policies = policies.get()?;
    let mut covered = BTreeSet::new();
    let mut all_members = BTreeSet::new();
    let mut names = BTreeSet::new();
    let mut maximum: f64 = 0.0;
    for policy in policies {
        if !names.insert(&policy.name) {
            return Err(UnavailableReason::Malformed);
        }
        let text = policy
            .cpus
            .get()?
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(",");
        let members = cpu_list(&text, limits)?;
        let raw = policy.maximum_khz.get()?.trim();
        if raw.is_empty() || !raw.bytes().all(|b| b.is_ascii_digit()) {
            return Err(UnavailableReason::Malformed);
        }
        let khz: u64 = raw.parse().map_err(|_| UnavailableReason::Malformed)?;
        if khz == 0 {
            return Err(UnavailableReason::Malformed);
        }
        if members.iter().any(|id| ids.binary_search(id).is_ok()) {
            maximum = maximum.max(khz as f64 / 1000.0);
        }
        for id in members {
            if !all_members.insert(id) {
                return Err(UnavailableReason::Malformed);
            }
            if ids.binary_search(&id).is_ok() && !covered.insert(id) {
                return Err(UnavailableReason::Malformed);
            }
        }
    }
    if ids.is_empty() || covered.len() != ids.len() {
        return Err(UnavailableReason::IncompleteCoverage);
    }
    Ok(maximum)
}
