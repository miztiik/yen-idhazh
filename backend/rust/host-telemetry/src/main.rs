//! Which producer command did the operator invoke?

fn main() {
    if let Err(error) = idhazh_host_telemetry::cli::run(std::env::args().skip(1)) {
        eprintln!("{error}");
        std::process::exit(1);
    }
}
