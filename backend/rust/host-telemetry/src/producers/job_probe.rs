//! Which initial whole host row and exact native completion does this job produce?

use crate::config::{CodecConfig, Lifecycle};
use crate::contracts::events::{
    HostCommandBody, HostEvent, HostResultBody, HostSessionManifest, ProcessTarget,
};
use crate::contracts::file_envelope::HostWriterIdentity;
use crate::contracts::host::{
    CorrectedHostFingerprintRow, HostStoredRow, Result, Validate, host_unit_id, require,
};
use crate::contracts::write_plan::{HostWriteCompletion, HostWritePlan};
use crate::probe_inputs::{
    bandwidth, cpu, frequency,
    placement::Placement,
    snapshots::{CpuCapture, validate_capture},
};
use crate::{fingerprint, ledger::store, receipts};
use std::path::Path;
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct ProducedHost {
    pub result: HostResultBody,
    pub plan: HostWritePlan,
    pub completion: HostWriteCompletion,
}
pub struct Publication<'a> {
    pub workspace: &'a Path,
    pub target_root: &'a str,
    pub evidence_root: &'a str,
    pub prefix: &'a [String],
    pub identity: &'a HostWriterIdentity,
    pub codec: &'a CodecConfig,
    pub lifecycle: Lifecycle,
    pub event_id: Uuid,
    pub written_at_ms: i64,
    pub limits: &'a receipts::ReceiptLimits,
}
pub fn validate_command<'a>(
    manifest: &HostSessionManifest,
    event: &'a HostEvent,
) -> Result<&'a HostCommandBody> {
    manifest.validate()?;
    event.validate()?;
    require(
        event.session_id == manifest.session_id
            && event.date == manifest.date
            && event.run_id == manifest.run_id
            && event.attempt == manifest.attempt
            && event.job == manifest.job
            && event.shard == manifest.shard
            && event.emitter_id == manifest.operator_emitter_id,
        "command conflicts with manifest identity",
    )?;
    let crate::contracts::events::EventBody::HostCommand(body) = &event.body else {
        return Err("not a host command".to_owned());
    };
    require(
        body.input_names
            .iter()
            .all(|n| manifest.named_inputs.iter().any(|i| i.name == *n)),
        "undeclared command input",
    )?;
    if let Some(target) = &body.target {
        validate_target(manifest, target)?;
    }
    Ok(body)
}
pub fn validate_target(manifest: &HostSessionManifest, target: &ProcessTarget) -> Result<()> {
    target.validate()?;
    let servers: Vec<_> = manifest
        .workers
        .iter()
        .filter_map(|w| w.server.as_ref())
        .collect();
    require(
        if servers.is_empty() {
            manifest.workers.iter().any(|w| &w.target == target)
        } else {
            servers.iter().all(|v| *v == target)
        },
        "target is not the selected server or profiled worker",
    )?;
    require(
        manifest.cpu_target.as_ref().is_none_or(|v| v == target),
        "conflicting manifest target",
    )
}
pub fn probe(
    manifest: &HostSessionManifest,
    event: &HostEvent,
    capture: &CpuCapture,
    where_: &Placement,
    runner: Option<String>,
    measured_at: &str,
    cache_multiple: i64,
) -> Result<HostResultBody> {
    let body = validate_command(manifest, event)?;
    require(
        event.kind == crate::contracts::events::EventKind::HostProbe
            && body.previous_result_id.is_none(),
        "probe cannot replace a previous result",
    )?;
    validate_capture(capture, &manifest.capture_limits)?;
    let mut row: CorrectedHostFingerprintRow = serde_json::from_value(serde_json::json!({
        "date":manifest.date,"run_id":manifest.run_id,"job":manifest.job,"shard":manifest.shard
    }))
    .map_err(|e| e.to_string())?;
    row.measured_at = Some(measured_at.to_owned());
    fingerprint::hardware(
        &mut row,
        capture.cpuinfo.value.as_deref(),
        capture.cache_bytes.value,
    )?;
    let mut diagnostics = cpu::measure(&mut row, capture, &manifest.capture_limits);
    if let Some(target) = body.target.as_ref().or(manifest.cpu_target.as_ref()) {
        cpu::target(
            &mut row,
            &mut diagnostics,
            capture,
            target,
            measured_at,
            &manifest.capture_limits,
        );
    }
    row.boot_seconds = capture
        .uptime
        .value
        .as_deref()
        .and_then(|v| v.split_whitespace().next())
        .and_then(frequency::positive_float);
    let size = bandwidth::buffer_mib(
        if body.controls.memcpy_enabled {
            body.controls.memcpy_probe_mib
        } else {
            0
        },
        row.l3_cache_bytes,
        cache_multiple,
    )?;
    row.memcpy_probe_mib = Some(size);
    row.memcpy_gib_s = bandwidth::measure(size, body.controls.memcpy_passes)?;
    row.vm_size = where_.vm_size.clone();
    row.vm_location = where_.location.clone();
    row.vm_zone = where_.zone.clone();
    row.vm_fault_domain = where_.fault_domain.clone();
    row.runner_name = runner
        .map(|v| v.trim().to_owned())
        .filter(|v| !v.is_empty());
    row.validate()?;
    diagnostics.validate()?;
    Ok(HostResultBody {
        row,
        cpu: diagnostics,
        completion_event_ids: vec![event.event_id],
    })
}
pub fn publish(
    publication: &Publication<'_>,
    result: HostResultBody,
    previous: Option<&HostWritePlan>,
) -> Result<Option<ProducedHost>> {
    result.validate()?;
    let stored = HostStoredRow {
        unit_id: host_unit_id(
            &result.row.date,
            &result.row.run_id,
            result.row.job,
            result.row.shard,
        )?,
        covers: result.row.date.clone(),
        ledger: "host-fingerprint".to_owned(),
        attempt: publication.identity.attempt,
        host: result.row.clone(),
    };
    let rows = [stored];
    let request = store::WriteRequest {
        target_root: publication.target_root,
        prefix: publication.prefix,
        publication_identity: publication.identity,
        rows: &rows,
        codec: publication.codec,
        lifecycle: publication.lifecycle,
        event_id: publication.event_id,
        written_at_ms: publication.written_at_ms,
    };
    let prepared = if let Some(previous) = previous {
        if previous.event_id == publication.event_id {
            let candidate = store::prepare(publication.workspace, request)?;
            require(
                candidate.as_ref().is_none_or(|v| v.plan() == previous),
                "retry conflicts with immutable plan",
            )?;
            candidate
        } else {
            store::prepare_successor(publication.workspace, request, previous)?
        }
    } else {
        store::prepare(publication.workspace, request)?
    };
    let Some(prepared) = prepared else {
        return Ok(None);
    };
    let completion = receipts::write(&prepared, publication.evidence_root, publication.limits)
        .map_err(|e| e.message.clone())?;
    let mut result = result;
    result.completion_event_ids = vec![completion.event_id];
    Ok(Some(ProducedHost {
        result,
        plan: prepared.plan().clone(),
        completion,
    }))
}
pub fn prior_matches(
    manifest: &HostSessionManifest,
    event: &HostEvent,
    previous_id: Uuid,
    previous: &HostResultBody,
    plan: &HostWritePlan,
) -> Result<()> {
    previous.validate()?;
    plan.validate()?;
    let body = validate_command(manifest, event)?;
    require(
        body.previous_result_id == Some(previous_id),
        "previous result reference mismatch",
    )?;
    require(
        previous.row.date == manifest.date
            && previous.row.run_id == manifest.run_id
            && previous.row.job == manifest.job
            && previous.row.shard == manifest.shard
            && plan.publication_identity.attempt == manifest.attempt
            && plan.files.len() == 1
            && plan.files[0].rows[0].host == previous.row,
        "previous row/plan identity mismatch",
    )
}
