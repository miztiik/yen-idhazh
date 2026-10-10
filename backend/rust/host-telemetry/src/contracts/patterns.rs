//! Which fixed contract expressions can reuse compilation without changing their predicates?

use crate::contracts::host::{Result, require};
use regex::Regex;
use std::sync::OnceLock;

const EXPRESSIONS: [&str; 9] = [
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$",
    r"^\d{4}-\d{2}-\d{2}-[0-9]+$",
    r"^[A-Za-z0-9._-]*[A-Za-z0-9_-][A-Za-z0-9._-]*(/[A-Za-z0-9._-]*[A-Za-z0-9_-][A-Za-z0-9._-]*)*$",
    r"^[a-z0-9][a-z0-9_.-]*$",
    r"^\d{4}-\d{2}-\d{2}$",
    r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?$",
    r"^\d{4}-\d{2}$",
    r"^\d{4}$",
    r"^[a-z0-9]+(-[a-z0-9]+)*-([0-9]{2,}|[0-9a-hjkmnp-tv-z]{16})$",
];
static COMPILED: [OnceLock<Result<Regex>>; 9] = [const { OnceLock::new() }; 9];

pub fn pattern(value: &str, expression: &str, name: &str) -> Result<()> {
    let matched = if let Some(index) = EXPRESSIONS.iter().position(|known| *known == expression) {
        match COMPILED[index].get_or_init(|| Regex::new(expression).map_err(|e| e.to_string())) {
            Ok(regex) => regex.is_match(value),
            Err(error) => return Err(error.clone()),
        }
    } else {
        Regex::new(expression)
            .map_err(|e| e.to_string())?
            .is_match(value)
    };
    require(matched, name)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fixed_unknown_and_invalid_expressions_keep_complete_original_results() {
        for expression in EXPRESSIONS
            .into_iter()
            .chain(["[", "^unlisted$", r"\p{Greek}+"])
        {
            for value in [
                "",
                "2026-10-10",
                "2026-10-10-42",
                "2026-10-10T12:00:00Z",
                "2026-10-10T12:00",
                "2026-10",
                "2026",
                "state/raw/a.json",
                "../escape",
                "trial-00",
                "hello",
                "unlisted",
                "\u{03bb}",
                "2026-10-10\n",
            ] {
                let original = Regex::new(expression)
                    .map_err(|e| e.to_string())
                    .and_then(|regex| require(regex.is_match(value), "refusal"));
                assert_eq!(pattern(value, expression, "refusal"), original);
            }
        }
    }

    #[test]
    fn fixed_registry_reuses_one_compilation_across_concurrent_readers() {
        std::thread::scope(|scope| {
            for _ in 0..8 {
                scope.spawn(|| {
                    for _ in 0..100 {
                        pattern("2026-10-10", EXPRESSIONS[4], "day").unwrap();
                    }
                });
            }
        });
        let first = COMPILED[4].get().unwrap().as_ref().unwrap() as *const Regex;
        pattern("2026-10-11", EXPRESSIONS[4], "day").unwrap();
        assert_eq!(
            first,
            COMPILED[4].get().unwrap().as_ref().unwrap() as *const Regex
        );
    }
}
