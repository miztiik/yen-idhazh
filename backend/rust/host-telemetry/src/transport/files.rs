//! How are finite immutable command, response and consumed-evidence files exchanged?

use crate::contracts::events::*;
use crate::contracts::host::require;
use crate::transport::bounds::{ReadBudget, ordinary_reserve, publication_reserve};
use crate::{Result, Validate};
use std::{
    io::Read,
    path::{Path, PathBuf},
};
use uuid::Uuid;

fn is_command_event(kind: EventKind) -> bool {
    matches!(
        kind,
        EventKind::HostProbe
            | EventKind::HostTarget
            | EventKind::HostClock
            | EventKind::WorkerRegister
            | EventKind::WindowBegin
            | EventKind::WindowEnd
            | EventKind::WindowAbort
            | EventKind::MonitorStop
    )
}

fn is_operator_command(kind: EventKind) -> bool {
    matches!(
        kind,
        EventKind::HostProbe
            | EventKind::HostTarget
            | EventKind::HostClock
            | EventKind::MonitorStop
    )
}

pub fn read_bounded(path: &Path, maximum: usize) -> Result<Vec<u8>> {
    match read_bounded_classified(path, maximum)? {
        ReadOutcome::Present(raw) => Ok(raw),
        ReadOutcome::Missing(error) => Err(error.to_string()),
    }
}
enum ReadOutcome<T> {
    Present(T),
    Missing(std::io::Error),
}
fn read_bounded_classified(path: &Path, maximum: usize) -> Result<ReadOutcome<Vec<u8>>> {
    let metadata = match std::fs::symlink_metadata(path) {
        Ok(metadata) => metadata,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(ReadOutcome::Missing(error));
        }
        Err(error) => return Err(error.to_string()),
    };
    require(
        metadata.is_file()
            && !metadata.file_type().is_symlink()
            && metadata.len() <= maximum as u64,
        "named file exceeds bound or is not regular",
    )?;
    let mut raw = Vec::new();
    let file = match std::fs::File::open(path) {
        Ok(file) => file,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            return Ok(ReadOutcome::Missing(error));
        }
        Err(error) => return Err(error.to_string()),
    };
    if let Err(error) = file
        .take(maximum.saturating_add(1) as u64)
        .read_to_end(&mut raw)
    {
        if error.kind() == std::io::ErrorKind::NotFound {
            return Ok(ReadOutcome::Missing(error));
        }
        return Err(error.to_string());
    }
    require(raw.len() <= maximum, "named file grew beyond bound")?;
    Ok(ReadOutcome::Present(raw))
}
pub fn decode_event(raw: &[u8]) -> Result<HostEvent> {
    require(
        raw.ends_with(b"\n") && !raw.contains(&b'\r'),
        "event requires LF and no CR",
    )?;
    let unique: UniqueJson = serde_json::from_slice(raw).map_err(|e| e.to_string())?;
    serde_json::from_value(unique.0).map_err(|e| e.to_string())
}
struct UniqueJson(serde_json::Value);
impl<'de> serde::Deserialize<'de> for UniqueJson {
    fn deserialize<D: serde::Deserializer<'de>>(decoder: D) -> std::result::Result<Self, D::Error> {
        struct Visitor;
        impl<'de> serde::de::Visitor<'de> for Visitor {
            type Value = UniqueJson;
            fn expecting(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
                f.write_str("JSON with unique object keys")
            }
            fn visit_bool<E: serde::de::Error>(
                self,
                v: bool,
            ) -> std::result::Result<Self::Value, E> {
                Ok(UniqueJson(v.into()))
            }
            fn visit_i64<E: serde::de::Error>(self, v: i64) -> std::result::Result<Self::Value, E> {
                Ok(UniqueJson(v.into()))
            }
            fn visit_u64<E: serde::de::Error>(self, v: u64) -> std::result::Result<Self::Value, E> {
                Ok(UniqueJson(v.into()))
            }
            fn visit_f64<E: serde::de::Error>(self, v: f64) -> std::result::Result<Self::Value, E> {
                serde_json::Number::from_f64(v)
                    .map(|v| UniqueJson(v.into()))
                    .ok_or_else(|| E::custom("nonfinite JSON"))
            }
            fn visit_str<E: serde::de::Error>(
                self,
                v: &str,
            ) -> std::result::Result<Self::Value, E> {
                Ok(UniqueJson(v.into()))
            }
            fn visit_none<E: serde::de::Error>(self) -> std::result::Result<Self::Value, E> {
                Ok(UniqueJson(serde_json::Value::Null))
            }
            fn visit_unit<E: serde::de::Error>(self) -> std::result::Result<Self::Value, E> {
                self.visit_none()
            }
            fn visit_seq<A: serde::de::SeqAccess<'de>>(
                self,
                mut seq: A,
            ) -> std::result::Result<Self::Value, A::Error> {
                let mut values = Vec::new();
                while let Some(value) = seq.next_element::<UniqueJson>()? {
                    values.push(value.0);
                }
                Ok(UniqueJson(values.into()))
            }
            fn visit_map<A: serde::de::MapAccess<'de>>(
                self,
                mut map: A,
            ) -> std::result::Result<Self::Value, A::Error> {
                let mut values = serde_json::Map::new();
                while let Some(key) = map.next_key::<String>()? {
                    if values.contains_key(&key) {
                        return Err(serde::de::Error::custom("duplicate JSON field"));
                    }
                    values.insert(key, map.next_value::<UniqueJson>()?.0);
                }
                Ok(UniqueJson(values.into()))
            }
        }
        decoder.deserialize_any(Visitor)
    }
}
pub struct FileTransport {
    workspace: PathBuf,
    root: PathBuf,
    pub manifest: HostSessionManifest,
    budget: ReadBudget,
    published: std::collections::HashMap<Uuid, String>,
    pub total_bytes: u64,
    pub total_events: u64,
}
impl FileTransport {
    pub fn new(workspace: &Path, manifest: HostSessionManifest) -> Result<Self> {
        manifest.validate()?;
        let root = crate::ledger::paths::resolve_directory(workspace, &manifest.event_root)?;
        let workspace = workspace.canonicalize().map_err(|e| e.to_string())?;
        require(
            root == workspace.join(&manifest.event_root),
            "session root cannot alias another workspace directory",
        )?;
        std::fs::create_dir_all(&root).map_err(|e| e.to_string())?;
        for direction in ["inbox", "results", "consumed"] {
            let child = crate::ledger::paths::resolve_directory(
                &workspace,
                &format!("{}/{direction}", manifest.event_root),
            )?;
            require(
                child == root.join(direction),
                "session direction cannot alias another directory",
            )?;
            std::fs::create_dir_all(child).map_err(|e| e.to_string())?;
        }
        Ok(Self {
            workspace,
            root,
            budget: ReadBudget::new(manifest.limits.clone()),
            manifest,
            published: std::collections::HashMap::new(),
            total_bytes: 0,
            total_events: 0,
        })
    }
    // Capacity scans and retirement share this lock so listed files cannot vanish mid-scan.
    fn lock_lifecycle(&self) -> Result<std::fs::File> {
        let path = self.root.join(".transport.lock");
        let file = match std::fs::OpenOptions::new()
            .create_new(true)
            .read(true)
            .write(true)
            .open(&path)
        {
            Ok(file) => file,
            Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {
                let metadata = std::fs::symlink_metadata(&path).map_err(|e| e.to_string())?;
                require(
                    metadata.is_file() && !metadata.file_type().is_symlink(),
                    "transport lifecycle lock is not a regular file",
                )?;
                std::fs::OpenOptions::new()
                    .read(true)
                    .write(true)
                    .open(path)
                    .map_err(|e| e.to_string())?
            }
            Err(error) => return Err(error.to_string()),
        };
        file.lock().map_err(|e| e.to_string())?;
        Ok(file)
    }
    pub fn path(&self, event_id: Uuid, direction: &str) -> Result<PathBuf> {
        let relative = self.relative_path(event_id, direction)?;
        let path = crate::ledger::paths::resolve_document(&self.workspace, &relative)?;
        require(
            path.parent() == Some(self.root.join(direction).as_path()),
            "event path aliases another session directory",
        )?;
        Ok(path)
    }
    pub fn relative_path(&self, event_id: Uuid, direction: &str) -> Result<String> {
        require(
            matches!(direction, "inbox" | "results" | "consumed"),
            "unknown event direction",
        )?;
        Ok(format!(
            "{}/{direction}/{event_id}.json",
            self.manifest.event_root
        ))
    }
    pub fn publish(&mut self, event: &HostEvent, direction: &str) -> Result<PathBuf> {
        self.publish_batch(std::slice::from_ref(event), direction)?;
        self.path(event.event_id, direction)
    }
    pub fn publish_batch(&mut self, events: &[HostEvent], direction: &str) -> Result<()> {
        let _lifecycle = self.lock_lifecycle()?;
        require(
            events.len() <= self.manifest.limits.max_files as usize && direction != "consumed",
            "invalid publication batch",
        )?;
        let refs = events.iter().collect::<Vec<_>>();
        let reserve = publication_reserve(&self.manifest.limits, &refs)?;
        let cap = if direction == "inbox" {
            self.manifest.limits.max_command_bytes
        } else {
            self.manifest.limits.max_result_bytes
        };
        let mut staged = Vec::new();
        let mut ids = std::collections::HashSet::new();
        let mut new_events = 0_u64;
        let mut new_bytes = 0_u64;
        let mut new_files = 0_usize;
        let mut stored_bytes = 0_u64;
        for event in events {
            event.validate()?;
            self.identity(event, direction)?;
            require(ids.insert(event.event_id), "duplicate publication batch ID")?;
            let raw = crate::canonical_json::row_line(event)?;
            require(raw.len() as i64 <= cap, "published event exceeds cap")?;
            let digest = crate::canonical_json::sha256(&raw);
            let path = self.path(event.event_id, direction)?;
            if let Some(previous) = self.published.get(&event.event_id) {
                require(previous == &digest, "immutable event duplicate conflict")?;
            }
            if path.exists() {
                self.budget.reserve(cap as usize)?;
                let existing = read_bounded(&path, cap as usize)?;
                self.budget.used(existing.len());
                require(existing == raw, "immutable event duplicate conflict")?;
            } else {
                new_files += 1;
                stored_bytes += raw.len() as u64;
            }
            if !self.published.contains_key(&event.event_id) {
                new_events += 1;
                new_bytes += raw.len() as u64;
            }
            staged.push((event.event_id, path, raw, digest));
        }
        let reserved_bytes = reserve.saturating_mul(
            self.manifest
                .limits
                .max_command_bytes
                .max(self.manifest.limits.max_result_bytes) as u64,
        );
        if new_events > 0 {
            let reserve = if new_files > 0 { reserve } else { 0 };
            let reserved_bytes = if new_files > 0 { reserved_bytes } else { 0 };
            require(
                self.total_events
                    .saturating_add(new_events)
                    .saturating_add(reserve)
                    <= self.manifest.limits.max_session_events as u64
                    && self
                        .total_bytes
                        .saturating_add(new_bytes)
                        .saturating_add(reserved_bytes)
                        <= self.manifest.limits.max_session_bytes as u64,
                "transport session capacity exhausted",
            )?;
        }
        if new_files > 0 {
            self.reserve_storage(new_files, stored_bytes, reserve)?;
        }
        // Capacity and immutable conflicts are checked for the whole batch before any file is written.
        for (id, path, raw, digest) in staged {
            crate::fs::atomic::publish_immutable(&path, &raw).map_err(|e| e.to_string())?;
            if self.published.insert(id, digest).is_none() {
                self.total_events += 1;
                self.total_bytes += raw.len() as u64;
            }
        }
        Ok(())
    }
    fn reserve_storage(&self, files: usize, bytes: u64, reserve: u64) -> Result<()> {
        require(
            self.file_count()?
                .saturating_add(files)
                .saturating_add(reserve as usize)
                <= self.manifest.limits.max_files as usize,
            "transport file capacity exhausted",
        )?;
        let reserved_bytes = reserve.saturating_mul(
            self.manifest
                .limits
                .max_command_bytes
                .max(self.manifest.limits.max_result_bytes) as u64,
        );
        require(
            self.physical_bytes()?
                .saturating_add(bytes)
                .saturating_add(reserved_bytes)
                <= self.manifest.limits.max_session_bytes as u64,
            "stored session byte capacity exhausted",
        )
    }
    pub fn read(&mut self, event_id: Uuid, direction: &str) -> Result<HostEvent> {
        match self.read_classified(event_id, direction)? {
            ReadOutcome::Present(event) => Ok(event),
            ReadOutcome::Missing(error) => Err(error.to_string()),
        }
    }
    pub fn read_listed_result(&mut self, event_id: Uuid) -> Result<Option<HostEvent>> {
        match self.read_classified(event_id, "results")? {
            ReadOutcome::Present(event) => Ok(Some(event)),
            ReadOutcome::Missing(_) => Ok(None),
        }
    }
    pub fn read_staged_result(&mut self, event_id: Uuid) -> Result<HostEvent> {
        let path = crate::ledger::paths::resolve_document(
            &self.workspace,
            &format!(
                "{}/results/.pending-{event_id}.json",
                self.manifest.event_root
            ),
        )?;
        require(
            path.parent() == Some(self.root.join("results").as_path()),
            "staged result aliases another session directory",
        )?;
        match self.read_classified_path(event_id, "results", &path)? {
            ReadOutcome::Present(event) => Ok(event),
            ReadOutcome::Missing(error) => Err(error.to_string()),
        }
    }
    fn read_classified(
        &mut self,
        event_id: Uuid,
        direction: &str,
    ) -> Result<ReadOutcome<HostEvent>> {
        let path = self.path(event_id, direction)?;
        self.read_classified_path(event_id, direction, &path)
    }
    fn read_classified_path(
        &mut self,
        event_id: Uuid,
        direction: &str,
        path: &Path,
    ) -> Result<ReadOutcome<HostEvent>> {
        let cap = if direction == "inbox" {
            self.manifest.limits.max_command_bytes
        } else {
            self.manifest.limits.max_result_bytes
        };
        self.budget.reserve(cap as usize)?;
        let raw = match read_bounded_classified(path, cap as usize)? {
            ReadOutcome::Present(raw) => raw,
            ReadOutcome::Missing(error) => return Ok(ReadOutcome::Missing(error)),
        };
        self.budget.used(raw.len());
        let event = decode_event(&raw)?;
        require(
            event.event_id == event_id,
            "event filename identity mismatch",
        )?;
        self.identity(&event, direction)?;
        Ok(ReadOutcome::Present(event))
    }
    pub fn named(&self, name: &str) -> Result<PathBuf> {
        let input = self
            .manifest
            .named_inputs
            .iter()
            .find(|v| v.name == name)
            .ok_or("undeclared named input")?;
        let path = crate::ledger::paths::resolve_document(
            &self.workspace,
            &format!("{}/{}", self.manifest.event_root, input.relative_path),
        )?;
        require(
            path.starts_with(&self.root),
            "named input escapes its session root",
        )?;
        Ok(path)
    }
    pub fn ids(&self, direction: &str) -> Result<Vec<Uuid>> {
        require(
            matches!(direction, "inbox" | "results" | "consumed"),
            "unknown direction",
        )?;
        let root = crate::ledger::paths::resolve_directory(
            &self.workspace,
            &format!("{}/{direction}", self.manifest.event_root),
        )?;
        require(
            root == self.root.join(direction),
            "session directory alias refused",
        )?;
        let mut ids = Vec::new();
        let mut entries = 0_usize;
        for entry in std::fs::read_dir(root)
            .map_err(|e| e.to_string())?
            .take(self.manifest.limits.max_files as usize + 1)
        {
            entries += 1;
            require(
                entries <= self.manifest.limits.max_files as usize,
                "session directory read limit exhausted",
            )?;
            let entry = entry.map_err(|e| e.to_string())?;
            let name = entry.file_name().to_string_lossy().into_owned();
            // Atomic helpers own dot-prefixed staging names; never read partial messages.
            if name.starts_with('.') {
                continue;
            }
            let id = name
                .strip_suffix(".json")
                .ok_or("foreign session filename")?;
            let id = Uuid::parse_str(id).map_err(|e| e.to_string())?;
            require(
                name == format!("{id}.json"),
                "noncanonical session filename",
            )?;
            ids.push(id);
        }
        require(
            ids.len() <= self.manifest.limits.max_files as usize,
            "directory file capacity exhausted",
        )?;
        ids.sort();
        Ok(ids)
    }
    fn file_count(&self) -> Result<usize> {
        let count =
            self.ids("inbox")?.len() + self.ids("results")?.len() + self.ids("consumed")?.len();
        require(
            count <= self.manifest.limits.max_files as usize,
            "total session file capacity exhausted",
        )?;
        Ok(count)
    }
    fn physical_bytes(&self) -> Result<u64> {
        let mut bytes = 0_u64;
        for direction in ["inbox", "results", "consumed"] {
            for id in self.ids(direction)? {
                bytes = bytes.saturating_add(
                    std::fs::metadata(self.path(id, direction)?)
                        .map_err(|e| e.to_string())?
                        .len(),
                );
            }
        }
        Ok(bytes)
    }
    pub fn consume(&mut self, event: &HostEvent) -> Result<()> {
        let _lifecycle = self.lock_lifecycle()?;
        event.validate()?;
        self.identity(event, "consumed")?;
        let raw = crate::canonical_json::row_line(event)?;
        let path = self.path(event.event_id, "consumed")?;
        let direction = if is_command_event(event.kind) {
            "inbox"
        } else {
            "results"
        };
        let original = self.path(event.event_id, direction)?;
        let cap = if direction == "inbox" {
            self.manifest.limits.max_command_bytes
        } else {
            self.manifest.limits.max_result_bytes
        };
        if path.exists() {
            self.budget.reserve(cap as usize)?;
            let existing = read_bounded(&path, cap as usize)?;
            self.budget.used(existing.len());
            require(existing == raw, "consumption differs from original event")?;
            return Ok(());
        }
        if !path.exists() {
            self.reserve_storage(1, raw.len() as u64, ordinary_reserve(&self.manifest.limits))?;
        }
        self.budget.reserve(cap as usize)?;
        let existing = read_bounded(&original, cap as usize)?;
        self.budget.used(existing.len());
        crate::fs::atomic::publish_immutable(&path, &raw).map_err(|e| e.to_string())
    }
    pub fn remove_retired(&self, ids: &[Uuid]) -> Result<()> {
        let _lifecycle = self.lock_lifecycle()?;
        for id in ids {
            for direction in ["inbox", "results", "consumed"] {
                let path = self.path(*id, direction)?;
                if path.exists() {
                    std::fs::remove_file(path).map_err(|e| e.to_string())?;
                }
            }
        }
        Ok(())
    }
    pub fn reads(&self) -> u64 {
        self.budget.reads
    }
    pub fn check_command(&self, event: &HostEvent) -> Result<()> {
        event.validate()?;
        self.identity(event, "inbox")
    }
    fn identity(&self, event: &HostEvent, direction: &str) -> Result<()> {
        let m = &self.manifest;
        require(
            event.session_id == m.session_id
                && event.date == m.date
                && event.run_id == m.run_id
                && event.attempt == m.attempt
                && event.job == m.job
                && event.shard == m.shard,
            "foreign event invocation/session",
        )?;
        let command = is_command_event(event.kind);
        require(
            direction == "consumed" || command == (direction == "inbox"),
            "event kind contradicts file direction",
        )?;
        let valid = if command {
            if is_operator_command(event.kind) {
                event.emitter_id == m.operator_emitter_id
            } else {
                m.workers.iter().any(|v| v.emitter_id == event.emitter_id)
            }
        } else {
            event.emitter_id == m.monitor_emitter_id
        };
        require(valid, "event emitter is not declared for its direction")?;
        match &event.body {
            EventBody::Ready(v) => require(
                v.boot_id == m.boot_id && v.supported_version == m.version,
                "ready names another boot/version",
            )?,
            EventBody::Worker(v) => {
                require(
                    v.memory_profiling_enabled == m.controls.memory_profiling_enabled
                        && m.workers.iter().any(|w| {
                            w.target == v.target
                                && w.server == v.server
                                && (!command || w.emitter_id == event.emitter_id)
                        }),
                    "worker body names another target/control",
                )?;
            }
            body => {
                let window = match body {
                    EventBody::Window(v) => Some(v),
                    EventBody::Abort(v) => Some(&v.window),
                    EventBody::Begun(v) => Some(&v.window),
                    EventBody::WindowResult(v) => Some(&v.window),
                    _ => None,
                };
                if let Some(window) = window {
                    let declared = m
                        .windows
                        .iter()
                        .find(|v| v.window_id == window.window_id)
                        .ok_or("undeclared window body")?;
                    let worker = m
                        .workers
                        .iter()
                        .find(|v| v.emitter_id == declared.emitter_id)
                        .ok_or("undeclared window worker")?;
                    require(
                        window.item_id == declared.item_id
                            && window.target == worker.target
                            && window.server == worker.server
                            && (!command || event.emitter_id == worker.emitter_id),
                        "window body names another item/worker/target",
                    )?;
                }
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod lifecycle_lock_tests {
    use super::*;

    #[test]
    fn operator_host_commands_are_inbox_commands() {
        for kind in [
            EventKind::HostProbe,
            EventKind::HostTarget,
            EventKind::HostClock,
            EventKind::WorkerRegister,
            EventKind::WindowBegin,
            EventKind::WindowEnd,
            EventKind::WindowAbort,
            EventKind::MonitorStop,
        ] {
            assert!(is_command_event(kind));
        }
        for kind in [
            EventKind::HostProbe,
            EventKind::HostTarget,
            EventKind::HostClock,
            EventKind::MonitorStop,
        ] {
            assert!(is_operator_command(kind));
        }
        for kind in [
            EventKind::WorkerRegister,
            EventKind::WindowBegin,
            EventKind::WindowEnd,
            EventKind::WindowAbort,
        ] {
            assert!(!is_operator_command(kind));
        }
        assert!(!is_command_event(EventKind::HostResult));
        assert!(!is_command_event(EventKind::MonitorStopped));
    }

    #[test]
    fn capacity_snapshot_and_retirement_share_the_lifecycle_lock() {
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("..")
            .join("var")
            .join(format!(
                "d5-transport-lifecycle-lock-{}",
                std::process::id()
            ));
        if root.exists() {
            std::fs::remove_dir_all(&root).unwrap();
        }
        std::fs::create_dir_all(&root).unwrap();
        let manifest: HostSessionManifest = serde_json::from_str(include_str!(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../../../tests/fixtures/host-events/manifest.json"
        )))
        .unwrap();
        let files = FileTransport::new(&root, manifest).unwrap();
        let id = Uuid::from_u128(42);
        for direction in ["inbox", "results", "consumed"] {
            std::fs::write(files.path(id, direction).unwrap(), b"x").unwrap();
        }

        let lock = files.lock_lifecycle().unwrap();
        let contender = std::fs::OpenOptions::new()
            .read(true)
            .write(true)
            .open(files.root.join(".transport.lock"))
            .unwrap();
        assert!(contender.try_lock().is_err());
        assert_eq!(files.physical_bytes().unwrap(), 3);
        drop(lock);

        files.remove_retired(&[id]).unwrap();
        assert_eq!(files.physical_bytes().unwrap(), 0);
        drop(contender);
        std::fs::remove_dir_all(root).unwrap();
    }
}
