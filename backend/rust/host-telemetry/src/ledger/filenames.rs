//! Which UUIDs name a logical host work unit and one clock-addressed file?

use crate::contracts::host::{
    HOST_PRODUCER, Result, ServerJob, day, job_text, nonnegative, positive, require,
    run_id as validate_run_id,
};
use sha2::{Digest, Sha256};
use uuid::{Uuid, Variant};

pub fn unit_id(covers: &str, run_id: &str, job: ServerJob, shard: i64) -> Result<Uuid> {
    day(covers)?;
    validate_run_id(run_id)?;
    day(run_id.get(..10).ok_or("invalid run_id day")?)?;
    nonnegative(shard)?;
    // This namespace is a protocol constant: changing it breaks retry settlement.
    let namespace = Uuid::new_v5(&Uuid::NAMESPACE_URL, b"github.com/miztiik/yen-idhazh");
    Ok(Uuid::new_v5(
        &namespace,
        format!(
            "host-fingerprint|{covers}|{run_id}|{}|{shard}|{HOST_PRODUCER}",
            job_text(job)
        )
        .as_bytes(),
    ))
}

/// The caller supplies the actual epoch millisecond; no payload enters the seed.
pub fn file_id(unit: Uuid, attempt: i64, written_at_ms: i64) -> Result<Uuid> {
    require(
        unit.get_version_num() == 5 && unit.get_variant() == Variant::RFC4122,
        "unit must be RFC UUID5",
    )?;
    positive(attempt)?;
    nonnegative(written_at_ms)?;
    let digest = Sha256::digest(format!("{unit}|{attempt}|{written_at_ms}").as_bytes());
    let rand_a = u16::from_be_bytes([digest[0], digest[1]]) & ((1 << 12) - 1);
    let rand_b =
        u64::from_be_bytes(digest[2..10].try_into().map_err(|_| "digest width")?) & ((1 << 62) - 1);
    Ok(Uuid::from_u128(
        ((written_at_ms as u128 & ((1 << 48) - 1)) << 80)
            | (8 << 76)
            | ((rand_a as u128) << 64)
            | (2 << 62)
            | rand_b as u128,
    ))
}
