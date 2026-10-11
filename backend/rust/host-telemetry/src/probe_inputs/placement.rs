//! Which bounded link-local metadata response states this host's placement?

use serde::{Deserialize, Serialize};
use std::time::Duration;

const METADATA_URL: &str =
    "http://169.254.169.254/metadata/instance/compute?api-version=2021-02-01";
const METADATA_TIMEOUT: Duration = Duration::from_secs(2);
#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Placement {
    pub vm_size: Option<String>,
    pub location: Option<String>,
    pub zone: Option<String>,
    pub fault_domain: Option<String>,
}
pub fn recorded(bytes: &[u8]) -> Placement {
    let Ok(serde_json::Value::Object(payload)) = serde_json::from_slice(bytes) else {
        return Placement::default();
    };
    let cell = |name| match payload.get(name) {
        Some(serde_json::Value::String(v)) if !v.is_empty() => Some(v.clone()),
        Some(serde_json::Value::Number(v)) if v.to_string() != "0" => Some(v.to_string()),
        Some(serde_json::Value::Bool(true)) => Some("True".to_owned()),
        _ => None,
    };
    Placement {
        vm_size: cell("vmSize"),
        location: cell("location"),
        zone: cell("zone"),
        fault_domain: cell("platformFaultDomain"),
    }
}
pub fn live(maximum_bytes: usize) -> Placement {
    let agent: ureq::Agent = ureq::Agent::config_builder()
        .timeout_global(Some(METADATA_TIMEOUT))
        .max_redirects(0)
        .build()
        .into();
    let Ok(mut response) = agent.get(METADATA_URL).header("Metadata", "true").call() else {
        return Placement::default();
    };
    match response
        .body_mut()
        .with_config()
        .limit(maximum_bytes as u64)
        .read_to_vec()
    {
        Ok(bytes) => recorded(&bytes),
        Err(_) => Placement::default(),
    }
}
