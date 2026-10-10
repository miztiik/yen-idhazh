//! Which validated host producer invocation do these command-line arguments select?

use crate::contracts::host::{Result, require};
use std::collections::BTreeMap;

pub fn run(mut arguments: impl Iterator<Item = String>) -> Result<()> {
    let verb = arguments.next().ok_or("expected probe, target or clock")?;
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
        "--result-id",
        "--captured-at",
        "--affinity-input",
    ];
    let mut args = BTreeMap::new();
    while let Some(key) = arguments.next() {
        require(known.contains(&key.as_str()), "unknown argument")?;
        let value = arguments.next().ok_or("argument lacks value")?;
        require(args.insert(key, value).is_none(), "duplicate argument")?;
    }
    crate::invocation::execute(&verb, args)
}
