"""The one door into the committed ledgers under `state/`.

Every file under `state/` is written by one run and read by a later one, because
the pipeline has no memory of its own. What each ledger answers, and why it files
at the grain it does, is `docs/architecture/contracts/state-ledgers.md`.

Callers reach a ledger through this name rather than through the module that
holds it, so a name can move house without a caller changing. That is the whole
job of this file: imports and one `__all__`, and nothing else. A definition here
would be a second home for something a module below already owns, and the two
would drift.
"""

from idhazh.contracts.ledger_fault import LedgerFault
from idhazh.ledger import paths
from idhazh.ledger.csv_file import (
    CsvContract,
    CsvRecord,
    extend_ledger_file,
    read_header,
    render_file,
    require_matching_header,
)
from idhazh.ledger.day_removal import HeldFile, find_holding_files, rebuild_without
from idhazh.ledger.filenames import (
    BEFORE_PARTITION_NAME,
    PRE_IDENTITY_TRACE,
    SegmentName,
    file_id,
    fragment_name,
    is_repair,
    parse_segment_name,
    repair_name,
    segment_name,
    unit_id,
)
from idhazh.ledger.headers import migrate_header, refiler
from idhazh.ledger.keys import (
    COLLECTION_PRUNE_KEY,
    COUNCIL_SHARD_OUTCOME_KEY,
    COUNTERFACTUAL_SCORE_KEY,
    DATE_CELL,
    FEED_HEALTH_KEY,
    FEED_HEALTH_RULE,
    FEED_RETIREMENT_KEY,
    FITTED_SIMILARITY_THRESHOLD_CARRIED,
    HOST_FINGERPRINT_KEY,
    ITEM_HEALTH_KEY,
    ITEM_HEALTH_RULE,
    MERGE_LINE_HOLDOUT_SCORE_KEY,
    OBSERVATION_KEY,
    STORY_SIMILARITY_PAIR_CARRIED,
    STORY_SIMILARITY_PAIR_KEY,
    STORY_SIMILARITY_THRESHOLD_KEY,
    VALIDATION_KEY,
    VISUAL_PRUNE_KEY,
    Preference,
    door_contract,
    door_key,
    preference_for,
    segment_carried,
    segment_contract,
    segment_key,
)
from idhazh.ledger.ledger_files import (
    LedgerFiles,
    Source,
    compact_file,
    held_days,
    held_months,
    list_ledger_files,
    load_days,
    load_ledger_rows,
    month_days,
)
from idhazh.ledger.lifecycle import accepts_new_rows
from idhazh.ledger.paths import (
    STATE_DIRNAME,
    claimed_roots,
    compact_index_path,
    compact_path,
    door_folders,
    door_ledger_at,
    entry,
    path,
    raw_path,
    raw_root,
    registry_entries,
    relpath,
    set_aside_path,
    tree_relpath,
    tree_root,
    watermark_path,
)
from idhazh.ledger.persist import (
    FileFooter,
    PeriodFile,
    StoredRow,
    load,
    load_stored,
    persist,
    persist_period,
    read_envelope,
    read_footer,
    render_grouped_period,
    render_period,
    render_renamed,
)
from idhazh.ledger.raw_files import (
    DayFolder,
    RawFile,
    list_raw_files,
    load_current_rows,
    raw_days,
    read_day_files,
    read_day_folder,
    settle_rows,
)
from idhazh.ledger.rows import (
    HEALTH_WINDOW_DAYS,
    append_council_shard_outcomes,
    append_fitted_thresholds,
    append_published,
    append_seen,
    append_story_similarity_pairs,
    day_shard_path,
    day_shard_relpath,
    extend_segment,
    load_fitted_thresholds,
    load_health,
    load_item_health_summary,
    load_published,
    load_retirements,
    load_seen,
    load_settled_failures,
    load_source_counts,
    load_story_similarity_pairs,
    load_visual_prunes,
    write_item_health_summary,
    write_segment,
)
from idhazh.ledger.settle import KeyedLedger, drop_repeated_rows, keyed_paths, repeated_keys

# Grouped by the module that holds each name, so this list reads as the index of
# the package. A reader following `ledger.X` has one extra hop to make, and this
# group comment is what pays for it.
#
# RUF022 wants one sorted list. Sorting it would interleave the groups and lose
# the only thing the list is here to say, so the grouping is kept and the rule is
# refused on this line alone. Each group is sorted inside itself.
__all__ = [  # noqa: RUF022
    # paths.py: where a ledger's file lives, read from config/ledgers.json or built
    # under the two roots the door files into.
    "STATE_DIRNAME",
    "claimed_roots",
    "compact_index_path",
    "compact_path",
    "door_folders",
    "door_ledger_at",
    "entry",
    "path",
    "paths",
    "raw_path",
    "raw_root",
    "registry_entries",
    "relpath",
    "set_aside_path",
    "tree_relpath",
    "tree_root",
    "watermark_path",
    # persist.py: the one door a contract payload takes to disk, and back.
    "FileFooter",
    "PeriodFile",
    "StoredRow",
    "load",
    "load_stored",
    "persist",
    "persist_period",
    "read_envelope",
    "read_footer",
    "render_grouped_period",
    "render_period",
    "render_renamed",
    # raw_files.py: which raw files hold a ledger's current rows, and what they are.
    "DayFolder",
    "RawFile",
    "list_raw_files",
    "load_current_rows",
    "raw_days",
    "read_day_files",
    "read_day_folder",
    "settle_rows",
    # ledger_files.py: which files - yearly, monthly, daily or raw - hold a ledger's current rows.
    "LedgerFiles",
    "Source",
    "compact_file",
    "held_days",
    "held_months",
    "list_ledger_files",
    "load_days",
    "load_ledger_rows",
    "month_days",
    # day_removal.py: which door files hold a range of days, and each one rebuilt without them.
    "HeldFile",
    "find_holding_files",
    "rebuild_without",
    # contracts/ledger_fault.py: the four ways a packed ledger can be missing a file, by name.
    "LedgerFault",
    # lifecycle.py: whether a ledger takes new rows now.
    "accepts_new_rows",
    # keys.py: what makes two rows one record, and which contract reads one.
    "COLLECTION_PRUNE_KEY",
    "COUNCIL_SHARD_OUTCOME_KEY",
    "COUNTERFACTUAL_SCORE_KEY",
    "DATE_CELL",
    "FEED_HEALTH_KEY",
    "FEED_HEALTH_RULE",
    "FEED_RETIREMENT_KEY",
    "FITTED_SIMILARITY_THRESHOLD_CARRIED",
    "HOST_FINGERPRINT_KEY",
    "ITEM_HEALTH_KEY",
    "ITEM_HEALTH_RULE",
    "MERGE_LINE_HOLDOUT_SCORE_KEY",
    "OBSERVATION_KEY",
    "STORY_SIMILARITY_PAIR_CARRIED",
    "STORY_SIMILARITY_PAIR_KEY",
    "STORY_SIMILARITY_THRESHOLD_KEY",
    "VALIDATION_KEY",
    "VISUAL_PRUNE_KEY",
    "Preference",
    "door_contract",
    "door_key",
    "preference_for",
    "segment_carried",
    "segment_contract",
    "segment_key",
    # filenames.py: what one writer's file is called.
    "BEFORE_PARTITION_NAME",
    "PRE_IDENTITY_TRACE",
    "SegmentName",
    "file_id",
    "fragment_name",
    "is_repair",
    "parse_segment_name",
    "repair_name",
    "segment_name",
    "unit_id",
    # csv_file.py: how rows are read out of and written into a CSV.
    "CsvContract",
    "CsvRecord",
    "extend_ledger_file",
    "read_header",
    "render_file",
    "require_matching_header",
    # headers.py: how a file under an older header is read.
    "migrate_header",
    "refiler",
    # rows.py: how a caller puts rows in and gets them back.
    "HEALTH_WINDOW_DAYS",
    "append_council_shard_outcomes",
    "append_fitted_thresholds",
    "append_published",
    "append_seen",
    "append_story_similarity_pairs",
    "day_shard_path",
    "day_shard_relpath",
    "extend_segment",
    "load_fitted_thresholds",
    "load_health",
    "load_item_health_summary",
    "load_published",
    "load_retirements",
    "load_seen",
    "load_settled_failures",
    "load_source_counts",
    "load_story_similarity_pairs",
    "load_visual_prunes",
    "write_item_health_summary",
    "write_segment",
    # settle.py: which rows repeat a key, and what dropping them costs.
    "KeyedLedger",
    "drop_repeated_rows",
    "keyed_paths",
    "repeated_keys",
]
