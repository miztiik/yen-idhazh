//! What rate does an observable cache-aware two-buffer copy measure?

use crate::contracts::host::{Result, require};
use std::hint::black_box;
use std::time::Instant;

const MIB: i64 = 1024 * 1024;
const GIB: f64 = 1024.0 * 1024.0 * 1024.0;
pub fn buffer_mib(floor: i64, cache: Option<i64>, multiple: i64) -> Result<i64> {
    require(
        floor >= 0 && multiple > 0,
        "invalid bandwidth sizing controls",
    )?;
    if floor == 0 {
        return Ok(0);
    }
    let Some(cache) = cache.filter(|v| *v > 0) else {
        return Ok(floor);
    };
    let rounded = cache.checked_add(MIB - 1).ok_or("cache size overflow")? / MIB;
    Ok(floor.max(rounded.checked_mul(multiple).ok_or("copy size overflow")?))
}
pub fn measure(mib: i64, passes: i64) -> Result<Option<f64>> {
    require(mib >= 0 && passes > 0, "invalid copy controls")?;
    if mib == 0 {
        return Ok(None);
    }
    let size = usize::try_from(mib.checked_mul(MIB).ok_or("copy byte size overflow")?)
        .map_err(|e| e.to_string())?;
    let mut source = Vec::new();
    let mut destination = Vec::new();
    if source.try_reserve_exact(size).is_err() || destination.try_reserve_exact(size).is_err() {
        return Ok(None);
    }
    source.resize(size, 0x5au8);
    destination.resize(size, 0u8);
    let mut rates = Vec::new();
    rates
        .try_reserve_exact(usize::try_from(passes).map_err(|e| e.to_string())?)
        .map_err(|e| e.to_string())?;
    for pass in 0..passes {
        source[0] = pass as u8;
        let start = Instant::now();
        black_box(&mut destination).copy_from_slice(black_box(&source));
        let seconds = start.elapsed().as_secs_f64();
        // The timed destination escapes to black_box and its bytes are checked outside timing.
        let checksum = black_box(&destination)
            .iter()
            .fold(0u64, |sum, v| sum.wrapping_add(*v as u64));
        require(
            checksum == (size as u64 - 1) * 0x5a + pass as u8 as u64,
            "copy checksum mismatch",
        )?;
        let rate = (2.0 * size as f64 / GIB) / seconds;
        if seconds > 0.0 && rate.is_finite() && rate > 0.0 {
            rates.push(rate);
        }
    }
    rates.sort_by(f64::total_cmp);
    Ok(if rates.is_empty() {
        None
    } else if rates.len() % 2 == 0 {
        Some(rates[rates.len() / 2 - 1] / 2.0 + rates[rates.len() / 2] / 2.0)
    } else {
        Some(rates[rates.len() / 2])
    })
}
