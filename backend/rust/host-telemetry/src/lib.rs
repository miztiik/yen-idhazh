//! Which host contracts, native codecs and raw-file storage can callers use?

pub mod contracts {
    pub mod events;
    pub mod file_envelope;
    pub mod host;
    mod patterns;
    pub mod write_plan;
}
pub mod canonical_json;
pub mod config;
pub mod ledger {
    pub mod envelope;
    pub mod filenames;
    pub mod identity;
    pub mod paths;
    pub mod schema;
    pub mod store;
}
pub mod fs {
    pub mod atomic;
}
pub mod codec {
    pub mod jsonl;
    pub mod parquet;
}
pub use contracts::host::{Result, Validate};
