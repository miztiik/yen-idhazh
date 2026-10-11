//! Do real bounded source trees, placement replay and observable copies preserve the probe meaning?

mod support;
use idhazh_host_telemetry::{
    contracts::events::*,
    probe_inputs::{
        bandwidth,
        files::{Reading, SourceRoot},
        placement,
        snapshots::{self, LiveRoots},
    },
};
#[test]
fn generated_proc_and_sysfs_sources_equal_the_named_recording() {
    let root = support::workspace("sources");
    let r = support::replay();
    let c = &r.attempts[0];
    let write = |name: &str, text: &str| {
        let path = root.join(name);
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, text).unwrap();
    };
    write("cpu/online", c.online_before.value.as_ref().unwrap());
    write("cpu/present", c.inventory.value.as_ref().unwrap());
    write("proc/cpuinfo", c.cpuinfo.value.as_ref().unwrap());
    write("proc/uptime", c.uptime.value.as_ref().unwrap());
    write("cpu/cpu0/cache/index0/level", "1\n");
    write("cpu/cpu0/cache/index0/size", "32K\n");
    write("cpu/cpu0/cache/index3/level", "3\n");
    write("cpu/cpu0/cache/index3/size", "32M\n");
    for t in &c.topology {
        for (name, value) in [
            ("physical_package_id", &t.package),
            ("core_id", &t.core),
            ("thread_siblings_list", &t.thread_siblings),
            ("core_siblings_list", &t.package_siblings),
        ] {
            write(
                &format!("cpu/cpu{}/topology/{name}", t.id),
                value.value.as_ref().unwrap(),
            );
        }
    }
    for p in c.policies.value.as_ref().unwrap() {
        write(
            &format!("cpu/cpufreq/{}/related_cpus", p.name),
            p.cpus.value.as_ref().unwrap(),
        );
        write(
            &format!("cpu/cpufreq/{}/cpuinfo_max_freq", p.name),
            p.maximum_khz.value.as_ref().unwrap(),
        );
        write(
            &format!("cpu/cpufreq/{}/scaling_max_freq", p.name),
            "9999999",
        );
    }
    let t = c.target_before.as_ref().unwrap();
    write("proc/100/cgroup", t.cgroup.value.as_ref().unwrap());
    write("proc/100/mountinfo", t.mountinfo.value.as_ref().unwrap());
    write(
        "proc/100/stat",
        &format!("100 (worker with spaces) S {} 800\n", ["0"; 18].join(" ")),
    );
    for constraint in t.constraints.value.as_ref().unwrap() {
        for (name, value) in [
            ("cgroup.controllers", &constraint.controllers),
            ("cgroup.subtree_control", &constraint.subtree_control),
            ("cpuset.cpus.effective", &constraint.cpuset),
            ("cpu.max", &constraint.quota),
        ] {
            if let Some(text) = &value.value {
                write(&format!("namespace{}/{name}", constraint.directory), text);
            }
        }
    }
    let mut observed = snapshots::capture(
        &LiveRoots {
            proc: &root.join("proc"),
            cpu: &root.join("cpu"),
            namespace: &root.join("namespace"),
        },
        Some(&ProcessTarget {
            pid: 100,
            start_ticks: 800,
        }),
        &support::manifest().capture_limits,
        Some(&t.affinity),
    )
    .unwrap();
    assert_eq!(
        idhazh_host_telemetry::probe_inputs::allowance::quota(
            observed.target_before.as_ref().unwrap(),
            &support::manifest().capture_limits
        ),
        Err(UnavailableReason::IncompleteCoverage),
        "ordinary directory files cannot establish kernel root evidence",
    );
    let recorded = idhazh_host_telemetry::probe_inputs::hierarchy::RecordedHierarchy {
        source_context: t.source_context.clone(),
        root_evidence: t
            .constraints
            .value
            .as_ref()
            .unwrap()
            .iter()
            .map(|r| r.root_evidence.clone())
            .collect(),
    };
    for target in [&mut observed.target_before, &mut observed.target_after]
        .into_iter()
        .flatten()
    {
        recorded.apply(target).unwrap();
    }
    assert_eq!(&observed, c);
    let cpu = SourceRoot::new(&root.join("cpu"), 4).unwrap();
    assert_eq!(
        cpu.text("online").reason,
        Some(UnavailableReason::Malformed)
    );
    assert!(cpu.path("../proc/cpuinfo").is_err());
}
#[test]
fn metadata_uptime_cache_sizing_and_memory_off_copy_controls_are_independent() {
    let r = support::replay();
    let p = placement::recorded(r.placement_json.value.as_ref().unwrap().as_bytes());
    assert_eq!(p.vm_size.as_deref(), Some("Standard_D4s_v5"));
    assert_eq!(p.fault_domain.as_deref(), Some("1"));
    assert_eq!(
        placement::recorded(b"not json"),
        placement::Placement::default()
    );
    assert_eq!(bandwidth::buffer_mib(1, Some(1048577), 2).unwrap(), 4);
    assert_eq!(bandwidth::buffer_mib(0, Some(33554432), 2).unwrap(), 0);
    assert_eq!(bandwidth::measure(0, 3).unwrap(), None);
    assert!(bandwidth::measure(1, 3).unwrap().unwrap() > 0.0);
    assert!(bandwidth::buffer_mib(1, Some(i64::MAX), 2).is_err());
    Reading::<String>::absent(UnavailableReason::Missing)
        .validate()
        .unwrap();
}
