//! Which independent CPU cells and seven source diagnostics survive one bracketed capture?

use crate::contracts::events::{
    CaptureSource, CoverageStatus, CpuDiagnostics, HostCaptureLimits, ProcessTarget,
    SourceCoverage, UnavailableReason,
};
use crate::contracts::host::{CorrectedHostFingerprintRow, QuotaState};
use crate::probe_inputs::{
    allowance::{self, TargetCapture},
    frequency,
    snapshots::CpuCapture,
    topology,
};

pub fn coverage(
    source: CaptureSource,
    expected: usize,
    observed: usize,
    reason: Option<UnavailableReason>,
) -> SourceCoverage {
    SourceCoverage {
        source,
        status: if reason.is_none() && expected > 0 && expected == observed {
            CoverageStatus::Complete
        } else if observed > 0 {
            CoverageStatus::Partial
        } else {
            CoverageStatus::Unavailable
        },
        expected: expected as i64,
        observed: observed as i64,
        reason,
    }
}
pub fn failed(source: CaptureSource, expected: usize, reason: UnavailableReason) -> SourceCoverage {
    coverage(source, expected, 0, Some(reason))
}
pub fn measure(
    row: &mut CorrectedHostFingerprintRow,
    capture: &CpuCapture,
    limits: &HostCaptureLimits,
) -> CpuDiagnostics {
    use CaptureSource::*;
    let online = if capture.online_before != capture.online_after {
        Err(UnavailableReason::SnapshotChanged)
    } else {
        topology::online(&capture.online_before, &capture.inventory, limits)
    };
    let ids = online.as_ref().cloned().unwrap_or_default();
    row.cpu_logical_processors = online.as_ref().ok().map(|v| v.len() as i64);
    let count = ids.len();
    let mut sources = vec![match online {
        Ok(_) => coverage(Online, count, count, None),
        Err(r) => failed(Online, count, r),
    }];
    let physical = if count > 0 {
        topology::physical(&ids, &capture.topology, limits)
    } else {
        Err(sources[0]
            .reason
            .unwrap_or(UnavailableReason::IncompleteCoverage))
    };
    row.cpu_physical_cores = physical.as_ref().ok().copied();
    sources.push(match physical {
        Ok(_) => coverage(Topology, count, count, None),
        Err(r) => failed(Topology, count, r),
    });
    let observed = if count > 0 {
        frequency::observed(&capture.cpuinfo, &ids)
    } else {
        Err(sources[0]
            .reason
            .unwrap_or(UnavailableReason::IncompleteCoverage))
    };
    row.cpu_observed_mhz = observed.as_ref().ok().and_then(|v| v.0);
    sources.push(match observed {
        Ok((Some(_), valid)) => coverage(
            Cpuinfo,
            count,
            valid,
            if valid == count {
                None
            } else {
                Some(UnavailableReason::IncompleteCoverage)
            },
        ),
        Ok(_) => failed(Cpuinfo, count, UnavailableReason::Missing),
        Err(r) => failed(Cpuinfo, count, r),
    });
    let reported = if count > 0 {
        frequency::reported(&capture.policies, &ids, limits)
    } else {
        Err(sources[0]
            .reason
            .unwrap_or(UnavailableReason::IncompleteCoverage))
    };
    row.cpu_reported_max_mhz = reported.as_ref().ok().copied();
    sources.push(match reported {
        Ok(_) => coverage(Cpufreq, count, count, None),
        Err(r) => failed(Cpufreq, count, r),
    });
    for source in [Affinity, Cpuset, Quota] {
        sources.push(failed(source, 1, UnavailableReason::Missing));
    }
    CpuDiagnostics {
        online_cpu_ids: ids,
        sources,
        target: None,
    }
}
fn replace(cpu: &mut CpuDiagnostics, source: SourceCoverage) {
    if let Some(cell) = cpu.sources.iter_mut().find(|v| v.source == source.source) {
        *cell = source;
    }
}
fn identity_stable(before: &TargetCapture, after: &TargetCapture) -> bool {
    before.start_ticks == after.start_ticks
        && before.cgroup == after.cgroup
        && before.mountinfo == after.mountinfo
}
fn constraints_stable(before: &TargetCapture, after: &TargetCapture, quota: bool) -> bool {
    match (&before.constraints.value, &after.constraints.value) {
        (Some(a), Some(b)) => {
            a.len() == b.len()
                && a.iter().zip(b).all(|(a, b)| {
                    a.controller == b.controller
                        && a.directory == b.directory
                        && a.root == b.root
                        && a.controllers == b.controllers
                        && if quota {
                            a.quota == b.quota && a.period == b.period
                        } else {
                            a.cpuset == b.cpuset
                        }
                })
        }
        _ => before.constraints == after.constraints,
    }
}
pub fn target(
    row: &mut CorrectedHostFingerprintRow,
    cpu: &mut CpuDiagnostics,
    capture: &CpuCapture,
    target: &ProcessTarget,
    measured_at: &str,
    limits: &HostCaptureLimits,
) {
    use CaptureSource::*;
    row.cpu_target_measured_at = Some(measured_at.to_owned());
    row.cpu_allowed_processors = None;
    row.cpu_quota_cores = None;
    row.cpu_quota_state = Some(QuotaState::Unavailable);
    cpu.target = Some(target.clone());
    let pair = capture
        .target_before
        .as_ref()
        .zip(capture.target_after.as_ref());
    let identity = pair.ok_or(UnavailableReason::Missing).and_then(|(a, b)| {
        allowance::identity(a, target)?;
        allowance::identity(b, target)?;
        if identity_stable(a, b) {
            Ok((a, b))
        } else {
            Err(UnavailableReason::SnapshotChanged)
        }
    });
    let ids = topology::online(&capture.online_before, &capture.inventory, limits);
    let online_matches = capture.online_before == capture.online_after
        && ids.as_ref().is_ok_and(|ids| *ids == cpu.online_cpu_ids)
        && !cpu.online_cpu_ids.is_empty();
    let affinity = identity.and_then(|(a, b)| {
        if !online_matches || a.affinity != b.affinity || !constraints_stable(a, b, false) {
            return Err(UnavailableReason::SnapshotChanged);
        }
        allowance::allowed(a, &cpu.online_cpu_ids, limits)
    });
    replace(
        cpu,
        match affinity {
            Ok(count) => {
                row.cpu_allowed_processors = Some(count);
                coverage(Affinity, 1, 1, None)
            }
            Err(r) => failed(Affinity, 1, r),
        },
    );
    let cpuset = identity.and_then(|(a, b)| {
        if !online_matches || !constraints_stable(a, b, false) {
            return Err(UnavailableReason::SnapshotChanged);
        }
        allowance::cpuset(a, &cpu.online_cpu_ids, limits)
    });
    replace(
        cpu,
        match cpuset {
            Ok(_) => coverage(Cpuset, 1, 1, None),
            Err(r) => failed(Cpuset, 1, r),
        },
    );
    let quota = identity.and_then(|(a, b)| {
        if !constraints_stable(a, b, true) {
            return Err(UnavailableReason::SnapshotChanged);
        }
        allowance::quota(a, limits)
    });
    replace(
        cpu,
        match quota {
            Ok((value, state)) => {
                row.cpu_quota_cores = value;
                row.cpu_quota_state = Some(state);
                coverage(Quota, 1, 1, None)
            }
            Err(r) => failed(Quota, 1, r),
        },
    );
}
