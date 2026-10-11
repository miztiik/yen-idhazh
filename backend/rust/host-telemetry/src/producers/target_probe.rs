//! Which first selected target capture enriches the original probe without refreshing its hardware?

use crate::contracts::events::{EventKind, HostEvent, HostResultBody, HostSessionManifest};
use crate::contracts::host::{Result, require};
use crate::contracts::write_plan::HostWritePlan;
use crate::probe_inputs::{
    cpu,
    snapshots::{CpuCapture, validate_capture},
};
use crate::producers::job_probe::{prior_matches, validate_command};
use uuid::Uuid;

pub fn enrich(
    manifest: &HostSessionManifest,
    event: &HostEvent,
    previous_id: Uuid,
    previous: &HostResultBody,
    plan: &HostWritePlan,
    capture: &CpuCapture,
    captured_at: &str,
) -> Result<HostResultBody> {
    prior_matches(manifest, event, previous_id, previous, plan)?;
    require(event.kind == EventKind::HostTarget, "not a target command")?;
    let body = validate_command(manifest, event)?;
    let target = body.target.as_ref().ok_or("target command lacks target")?;
    if let Some(frozen) = &previous.cpu.target {
        require(frozen == target, "conflicting shard target")?;
        return Ok(previous.clone());
    }
    validate_capture(capture, &manifest.capture_limits)?;
    let mut result = previous.clone();
    cpu::target(
        &mut result.row,
        &mut result.cpu,
        capture,
        target,
        captured_at,
        &manifest.capture_limits,
    );
    result.completion_event_ids = vec![event.event_id];
    result.validate()?;
    Ok(result)
}
use crate::contracts::host::Validate;
