//! Which immutable event history fits this session's ordering, retry and total budgets?

use crate::contracts::events::*;
use crate::{Result, Validate};
use std::collections::{HashMap, HashSet};
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct ProtocolError {
    pub code: ProtocolFaultCode,
    pub message: String,
}
impl std::fmt::Display for ProtocolError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{:?}: {}", self.code, self.message)
    }
}
impl std::error::Error for ProtocolError {}
pub type ProtocolResult<T> = std::result::Result<T, ProtocolError>;
pub fn refuse(code: ProtocolFaultCode, message: &str) -> ProtocolError {
    ProtocolError {
        code,
        message: message.to_owned(),
    }
}

pub fn ordinary_reserve(limits: &HostEventLimits) -> u64 {
    // Even one active window needs a stop command, fault, result and stopped event.
    limits.max_concurrent_windows as u64 * 2 + 2
}

pub fn publication_reserve(limits: &HostEventLimits, events: &[&HostEvent]) -> Result<u64> {
    if let Some(stopped) = events.iter().find(|v| v.kind == EventKind::MonitorStopped) {
        let EventBody::Stopped(body) = &stopped.body else {
            return Err("shutdown requires stopped body".to_owned());
        };
        let mut windows = HashSet::new();
        let mut stops = 0;
        for event in events.iter().filter(|v| v.event_id != stopped.event_id) {
            match &event.body {
                EventBody::WindowResult(result) if event.kind == EventKind::WindowResult => {
                    crate::contracts::host::require(
                        result.status == WindowStatus::Incomplete
                            && windows.insert(result.window.window_id),
                        "shutdown requires unique incomplete windows",
                    )?;
                }
                EventBody::Stop(_) if event.kind == EventKind::MonitorStop => {
                    stops += 1;
                    crate::contracts::host::require(
                        stopped.reply_to == Some(event.event_id),
                        "shutdown names another stop command",
                    )?;
                }
                _ => return Err("shutdown batch contains ordinary traffic".to_owned()),
            }
        }
        crate::contracts::host::require(
            events.len() <= limits.max_concurrent_windows as usize + 2
                && events
                    .last()
                    .is_some_and(|v| v.event_id == stopped.event_id)
                && events
                    .iter()
                    .filter(|v| v.kind == EventKind::MonitorStopped)
                    .count()
                    == 1
                && body.drained
                && stops <= 1
                && windows.len() <= limits.max_concurrent_windows as usize
                && windows.len() == body.aborted_window_ids.len()
                && body
                    .aborted_window_ids
                    .iter()
                    .all(|id| windows.contains(id)),
            "shutdown batch lacks complete drain evidence",
        )?;
        return Ok(0);
    }
    Ok(events
        .iter()
        .map(|event| {
            if matches!(
                event.kind,
                EventKind::MonitorStop | EventKind::ProtocolFault
            ) {
                limits.max_concurrent_windows as u64 + 1
            } else if matches!(
                event.kind,
                EventKind::WindowEnd | EventKind::WindowAbort | EventKind::WindowResult
            ) {
                limits.max_concurrent_windows as u64 + 2
            } else {
                ordinary_reserve(limits)
            }
        })
        .max()
        .unwrap_or(0))
}

#[derive(Clone)]
struct History {
    digest: String,
    event: Option<HostEvent>,
    replies: Vec<HostEvent>,
    received_at: u64,
    consumed: bool,
}
#[derive(Clone)]
pub struct EventBook {
    manifest: HostSessionManifest,
    history: HashMap<Uuid, History>,
    sequences: HashMap<String, i64>,
    retained: usize,
    pub total_events: u64,
    pub total_bytes: u64,
    last_ms: u64,
}
impl EventBook {
    pub fn new(manifest: HostSessionManifest) -> Result<Self> {
        manifest.validate()?;
        Ok(Self {
            manifest,
            history: HashMap::new(),
            sequences: HashMap::new(),
            retained: 0,
            total_events: 0,
            total_bytes: 0,
            last_ms: 0,
        })
    }
    pub fn check(
        &mut self,
        event: &HostEvent,
        now_ms: u64,
    ) -> ProtocolResult<Option<Vec<HostEvent>>> {
        event
            .validate()
            .map_err(|v| refuse(ProtocolFaultCode::State, &v))?;
        if now_ms < self.last_ms {
            return Err(refuse(ProtocolFaultCode::Order, "monotonic time reversed"));
        }
        let raw = crate::canonical_json::row_line(event)
            .map_err(|v| refuse(ProtocolFaultCode::State, &v))?;
        let digest = crate::canonical_json::sha256(&raw);
        if let Some(known) = self.history.get_mut(&event.event_id) {
            if known.digest != digest {
                return Err(refuse(
                    ProtocolFaultCode::Duplicate,
                    "event ID reused with different bytes",
                ));
            }
            if known.event.is_none() {
                return Err(refuse(
                    ProtocolFaultCode::Retired,
                    "event retired after consumption and retry window",
                ));
            }
            known.received_at = now_ms;
            let replies = known.replies.clone();
            for reply in &replies {
                if let Some(entry) = self.history.get_mut(&reply.event_id) {
                    entry.received_at = now_ms;
                }
            }
            self.last_ms = now_ms;
            return Ok(Some(replies));
        }
        let m = &self.manifest;
        if event.date != m.date
            || event.run_id != m.run_id
            || event.attempt != m.attempt
            || event.job != m.job
            || event.shard != m.shard
            || event.session_id != m.session_id
        {
            return Err(refuse(
                ProtocolFaultCode::Identity,
                "foreign event invocation/session",
            ));
        }
        let emitter_valid = match event.kind {
            EventKind::MonitorStop => event.emitter_id == m.operator_emitter_id,
            EventKind::HostProbe | EventKind::HostTarget | EventKind::HostClock => {
                event.emitter_id == m.operator_emitter_id
            }
            EventKind::WorkerRegister
            | EventKind::WindowBegin
            | EventKind::WindowEnd
            | EventKind::WindowAbort => m.workers.iter().any(|v| v.emitter_id == event.emitter_id),
            _ => event.emitter_id == m.monitor_emitter_id,
        };
        if !emitter_valid {
            return Err(refuse(
                ProtocolFaultCode::Identity,
                "foreign emitter or command kind",
            ));
        }
        if event.sequence <= self.sequences.get(&event.emitter_id).copied().unwrap_or(0) {
            return Err(refuse(
                ProtocolFaultCode::Order,
                "sequence must increase per emitter",
            ));
        }
        Ok(None)
    }
    pub fn commit(
        &mut self,
        event: HostEvent,
        replies: Vec<HostEvent>,
        now_ms: u64,
    ) -> ProtocolResult<()> {
        let events = std::iter::once(&event)
            .chain(replies.iter())
            .collect::<Vec<_>>();
        let reserve = publication_reserve(&self.manifest.limits, &events)
            .map_err(|e| refuse(ProtocolFaultCode::Bounds, &e))?;
        self.commit_reserved(event, replies, now_ms, reserve)
    }
    pub fn commit_closing(
        &mut self,
        event: HostEvent,
        replies: Vec<HostEvent>,
        now_ms: u64,
        remaining_windows: usize,
    ) -> ProtocolResult<()> {
        if !matches!(event.kind, EventKind::WindowEnd | EventKind::WindowAbort)
            || replies.len() != 1
            || replies[0].kind != EventKind::WindowResult
            || replies[0].reply_to != Some(event.event_id)
            || remaining_windows > self.manifest.limits.max_concurrent_windows as usize
        {
            return Err(refuse(
                ProtocolFaultCode::State,
                "invalid closing reservation",
            ));
        }
        // A closed window no longer needs an aborted result; fault, stop and stopped still do.
        self.commit_reserved(event, replies, now_ms, remaining_windows as u64 + 3)
    }
    pub fn commit_shutdown(&mut self, events: &[HostEvent], now_ms: u64) -> ProtocolResult<()> {
        let refs = events.iter().collect::<Vec<_>>();
        if !events.iter().any(|v| v.kind == EventKind::MonitorStopped)
            || publication_reserve(&self.manifest.limits, &refs)
                .map_err(|e| refuse(ProtocolFaultCode::Bounds, &e))?
                != 0
        {
            return Err(refuse(
                ProtocolFaultCode::Bounds,
                "incomplete shutdown batch",
            ));
        }
        let mut staged = self.clone();
        for event in events {
            staged.commit_reserved(event.clone(), Vec::new(), now_ms, 0)?;
        }
        *self = staged;
        Ok(())
    }
    fn commit_reserved(
        &mut self,
        event: HostEvent,
        replies: Vec<HostEvent>,
        now_ms: u64,
        reserve: u64,
    ) -> ProtocolResult<()> {
        let events = std::iter::once(&event)
            .chain(replies.iter())
            .collect::<Vec<_>>();
        let mut bytes = 0_u64;
        let mut ids = HashSet::new();
        for value in &events {
            value
                .validate()
                .map_err(|e| refuse(ProtocolFaultCode::State, &e))?;
            let raw = crate::canonical_json::row_line(value)
                .map_err(|e| refuse(ProtocolFaultCode::State, &e))?;
            let command = matches!(
                value.kind,
                EventKind::HostProbe
                    | EventKind::HostTarget
                    | EventKind::HostClock
                    | EventKind::WorkerRegister
                    | EventKind::WindowBegin
                    | EventKind::WindowEnd
                    | EventKind::WindowAbort
                    | EventKind::MonitorStop
            );
            let cap = if command {
                self.manifest.limits.max_command_bytes
            } else {
                self.manifest.limits.max_result_bytes
            };
            if raw.len() as i64 > cap
                || self.history.contains_key(&value.event_id)
                || !ids.insert(value.event_id)
            {
                return Err(refuse(
                    ProtocolFaultCode::Bounds,
                    "event size or identity capacity exhausted",
                ));
            }
            bytes = bytes.saturating_add(raw.len() as u64);
        }
        let limits = &self.manifest.limits;
        let reserved_bytes =
            reserve.saturating_mul(limits.max_result_bytes.max(limits.max_command_bytes) as u64);
        if self
            .total_events
            .saturating_add(events.len() as u64)
            .saturating_add(reserve)
            > limits.max_session_events as u64
            || self
                .total_bytes
                .saturating_add(bytes)
                .saturating_add(reserved_bytes)
                > limits.max_session_bytes as u64
            || self.retained + events.len() + reserve as usize
                > (limits
                    .max_files
                    .min(self.manifest.pending_event_limit().unwrap_or(0)))
                    as usize
        {
            return Err(refuse(
                ProtocolFaultCode::Bounds,
                "session total or pending capacity exhausted",
            ));
        }
        for value in events {
            self.sequences
                .insert(value.emitter_id.clone(), value.sequence);
            self.history.insert(
                value.event_id,
                History {
                    digest: crate::canonical_json::sha256(
                        &crate::canonical_json::row_line(value).unwrap(),
                    ),
                    event: Some(value.clone()),
                    replies: if value.event_id == event.event_id {
                        replies.clone()
                    } else {
                        Vec::new()
                    },
                    received_at: now_ms,
                    consumed: false,
                },
            );
        }
        self.retained += replies.len() + 1;
        self.total_events += (replies.len() + 1) as u64;
        self.total_bytes += bytes;
        self.last_ms = now_ms;
        Ok(())
    }
    pub fn consume(&mut self, event_id: Uuid) -> ProtocolResult<()> {
        let entry = self
            .history
            .get_mut(&event_id)
            .ok_or_else(|| refuse(ProtocolFaultCode::Retired, "unknown consumed event"))?;
        if entry.event.is_none() {
            return Err(refuse(
                ProtocolFaultCode::Retired,
                "consumed event already retired",
            ));
        }
        entry.consumed = true;
        Ok(())
    }
    pub fn retire(&mut self, now_ms: u64, protected: &HashSet<Uuid>) -> Vec<Uuid> {
        let mut retired = Vec::new();
        let mut groups = Vec::new();
        for (id, value) in &self.history {
            if value.event.is_none()
                || protected.contains(id)
                || value.event.as_ref().is_some_and(|v| v.reply_to.is_some())
            {
                continue;
            }
            let mut group = vec![*id];
            group.extend(value.replies.iter().map(|v| v.event_id));
            if group.iter().all(|id| {
                self.history.get(id).is_some_and(|h| {
                    h.event.is_some()
                        && h.consumed
                        && now_ms.saturating_sub(h.received_at)
                            >= self.manifest.limits.retry_window_ms as u64
                        && !protected.contains(id)
                })
            }) {
                groups.push(group);
            }
        }
        for id in groups.into_iter().flatten() {
            if let Some(value) = self.history.get_mut(&id)
                && value.event.take().is_some()
            {
                value.replies.clear();
                self.retained -= 1;
                retired.push(id);
            }
        }
        retired
    }
    pub fn retained(&self) -> usize {
        self.retained
    }
    pub fn history_len(&self) -> usize {
        self.history.len()
    }
}

pub struct ReadBudget {
    pub reads: u64,
    pub bytes: u64,
    reserved: usize,
    limits: HostEventLimits,
}
impl ReadBudget {
    pub fn new(limits: HostEventLimits) -> Self {
        Self {
            reads: 0,
            bytes: 0,
            reserved: 0,
            limits,
        }
    }
    pub fn reserve(&mut self, maximum: usize) -> Result<()> {
        crate::contracts::host::require(
            self.reads < self.limits.max_reads as u64
                && self.bytes.saturating_add(maximum as u64) <= self.limits.max_read_bytes as u64,
            "session cumulative read budget exhausted",
        )?;
        self.reads += 1;
        self.bytes = self.bytes.saturating_add(maximum as u64);
        self.reserved = maximum;
        Ok(())
    }
    pub fn used(&mut self, bytes: usize) {
        self.bytes = self
            .bytes
            .saturating_sub(self.reserved as u64)
            .saturating_add(bytes as u64);
        self.reserved = 0;
    }
}
