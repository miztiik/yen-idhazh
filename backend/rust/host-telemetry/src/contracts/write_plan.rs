//! Which immutable files and completed-byte evidence belong to one invocation?

use super::events::default_version;
use super::file_envelope::*;
use super::host::*;
use crate::canonical_json::{rows_bytes, sha256};
use std::collections::{BTreeMap, HashSet};
use uuid::Uuid;

contract!(HostPlannedFile {envelope:CandidateFileEnvelope,format:Format,relative_path:String,rows:Vec<HostStoredRow>});
impl Validate for HostPlannedFile {
    fn validate(&self) -> Result<()> {
        self.envelope.validate_container(self.format)?;
        rel_path(&self.relative_path)?;
        let env = &self.envelope;
        require(
            env.ledger == "host-fingerprint"
                && env.tier == Tier::Raw
                && env.version == VERSION
                && env.row_schema_version == VERSION
                && env.identity.producer == HOST_PRODUCER,
            "plan must be corrected logical host raw",
        )?;
        require(
            env.unit_id
                == host_unit_id(
                    &env.covers,
                    &env.identity.run_id,
                    env.identity.job,
                    env.identity.shard,
                )?,
            "planned unit seed mismatch",
        )?;
        require(
            env.file_id == host_file_id(env.unit_id, env.identity.attempt, env.written_at_ms)?,
            "planned file clock seed mismatch",
        )?;
        require(self.rows.len() == 1, "host plan requires one whole row")?;
        for row in &self.rows {
            row.validate()?;
            require(
                row.covers == env.covers
                    && row.host.run_id == env.identity.run_id
                    && row.attempt == env.identity.attempt
                    && row.host.job == env.identity.job
                    && row.host.shard == env.identity.shard
                    && row.unit_id == env.unit_id,
                "row/envelope identity mismatch",
            )?;
        }
        require(
            sha256(&rows_bytes(&self.rows)?) == env.content_sha256,
            "planned canonical hash mismatch",
        )
    }
}
fn default_prefix() -> Vec<String> {
    vec!["host-fingerprint".to_owned()]
}
contract!(HostWritePlan {
    #[serde(default="default_version")] version:String,event_id:Uuid,target_root:String,
    publication_identity:HostWriterIdentity,#[serde(default="default_prefix")] prefix:Vec<String>,
    files:Vec<HostPlannedFile>,
});
impl Validate for HostWritePlan {
    fn validate(&self) -> Result<()> {
        require(self.version == VERSION, "unknown plan version")?;
        rel_path(&self.target_root)?;
        self.publication_identity.validate()?;
        require(
            self.prefix.last().is_some_and(|v| v == "host-fingerprint"),
            "host prefix must end in host-fingerprint",
        )?;
        for v in &self.prefix {
            rel_path(v)?;
            require(!v.contains('/'), "prefix contains paths, not segments")?;
        }
        require(!self.files.is_empty(), "empty write plan")?;
        let mut paths = HashSet::new();
        let mut days = HashSet::new();
        for file in &self.files {
            file.validate()?;
            let env = &file.envelope;
            let a = &env.identity;
            let b = &self.publication_identity;
            require(
                a.run_id == b.run_id
                    && a.attempt == b.attempt
                    && a.job == b.job
                    && a.shard == b.shard
                    && a.git_sha == b.git_sha,
                "file belongs to foreign invocation",
            )?;
            day(&env.covers)?;
            let suffix = if file.format == Format::Parquet {
                "parquet"
            } else {
                "json"
            };
            let expected = format!(
                "raw/{}/{}/{}.{}",
                self.prefix.join("/"),
                env.covers.replace('-', "/"),
                env.file_id,
                suffix
            );
            require(
                file.relative_path == expected,
                "planned path contradicts raw grammar",
            )?;
            require(
                paths.insert(&file.relative_path) && days.insert(&env.covers),
                "duplicate path/day group",
            )?;
        }
        Ok(())
    }
}
impl HostWritePlan {
    pub fn validate_successor(&self, previous: &Self) -> Result<()> {
        self.validate()?;
        previous.validate()?;
        require(
            self.target_root == previous.target_root
                && self.prefix == previous.prefix
                && self.publication_identity == previous.publication_identity,
            "successor changes root/invocation",
        )?;
        let prior = previous
            .files
            .iter()
            .map(|f| (f.envelope.unit_id, f))
            .collect::<BTreeMap<_, _>>();
        require(
            prior.keys().copied().collect::<HashSet<_>>()
                == self
                    .files
                    .iter()
                    .map(|f| f.envelope.unit_id)
                    .collect::<HashSet<_>>(),
            "successor changes work units",
        )?;
        let unchanged = self.files.iter().all(|f| {
            f.envelope.content_sha256 == prior[&f.envelope.unit_id].envelope.content_sha256
        });
        if unchanged {
            return require(
                self == previous,
                "identical retry must retain immutable plan/event",
            );
        }
        require(
            self.event_id != previous.event_id,
            "changed content requires new event",
        )?;
        for file in &self.files {
            let old = prior[&file.envelope.unit_id];
            let before = &old.rows[0].host;
            let after = &file.rows[0].host;
            let mut before_cells = serde_json::to_value(before).map_err(|e| e.to_string())?;
            let mut after_cells = serde_json::to_value(after).map_err(|e| e.to_string())?;
            const TARGET: &[&str] = &[
                "cpu_allowed_processors",
                "cpu_quota_cores",
                "cpu_quota_state",
                "cpu_target_measured_at",
            ];
            const CLOCK: &[&str] = &[
                "model_load_ms",
                "job_seconds",
                "server_prompt_tokens",
                "server_prompt_seconds",
            ];
            if before.cpu_target_measured_at.is_some() {
                for key in TARGET {
                    require(
                        before_cells[*key] == after_cells[*key],
                        "successor refreshes frozen target",
                    )?;
                }
            }
            for key in TARGET.iter().chain(CLOCK) {
                before_cells
                    .as_object_mut()
                    .ok_or("host object")?
                    .remove(*key);
                after_cells
                    .as_object_mut()
                    .ok_or("host object")?
                    .remove(*key);
            }
            require(
                before_cells == after_cells,
                "successor remeasures original probe/hash",
            )?;
            if file.envelope.content_sha256 == old.envelope.content_sha256 {
                require(file == old, "unchanged day must retain file plan")?;
            } else {
                require(
                    file.envelope.written_at_ms > old.envelope.written_at_ms,
                    "changed content requires later actual clock",
                )?;
            }
        }
        Ok(())
    }
}
fn receipt_version() -> String {
    "2026-10-09".to_owned()
}
contract!(HostPublicationReceipt {
    #[serde(default="receipt_version")] version:String,identity:HostWriterIdentity,
    #[serde(default)] writes:BTreeMap<String,String>,
});
impl Validate for HostPublicationReceipt {
    fn validate(&self) -> Result<()> {
        require(self.version == receipt_version(), "unknown receipt version")?;
        self.identity.validate()?;
        for (path, digest) in &self.writes {
            rel_path(path)?;
            hex(digest, 64)?;
        }
        Ok(())
    }
}
contract!(HostWriteCompletion {
    #[serde(default = "default_version")]
    version: String,
    event_id: Uuid,
    receipt: HostPublicationReceipt
});
impl Validate for HostWriteCompletion {
    fn validate(&self) -> Result<()> {
        require(self.version == VERSION, "unknown completion version")?;
        self.receipt.validate()
    }
}
impl HostWriteCompletion {
    pub fn validate_plan(&self, plan: &HostWritePlan, require_all: bool) -> Result<()> {
        self.validate()?;
        plan.validate()?;
        require(
            self.event_id == plan.event_id && self.receipt.identity == plan.publication_identity,
            "completion belongs to foreign event/invocation",
        )?;
        let paths = plan
            .files
            .iter()
            .map(|f| format!("{}/{}", plan.target_root, f.relative_path))
            .collect::<HashSet<_>>();
        require(
            self.receipt.writes.keys().all(|v| paths.contains(v)),
            "completion contains unplanned path",
        )?;
        require(
            !require_all || paths.len() == self.receipt.writes.len(),
            "completion omits planned files",
        )
    }
}
