//! Which four job-end clock cells enrich the retained probe without new CPU reads?

use crate::contracts::events::{EventKind, HostEvent, HostResultBody, HostSessionManifest};
use crate::contracts::host::{Result, Validate, require, timestamp};
use crate::contracts::write_plan::HostWritePlan;
use crate::producers::job_probe::prior_matches;
use chrono::NaiveDateTime;
use regex::Regex;
use std::sync::OnceLock;
use uuid::Uuid;

pub fn model_load_ms(text: &str) -> Option<f64> {
    static STAMP: OnceLock<Regex> = OnceLock::new();
    let stamp = STAMP
        .get_or_init(|| Regex::new(r"^(\d+)\.(\d{2})\.(\d{3})\.(\d{3}) ").expect("wire stamp"));
    let mut start = None;
    for line in text.lines() {
        let Some(cells) = stamp.captures(line) else {
            continue;
        };
        let number = |i| cells.get(i)?.as_str().parse::<u64>().ok();
        let minutes = number(1)?;
        let seconds = number(2)?;
        if seconds >= 60 {
            return None;
        };
        let micros = minutes
            .checked_mul(60_000_000)?
            .checked_add(seconds.checked_mul(1_000_000)?)?
            .checked_add(number(3)?.checked_mul(1000)?)?
            .checked_add(number(4)?)?;
        if line.contains("load_model: loading model") && start.is_none() {
            start = Some(micros);
        }
        if line.contains("llama_server: model loaded") {
            return micros.checked_sub(start?).map(|v| v as f64 / 1000.0);
        }
    }
    None
}
pub fn prompt_totals(text: &str) -> Result<(Option<i64>, Option<f64>)> {
    let mut tokens = None;
    let mut seconds = None;
    for line in text.lines().map(str::trim).filter(|v| !v.starts_with('#')) {
        let fields: Vec<_> = line.split_whitespace().collect();
        if fields.len() < 2 {
            continue;
        };
        if !matches!(
            fields[0],
            "llamacpp:prompt_tokens_total" | "llamacpp:prompt_seconds_total"
        ) {
            continue;
        };
        let value: f64 = fields[1].parse().map_err(|_| "malformed prompt counter")?;
        require(
            value.is_finite() && value >= 0.0,
            "nonfinite or negative prompt counter",
        )?;
        if fields[0] == "llamacpp:prompt_tokens_total" {
            require(
                value.fract() == 0.0 && value < 9223372036854775808.0,
                "prompt token count is not a whole int64",
            )?;
            require(tokens.is_none(), "duplicate prompt counter")?;
            tokens = Some(value as i64);
        } else {
            require(seconds.is_none(), "duplicate prompt counter")?;
            seconds = Some(value);
        }
    }
    Ok((tokens, seconds))
}
pub fn elapsed(start: Option<&str>, finish: &str) -> Result<Option<i64>> {
    timestamp(finish)?;
    let Some(start) = start else { return Ok(None) };
    timestamp(start)?;
    let parse =
        |v| NaiveDateTime::parse_from_str(v, "%Y-%m-%dT%H:%M:%SZ").map_err(|e| e.to_string());
    let seconds = (parse(finish)? - parse(start)?).num_seconds();
    require(seconds >= 0, "job finish precedes start")?;
    Ok(Some(seconds))
}
pub struct ClockInputs<'a> {
    pub start: Option<&'a str>,
    pub finish: &'a str,
    pub log: Option<&'a str>,
    pub metrics: Option<&'a str>,
}
pub fn enrich(
    manifest: &HostSessionManifest,
    event: &HostEvent,
    previous_id: Uuid,
    previous: &HostResultBody,
    plan: &HostWritePlan,
    inputs: ClockInputs<'_>,
) -> Result<HostResultBody> {
    prior_matches(manifest, event, previous_id, previous, plan)?;
    require(event.kind == EventKind::HostClock, "not a clock command")?;
    let mut result = previous.clone();
    result.row.model_load_ms = inputs.log.and_then(model_load_ms);
    result.row.job_seconds = elapsed(inputs.start, inputs.finish)?;
    (
        result.row.server_prompt_tokens,
        result.row.server_prompt_seconds,
    ) = match inputs.metrics {
        Some(v) => prompt_totals(v)?,
        None => (None, None),
    };
    result.completion_event_ids = vec![event.event_id];
    result.validate()?;
    Ok(result)
}
