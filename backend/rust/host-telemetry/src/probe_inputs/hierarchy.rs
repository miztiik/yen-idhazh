//! Which structural kernel evidence proves that the visible hierarchy includes its actual root?

use super::allowance::{Constraint, Controller, Scope};
use super::files::Reading;
use super::snapshots::LiveRoots;
use crate::contracts::events::{ProcessTarget, UnavailableReason};
use crate::probe_inputs::topology::Observation;
use serde::{Deserialize, Serialize};

pub const CGROUP_SUPER_MAGIC: i64 = 0x27e0eb;
pub const CGROUP2_SUPER_MAGIC: i64 = 0x63677270;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Identity {
    pub device: u64,
    pub inode: u64,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CgroupSourceContext {
    pub reader_cgroupns: Identity,
    pub target_cgroupns: Identity,
    pub reader_mountns: Identity,
    pub target_mountns: Identity,
    pub reader_root: Identity,
    pub target_root: Identity,
    pub source_root: Identity,
}
impl CgroupSourceContext {
    pub fn aligned(&self) -> Observation<()> {
        if self.reader_cgroupns == self.target_cgroupns
            && self.reader_mountns == self.target_mountns
            && self.reader_root == self.target_root
            && self.reader_root == self.source_root
        {
            Ok(())
        } else {
            Err(UnavailableReason::IncompleteCoverage)
        }
    }
}
pub fn missing_context() -> Reading<CgroupSourceContext> {
    Reading::absent(UnavailableReason::IncompleteCoverage)
}
pub fn missing_text() -> Reading<String> {
    Reading::absent(UnavailableReason::IncompleteCoverage)
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct MountIdentity {
    pub id: u64,
    pub major: u32,
    pub minor: u32,
    pub root: String,
    pub mountpoint: String,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct DirectoryIdentity {
    pub filesystem_type: i64,
    pub identity: Identity,
    pub mount_id: u64,
    pub major: u32,
    pub minor: u32,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EntryMetadata {
    pub identity: Identity,
    pub regular: bool,
    pub mount_id: u64,
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum Lookup {
    Present(EntryMetadata),
    ExactEnoent,
    Failed(UnavailableReason),
}
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RootEvidence {
    pub selected_mount: MountIdentity,
    pub directory: Reading<DirectoryIdentity>,
    pub cgroup_procs: Lookup,
    pub marker: Lookup,
}
pub fn verify_root(scope: &Scope, evidence: &RootEvidence) -> Observation<()> {
    if evidence.selected_mount != scope.mount || !scope.root {
        return Err(UnavailableReason::IncompleteCoverage);
    }
    evidence
        .directory
        .validate()
        .map_err(|_| UnavailableReason::Malformed)?;
    let directory = evidence.directory.get()?;
    if directory.filesystem_type
        != if scope.controller == Controller::V2 {
            CGROUP2_SUPER_MAGIC
        } else {
            CGROUP_SUPER_MAGIC
        }
        || directory.mount_id != scope.mount.id
        || directory.major != scope.mount.major
        || directory.minor != scope.mount.minor
    {
        return Err(UnavailableReason::IncompleteCoverage);
    }
    let present = |entry: &Lookup| -> Observation<()> {
        match entry {
            Lookup::Present(metadata)
                if metadata.regular
                    && metadata.identity.device == directory.identity.device
                    && metadata.mount_id == directory.mount_id =>
            {
                Ok(())
            }
            Lookup::Failed(reason) => Err(*reason),
            _ => Err(UnavailableReason::IncompleteCoverage),
        }
    };
    present(&evidence.cgroup_procs)?;
    if scope.controller == Controller::V2 {
        match evidence.marker {
            Lookup::ExactEnoent => Ok(()),
            Lookup::Failed(reason) => Err(reason),
            _ => Err(UnavailableReason::IncompleteCoverage),
        }
    } else {
        present(&evidence.marker)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RecordedHierarchy {
    pub source_context: Reading<CgroupSourceContext>,
    pub root_evidence: Vec<Option<RootEvidence>>,
}
impl RecordedHierarchy {
    pub fn apply(&self, capture: &mut super::allowance::TargetCapture) -> crate::Result<()> {
        self.source_context.validate()?;
        let rows = capture
            .constraints
            .value
            .as_mut()
            .ok_or("missing constraints")?;
        crate::contracts::host::require(
            rows.len() == self.root_evidence.len(),
            "recorded root evidence row count differs",
        )?;
        capture.source_context = self.source_context.clone();
        for (row, root) in rows.iter_mut().zip(&self.root_evidence) {
            crate::contracts::host::require(
                row.root || root.is_none(),
                "root evidence outside candidate mount root",
            )?;
            row.root_evidence = root.clone();
        }
        Ok(())
    }
}

#[cfg(target_os = "linux")]
mod linux {
    use super::*;
    use std::ffi::CString;
    use std::fs::File;
    use std::io::Read;
    use std::os::fd::{AsRawFd, FromRawFd};
    use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
    use std::path::{Component, Path};

    fn reason() -> UnavailableReason {
        match std::io::Error::last_os_error().raw_os_error() {
            Some(libc::EACCES | libc::EPERM) => UnavailableReason::PermissionDenied,
            Some(libc::ENOENT) => UnavailableReason::Missing,
            _ => UnavailableReason::IncompleteCoverage,
        }
    }
    fn identity(file: &File) -> Observation<Identity> {
        let m = file.metadata().map_err(|_| reason())?;
        Ok(Identity {
            device: m.dev(),
            inode: m.ino(),
        })
    }
    fn open(path: &Path) -> Observation<File> {
        File::open(path).map_err(|_| reason())
    }
    pub fn context(roots: &LiveRoots<'_>, target: &ProcessTarget) -> Reading<CgroupSourceContext> {
        let result = || -> Observation<CgroupSourceContext> {
            // Namespace handles are magic links; their fd metadata identifies the namespace.
            let id = |path: &Path| identity(&open(path)?);
            Ok(CgroupSourceContext {
                reader_cgroupns: id(&roots.proc.join("self/ns/cgroup"))?,
                target_cgroupns: id(&roots.proc.join(format!("{}/ns/cgroup", target.pid)))?,
                reader_mountns: id(&roots.proc.join("self/ns/mnt"))?,
                target_mountns: id(&roots.proc.join(format!("{}/ns/mnt", target.pid)))?,
                reader_root: id(Path::new("/"))?,
                target_root: id(&roots.proc.join(format!("{}/root", target.pid)))?,
                source_root: id(roots.namespace)?,
            })
        };
        match result() {
            Ok(value) => Reading::found(value),
            Err(value) => Reading::absent(value),
        }
    }
    fn directory(root: &Path, relative: &str) -> Observation<File> {
        let mut fd = std::fs::OpenOptions::new()
            .read(true)
            .custom_flags(libc::O_DIRECTORY | libc::O_CLOEXEC)
            .open(root)
            .map_err(|_| reason())?;
        for component in Path::new(relative.trim_start_matches('/')).components() {
            let Component::Normal(name) = component else {
                return Err(UnavailableReason::Malformed);
            };
            let name =
                CString::new(name.as_encoded_bytes()).map_err(|_| UnavailableReason::Malformed)?;
            let next = unsafe {
                libc::openat(
                    fd.as_raw_fd(),
                    name.as_ptr(),
                    libc::O_RDONLY | libc::O_DIRECTORY | libc::O_CLOEXEC | libc::O_NOFOLLOW,
                )
            };
            if next < 0 {
                return Err(reason());
            }
            fd = unsafe { File::from_raw_fd(next) };
        }
        Ok(fd)
    }
    fn filesystem_type(value: impl TryInto<i64>) -> Observation<i64> {
        value
            .try_into()
            .map_err(|_| UnavailableReason::IncompleteCoverage)
    }
    fn directory_identity(fd: &File) -> Observation<DirectoryIdentity> {
        let mut fs = std::mem::MaybeUninit::<libc::statfs>::uninit();
        let mut st = std::mem::MaybeUninit::<libc::statx>::uninit();
        let empty = c"";
        if unsafe { libc::fstatfs(fd.as_raw_fd(), fs.as_mut_ptr()) } != 0
            || unsafe {
                libc::statx(
                    fd.as_raw_fd(),
                    empty.as_ptr(),
                    libc::AT_EMPTY_PATH,
                    libc::STATX_BASIC_STATS | libc::STATX_MNT_ID,
                    st.as_mut_ptr(),
                )
            } != 0
        {
            return Err(reason());
        }
        let fs = unsafe { fs.assume_init() };
        let st = unsafe { st.assume_init() };
        let filesystem_type = filesystem_type(fs.f_type)?;
        if st.stx_mask & (libc::STATX_MNT_ID | libc::STATX_INO)
            != (libc::STATX_MNT_ID | libc::STATX_INO)
        {
            return Err(UnavailableReason::IncompleteCoverage);
        }
        Ok(DirectoryIdentity {
            filesystem_type,
            identity: identity(fd)?,
            mount_id: st.stx_mnt_id,
            major: st.stx_dev_major,
            minor: st.stx_dev_minor,
        })
    }
    fn lookup(fd: &File, name: &str) -> Lookup {
        let name = CString::new(name).expect("fixed core entry");
        let mut st = std::mem::MaybeUninit::<libc::stat>::uninit();
        if unsafe {
            libc::fstatat(
                fd.as_raw_fd(),
                name.as_ptr(),
                st.as_mut_ptr(),
                libc::AT_SYMLINK_NOFOLLOW,
            )
        } != 0
        {
            return if std::io::Error::last_os_error().raw_os_error() == Some(libc::ENOENT) {
                Lookup::ExactEnoent
            } else {
                Lookup::Failed(reason())
            };
        }
        let st = unsafe { st.assume_init() };
        let mut extended = std::mem::MaybeUninit::<libc::statx>::uninit();
        if unsafe {
            libc::statx(
                fd.as_raw_fd(),
                name.as_ptr(),
                libc::AT_SYMLINK_NOFOLLOW,
                libc::STATX_MNT_ID,
                extended.as_mut_ptr(),
            )
        } != 0
        {
            return Lookup::Failed(reason());
        }
        let extended = unsafe { extended.assume_init() };
        if extended.stx_mask & libc::STATX_MNT_ID == 0 {
            return Lookup::Failed(UnavailableReason::IncompleteCoverage);
        }
        Lookup::Present(EntryMetadata {
            identity: Identity {
                device: st.st_dev,
                inode: st.st_ino,
            },
            regular: st.st_mode & libc::S_IFMT == libc::S_IFREG,
            mount_id: extended.stx_mnt_id,
        })
    }
    fn text(fd: &File, name: &str, maximum: usize) -> Reading<String> {
        let result = || -> Observation<String> {
            let name = CString::new(name).expect("fixed controller entry");
            let raw = unsafe {
                libc::openat(
                    fd.as_raw_fd(),
                    name.as_ptr(),
                    libc::O_RDONLY | libc::O_CLOEXEC | libc::O_NOFOLLOW,
                )
            };
            if raw < 0 {
                return Err(reason());
            }
            let file = unsafe { File::from_raw_fd(raw) };
            let a = file.metadata().map_err(|_| reason())?;
            let b = fd.metadata().map_err(|_| reason())?;
            if !a.is_file()
                || a.dev() != b.dev()
                || directory_identity(&file)?.mount_id != directory_identity(fd)?.mount_id
            {
                return Err(UnavailableReason::IncompleteCoverage);
            }
            let mut bytes = Vec::new();
            file.take(maximum.saturating_add(1) as u64)
                .read_to_end(&mut bytes)
                .map_err(|_| reason())?;
            if bytes.len() > maximum {
                return Err(UnavailableReason::IncompleteCoverage);
            }
            String::from_utf8(bytes).map_err(|_| UnavailableReason::Malformed)
        };
        match result() {
            Ok(v) => Reading::found(v),
            Err(r) => Reading::absent(r),
        }
    }
    pub fn constraints(root: &Path, scopes: &[Scope], maximum: usize) -> Vec<Constraint> {
        scopes
            .iter()
            .map(|scope| {
                let fd = directory(root, &scope.directory);
                let metadata = fd.as_ref().map_err(|r| *r).and_then(directory_identity);
                let matched = metadata.as_ref().is_ok_and(|m| {
                    m.mount_id == scope.mount.id
                        && m.major == scope.mount.major
                        && m.minor == scope.mount.minor
                        && m.filesystem_type
                            == if scope.controller == Controller::V2 {
                                CGROUP2_SUPER_MAGIC
                            } else {
                                CGROUP_SUPER_MAGIC
                            }
                });
                let read = |name| match &fd {
                    Ok(fd) if matched => text(fd, name, maximum),
                    Err(r) => Reading::absent(*r),
                    _ => Reading::absent(UnavailableReason::IncompleteCoverage),
                };
                let evidence = scope.root.then(|| RootEvidence {
                    selected_mount: scope.mount.clone(),
                    directory: match &metadata {
                        Ok(v) => Reading::found(v.clone()),
                        Err(r) => Reading::absent(*r),
                    },
                    cgroup_procs: fd
                        .as_ref()
                        .map_or_else(|r| Lookup::Failed(*r), |fd| lookup(fd, "cgroup.procs")),
                    marker: fd.as_ref().map_or_else(
                        |r| Lookup::Failed(*r),
                        |fd| {
                            lookup(
                                fd,
                                if scope.controller == Controller::V2 {
                                    "cgroup.events"
                                } else {
                                    "release_agent"
                                },
                            )
                        },
                    ),
                });
                Constraint {
                    controller: scope.controller,
                    directory: scope.directory.clone(),
                    root: scope.root,
                    controllers: read("cgroup.controllers"),
                    subtree_control: read("cgroup.subtree_control"),
                    cpuset: read(if scope.controller == Controller::V2 {
                        "cpuset.cpus.effective"
                    } else {
                        "cpuset.cpus"
                    }),
                    quota: read(if scope.controller == Controller::V2 {
                        "cpu.max"
                    } else {
                        "cpu.cfs_quota_us"
                    }),
                    period: read("cpu.cfs_period_us"),
                    root_evidence: evidence,
                }
            })
            .collect()
    }
}
pub fn context(roots: &LiveRoots<'_>, target: &ProcessTarget) -> Reading<CgroupSourceContext> {
    #[cfg(target_os = "linux")]
    {
        linux::context(roots, target)
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = (roots, target);
        missing_context()
    }
}
pub fn constraints(root: &std::path::Path, scopes: &[Scope], maximum: usize) -> Vec<Constraint> {
    #[cfg(target_os = "linux")]
    {
        linux::constraints(root, scopes, maximum)
    }
    #[cfg(not(target_os = "linux"))]
    {
        let root = super::files::SourceRoot::new(root, maximum).expect("validated source root");
        super::allowance::capture_constraints(&root, scopes)
    }
}
