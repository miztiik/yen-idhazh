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
pub mod receipts;
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
pub mod cli;
pub mod fingerprint;
mod invocation;
pub mod producers {
    pub mod job_clock;
    pub mod job_probe;
    pub mod job_samples;
    pub mod target_probe;
}
pub mod sampling {
    pub mod capture;
    pub mod machine;
    pub mod process;
}
pub mod windows {
    pub mod reduce;
}
pub mod transport {
    pub mod bounds;
    pub mod client;
    pub mod files;
}
pub mod monitor {
    pub mod runner;
    pub mod session;
}
pub mod probe_inputs {
    pub mod allowance;
    pub mod bandwidth;
    pub mod cpu;
    pub mod files;
    pub mod frequency;
    pub mod hierarchy;
    pub mod placement;
    pub mod snapshots;
    pub mod topology;
}
