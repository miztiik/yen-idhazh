# The corpus moves to its own ref

**Last Updated**: 2026-09-23

**Level**: 5 (`CLAUDE.md` section 6). It moves a committed collection off `main`, changes what the one force push in this repository rewrites, and reaches a Colab notebook that no commit here can fix.

> **Nothing in this plan is dispatched, and nothing is scheduled.** The recommendation in section 4 is to leave the corpus on `main`. Section 1's one row is the measurement that reopens the question, and section 3 is the survey that a consultation would start from rather than repeat.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| **Intent** | `corpus/` stops being a directory on `main`, so the bytes it adds to every clone leave with it, and the reason `main`'s history is rewritten leaves with them. |
| **Where it came from** | Row 17 of `20260922-46-no-file-has-two-writers-plan.md`. That plan closed with every other row DONE and its file was deleted on 2026-09-23; git holds it. Row 7 of that plan carried this title until 2026-09-22 and never carried the work, so the owner split them: the force-push rule shipped, and this half is priced here. |
| **What changes for the reader** | Nothing, under every option below. The corpus is a training input and no published page reads it. |
| **Hard scope - in** | Where the corpus lives, how a run reaches it, what happens to the two path constants that spell it, what the prune becomes afterwards, and what replaces the join between a corpus row and the code that produced it. |
| **Hard scope - out** | Table E. |
| **Ruled by** | Fowler, 2026-09-23. |

---

## 1. Status Reckoner

| # | Row title | Depends-on | Status | Level | What moves it |
| --- | --- | --- | --- | --- | --- |
| 1 | The corpus share of the packed repository is re-measured | - | OPEN | 0 | It is a measurement, not a build. Take it when somebody next asks this question. Section 2 says how. |
| 2 | The corpus moves to its own ref | 1 | NOT BUILT | 5 | The corpus passes **40 percent of the packed repository**. Below that, section 4 stands. |

**Row 2 has no worktree, no branch and no acceptance gates**, because it has no design. Section 3 is the survey somebody would design against, and section 5 is the list of questions a Level 5 consultation has to settle first.

---

## 2. The measurements

Taken 2026-09-23 on a full clone of `main`. Every one of them describes a collection that grows, so re-measure before quoting one.

### Table A - what the corpus actually costs today

| id | Measurement | Value |
| --- | --- | --- |
| A1 | The corpus's whole history, packed | **13.7 MB of a 142.5 MB repository, which is 9.6 percent** |
| A2 | Commits touching `corpus/` | **13 of 2,396.** `state/` is touched by 876, which is sixty-seven times more often |
| A3 | The force push the move would remove | **It has never run.** The oldest commit on `main` is 34 days old and the prune keeps 60, so it cannot fire before **2026-10-19** |
| A4 | The two reference datasets | **39.6 MB of the 53.9 MB checked-out corpus tree**, changed four times ever. Three quarters of the weight, and it never churns |

**How to take A1 again.** Compare the packed size of the paths under `corpus/` against the packed size of the whole repository. The number that matters is the share rather than either figure on its own: a repository that grows everywhere at once has not made this case any stronger.

**A3 is the sharpest of the four.** The job this move would retire has not yet done the thing it is criticised for. A cost that has never been paid is an estimate, and `CLAUDE.md` Guardrail #10 says an estimate carries its own label. After 2026-10-19 it becomes a measurement, and that is a better time to ask the question than now.

---

## 3. What the move reaches

Surveyed 2026-09-23 against the tree rather than recalled.

### Table B - the surface

| id | Kind | Count | What they are |
| --- | --- | --- | --- |
| B1 | Writers | 4 | the harvest step and the commit call in `.github/workflows/digest.yml`, `corpus.harvest()` and `corpus.write()`, and the prune's stamp step |
| B2 | Readers, automated | 9 | `stages/harvest.py`, `stages/prune_stamp.py`, `utilities/prune_due.py`, the `corpus` target in `measure.yml`, and the qualification freeze in `validate.yml` |
| B3 | Path constants, hardcoded | 2 | `corpus.CORPUS_ROOT_RELPATH` and `stages/common.CORPUS_ROOT`, which is derived from it. No environment value and no config knob overrides either |
| B4 | CI gates that would fail | 2 | the committed-corpus test in `backend/tests/test_corpus_harvest.py`, and the prune's due check, which reads `corpus/corpus.meta.json` out of a shallow checkout before any install |
| B5 | Steps that would fail quietly | 1 | the harvest is `continue-on-error`, so the corpus would stop filling and the run would still go green |
| B6 | Things a person runs by hand | 7 | `data_wrangler.py`, `reference_set.py`, `build_reference_dataset.py` and the operator paths around them, plus `notebooks/finetune.ipynb`, which runs on Colab, keeps nothing between sessions, and would re-download **53.9 MB** every time |

### What was found, and this is the expensive part

**It would work.** Mount the corpus branch at `corpus/` and add that path to `.gitignore`. No reader changes and neither path constant in B3 moves. The design question is not whether the mechanism exists.

**The prune gets smaller and safer.** Its blast radius shrinks to one branch. Today the squash boundary is per commit rather than per path, so the range it collapses carries `backend/`, `docs/` and `state/` as collateral - stated already in `CLAUDE.md` section 8 and in [`../docs/how-to/fine-tune-a-model.md`](../docs/how-to/fine-tune-a-model.md). The tip re-check in `.github/scripts/push-rewritten-history.sh` spells `main` in three places, so that is a three-line change. The protection gets stronger as well as narrower: the contested ref would take one push every seven days instead of five a day.

**One thing would have to be redone.** The prune's 23:37 wake-up was chosen against when `digest.yml` pushes `main`. After the move the contested ref has a different writer, so that gap analysis is recalculated rather than carried over.

**The real cost is the lost join.** Today the harvest stages `corpus` in the same commit as the code, so `git log -- corpus/corpus.jsonl` says which code produced which rows. After the move there are two refs and no join between them, and once the prune collapses the corpus branch's own commits even the within-branch answer is gone. **When a fine-tune goes wrong, "which code produced this row?" is the only question the corpus exists to answer.**

**A mitigation exists, and this repository already uses the pattern.** Write the producing commit sha into every corpus row - a provenance stamp. `digest.yml` already runs `python -m idhazh assemble --commit "${{ github.sha }}"`, which stamps the run manifest with the commit that produced the published day. The corpus rows never got the same treatment. **That is a gap on `main` today, independent of this move**, and it is the one piece of work here worth doing whether or not row 2 is ever built. Beside it, one CI job comparing the corpus branch's schema against `main`'s readers replaces what a shared commit used to guarantee for free.

**A much smaller change captures most of the bytes.** Move or drop the two reference datasets alone and you take three quarters of the weight (A4), touching two utilities and leaving the harvest, the prune, the notebook and the daily job exactly where they are. **If the goal is bytes, that is the change to cost.** If the goal is stopping the force push on `main`, that is a better argument and it should be made on its own rather than carried on the byte count.

---

## 4. The options, and the recommendation

### Table C - what could be done

| id | Option | What it costs | What it gives up | Pick |
| --- | --- | --- | --- | --- |
| C1 | **Do not build it yet. Re-measure when the share moves.** | Nothing to build. The costs in section 3 stay: a per-commit squash boundary that collapses `backend/`, `docs/` and `state/` as collateral, `git blame` reaching back 60 to 90 days, and a force push that starts firing on 2026-10-19 | The 13.7 MB stays in every clone, and the force push on `main` stays in the design | **Recommended** |
| C2 | Move the corpus to its own ref, with a provenance stamp and a schema gate | 4 writers, 9 readers, 2 path constants, 2 CI gates, 7 hand-run tools and a Colab notebook that re-downloads 53.9 MB a session (Table B). Plus the stamp, the schema job, and a recalculated prune schedule | The join between a corpus row and the code that produced it, replaced by a stamp that has to be trusted instead of derived | |
| C3 | Move or drop the two reference datasets alone | Two utilities | Three quarters of the corpus weight for two files' worth of work - and it removes none of the force push, so it answers the byte question and not the history one | |
| C4 | Stamp every corpus row with its producing commit, and change nothing else | One writer and one column | Nothing. It closes a gap that exists on `main` today, and it is the prerequisite C2 would need anyway | |

**Recommended: C1.** The corpus is 9.6 percent of the packed repository against a reopen line of 40 percent, it is touched by 13 commits in 2,396, and the force push this move would remove has never run once. A Level 5 change that reaches a Colab notebook is not bought by any of those three numbers. **C4 is worth taking on its own merits and is not part of this decision** - the provenance gap is real today.

**The number that reopens this: the corpus passes 40 percent of the packed repository.** Not a date, and not the first force push. A share, because a repository growing everywhere at once has not strengthened this argument.

---

## 5. What a consultation would have to settle

Row 2 is Level 5, so it pauses for a design consultation before any code (`CLAUDE.md` section 6). These are the questions that consultation answers. None is answered here.

### Table D - open questions

| id | Question | Authority |
| --- | --- | --- |
| D1 | **Where does the ref live, and what is it called?** A branch on this repository, an orphan branch, or a second repository are three answers with three different permission stories | Owner |
| D2 | **How does the daily run reach it without paying for it every run?** The harvest runs weekly and the digest runs five times a day, so a fetch on every run pays for a corpus four days out of five for nothing | Carmack |
| D3 | **Does `corpus/` stay in `main`'s working tree as a fetched artifact, or leave entirely?** Staying keeps every reader's path and moves only the history. Leaving is the only version that also removes the bytes from a `main` clone. They are not the same change, and only one of them is what the prune exists for | Fowler |
| D4 | **What replaces `CORPUS_ROOT_RELPATH`?** A config knob is the obvious answer and it is not free: `config/idhazh.json` has a schema, and a path that varies is a path a test has to be given rather than assume | Fowler |
| D5 | **What happens to the test that reads the committed corpus?** `CLAUDE.md` section 13 gives it three fates - move, become a fixture, or become an operator tool under `backend/utilities/` - and no fourth. Doing nothing is not one, because after the move there is nothing on `main` for it to read | Fowler |
| D6 | **How does a person running `data_wrangler.py` get a corpus to point at?** Whatever replaces "the directory is simply there" has to be one documented step, or the tools stop being used | Reader |
| D7 | **Does the prune still exist afterwards, and does it still force-push?** If the corpus leaves `main`, the reason `main`'s history is rewritten leaves with it - and the tip check is then guarding a job that may not need to run at all | Owner |

---

## 6. Rejected alternatives

### Table E - what is out, and why

| id | Option | Why not | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Ship the move inside the force-push rule | That row was Level 4 and named five files, one of which did not exist. The move reaches the surface in Table B | A Level 5 change merged without the consultation Level 5 requires | Owner, 2026-09-22 |
| E2 | Move the path behind a config knob first, and decide the ref later | It looks like a safe first step and it is a second writer of the same question: a knob whose only value is `corpus` is a knob nobody reads, and the readers still have to be found either way | One schema change and a knob that answers nothing until D1 is settled | Fowler |
| E3 | Stop pruning and let the history grow | The corpus commits article text and git history is append-only, so deleting a row does not delete its bytes | An unbounded repository, which is the reason the prune exists | Fowler |
| E4 | Re-price this on the first force push rather than on a share | One force push is one event, and the thing being weighed is a standing cost. A3 becomes a measurement on 2026-10-19 and that makes the argument cheaper to have, not different | Nothing. The share is still the number that decides it | Fowler, 2026-09-23 |

---

## See also

- [`../docs/how-to/fine-tune-a-model.md`](../docs/how-to/fine-tune-a-model.md) - the corpus window, the prune, its tip re-check, and what a rewrite costs.
- [`../CLAUDE.md`](../CLAUDE.md) - section 0a for the corpus carve-out, section 6 for the correction levels, section 8 for the force-push exception.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a row is run and closed, if row 2 is ever dispatched.
