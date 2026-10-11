//! What CPU, load and memory figures did this machine report at one instant?

use crate::Result;
use crate::contracts::events::UnavailableReason;
use crate::probe_inputs::files::{Reading, SourceRoot};
use crate::sampling::process::bytes;
use std::path::Path;

#[derive(Debug, Clone, PartialEq)]
pub struct CpuTicks(pub Vec<i64>);
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CpuShares {
    pub busy: f64,
    pub steal: Option<f64>,
}

pub fn cpu_ticks(text: &Reading<String>) -> Reading<CpuTicks> {
    let text = match text.get() {
        Ok(v) => v,
        Err(e) => return Reading::absent(e),
    };
    for line in text.lines() {
        let mut fields = line.split_whitespace();
        if fields.next() != Some("cpu") {
            continue;
        }
        let mut ticks = Vec::new();
        for value in fields.take(10) {
            if !value.bytes().all(|v| v.is_ascii_digit()) {
                return Reading::absent(UnavailableReason::Malformed);
            }
            let Ok(value) = value.parse::<i64>() else {
                return Reading::absent(UnavailableReason::Malformed);
            };
            ticks.push(value);
        }
        return if ticks.is_empty() {
            Reading::absent(UnavailableReason::Malformed)
        } else {
            Reading::found(CpuTicks(ticks))
        };
    }
    Reading::absent(UnavailableReason::Malformed)
}

pub fn shares(first: &Reading<CpuTicks>, last: &Reading<CpuTicks>) -> Reading<CpuShares> {
    let a = match first.get() {
        Ok(v) => &v.0,
        Err(e) => return Reading::absent(e),
    };
    let b = match last.get() {
        Ok(v) => &v.0,
        Err(e) => return Reading::absent(e),
    };
    let total = |v: &[i64]| v.iter().take(8).map(|v| i128::from(*v)).sum::<i128>();
    let get = |v: &[i64], i| i128::from(v.get(i).copied().unwrap_or(0));
    let available = total(b) - total(a);
    if available <= 0 {
        return Reading::absent(UnavailableReason::SnapshotChanged);
    }
    let stolen = get(b, 7) - get(a, 7);
    let idle = get(b, 3) + get(b, 4) - get(a, 3) - get(a, 4);
    let round = |v: i128| round_percentage((100 * v) as f64 / available as f64);
    let busy = round(available - idle - stolen);
    let steal = (a.len() > 7 && b.len() > 7).then(|| round(stolen));
    if !(0.0..=100.0).contains(&busy) || steal.is_some_and(|v| !(0.0..=100.0).contains(&v)) {
        return Reading::absent(UnavailableReason::SnapshotChanged);
    }
    Reading::found(CpuShares { busy, steal })
}

fn round_percentage(value: f64) -> f64 {
    // Multiplying a binary float by 100 before rounding changes decimal-half cases.
    // Round the exact binary significand instead, as Python round(value, 2) does.
    let bits = value.abs().to_bits();
    let exponent = ((bits >> 52) & 0x7ff) as i32 - 1023 - 52;
    let numerator = u128::from((bits & ((1_u64 << 52) - 1)) | (1_u64 << 52)) * 100;
    let rounded = if exponent >= 0 {
        numerator.checked_shl(exponent as u32).unwrap_or(u128::MAX)
    } else if -exponent >= 128 {
        0
    } else {
        let denominator = 1_u128 << -exponent;
        let whole = numerator / denominator;
        let remainder = numerator % denominator;
        whole
            + u128::from(
                remainder > denominator / 2 || (remainder == denominator / 2 && whole % 2 == 1),
            )
    };
    (rounded as f64 / 100.0).copysign(value)
}

pub fn load(text: &Reading<String>) -> Reading<f64> {
    let text = match text.get() {
        Ok(v) => v,
        Err(e) => return Reading::absent(e),
    };
    text.split_whitespace()
        .next()
        .and_then(|v| v.parse::<f64>().ok())
        .filter(|v| v.is_finite() && *v >= 0.0)
        .map_or_else(
            || Reading::absent(UnavailableReason::Malformed),
            Reading::found,
        )
}

#[derive(Debug, Clone, PartialEq)]
pub struct MachineReading {
    pub cpu: Reading<CpuTicks>,
    pub load: Reading<f64>,
    pub available: Reading<i64>,
    pub total: Reading<i64>,
    pub cached: Reading<i64>,
    pub swap_free: Reading<i64>,
    pub swap_total: Reading<i64>,
}
pub fn reduce(
    stat: &Reading<String>,
    loadavg: &Reading<String>,
    meminfo: &Reading<String>,
    memory: bool,
) -> MachineReading {
    let mem = |key| {
        if memory {
            bytes(meminfo, key)
        } else {
            Reading::absent(UnavailableReason::Disabled)
        }
    };
    MachineReading {
        cpu: cpu_ticks(stat),
        load: load(loadavg),
        available: mem("MemAvailable"),
        total: mem("MemTotal"),
        cached: mem("Cached"),
        swap_free: mem("SwapFree"),
        swap_total: mem("SwapTotal"),
    }
}
pub struct MachineSampler {
    source: SourceRoot,
}
impl MachineSampler {
    pub fn new(proc_root: &Path, maximum: usize) -> Result<Self> {
        Ok(Self {
            source: SourceRoot::new(proc_root, maximum)?,
        })
    }
    pub fn texts(&self, memory: bool) -> (Reading<String>, Reading<String>, Reading<String>) {
        (
            self.source.text("stat"),
            self.source.text("loadavg"),
            if memory {
                self.source.text("meminfo")
            } else {
                Reading::absent(UnavailableReason::Disabled)
            },
        )
    }
    pub fn sample(&self, memory: bool) -> MachineReading {
        let (stat, load, mem) = self.texts(memory);
        reduce(&stat, &load, &mem, memory)
    }
}
