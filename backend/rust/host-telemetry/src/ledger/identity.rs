//! Which ranked identity belongs to a host row, and which attempts survive?

use super::filenames;
use crate::canonical_json::rows_bytes;
use crate::contracts::file_envelope::HostWriterIdentity;
use crate::contracts::host::{
    CorrectedHostFingerprintRow, HOST_PRODUCER, HostStoredRow, Result, Validate, job_text, require,
};
use std::collections::{BTreeMap, btree_map::Entry};

pub fn stamp(
    row: &CorrectedHostFingerprintRow,
    identity: &HostWriterIdentity,
) -> Result<HostStoredRow> {
    row.validate()?;
    identity.validate()?;
    require(
        identity.producer == HOST_PRODUCER,
        "host writer must use logical telemetry.silicon producer",
    )?;
    require(
        row.run_id == identity.run_id && row.job == identity.job && row.shard == identity.shard,
        "host row belongs to another run/job/shard",
    )?;
    let stored = HostStoredRow {
        host: row.clone(),
        ledger: "host-fingerprint".to_owned(),
        covers: row.date.clone(),
        attempt: identity.attempt,
        unit_id: filenames::unit_id(&row.date, &row.run_id, row.job, row.shard)?,
    };
    stored.validate()?;
    Ok(stored)
}

/// Preserve a previously ranked row, or refuse it rather than restamping it.
pub fn preserve(row: &HostStoredRow, identity: &HostWriterIdentity) -> Result<HostStoredRow> {
    row.validate()?;
    let expected = stamp(&row.host, identity)?;
    require(
        row.ledger == expected.ledger
            && row.covers == expected.covers
            && row.attempt == expected.attempt
            && row.unit_id == expected.unit_id,
        "stored host rank contradicts writer identity",
    )?;
    Ok(row.clone())
}

/// Keep the highest attempt per unit, ordered by day, run, job and shard.
///
/// Rows have no file clock. Unequal rows at the same rank cannot be ordered
/// honestly here, so they are refused, even if a higher attempt is present.
pub fn settle(rows: &[HostStoredRow]) -> Result<Vec<HostStoredRow>> {
    let mut ranked: BTreeMap<(uuid::Uuid, i64), (&HostStoredRow, Vec<u8>)> = BTreeMap::new();
    for row in rows {
        row.validate()?;
        require(
            row.unit_id
                == filenames::unit_id(&row.covers, &row.host.run_id, row.host.job, row.host.shard)?,
            "stored host unit contradicts its seed",
        )?;
        let key = (row.unit_id, row.attempt);
        let bytes = rows_bytes(std::slice::from_ref(row))?;
        match ranked.entry(key) {
            Entry::Occupied(previous) => {
                require(
                    previous.get().1 == bytes,
                    "conflicting host rows at equal unit/attempt rank require file clocks",
                )?;
            }
            Entry::Vacant(entry) => {
                entry.insert((row, bytes));
            }
        }
    }
    let mut current = BTreeMap::new();
    for ((unit, _), (row, _)) in ranked {
        current.insert(unit, row.clone());
    }
    let mut result: Vec<HostStoredRow> = current.into_values().collect();
    result.sort_by_key(|row| {
        (
            row.covers.clone(),
            row.host.run_id.clone(),
            job_text(row.host.job),
            row.host.shard,
            row.unit_id,
        )
    });
    Ok(result)
}
