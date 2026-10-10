//! Which typed contracts and in-memory host codecs can callers use?

pub mod contracts {
    pub mod events;
    pub mod file_envelope;
    pub mod host;
    pub mod write_plan;
}
pub mod canonical_json;
pub mod config;
pub mod ledger {
    pub mod schema;
}
pub mod codec {
    pub mod jsonl;
    pub mod parquet;
}
pub use contracts::host::{Result, Validate};
