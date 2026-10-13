//! Which resource command may advance this session and which independent result must it return?

use crate::contracts::events::*;
use crate::contracts::write_plan::{HostWriteCompletion, HostWritePlan};
use crate::sampling::capture::ResourceFrame;
use crate::transport::bounds::{EventBook, ProtocolError, ProtocolResult, refuse};
use crate::windows::reduce::WindowReducer;
use crate::{Result, Validate};
use std::collections::{HashMap, HashSet};
use uuid::Uuid;

#[derive(Clone)]
struct ActiveWindow {
    begin: HostEvent,
    reducer: WindowReducer,
    next_tick_ms: u64,
}
#[derive(Clone)]
pub struct Session {
    pub manifest: HostSessionManifest,
    pub book: EventBook,
    registered: HashSet<String>,
    active: HashMap<Uuid, ActiveWindow>,
    finished: HashSet<Uuid>,
    pub stopped: bool,
    sequence: i64,
    last_ms: u64,
    ready_id: Option<Uuid>,
    last_host: Option<(Uuid, HostResultBody)>,
    last_plan: Option<HostWritePlan>,
}

/// Native producer output supplied to the session boundary after the raw
/// publication and its immutable receipt have been completed.
#[derive(Clone)]
pub struct NativeHostOutput {
    pub result: HostResultBody,
    pub plan: HostWritePlan,
    pub completion: HostWriteCompletion,
    pub emitted_at: String,
}
impl Session {
    pub fn new(manifest: HostSessionManifest) -> Result<Self> {
        let book = EventBook::new(manifest.clone())?;
        Ok(Self {
            manifest,
            book,
            registered: HashSet::new(),
            active: HashMap::new(),
            finished: HashSet::new(),
            stopped: false,
            sequence: 0,
            last_ms: 0,
            ready_id: None,
            last_host: None,
            last_plan: None,
        })
    }
    fn event_id(&self, kind: EventKind, reply_to: Option<Uuid>, sequence: i64) -> Uuid {
        Uuid::new_v5(
            &self.manifest.session_id,
            format!("{reply_to:?}:{kind:?}:{sequence}").as_bytes(),
        )
    }
    fn event(
        &mut self,
        kind: EventKind,
        body: EventBody,
        reply_to: Option<Uuid>,
        at: &str,
    ) -> HostEvent {
        self.sequence += 1;
        let event_id = self.event_id(kind, reply_to, self.sequence);
        HostEvent {
            version: self.manifest.version.clone(),
            kind,
            event_id,
            reply_to,
            date: self.manifest.date.clone(),
            run_id: self.manifest.run_id.clone(),
            attempt: self.manifest.attempt,
            job: self.manifest.job,
            shard: self.manifest.shard,
            session_id: self.manifest.session_id,
            emitter_id: self.manifest.monitor_emitter_id.clone(),
            sequence: self.sequence,
            emitted_at: at.to_owned(),
            body,
        }
    }
    pub fn ready(&mut self, at: &str, now_ms: u64) -> Result<HostEvent> {
        let checkpoint = self.clone();
        let event = self.event(
            EventKind::MonitorReady,
            EventBody::Ready(MonitorReadyBody {
                boot_id: self.manifest.boot_id,
                supported_version: self.manifest.version.clone(),
            }),
            None,
            at,
        );
        self.ready_id = Some(event.event_id);
        let result = self.check_shutdown_capacity(at).and_then(|()| {
            self.book
                .commit(event.clone(), Vec::new(), now_ms)
                .map_err(|e| e.to_string())
        });
        if let Err(error) = result {
            *self = checkpoint;
            return Err(error);
        }
        Ok(event)
    }
    pub fn handle(
        &mut self,
        command: &HostEvent,
        frame: &ResourceFrame,
        now_ms: u64,
    ) -> ProtocolResult<Vec<HostEvent>> {
        if let Some(replies) = self.book.check(command, now_ms)? {
            return Ok(replies);
        }
        if self.stopped {
            return Err(refuse(ProtocolFaultCode::State, "monitor already stopped"));
        }
        let checkpoint = self.clone();
        let result = self.advance(command, frame, now_ms).and_then(|replies| {
            if command.kind == EventKind::WindowBegin {
                self.check_shutdown_capacity(&frame.captured_at)
                    .map_err(|e| refuse(ProtocolFaultCode::Bounds, &e))?;
            }
            if matches!(command.kind, EventKind::WindowEnd | EventKind::WindowAbort) {
                self.book.commit_closing(
                    command.clone(),
                    replies.clone(),
                    now_ms,
                    self.active.len(),
                )?;
            } else {
                self.book.commit(command.clone(), replies.clone(), now_ms)?;
            }
            self.last_ms = now_ms;
            Ok(replies)
        });
        if result.is_err() {
            *self = checkpoint;
        }
        result
    }
    /// Return the deterministic IDs reserved for a native command's plan,
    /// completion and result events.  The producer uses the result ID before
    /// it writes its immutable result document; the session then emits the
    /// exact same IDs in one validated reply batch.
    pub fn host_reply_ids(&self, command_id: Uuid) -> (Uuid, Uuid, Uuid) {
        (
            self.event_id(EventKind::WritePlan, Some(command_id), self.sequence + 1),
            self.event_id(
                EventKind::WriteCompleted,
                Some(command_id),
                self.sequence + 2,
            ),
            self.event_id(EventKind::HostResult, Some(command_id), self.sequence + 3),
        )
    }
    pub fn host_result_sequence(&self) -> i64 {
        self.sequence + 3
    }
    pub fn last_host_command_id(&self) -> Option<Uuid> {
        self.last_plan.as_ref().map(|plan| plan.event_id)
    }
    fn validate_host_shape(&self, command: &HostEvent) -> ProtocolResult<()> {
        let EventBody::HostCommand(body) = &command.body else {
            return Err(refuse(
                ProtocolFaultCode::State,
                "host command has wrong body",
            ));
        };
        if command.emitter_id != self.manifest.operator_emitter_id {
            return Err(refuse(
                ProtocolFaultCode::Identity,
                "host command is not operator-owned",
            ));
        }
        let host_pending = self.last_host.as_ref().map(|(id, _)| *id);
        match command.kind {
            EventKind::HostProbe => {
                if host_pending.is_some()
                    || body.previous_result_id.is_some()
                    || body.target.is_some()
                {
                    return Err(refuse(
                        ProtocolFaultCode::State,
                        "probe cannot replace an existing host row",
                    ));
                }
            }
            EventKind::HostTarget | EventKind::HostClock => {
                if host_pending != body.previous_result_id {
                    return Err(refuse(
                        ProtocolFaultCode::Identity,
                        "host enrichment requires the latest result",
                    ));
                }
                if command.kind == EventKind::HostTarget {
                    let target = body.target.as_ref().ok_or_else(|| {
                        refuse(
                            ProtocolFaultCode::Target,
                            "target enrichment needs a target",
                        )
                    })?;
                    if self.manifest.cpu_target.as_ref() != Some(target) {
                        return Err(refuse(
                            ProtocolFaultCode::Target,
                            "target differs from the manifest selection",
                        ));
                    }
                    let selected = self
                        .manifest
                        .workers
                        .iter()
                        .filter(|worker| {
                            worker.target == *target || worker.server.as_ref() == Some(target)
                        })
                        .any(|worker| self.registered.contains(&worker.emitter_id));
                    if !selected {
                        return Err(refuse(
                            ProtocolFaultCode::State,
                            "target enrichment requires registration ACK",
                        ));
                    }
                }
            }
            _ => return Err(refuse(ProtocolFaultCode::State, "not a host command")),
        }
        if body.controls != self.manifest.controls {
            return Err(refuse(
                ProtocolFaultCode::Target,
                "host command controls differ from the manifest",
            ));
        }
        Ok(())
    }
    /// Validate command identity and lifecycle state before a producer is
    /// allowed to create immutable raw evidence.
    pub fn preflight_host_command(
        &self,
        command: &HostEvent,
        now_ms: u64,
    ) -> ProtocolResult<Option<Vec<HostEvent>>> {
        let mut book = self.book.clone();
        if let Some(replies) = book.check(command, now_ms)? {
            return Ok(Some(replies));
        }
        if self.stopped {
            return Err(refuse(ProtocolFaultCode::State, "monitor already stopped"));
        }
        self.validate_host_shape(command)?;
        Ok(None)
    }
    pub fn handle_host(
        &mut self,
        command: &HostEvent,
        mut output: NativeHostOutput,
        now_ms: u64,
    ) -> ProtocolResult<Vec<HostEvent>> {
        if let Some(replies) = self.book.check(command, now_ms)? {
            return Ok(replies);
        }
        if self.stopped {
            return Err(refuse(ProtocolFaultCode::State, "monitor already stopped"));
        }
        let checkpoint = self.clone();
        let result = (|| {
            let EventBody::HostCommand(body) = &command.body else {
                return Err(refuse(
                    ProtocolFaultCode::State,
                    "host command has wrong body",
                ));
            };
            self.validate_host_shape(command)?;
            output
                .plan
                .validate()
                .map_err(|e| refuse(ProtocolFaultCode::State, &e))?;
            output
                .completion
                .validate_plan(&output.plan, true)
                .map_err(|e| refuse(ProtocolFaultCode::Store, &e))?;
            if output.plan.event_id != command.event_id
                || !self
                    .manifest
                    .output_roots
                    .iter()
                    .any(|root| root == &output.plan.target_root)
            {
                return Err(refuse(
                    ProtocolFaultCode::Identity,
                    "native plan references another command or output root",
                ));
            }
            if let Some(previous) = &self.last_plan {
                output
                    .plan
                    .validate_successor(previous)
                    .map_err(|e| refuse(ProtocolFaultCode::State, &e))?;
            }
            if output.plan.files.len() != 1 || output.plan.files[0].rows.len() != 1 {
                return Err(refuse(
                    ProtocolFaultCode::Identity,
                    "native plan row cardinality differs",
                ));
            }
            output.result.completion_event_ids = vec![self.host_reply_ids(command.event_id).1];
            output
                .result
                .validate()
                .map_err(|e| refuse(ProtocolFaultCode::State, &e))?;
            if output.plan.files[0].rows[0].host != output.result.row {
                return Err(refuse(
                    ProtocolFaultCode::Identity,
                    "native result differs from its immutable plan",
                ));
            }
            if body.target.is_none() && output.result.row.cpu_target_measured_at.is_some() {
                return Err(refuse(
                    ProtocolFaultCode::Target,
                    "targetless host command produced target cells",
                ));
            }
            if command.kind == EventKind::HostClock
                && let Some((_, previous)) = &self.last_host
                && previous.cpu != output.result.cpu
            {
                return Err(refuse(
                    ProtocolFaultCode::State,
                    "clock command remeasured CPU evidence",
                ));
            }
            let (plan_id, completed_id, result_id) = self.host_reply_ids(command.event_id);
            let at = &command.emitted_at;
            let plan = self.event(
                EventKind::WritePlan,
                EventBody::Plan(WritePlanBody {
                    plan: output.plan.clone(),
                }),
                Some(command.event_id),
                at,
            );
            let completed = self.event(
                EventKind::WriteCompleted,
                EventBody::Completed(WriteCompletedBody {
                    completion: output.completion.clone(),
                }),
                Some(command.event_id),
                at,
            );
            let result_event = self.event(
                EventKind::HostResult,
                EventBody::HostResult(Box::new(output.result.clone())),
                Some(command.event_id),
                &output.emitted_at,
            );
            if (plan.event_id, completed.event_id, result_event.event_id)
                != (plan_id, completed_id, result_id)
            {
                return Err(refuse(
                    ProtocolFaultCode::Order,
                    "native reply ID reservation drifted",
                ));
            }
            self.book.commit(
                command.clone(),
                vec![plan.clone(), completed.clone(), result_event.clone()],
                now_ms,
            )?;
            self.last_host = Some((result_event.event_id, output.result));
            self.last_plan = Some(output.plan);
            self.last_ms = now_ms;
            Ok(vec![plan, completed, result_event])
        })();
        if result.is_err() {
            *self = checkpoint;
        }
        result
    }
    fn worker(&self, emitter: &str) -> ProtocolResult<&ExpectedWorker> {
        self.manifest
            .workers
            .iter()
            .find(|v| v.emitter_id == emitter)
            .ok_or_else(|| refuse(ProtocolFaultCode::Identity, "undeclared worker"))
    }
    fn window(&self, command: &HostEvent, body: &WindowBody) -> ProtocolResult<()> {
        let worker = self.worker(&command.emitter_id)?;
        let declared = self
            .manifest
            .windows
            .iter()
            .find(|v| v.window_id == body.window_id)
            .ok_or_else(|| refuse(ProtocolFaultCode::Identity, "undeclared window"))?;
        if body.target != worker.target || body.server != worker.server {
            return Err(refuse(
                ProtocolFaultCode::Target,
                "foreign PID or process start identity",
            ));
        }
        if declared.emitter_id != command.emitter_id || declared.item_id != body.item_id {
            return Err(refuse(
                ProtocolFaultCode::Identity,
                "window belongs to another item/emitter",
            ));
        }
        if !self.registered.contains(&command.emitter_id) {
            return Err(refuse(
                ProtocolFaultCode::State,
                "work requires registration ACK",
            ));
        }
        Ok(())
    }
    fn verify_target(&self, frame: &ResourceFrame, target: &ProcessTarget) -> ProtocolResult<()> {
        let Some(texts) = frame.processes.iter().find(|v| &v.target == target) else {
            return Err(refuse(
                ProtocolFaultCode::Target,
                "declared process unavailable",
            ));
        };
        let reading = crate::sampling::process::reduce(texts, false, false);
        if reading.identity.value.as_ref() != Some(target) {
            return Err(refuse(
                ProtocolFaultCode::Target,
                "PID exited/reused or identity unavailable",
            ));
        }
        Ok(())
    }
    fn advance(
        &mut self,
        command: &HostEvent,
        frame: &ResourceFrame,
        now_ms: u64,
    ) -> ProtocolResult<Vec<HostEvent>> {
        frame
            .validate(&self.manifest.capture_limits)
            .map_err(|v| refuse(ProtocolFaultCode::Bounds, &v))?;
        let memory = self.manifest.controls.memory_profiling_enabled;
        let at = &frame.captured_at;
        let result = match (&command.kind, &command.body) {
            (EventKind::WorkerRegister, EventBody::Worker(body)) => {
                let worker = self.worker(&command.emitter_id)?;
                if worker.target != body.target
                    || worker.server != body.server
                    || body.memory_profiling_enabled != memory
                {
                    return Err(refuse(
                        ProtocolFaultCode::Target,
                        "registration differs from declared target/controls",
                    ));
                }
                if self.registered.contains(&command.emitter_id) {
                    return Err(refuse(
                        ProtocolFaultCode::State,
                        "worker already registered under another event",
                    ));
                }
                self.verify_target(frame, &body.target)?;
                if let Some(server) = &body.server {
                    self.verify_target(frame, server)?;
                }
                self.registered.insert(command.emitter_id.clone());
                vec![self.event(
                    EventKind::WorkerRegistered,
                    EventBody::Worker(body.clone()),
                    Some(command.event_id),
                    at,
                )]
            }
            (EventKind::WindowBegin, EventBody::Window(body)) => {
                self.window(command, body)?;
                if self.active.contains_key(&body.window_id)
                    || self.finished.contains(&body.window_id)
                {
                    return Err(refuse(
                        ProtocolFaultCode::State,
                        "window already opened or finished",
                    ));
                }
                if self.active.len() >= self.manifest.limits.max_concurrent_windows as usize {
                    return Err(refuse(
                        ProtocolFaultCode::Bounds,
                        "active window capacity exhausted",
                    ));
                }
                self.verify_target(frame, &body.target)?;
                if let Some(server) = &body.server {
                    self.verify_target(frame, server)?;
                }
                let reducer =
                    WindowReducer::new(body.clone(), frame.snapshot(body, memory, true), memory)
                        .map_err(|v| refuse(ProtocolFaultCode::State, &v))?;
                let next_tick_ms = now_ms.saturating_add(self.interval_ms());
                self.active.insert(
                    body.window_id,
                    ActiveWindow {
                        begin: command.clone(),
                        reducer,
                        next_tick_ms,
                    },
                );
                vec![self.event(
                    EventKind::WindowBegun,
                    EventBody::Begun(WindowBegunBody {
                        window: body.clone(),
                        captured_at: at.clone(),
                    }),
                    Some(command.event_id),
                    at,
                )]
            }
            (EventKind::WindowEnd, EventBody::Window(body)) => {
                self.window(command, body)?;
                for target in std::iter::once(&body.target).chain(body.server.iter()) {
                    if frame
                        .processes
                        .iter()
                        .find(|v| &v.target == target)
                        .is_some_and(|v| {
                            crate::sampling::process::reduce(v, false, false)
                                .identity
                                .reason
                                == Some(UnavailableReason::PidReused)
                        })
                    {
                        return Err(refuse(
                            ProtocolFaultCode::Target,
                            "closing process PID was reused",
                        ));
                    }
                }
                let active = self.active.get(&body.window_id).ok_or_else(|| {
                    refuse(
                        ProtocolFaultCode::State,
                        "end before begin or window already closed",
                    )
                })?;
                let result = active
                    .reducer
                    .clone()
                    .close(frame.snapshot(body, memory, true))
                    .map_err(|v| refuse(ProtocolFaultCode::State, &v))?;
                self.active.remove(&body.window_id);
                self.finished.insert(body.window_id);
                vec![self.event(
                    EventKind::WindowResult,
                    EventBody::WindowResult(Box::new(result)),
                    Some(command.event_id),
                    at,
                )]
            }
            (EventKind::WindowAbort, EventBody::Abort(body)) => {
                self.window(command, &body.window)?;
                let active = self.active.remove(&body.window.window_id).ok_or_else(|| {
                    refuse(
                        ProtocolFaultCode::State,
                        "abort before begin or already closed",
                    )
                })?;
                self.finished.insert(body.window.window_id);
                vec![self.event(
                    EventKind::WindowResult,
                    EventBody::WindowResult(Box::new(
                        active.reducer.abort(UnavailableReason::IncompleteCoverage),
                    )),
                    Some(command.event_id),
                    at,
                )]
            }
            (EventKind::MonitorStop, EventBody::Stop(_)) => {
                let mut result = self.abort_active(at);
                self.stopped = true;
                let aborted_window_ids = result
                    .iter()
                    .filter_map(|v| match &v.body {
                        EventBody::WindowResult(v) => Some(v.window.window_id),
                        _ => None,
                    })
                    .collect();
                result.push(self.event(
                    EventKind::MonitorStopped,
                    EventBody::Stopped(StoppedBody {
                        drained: true,
                        aborted_window_ids,
                    }),
                    Some(command.event_id),
                    at,
                ));
                result
            }
            _ => {
                return Err(refuse(
                    ProtocolFaultCode::State,
                    "command does not belong to resource monitor",
                ));
            }
        };
        Ok(result)
    }
    fn abort_active(&mut self, at: &str) -> Vec<HostEvent> {
        let mut windows = self.active.drain().collect::<Vec<_>>();
        windows.sort_by_key(|(id, _)| *id);
        windows
            .into_iter()
            .map(|(id, active)| {
                self.finished.insert(id);
                self.event(
                    EventKind::WindowResult,
                    EventBody::WindowResult(Box::new(
                        active.reducer.abort(UnavailableReason::IncompleteCoverage),
                    )),
                    Some(active.begin.event_id),
                    at,
                )
            })
            .collect()
    }
    fn cancellation_events(&mut self, at: &str) -> Result<Vec<HostEvent>> {
        let ready_id = self
            .ready_id
            .ok_or("cancellation requires session readiness")?;
        let mut events = self.abort_active(at);
        let aborted_window_ids = events
            .iter()
            .filter_map(|v| match &v.body {
                EventBody::WindowResult(v) => Some(v.window.window_id),
                _ => None,
            })
            .collect();
        events.push(self.event(
            EventKind::MonitorStopped,
            EventBody::Stopped(StoppedBody {
                drained: true,
                aborted_window_ids,
            }),
            Some(ready_id),
            at,
        ));
        Ok(events)
    }
    fn check_shutdown_capacity(&self, at: &str) -> Result<()> {
        let mut staged = self.clone();
        for mut event in staged.cancellation_events(at)? {
            event.validate()?;
            // Admission must still fit after the monitor's sequence grows.
            event.sequence = i64::MAX;
            crate::contracts::host::require(
                crate::canonical_json::row_line(&event)?.len() as i64
                    <= self.manifest.limits.max_result_bytes,
                "shutdown result size capacity exhausted",
            )?;
        }
        Ok(())
    }
    pub fn cancelled(&mut self, at: &str, now_ms: u64) -> Result<Vec<HostEvent>> {
        let checkpoint = self.clone();
        let events = self.cancellation_events(at)?;
        if let Err(e) = self.book.commit_shutdown(&events, now_ms) {
            *self = checkpoint;
            return Err(e.to_string());
        }
        self.stopped = true;
        Ok(events)
    }
    pub fn protocol_fault(
        &mut self,
        error: &ProtocolError,
        related: Option<Uuid>,
        at: &str,
        now_ms: u64,
    ) -> Result<HostEvent> {
        let event = self.event(
            EventKind::ProtocolFault,
            EventBody::Fault(ProtocolFaultBody {
                code: error.code,
                related_event_id: related,
            }),
            related,
            at,
        );
        self.book
            .commit(event.clone(), Vec::new(), now_ms)
            .map_err(|e| e.to_string())?;
        Ok(event)
    }
    pub fn tick(&mut self, frame: &ResourceFrame, now_ms: u64) -> Result<()> {
        frame.validate(&self.manifest.capture_limits)?;
        crate::contracts::host::require(
            now_ms >= self.last_ms,
            "monotonic sampling time reversed",
        )?;
        let interval = self.interval_ms();
        if interval == 0 {
            return Ok(());
        }
        for active in self.active.values_mut() {
            if now_ms >= active.next_tick_ms {
                active.reducer.note(&frame.snapshot(
                    &active.reducer.window,
                    self.manifest.controls.memory_profiling_enabled,
                    false,
                ));
                // Missed wakes are not fabricated samples.
                active.next_tick_ms = now_ms.saturating_add(interval);
            }
        }
        self.last_ms = now_ms;
        Ok(())
    }
    fn interval_ms(&self) -> u64 {
        (self.manifest.controls.resource_interval_seconds * 1000.0).ceil() as u64
    }
    pub fn needs_tick(&self, now_ms: u64) -> bool {
        self.interval_ms() > 0 && self.active.values().any(|v| now_ms >= v.next_tick_ms)
    }
    pub fn active_count(&self) -> usize {
        self.active.len()
    }
    pub fn registered_count(&self) -> usize {
        self.registered.len()
    }
    pub fn retire(&mut self, now_ms: u64) -> Vec<Uuid> {
        let mut protected: HashSet<_> = self.active.values().map(|v| v.begin.event_id).collect();
        if !self.stopped {
            // Protect the whole reply group: the next host command reads its result file.
            protected.extend(self.last_host_command_id());
        }
        self.book.retire(now_ms, &protected)
    }
    pub fn observation(
        &mut self,
        kind: EventKind,
        body: EventBody,
        at: &str,
        now_ms: u64,
    ) -> Result<HostEvent> {
        let event = self.event(kind, body, None, at);
        self.book
            .commit(event.clone(), Vec::new(), now_ms)
            .map_err(|e| e.to_string())?;
        Ok(event)
    }
}
