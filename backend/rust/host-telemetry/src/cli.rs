//! Which validated host producer invocation do these command-line arguments select?

use crate::contracts::host::{Result, require};
use std::collections::BTreeMap;

pub fn run(mut arguments: impl Iterator<Item = String>) -> Result<()> {
    let verb = arguments
        .next()
        .ok_or("expected producer or monitor command")?;
    if matches!(
        verb.as_str(),
        "monitor" | "resource-replay" | "event-send" | "event-wait" | "monitor-cleanup"
    ) {
        let known = [
            "--workspace",
            "--manifest",
            "--config",
            "--snapshot",
            "--proc-root",
            "--cgroup-root",
            "--artifact-root",
            "--command",
            "--cpu-root",
            "--namespace-root",
            "--output-root",
            "--ledger-prefix",
            "--format",
            "--compression",
            "--cache-multiple",
            "--pid",
            "--start-ticks",
            "--memory-profiling",
        ];
        let mut args = BTreeMap::new();
        while let Some(key) = arguments.next() {
            require(known.contains(&key.as_str()), "unknown resource argument")?;
            let value = arguments.next().ok_or("argument lacks value")?;
            if key == "--memory-profiling" {
                crate::config::memory_profiling_override(Some(&value))?;
            }
            require(args.insert(key, value).is_none(), "duplicate argument")?;
        }
        return crate::monitor::runner::execute(&verb, args);
    }
    require(
        matches!(verb.as_str(), "probe" | "target" | "clock"),
        "unknown producer command",
    )?;
    let known = [
        "--workspace",
        "--manifest",
        "--command",
        "--config",
        "--snapshot",
        "--proc-root",
        "--cpu-root",
        "--namespace-root",
        "--previous-result",
        "--previous-plan",
        "--metadata-input",
        "--log-input",
        "--metrics-input",
        "--job-start-input",
        "--cache-multiple",
        "--format",
        "--compression",
        "--output-root",
        "--ledger-prefix",
        "--result-id",
        "--result-sequence",
        "--completion-id",
        "--captured-at",
        "--affinity-input",
        "--hierarchy-input",
        "--memory-profiling",
    ];
    let mut args = BTreeMap::new();
    while let Some(key) = arguments.next() {
        require(known.contains(&key.as_str()), "unknown argument")?;
        let value = arguments.next().ok_or("argument lacks value")?;
        if key == "--memory-profiling" {
            crate::config::memory_profiling_override(Some(&value))?;
        }
        require(args.insert(key, value).is_none(), "duplicate argument")?;
    }
    crate::invocation::execute(&verb, args)
}
