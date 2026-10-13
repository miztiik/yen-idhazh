//! Do native host predecessors stay readable until an admitted successor or session stop?

#[path = "support/resources.rs"]
mod resources;
mod support;

use idhazh_host_telemetry::{
    Result, canonical_json, cli,
    contracts::{events::*, write_plan::HostWritePlan},
    monitor::session::{NativeHostOutput, Session},
    receipts,
    transport::files::FileTransport,
};
use std::{collections::BTreeMap, fs, path::PathBuf};
use uuid::Uuid;

struct Fixture {
    root: PathBuf,
    session: Session,
    files: FileTransport,
}
impl Fixture {
    fn new(name: &str) -> Self {
        let root = support::workspace(&format!("host-reply-retention-{name}"));
        let mut manifest = support::manifest();
        manifest.named_inputs = vec![
            NamedHostInput {
                name: "snapshot".to_owned(),
                source: CaptureSource::Cpuinfo,
                relative_path: "capture.json".to_owned(),
            },
            NamedHostInput {
                name: "start".to_owned(),
                source: CaptureSource::ClockLog,
                relative_path: "start.txt".to_owned(),
            },
        ];
        resources::setup(&root, &manifest);
        fs::write(root.join("start.txt"), "2026-10-10T12:00:00Z").unwrap();
        let mut session = Session::new(manifest.clone()).unwrap();
        let mut files = FileTransport::new(&root, manifest).unwrap();
        let ready = session.ready("2026-10-10T12:00:00Z", 0).unwrap();
        files.publish(&ready, "results").unwrap();
        Self {
            root,
            session,
            files,
        }
    }
    fn command(
        &self,
        kind: EventKind,
        sequence: i64,
        previous: Option<Uuid>,
        at: &str,
    ) -> HostEvent {
        let mut command = support::command(
            &self.session.manifest,
            kind,
            sequence,
            previous,
            kind == EventKind::HostTarget,
        );
        command.emitted_at = at.to_owned();
        let EventBody::HostCommand(body) = &mut command.body else {
            unreachable!();
        };
        body.input_names = vec!["snapshot".to_owned()];
        if kind == EventKind::HostClock {
            body.input_names.push("start".to_owned());
        }
        command
    }
    fn output(&mut self, command: &HostEvent) -> Result<NativeHostOutput> {
        self.files.publish(command, "inbox")?;
        let mut replay = support::replay();
        replay.captured_at = command.emitted_at.clone();
        replay.written_at_ms += command.sequence;
        fs::write(
            self.root.join("capture.json"),
            serde_json::to_vec(&replay).unwrap(),
        )
        .unwrap();
        let (_, completion_id, result_id) = self.session.host_reply_ids(command.event_id);
        let event_root = &self.session.manifest.event_root;
        let result_path = format!("{event_root}/results/.pending-{result_id}.json");
        let evidence = format!("{event_root}/writes");
        let plan_path = format!("{evidence}/{}.plan.json", command.event_id);
        let mut args = BTreeMap::from([
            (
                "--workspace".to_owned(),
                self.root.to_string_lossy().into_owned(),
            ),
            ("--manifest".to_owned(), "manifest.json".to_owned()),
            ("--config".to_owned(), "config.json".to_owned()),
            (
                "--command".to_owned(),
                self.files.relative_path(command.event_id, "inbox")?,
            ),
            ("--snapshot".to_owned(), "snapshot".to_owned()),
            ("--format".to_owned(), "json".to_owned()),
            ("--compression".to_owned(), "none".to_owned()),
            ("--cache-multiple".to_owned(), "2".to_owned()),
            ("--result-id".to_owned(), result_id.to_string()),
            ("--completion-id".to_owned(), completion_id.to_string()),
            (
                "--result-sequence".to_owned(),
                self.session.host_result_sequence().to_string(),
            ),
            ("--result-output".to_owned(), result_path.clone()),
        ]);
        let EventBody::HostCommand(body) = &command.body else {
            unreachable!();
        };
        if let Some(previous) = body.previous_result_id {
            args.insert(
                "--previous-result".to_owned(),
                self.files.relative_path(previous, "results")?,
            );
            args.insert(
                "--previous-plan".to_owned(),
                format!(
                    "{evidence}/{}.plan.json",
                    self.session.last_host_command_id().unwrap()
                ),
            );
        }
        let verb = match command.kind {
            EventKind::HostProbe => "probe",
            EventKind::HostTarget => "target",
            EventKind::HostClock => {
                args.insert("--job-start-input".to_owned(), "start".to_owned());
                "clock"
            }
            _ => unreachable!(),
        };
        cli::run(
            std::iter::once(verb.to_owned())
                .chain(args.into_iter().flat_map(|(key, value)| [key, value])),
        )?;
        let path = self.root.join(result_path);
        let result: HostEvent = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        fs::remove_file(path).unwrap();
        let EventBody::HostResult(body) = result.body else {
            panic!("native producer did not return host.result");
        };
        let plan: HostWritePlan =
            serde_json::from_slice(&fs::read(self.root.join(plan_path)).unwrap()).unwrap();
        Ok(NativeHostOutput {
            result: *body,
            plan,
            completion: receipts::load_latest_completion(
                &self.root,
                &evidence,
                command.event_id,
                self.session.manifest.limits.max_result_bytes as usize,
            )?,
            emitted_at: result.emitted_at,
        })
    }
    fn admit(&mut self, command: &HostEvent, now_ms: u64) -> Vec<HostEvent> {
        assert!(
            self.session
                .preflight_host_command(command, now_ms)
                .unwrap()
                .is_none()
        );
        let output = self.output(command).unwrap();
        self.admit_output(command, output, now_ms).unwrap()
    }
    fn admit_output(
        &mut self,
        command: &HostEvent,
        output: NativeHostOutput,
        now_ms: u64,
    ) -> Result<Vec<HostEvent>> {
        let mut staged = self.session.clone();
        let replies = staged
            .handle_host(command, output, now_ms)
            .map_err(|e| e.to_string())?;
        self.files.publish_batch(&replies, "results")?;
        self.session = staged;
        Ok(std::iter::once(command.clone()).chain(replies).collect())
    }
    fn consume(&mut self, events: &[HostEvent]) {
        for event in events {
            self.files.consume(event).unwrap();
            self.session.book.consume(event.event_id).unwrap();
        }
    }
    fn retire(&mut self, now_ms: u64) -> Vec<Uuid> {
        let retired = self.session.retire(now_ms);
        self.files.remove_retired(&retired).unwrap();
        retired
    }
    fn assert_present(&self, events: &[HostEvent]) {
        for (index, event) in events.iter().enumerate() {
            let direction = if index == 0 { "inbox" } else { "results" };
            let raw = canonical_json::row_line(event).unwrap();
            assert_eq!(
                fs::read(self.files.path(event.event_id, direction).unwrap()).unwrap(),
                raw
            );
            assert_eq!(
                fs::read(self.files.path(event.event_id, "consumed").unwrap()).unwrap(),
                raw
            );
        }
    }
}
impl Drop for Fixture {
    fn drop(&mut self) {
        fs::remove_dir_all(&self.root).unwrap();
    }
}

#[test]
fn latest_target_survives_long_job_and_clock_releases_only_expired_older_groups() {
    let mut fixture = Fixture::new("long-job");
    let frame = resources::frames().remove(0);
    let mut window = Vec::new();
    for kind in [EventKind::WorkerRegister, EventKind::WindowBegin] {
        let sequence = if kind == EventKind::WorkerRegister {
            1
        } else {
            2
        };
        let command = resources::command(kind, 0, sequence);
        fixture.files.publish(&command, "inbox").unwrap();
        let replies = fixture.session.handle(&command, &frame, 0).unwrap();
        fixture.files.publish_batch(&replies, "results").unwrap();
        if kind == EventKind::WindowBegin {
            window = std::iter::once(command).chain(replies).collect();
        }
    }
    fixture.consume(&window);
    let probe = fixture.command(EventKind::HostProbe, 1, None, "2026-10-10T12:00:00Z");
    let initial = fixture.admit(&probe, 0);
    fixture.consume(&initial);
    let target = fixture.command(
        EventKind::HostTarget,
        2,
        Some(initial[3].event_id),
        "2026-10-10T12:00:01Z",
    );
    let selected = fixture.admit(&target, 1);
    fixture.consume(&selected);
    let EventBody::Completed(completed) = &selected[2].body else {
        unreachable!();
    };
    let raw_path = fixture
        .root
        .join(completed.completion.receipt.writes.keys().next().unwrap());
    let raw_bytes = fs::read(&raw_path).unwrap();
    let retry = fixture.session.manifest.limits.retry_window_ms as u64;
    assert!(fixture.retire(retry - 1).is_empty());
    assert_eq!(
        fixture.session.book.check(&probe, retry - 1).unwrap(),
        Some(initial[1..].to_vec())
    );
    for now_ms in [retry, retry + 1, 2 * retry - 2] {
        assert!(fixture.retire(now_ms).is_empty());
        fixture.assert_present(&initial);
        fixture.assert_present(&selected);
        fixture.assert_present(&window);
    }
    let history = (
        fixture.session.book.total_events,
        fixture.session.book.total_bytes,
        fixture.session.book.history_len(),
        fixture.files.total_events,
        fixture.files.total_bytes,
    );
    let retired = fixture.retire(2 * retry - 1);
    assert_eq!(retired.len(), initial.len());
    for event in &initial {
        assert!(retired.contains(&event.event_id));
        for direction in ["inbox", "results", "consumed"] {
            assert!(
                !fixture
                    .files
                    .path(event.event_id, direction)
                    .unwrap()
                    .exists()
            );
        }
    }
    assert_eq!(
        history,
        (
            fixture.session.book.total_events,
            fixture.session.book.total_bytes,
            fixture.session.book.history_len(),
            fixture.files.total_events,
            fixture.files.total_bytes,
        )
    );
    let long_ms = 2 * 60 * 60 * 1000;
    assert!(fixture.retire(long_ms).is_empty());
    fixture.assert_present(&selected);
    fixture.assert_present(&window);
    assert_eq!(fixture.session.active_count(), 1);
    assert_eq!(
        fixture
            .session
            .book
            .check(&probe, long_ms)
            .unwrap_err()
            .code,
        ProtocolFaultCode::Retired
    );
    let mut conflict = probe.clone();
    conflict.emitted_at = "2026-10-10T12:00:02Z".to_owned();
    assert_eq!(
        fixture
            .session
            .book
            .check(&conflict, long_ms)
            .unwrap_err()
            .code,
        ProtocolFaultCode::Duplicate
    );
    let mut clock = fixture.command(
        EventKind::HostClock,
        3,
        Some(selected[3].event_id),
        "2026-10-10T14:00:00Z",
    );
    let EventBody::HostCommand(target_body) = &target.body else {
        unreachable!();
    };
    let EventBody::HostCommand(clock_body) = &mut clock.body else {
        unreachable!();
    };
    clock_body.target.clone_from(&target_body.target);
    let closed = fixture.admit(&clock, long_ms);
    fixture.consume(&closed);
    let EventBody::HostResult(result) = &closed[3].body else {
        unreachable!();
    };
    let EventBody::HostResult(previous) = &selected[3].body else {
        unreachable!();
    };
    assert_eq!(result.row.job_seconds, Some(7200));
    assert_eq!(result.cpu, previous.cpu);
    assert_eq!(
        result.row.cpu_target_measured_at,
        previous.row.cpu_target_measured_at
    );
    assert_eq!(result.completion_event_ids, vec![closed[2].event_id]);
    let retired = fixture.retire(long_ms);
    assert_eq!(retired.len(), selected.len());
    assert!(
        selected
            .iter()
            .all(|event| retired.contains(&event.event_id))
    );
    assert!(fixture.retire(long_ms + retry).is_empty());
    fixture.assert_present(&closed);
    fixture.assert_present(&window);
    assert_eq!(fs::read(&raw_path).unwrap(), raw_bytes);
}

#[test]
fn invalid_producer_validation_and_publication_failures_preserve_the_predecessor() {
    let mut fixture = Fixture::new("failed-successor");
    let probe = fixture.command(EventKind::HostProbe, 1, None, "2026-10-10T12:00:00Z");
    let initial = fixture.admit(&probe, 0);
    fixture.consume(&initial);
    let retry = fixture.session.manifest.limits.retry_window_ms as u64;
    for now_ms in [retry, retry + 1, 2 * retry] {
        assert!(fixture.retire(now_ms).is_empty());
        fixture.assert_present(&initial);
    }
    let now_ms = 2 * retry;
    let clock = fixture.command(
        EventKind::HostClock,
        2,
        Some(initial[3].event_id),
        "2026-10-10T14:00:00Z",
    );
    let invalid = fixture.command(
        EventKind::HostClock,
        2,
        Some(Uuid::from_u128(9999)),
        "2026-10-10T14:00:00Z",
    );
    assert_eq!(
        fixture
            .session
            .preflight_host_command(&invalid, now_ms)
            .unwrap_err()
            .code,
        ProtocolFaultCode::Identity
    );
    fs::write(fixture.root.join("start.txt"), "2026-10-10T14:00:01Z").unwrap();
    let error = fixture.output(&clock).err().unwrap();
    assert!(error.contains("job finish precedes start"), "{error}");
    assert!(fixture.retire(now_ms).is_empty());
    fixture.assert_present(&initial);
    fs::write(fixture.root.join("start.txt"), "2026-10-10T12:00:00Z").unwrap();
    let output = fixture.output(&clock).unwrap();
    let reservation = fixture.session.host_reply_ids(clock.event_id);
    let mut invalid_output = output.clone();
    invalid_output.completion.event_id = probe.event_id;
    assert_eq!(
        fixture
            .session
            .handle_host(&clock, invalid_output, now_ms)
            .unwrap_err()
            .code,
        ProtocolFaultCode::Store
    );
    let mut invalid_output = output.clone();
    invalid_output.emitted_at = "invalid".to_owned();
    assert_eq!(
        fixture
            .session
            .handle_host(&clock, invalid_output, now_ms)
            .unwrap_err()
            .code,
        ProtocolFaultCode::State
    );
    assert_eq!(fixture.session.host_reply_ids(clock.event_id), reservation);
    assert_eq!(fixture.session.last_host_command_id(), Some(probe.event_id));
    assert!(fixture.retire(now_ms).is_empty());
    fixture.assert_present(&initial);

    let mut staged = fixture.session.clone();
    let replies = staged.handle_host(&clock, output.clone(), now_ms).unwrap();
    let mut conflict = replies[2].clone();
    conflict.emitted_at = "2026-10-10T14:00:01Z".to_owned();
    let conflict_path = fixture.files.path(conflict.event_id, "results").unwrap();
    fs::write(&conflict_path, canonical_json::row_line(&conflict).unwrap()).unwrap();
    assert!(
        fixture
            .admit_output(&clock, output.clone(), now_ms)
            .is_err()
    );
    assert_eq!(fixture.session.last_host_command_id(), Some(probe.event_id));
    assert_eq!(fixture.session.host_reply_ids(clock.event_id), reservation);
    assert!(fixture.retire(now_ms + retry).is_empty());
    fixture.assert_present(&initial);
    fs::remove_file(conflict_path).unwrap();
    let closed = fixture
        .admit_output(&clock, output, now_ms + retry)
        .unwrap();
    fixture.consume(&closed);
    assert_eq!(fixture.retire(now_ms + retry).len(), initial.len());
    fixture.assert_present(&closed);
}

#[test]
fn successor_and_stop_do_not_bypass_consumption_or_the_retry_window() {
    for cancel in [false, true] {
        let mut fixture = Fixture::new(if cancel { "cancel" } else { "stop" });
        let probe = fixture.command(EventKind::HostProbe, 1, None, "2026-10-10T12:00:00Z");
        let initial = fixture.admit(&probe, 0);
        fixture.consume(&initial[..3]);
        let retry = fixture.session.manifest.limits.retry_window_ms as u64;
        let clock = fixture.command(
            EventKind::HostClock,
            2,
            Some(initial[3].event_id),
            "2026-10-10T12:00:01Z",
        );
        assert!(fixture.retire(retry + 1).is_empty());
        let closed = fixture.admit(&clock, retry + 1);
        assert!(fixture.retire(retry + 1).is_empty());
        fixture.consume(&initial[3..]);
        let retired = fixture.retire(retry + 1);
        assert_eq!(retired.len(), initial.len());
        assert!(
            initial
                .iter()
                .all(|event| retired.contains(&event.event_id))
        );

        let stop_ms = 2 * retry;
        assert!(fixture.retire(stop_ms).is_empty());
        fixture.consume(&closed[..3]);
        let events = if cancel {
            fixture
                .session
                .cancelled(&clock.emitted_at, stop_ms)
                .unwrap()
        } else {
            let stop = resources::command(EventKind::MonitorStop, 0, 3);
            fixture.files.publish(&stop, "inbox").unwrap();
            fixture
                .session
                .handle(&stop, &resources::frames()[0], stop_ms)
                .unwrap()
        };
        fixture.files.publish_batch(&events, "results").unwrap();
        assert!(fixture.session.stopped);
        assert!(fixture.retire(stop_ms).is_empty());
        fixture.consume(&closed[3..]);
        assert!(fixture.retire(stop_ms).is_empty());
        let retired = fixture.retire(stop_ms + 1);
        assert_eq!(retired.len(), closed.len());
        assert!(closed.iter().all(|event| retired.contains(&event.event_id)));
    }
}
