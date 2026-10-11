//! Do real exchange files enforce immutable IDs, bounds, consumption and finite ACK failure?
#[path = "support/resources.rs"]
mod resources;
use idhazh_host_telemetry::{
    contracts::events::*,
    monitor::session::Session,
    transport::{bounds::*, client::*, files::*},
};

#[test]
fn immutable_file_retry_conflict_order_and_foreign_session() {
    let root = resources::workspace("transport");
    let mut files = FileTransport::new(&root, resources::manifest()).unwrap();
    let command = resources::command(EventKind::WorkerRegister, 0, 1);
    let path = files.publish(&command, "inbox").unwrap();
    let original = std::fs::read(&path).unwrap();
    assert_eq!(files.publish(&command, "inbox").unwrap(), path);
    assert_eq!(files.read(command.event_id, "inbox").unwrap(), command);
    let mut conflicting = command.clone();
    conflicting.sequence = 2;
    assert!(files.publish(&conflicting, "inbox").is_err());
    assert_eq!(std::fs::read(&path).unwrap(), original);
    let mut session = Session::new(resources::manifest()).unwrap();
    session
        .ready(&resources::frames()[0].captured_at, 0)
        .unwrap();
    session
        .handle(&command, &resources::frames()[0], 1)
        .unwrap();
    let mut old = resources::command(EventKind::WorkerRegister, 1, 1);
    old.session_id = uuid::Uuid::nil();
    assert_eq!(
        session
            .handle(&old, &resources::frames()[0], 2)
            .unwrap_err()
            .code,
        ProtocolFaultCode::Identity
    );
}
#[test]
fn consumed_retry_window_retirement_and_total_history_are_bounded() {
    let m = resources::manifest();
    let mut book = EventBook::new(m.clone()).unwrap();
    let command = resources::command(EventKind::WorkerRegister, 0, 1);
    book.commit(command.clone(), Vec::new(), 0).unwrap();
    book.consume(command.event_id).unwrap();
    assert!(book.retire(1, &Default::default()).is_empty());
    assert_eq!(
        book.retire(5000, &Default::default()),
        vec![command.event_id]
    );
    assert_eq!(book.retained(), 0);
    assert_eq!(book.history_len(), 1);
    assert_eq!(
        book.check(&command, 5001).unwrap_err().code,
        ProtocolFaultCode::Retired
    );
    assert_eq!(book.total_events, 1);
}
#[test]
fn read_caps_directory_caps_and_malformed_published_json_fail() {
    let root = resources::workspace("transport-caps");
    let mut m = resources::manifest();
    m.limits.max_reads = 1;
    let mut files = FileTransport::new(&root, m).unwrap();
    let command = resources::command(EventKind::WorkerRegister, 0, 1);
    files.publish(&command, "inbox").unwrap();
    files.read(command.event_id, "inbox").unwrap();
    assert!(files.read(command.event_id, "inbox").is_err());
    assert!(decode_event(b"{}\r\n").is_err());
    assert!(decode_event(b"{}").is_err());
    assert!(read_bounded(&files.path(command.event_id, "inbox").unwrap(), 8).is_err());
}

#[test]
fn failed_reads_still_consume_the_cumulative_byte_allowance() {
    let root = resources::workspace("transport-failed-read");
    let mut m = resources::manifest();
    m.limits.max_read_bytes = m.limits.max_command_bytes;
    let cap = m.limits.max_command_bytes as usize;
    let mut files = FileTransport::new(&root, m).unwrap();
    let command = resources::command(EventKind::WorkerRegister, 0, 1);
    std::fs::write(
        files.path(command.event_id, "inbox").unwrap(),
        vec![b'x'; cap + 1],
    )
    .unwrap();
    assert!(files.read(command.event_id, "inbox").is_err());
    assert!(
        files
            .read(command.event_id, "inbox")
            .unwrap_err()
            .contains("cumulative read budget")
    );
}
#[test]
fn missing_ack_returns_explicit_unavailable_window_without_fallback() {
    let root = resources::workspace("transport-timeout");
    let mut m = resources::manifest();
    m.limits.ack_timeout_ms = 1;
    m.limits.poll_ms = 1;
    let mut files = FileTransport::new(&root, m).unwrap();
    let command = resources::command(EventKind::WindowBegin, 0, 2);
    let value = await_result(&mut files, Some(&command)).unwrap();
    let result: WindowResultBody = serde_json::from_value(value).unwrap();
    assert_eq!(result.status, WindowStatus::Incomplete);
    assert!(
        result
            .unavailable
            .iter()
            .all(|v| v.reason == UnavailableReason::TimedOut)
    );
    assert!(!root.join("fallback").exists());
}

#[test]
fn listed_result_retired_before_read_is_skipped_without_hiding_present_errors() {
    let root = resources::workspace("transport-retired-result-race");
    let m = resources::manifest();
    let retire_at = m.limits.retry_window_ms as u64;
    let frame = resources::frames().remove(0);
    let mut session = Session::new(m.clone()).unwrap();
    let old_result = session.ready(&frame.captured_at, 0).unwrap();
    let command = resources::command(EventKind::WorkerRegister, 0, 1);
    let reply = session.handle(&command, &frame, 0).unwrap().remove(0);
    let mut files = FileTransport::new(&root, m).unwrap();
    files.publish(&old_result, "results").unwrap();
    files.consume(&old_result).unwrap();
    session.book.consume(old_result.event_id).unwrap();

    assert!(files.ids("results").unwrap().contains(&old_result.event_id));
    let retired = session.retire(retire_at);
    assert!(retired.contains(&old_result.event_id));
    files.remove_retired(&retired).unwrap();
    assert_eq!(files.read_listed_result(old_result.event_id).unwrap(), None);
    assert!(files.read(old_result.event_id, "results").is_err());

    let malformed_id = uuid::Uuid::from_u128(42);
    std::fs::write(files.path(malformed_id, "results").unwrap(), b"{}\n").unwrap();
    assert!(files.read_listed_result(malformed_id).is_err());
    std::fs::remove_file(files.path(malformed_id, "results").unwrap()).unwrap();

    files.publish(&command, "inbox").unwrap();
    files.publish(&reply, "results").unwrap();
    let actual: HostEvent =
        serde_json::from_value(await_result(&mut files, Some(&command)).unwrap()).unwrap();
    assert_eq!(actual, reply);
}

#[test]
fn filenames_reject_noncanonical_ids_and_traversal() {
    let root = resources::workspace("transport-paths");
    let files = FileTransport::new(&root, resources::manifest()).unwrap();
    assert!(files.path(uuid::Uuid::nil(), "../outside").is_err());
    let inbox = files
        .path(uuid::Uuid::nil(), "inbox")
        .unwrap()
        .parent()
        .unwrap()
        .to_owned();
    std::fs::write(inbox.join("foreign.json"), b"{}\n").unwrap();
    assert!(files.ids("inbox").is_err());
}

#[test]
fn nested_duplicate_fields_and_foreign_ack_bodies_are_refused() {
    let command = resources::command(EventKind::WorkerRegister, 0, 1);
    let raw = serde_json::to_string(&command).unwrap().replace(
        "\"memory_profiling_enabled\":true",
        "\"memory_profiling_enabled\":true,\"memory_profiling_enabled\":true",
    );
    assert!(decode_event(format!("{raw}\n").as_bytes()).is_err());
    let root = resources::workspace("foreign-ack");
    let mut files = FileTransport::new(&root, resources::manifest()).unwrap();
    let mut foreign = command.clone();
    if let EventBody::Worker(body) = &mut foreign.body {
        body.target.start_ticks += 1;
    }
    assert!(files.publish(&foreign, "inbox").is_err());
}

#[test]
fn pending_exhaustion_preserves_room_for_fault_and_active_window_drain() {
    let root = resources::workspace("transport-drain");
    let m = resources::manifest();
    let frame = resources::frames().remove(0);
    let mut files = FileTransport::new(&root, m.clone()).unwrap();
    let mut session = Session::new(m.clone()).unwrap();
    let ready = session.ready(&frame.captured_at, 0).unwrap();
    files.publish(&ready, "results").unwrap();
    for kind in [EventKind::WorkerRegister, EventKind::WindowBegin] {
        let command = resources::command(
            kind,
            0,
            if kind == EventKind::WorkerRegister {
                1
            } else {
                2
            },
        );
        files.publish(&command, "inbox").unwrap();
        for event in session.handle(&command, &frame, 0).unwrap() {
            files.publish(&event, "results").unwrap();
        }
    }
    let (record, _) = idhazh_host_telemetry::producers::job_samples::sample(&frame, None, true)
        .unwrap()
        .unwrap();
    let error = loop {
        match session.observation(
            EventKind::JobSample,
            EventBody::Sample(JobSampleBody {
                record: record.clone(),
            }),
            &frame.captured_at,
            0,
        ) {
            Ok(event) => {
                files.publish(&event, "results").unwrap();
            }
            Err(error) => break error,
        }
    };
    assert!(error.contains("capacity"));
    let fault = session
        .protocol_fault(
            &refuse(ProtocolFaultCode::Bounds, &error),
            None,
            &frame.captured_at,
            0,
        )
        .unwrap();
    files.publish(&fault, "results").unwrap();
    files
        .publish_batch(
            &session.cancelled(&frame.captured_at, 0).unwrap(),
            "results",
        )
        .unwrap();
    assert!(session.stopped);
    assert_eq!(session.active_count(), 0);
    assert!(session.book.total_events <= m.limits.max_session_events as u64);
    assert!(session.book.retained() <= m.pending_event_limit().unwrap() as usize);
}

#[test]
fn paired_consumed_messages_retire_only_after_the_refreshed_retry_window() {
    let root = resources::workspace("transport-retire");
    let m = resources::manifest();
    let frame = resources::frames().remove(0);
    let mut files = FileTransport::new(&root, m.clone()).unwrap();
    let mut session = Session::new(m).unwrap();
    let command = resources::command(EventKind::WorkerRegister, 0, 1);
    files.publish(&command, "inbox").unwrap();
    let ack = session.handle(&command, &frame, 0).unwrap().remove(0);
    files.publish(&ack, "results").unwrap();
    for event in [&command, &ack] {
        files.consume(event).unwrap();
        session.book.consume(event.event_id).unwrap();
    }
    assert_eq!(
        session.handle(&command, &frame, 4999).unwrap(),
        vec![ack.clone()]
    );
    assert!(session.retire(5000).is_empty());
    let retired = session.retire(10000);
    assert_eq!(retired.len(), 2);
    files.remove_retired(&retired).unwrap();
    assert!(files.ids("inbox").unwrap().is_empty());
    assert!(files.ids("results").unwrap().is_empty());
    assert!(files.ids("consumed").unwrap().is_empty());
}

fn memory_off_session() -> HostSessionManifest {
    let mut m = resources::manifest();
    m.workers.truncate(1);
    m.windows.truncate(1);
    m.limits.max_concurrent_windows = 1;
    m.controls.memory_profiling_enabled = false;
    m
}

fn off_register() -> HostEvent {
    let mut command = resources::command(EventKind::WorkerRegister, 0, 1);
    if let EventBody::Worker(body) = &mut command.body {
        body.memory_profiling_enabled = false;
    }
    command
}

#[test]
fn consumption_preserves_complete_stop_without_retry_retirement_at_twelve_files() {
    let root = resources::workspace("consume-stop-reserve");
    let mut m = memory_off_session();
    m.limits.max_files = 12;
    let frame = resources::frames().remove(0);
    let mut files = FileTransport::new(&root, m.clone()).unwrap();
    let mut session = Session::new(m).unwrap();
    let ready = session.ready(&frame.captured_at, 0).unwrap();
    files.publish(&ready, "results").unwrap();
    files.consume(&ready).unwrap();
    let mut refused = Vec::new();
    for command in [
        off_register(),
        resources::command(EventKind::WindowBegin, 0, 2),
    ] {
        files.publish(&command, "inbox").unwrap();
        let ack = session.handle(&command, &frame, 0).unwrap().remove(0);
        files.publish(&ack, "results").unwrap();
        for event in [&ack, &command] {
            if let Err(error) = files.consume(event) {
                assert!(error.contains("capacity"));
                assert!(!files.path(event.event_id, "consumed").unwrap().exists());
                refused.push(event.event_id);
            } else {
                session.book.consume(event.event_id).unwrap();
            }
        }
    }
    assert!(
        !refused.is_empty(),
        "ordinary consumption spent the shutdown reserve"
    );
    assert!(session.retire(0).is_empty());
    let stop = resources::command(EventKind::MonitorStop, 0, 99);
    files.publish(&stop, "inbox").unwrap();
    let replies = session.handle(&stop, &frame, 0).unwrap();
    files.publish_batch(&replies, "results").unwrap();
    let stopped = files
        .read(replies.last().unwrap().event_id, "results")
        .unwrap();
    let EventBody::Stopped(body) = stopped.body else {
        panic!()
    };
    assert!(body.drained);
    assert_eq!(
        body.aborted_window_ids,
        vec![resources::window(0).window_id]
    );
    assert!(session.stopped);
    assert!(
        files.ids("inbox").unwrap().len()
            + files.ids("results").unwrap().len()
            + files.ids("consumed").unwrap().len()
            <= 12
    );
}

#[test]
fn physical_consumption_bytes_preserve_shutdown_and_immutable_retries() {
    let root = resources::workspace("consume-byte-reserve");
    let mut m = memory_off_session();
    m.limits.max_command_bytes = 4096;
    m.limits.max_result_bytes = 4096;
    let frame = resources::frames().remove(0);
    let mut session = Session::new(m.clone()).unwrap();
    let ready = session.ready(&frame.captured_at, 0).unwrap();
    let register = off_register();
    let ack = session.handle(&register, &frame, 0).unwrap().remove(0);
    let begin = resources::command(EventKind::WindowBegin, 0, 2);
    let begun = session.handle(&begin, &frame, 0).unwrap().remove(0);
    let stored = [
        &ready, &ready, &register, &register, &ack, &ack, &begin, &begun,
    ]
    .into_iter()
    .map(|v| {
        idhazh_host_telemetry::canonical_json::row_line(v)
            .unwrap()
            .len() as i64
    })
    .sum::<i64>();
    m.limits.max_session_bytes = stored + 4 * 4096;
    let mut files = FileTransport::new(&root, m).unwrap();
    files.publish(&ready, "results").unwrap();
    files.consume(&ready).unwrap();
    files.publish(&register, "inbox").unwrap();
    files.publish(&ack, "results").unwrap();
    files.consume(&register).unwrap();
    files.consume(&ack).unwrap();
    files.publish(&begin, "inbox").unwrap();
    files.publish(&begun, "results").unwrap();
    assert!(files.consume(&begun).unwrap_err().contains("capacity"));
    let path = files.path(ack.event_id, "consumed").unwrap();
    let original = std::fs::read(&path).unwrap();
    files.consume(&ack).unwrap();
    files.publish(&ack, "results").unwrap();
    let mut conflict = ack.clone();
    conflict.emitted_at = "2026-10-10T12:00:01Z".to_owned();
    assert!(files.consume(&conflict).is_err());
    assert_eq!(std::fs::read(&path).unwrap(), original);
    let stop = resources::command(EventKind::MonitorStop, 0, 99);
    files.publish(&stop, "inbox").unwrap();
    files
        .publish_batch(&session.handle(&stop, &frame, 0).unwrap(), "results")
        .unwrap();
    assert!(session.stopped);
}

#[test]
fn normal_close_cannot_spend_future_fault_and_stopped_book_capacity() {
    for kind in [EventKind::WindowEnd, EventKind::WindowAbort] {
        let mut m = memory_off_session();
        m.limits.max_session_events = 9;
        let frame = resources::frames().remove(0);
        let mut session = Session::new(m).unwrap();
        session.ready(&frame.captured_at, 0).unwrap();
        session.handle(&off_register(), &frame, 0).unwrap();
        session
            .handle(&resources::command(EventKind::WindowBegin, 0, 2), &frame, 0)
            .unwrap();
        let close = resources::command(kind, 0, 3);
        assert_eq!(
            session.handle(&close, &frame, 0).unwrap_err().code,
            ProtocolFaultCode::Bounds
        );
        assert_eq!(session.active_count(), 1);
        session
            .protocol_fault(
                &refuse(ProtocolFaultCode::Bounds, "full"),
                Some(close.event_id),
                &frame.captured_at,
                0,
            )
            .unwrap();
        let drain = session.cancelled(&frame.captured_at, 0).unwrap();
        assert_eq!(drain.last().unwrap().kind, EventKind::MonitorStopped);
        assert!(session.book.total_events <= 9);
    }
}

#[test]
fn global_faults_reach_readiness_and_command_waits_before_sorted_success() {
    let mut failures = Vec::new();
    for (name, selected) in [
        ("ready", None),
        ("register", Some(EventKind::WorkerRegister)),
        ("end", Some(EventKind::WindowEnd)),
    ] {
        for success in [false, true] {
            let root = resources::workspace(&format!("global-fault-{name}-{success}"));
            let mut m = resources::manifest();
            m.limits.ack_timeout_ms = 1;
            m.limits.readiness_timeout_ms = 1;
            m.limits.poll_ms = 1;
            let frame = resources::frames().remove(0);
            let mut session = Session::new(m.clone()).unwrap();
            let ready = session.ready(&frame.captured_at, 0).unwrap();
            let register = resources::command(EventKind::WorkerRegister, 0, 1);
            let ack = session.handle(&register, &frame, 0).unwrap().remove(0);
            session
                .handle(&resources::command(EventKind::WindowBegin, 0, 2), &frame, 0)
                .unwrap();
            let end = resources::command(EventKind::WindowEnd, 0, 3);
            let result = session.handle(&end, &frame, 0).unwrap().remove(0);
            let command = selected.map(|kind| {
                if kind == EventKind::WorkerRegister {
                    &register
                } else {
                    &end
                }
            });
            let mut files = FileTransport::new(&root, m).unwrap();
            if success {
                let mut event = match selected {
                    None => ready.clone(),
                    Some(EventKind::WorkerRegister) => ack.clone(),
                    _ => result.clone(),
                };
                event.event_id = uuid::Uuid::from_u128(1);
                files.publish(&event, "results").unwrap();
                if let Some(command) = command {
                    files.publish(command, "inbox").unwrap();
                }
            }
            let mut fault = session
                .protocol_fault(
                    &refuse(ProtocolFaultCode::Target, "reused"),
                    None,
                    &frame.captured_at,
                    0,
                )
                .unwrap();
            fault.event_id = uuid::Uuid::from_u128(u128::MAX);
            files.publish(&fault, "results").unwrap();
            let result = await_result(&mut files, command);
            if !result
                .as_ref()
                .is_err_and(|error| error.contains("protocol fault: Target"))
            {
                failures.push(format!("{name}/{success}: {result:?}"));
            }
        }
    }
    assert!(failures.is_empty(), "{}", failures.join("\n"));
}

#[test]
fn unrelated_recoverable_fault_does_not_replace_selected_command_evidence() {
    let root = resources::workspace("unrelated-command-fault");
    let m = resources::manifest();
    let frame = resources::frames().remove(0);
    let mut session = Session::new(m.clone()).unwrap();
    let register = resources::command(EventKind::WorkerRegister, 0, 1);
    let ack = session.handle(&register, &frame, 0).unwrap().remove(0);
    let mut fault = session
        .protocol_fault(
            &refuse(ProtocolFaultCode::State, "unrelated"),
            Some(uuid::Uuid::from_u128(42)),
            &frame.captured_at,
            0,
        )
        .unwrap();
    fault.event_id = uuid::Uuid::from_u128(1);
    let mut files = FileTransport::new(&root, m).unwrap();
    files.publish(&register, "inbox").unwrap();
    files.publish(&fault, "results").unwrap();
    files.publish(&ack, "results").unwrap();
    let actual: HostEvent =
        serde_json::from_value(await_result(&mut files, Some(&register)).unwrap()).unwrap();
    assert_eq!(actual, ack);
}

#[test]
fn selected_fault_remains_explicit_and_success_cannot_bypass_scan_read_limits() {
    for exhausted in [false, true] {
        let root = resources::workspace(&format!("fault-scan-budget-{exhausted}"));
        let mut m = resources::manifest();
        if exhausted {
            m.limits.max_reads = 1;
        }
        let frame = resources::frames().remove(0);
        let mut session = Session::new(m.clone()).unwrap();
        let command = resources::command(EventKind::WorkerRegister, 0, 1);
        let mut ack = session.handle(&command, &frame, 0).unwrap().remove(0);
        ack.event_id = uuid::Uuid::from_u128(1);
        let mut fault = session
            .protocol_fault(
                &refuse(ProtocolFaultCode::State, "selected"),
                Some(command.event_id),
                &frame.captured_at,
                0,
            )
            .unwrap();
        fault.event_id = uuid::Uuid::from_u128(u128::MAX);
        let mut files = FileTransport::new(&root, m).unwrap();
        files.publish(&ack, "results").unwrap();
        files.publish(&fault, "results").unwrap();
        let error = await_result(&mut files, Some(&command)).unwrap_err();
        assert!(error.contains(if exhausted {
            "cumulative read budget"
        } else {
            "protocol fault: State"
        }));
        assert!(files.ids("consumed").unwrap().is_empty());
    }
}

#[test]
fn whole_shutdown_preflight_preserves_files_on_capacity_or_conflict_failure() {
    for conflict in [false, true] {
        let root = resources::workspace(&format!("shutdown-preflight-{conflict}"));
        let mut m = memory_off_session();
        let frame = resources::frames().remove(0);
        let mut session = Session::new(m.clone()).unwrap();
        session.ready(&frame.captured_at, 0).unwrap();
        session.handle(&off_register(), &frame, 0).unwrap();
        session
            .handle(&resources::command(EventKind::WindowBegin, 0, 2), &frame, 0)
            .unwrap();
        let replies = session
            .handle(
                &resources::command(EventKind::MonitorStop, 0, 99),
                &frame,
                0,
            )
            .unwrap();
        if !conflict {
            m.limits.max_files = 1;
        }

        let mut files = FileTransport::new(&root, m).unwrap();
        if conflict {
            let mut existing = replies.last().unwrap().clone();
            existing.emitted_at = "2026-10-10T12:00:01Z".to_owned();
            std::fs::write(
                files.path(existing.event_id, "results").unwrap(),
                idhazh_host_telemetry::canonical_json::row_line(&existing).unwrap(),
            )
            .unwrap();
        }
        assert!(files.publish_batch(&replies, "results").is_err());
        assert!(!files.path(replies[0].event_id, "results").unwrap().exists());
        assert_eq!(files.total_events, 0);
        assert_eq!(files.ids("results").unwrap().len(), usize::from(conflict));
    }
}

#[test]
fn begin_refuses_a_result_cap_that_cannot_hold_its_future_aborted_window() {
    let mut m = memory_off_session();
    let frame = resources::frames().remove(0);
    let mut sizing = Session::new(m.clone()).unwrap();
    sizing.ready(&frame.captured_at, 0).unwrap();
    sizing.handle(&off_register(), &frame, 0).unwrap();
    let begin = resources::command(EventKind::WindowBegin, 0, 2);
    let ack = sizing.handle(&begin, &frame, 0).unwrap().remove(0);
    m.limits.max_result_bytes = idhazh_host_telemetry::canonical_json::row_line(&ack)
        .unwrap()
        .len() as i64;
    let mut session = Session::new(m).unwrap();
    session.ready(&frame.captured_at, 0).unwrap();
    session.handle(&off_register(), &frame, 0).unwrap();
    let retained = session.book.retained();
    let error = session.handle(&begin, &frame, 0).unwrap_err();
    assert_eq!(error.code, ProtocolFaultCode::Bounds);
    assert!(error.message.contains("shutdown result size"));
    assert_eq!(session.active_count(), 0);
    assert_eq!(session.book.retained(), retained);
    let stopped = session.cancelled(&frame.captured_at, 0).unwrap();
    assert_eq!(stopped.len(), 1);
    assert_eq!(stopped[0].kind, EventKind::MonitorStopped);
}
