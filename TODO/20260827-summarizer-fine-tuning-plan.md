# Fine-tune the summarizer, then distil it - Plan

**Last Updated**: 2026-08-27

**Level**: 3, except rows 8 and 9, which are Level 5 if they end in adoption.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 2; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The pipeline writes about 149 summaries a day and throws the pairs away. Those pairs, plus a few hundred summaries written by a stronger model, are a training set for the exact job we run. The aim is two-stage: fine-tune Qwen3-8B so it writes better summaries, then distil that tuned model into Qwen3-4B so it writes them faster. |
| Hard scope - in | A contract and config for the corpus; the day's pairs written to a file; a data wrangler that adds atomically and deletes surgically; a reference set of expert-written summaries; a Colab notebook that trains a LoRA adapter; a low-memory merge using llama.cpp; a home for the GGUF; a blind read plus the existing gates; and the same again for a 4B student. |
| Hard scope - out | Training on the runner. Any hosted model call from the pipeline, at any stage. Human labelling campaigns. DPO or RLHF. Changes to the prompt, the bands, the scoring path or the published site. Adoption - each of rows 8 and 9 ends at a decision. |
| ESCALATE triggers | (1) A corpus file appearing in a committed path, because it holds article bodies. (2) Any training step added to a workflow. (3) A reference summary used for both training and testing. (4) Adoption of either fine-tuned model. (5) Colab cost above what the user approved. |
| Chosen strategy | Improve the 8B first, prove it, then compress it. Distilling from a tuned teacher beats distilling from a stock one, and doing them in one step would make any regression unattributable. |
| Naming note | This plan says **reference set**, never "golden set". `config/idhazh.json` already carries `golden_set_size: 20`, which means the articles a candidate model is validated on during qualification. Two different things must not share one word. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Say what the fine-tuning non-goal actually forbids | - | A | IN REVIEW | - | `docs/narrow-the-fine-tuning-non-goal` | - |
| 2 | A contract and a config for the corpus | 1 | B | PENDING | - | - | - |
| 3 | The daily run writes its pairs to a file | 2 | C | PENDING | - | - | - |
| 4 | `data_wrangler.py`: atomic add, surgical delete | 3 | D | PENDING | - | - | - |
| 5 | A reference set written by an expert model | 3 | D | PENDING | - | - | - |
| 6 | Train the 8B adapter on Colab, merge with llama.cpp | 4, 5 | E | PENDING | - | - | - |
| 7 | Give the GGUF a home the config can point at | 6 | F | PENDING | - | - | - |
| 8 | Judge the tuned 8B and decide | 7 | G | PENDING | - | - | - |
| 9 | Distil the tuned 8B into the 4B and decide | 8 | H | PENDING | - | - | - |

## Row #1 - Say what the fine-tuning non-goal actually forbids

- **Scope:** Narrow the non-goal from "fine-tuning" to "training on the runner", and say why, in all three places that carry it.
- **Files touched:** `CLAUDE.md`, `docs/agents/guardrails.md`, `.github/agents/andre.agent.md`
- **Acceptance gates:** ASCII-only; `Last Updated` stamped; the three copies agree; no other non-goal reworded.
- **Oracle:** A grep for the old wording returns nothing outside `TODO/` and `docs/archive/`.
- **Decisions:**

  | # | Decision | Why |
  | --- | --- | --- |
  | 1 | The clause protects one thing: a build step the runner cannot execute. No GPU, 4 vCPU, a job that stops at 6 hours. That reason is intact. | It is the actual constraint. |
  | 2 | It says nothing about where weights come from. The runner opens a finished GGUF and reads bytes. | The old wording forbade something for a reason that does not apply to it. |
  | 3 | All three copies move in one commit. | Section 0b records what happens when three files state one rule three ways: the weakest version becomes the binding one. |

- **Rejected alternatives:**

  | # | Option | Why rejected |
  | --- | --- | --- |
  | 1 | Delete the non-goal | It would also delete the GPU-runner and model-fit clauses, which still do work |
  | 2 | Treat this plan as an unwritten exception | An exception nobody wrote down is a rule the next agent enforces against this work |

## Row #2 - A contract and a config for the corpus

- **Scope:** Freeze the corpus shape as a Pydantic model, generate its schema, and put every size and freshness number in `config/`. Nothing writes a corpus until this exists.
- **Files touched:**
  - `backend/idhazh/contracts/corpus.py`
  - `backend/idhazh/contracts/app_config.py`
  - `config/idhazh.json`
  - `schemas/corpus_meta.schema.json`
  - `schemas/corpus_row.schema.json`
  - `schemas/app_config.schema.json`
  - `backend/tests/test_corpus_contract.py`
  - `docs/how-to/fine-tune-the-summarizer.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; the drift gate regenerates byte-identical; `version` date-stamped and `changelog` appended; every knob has a default so a fresh clone runs unconfigured.
- **Oracle:** Round-trip. A written corpus file re-reads into the same model with no field lost and no default silently filled in. `contracts/corpus.py` imports nothing from another `idhazh` subpackage.

- **The layout:**

  ```
  backend/var/corpus/                 gitignored, .gitignore line 47
    daily/2026-08-27.jsonl            one run's accepted pairs
    daily/2026-08-27.meta.json        the constants for that day
    reference/reference.jsonl         expert-written, authored once
    reference/reference.meta.json
    corpus.jsonl                      what the wrangler merges
    corpus.meta.json
  ```

- **A daily `meta.json`:**

  ```json
  {
    "version": "2026-08-27",
    "date": "2026-08-27",
    "description": "Accepted summarizer pairs, run 2026-08-27-1.",
    "model_id": "qwen3-8b-q4-k-m",
    "prompt_fingerprint": "9f2c1e4b8a7d036f",
    "count": 149
  }
  ```

- **A daily row - two keys:**

  ```json
  {"url_key": "3f1a...", "messages": [
    {"role": "system", "content": "You are ..."},
    {"role": "user", "content": "Title: ...\n\nArticle: ..."},
    {"role": "assistant", "content": "{\"summary\": \"...\", \"key_points\": [...]}"}]}
  ```

- **A merged `corpus.jsonl` row - four keys:**

  ```json
  {"url_key": "3f1a...", "date": "2026-08-27", "source": "pipeline", "messages": [...]}
  ```

- **The config block:**

  ```json
  "corpus": {
    "min_rows": 500,
    "max_rows": 8000,
    "retain_days": 180,
    "holdout_days": 14,
    "length_min_share": 0.15,
    "reference_rows": 300
  }
  ```

- **Decisions:**

  | # | Decision | Why |
  | --- | --- | --- |
  | 1 | The corpus is a Pydantic model before anything writes one, and `schemas/` is generated from it. | Rule #3. A training set that two tools disagree about is worse than no training set, because the disagreement is silent. |
  | 2 | A daily file carries two keys per row. Everything constant across the file - date, model, prompt fingerprint, count, description, version - lives in the `meta.json` beside it. | One run is one date and one model. Repeating them 149 times is waste, and a header is where a human looks first. |
  | 3 | The merged file carries four: the two above plus `date` and `source`. | A merged file holds many dates and two writers. `date` is how the wrangler prunes by age and holds out by recency; `source` is how it keeps expert-written rows out of the test set. Two extra keys is the floor, not a preference. |
  | 4 | `source` takes exactly two values: `pipeline` and `reference`. | Two tiers exist whether they are named or not - a summary our 8B wrote is not a summary an expert wrote. Two is the number. A gold/silver/bronze taxonomy would invent quality distinctions nothing measures. |
  | 5 | `min_rows` is both the training floor and the delete guard. Row 6 refuses to train below it; the wrangler refuses to prune below it. | Your "never drop below a certain number". One knob, both jobs, so they cannot drift apart. |
  | 6 | `holdout_days` holds out the trailing window by date, never at random. | Production always runs on tomorrow's news, so testing on the past measures a job the model does not have. A random split puts the same story from three feeds on both sides and reports memorisation as success. |
  | 7 | Length diversity is a **warning**, not a quota. `stats` prints the short/medium/long split and warns when any bucket falls under `length_min_share`. | The measured corpus is already 50 percent short, 25 medium, 25 long (2026-08-22, n=20), and pruning by age does not skew length. A quota that reshapes data would solve a problem that has not happened; a warning tells you the day it does. |
  | 8 | **There is no topic or theme knob, and this row does not add one.** | `lenses`, `events` and `entities` are empty on all 1889 published items across all six committed days (verified 2026-08-26, PR #130). A theme-balance knob would read a field nothing writes. Blocked on that Level 5 defect, not on this plan. |
  | 9 | Every number above is a starting estimate, labelled as one, replaced by what row 8 measures (Rule #10). | `min_rows: 500` is a floor to bother at all; the LIMA result puts useful SFT near 1000 curated examples. `max_rows: 8000` is about 54 days of harvest and keeps one Colab epoch bounded. Nothing here is measured yet. |

- **Rejected alternatives:**

  | # | Option | Why rejected |
  | --- | --- | --- |
  | 1 | Hardcode the sizes in the wrangler | Rule #6. These are exactly the tunables config exists for |
  | 2 | Repeat `date` and `model_id` on every daily row | Constant per file. That is what a metadata file is for |
  | 3 | Separate golden / silver / bronze corpus files | Two tiers, one field, one file. Separate files mean a merge step that can silently drop one |
  | 4 | Reserve the first 100 rows of the file as the reference set | Position is not a property. Any merge, sort or prune breaks it and nothing would notice. A field survives all three |
  | 5 | A band quota for training data | Only accepted summaries are harvested at all, so the band filter already happened upstream |
  | 6 | Put the knobs under `evaluation` | Corpus size is not an evaluation threshold. A separate `corpus` block keeps both readable |

## Row #3 - The daily run writes its pairs to a file

- **Scope:** After the day's summaries are written, dump each accepted prompt-and-response pair to `daily/<date>.jsonl` with its `meta.json`, and get both off the runner. This step exists only to fill the dataset; nothing else in the pipeline changes.
- **Files touched:**
  - `backend/idhazh/corpus.py`
  - `backend/idhazh/cli.py`
  - `.github/workflows/digest.yml`
  - `backend/tests/test_corpus.py`
  - `docs/how-to/fine-tune-the-summarizer.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; tests green; no test touches the network; the step cannot fail the digest; nothing new appears in a committed path.
- **Oracle:** Run the harvest over a fixture day. `git status --porcelain` shows no change, and both files validate against the row 2 schemas.
- **Decisions:**

  | # | Decision | Why |
  | --- | --- | --- |
  | 1 | `messages` is the standard three-turn chat shape: system, user, assistant. | TRL, Unsloth, Axolotl and LLaMA-Factory all read it as-is. No converter to write. |
  | 2 | The system and user turns are the exact bytes production sent; the assistant turn is the exact JSON the decoder produced. | A target that differs from what the model already emits teaches it to fight its own output format. |
  | 3 | Only summaries that passed the publish gate are written. | Training on rejected output teaches the model to produce rejected output. |
  | 4 | The step is `continue-on-error`. | A corpus row is never worth a missed digest. |
  | 5 | No per-run row cap. The day writes what the day produced. | 149 rows is roughly 450 KB. A cap would discard data already paid for to save nothing. |
  | 6 | The files leave as a workflow artifact with the shortest retention that lets you pull them. | Least machinery that works. **User's call:** artifacts on a public repository are downloadable by anyone with the run link, and these hold article text. The alternative is the Actions cache - not publicly downloadable, but it needs a second manual export job. |

- **Rejected alternatives:**

  | # | Option | Why rejected |
  | --- | --- | --- |
  | 1 | Commit the corpus | Article bodies in a public repo is the republishing non-goal, and it grows the repo daily |
  | 2 | Store hashes and re-fetch the articles later | Invented problem. The pipeline already holds the text |
  | 3 | Harvest inside the summarize stage | Ties a corpus writer's lifetime to a pipeline stage. A separate step can be run, skipped or re-run alone |

## Row #4 - `data_wrangler.py`: atomic add, surgical delete

- **Scope:** One local command that pulls day files in, merges them without duplicates, removes named rows, splits off the holdout and prints what is there.
- **Files touched:**
  - `backend/utilities/data_wrangler.py`
  - `backend/tests/test_data_wrangler.py`
  - `docs/how-to/fine-tune-the-summarizer.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; tests green; every subcommand runs on a fixture corpus; `remove` prints what it will delete and asks first.
- **Oracle:** Kill the process mid-`add` and the corpus on disk is either the old one or the new one, never a partial one. Merge a day into itself twice and the row count does not move. `remove` a `url_key` and every other row survives byte-identical.
- **Decisions:**

  | # | Decision | Why |
  | --- | --- | --- |
  | 1 | **Atomic add.** Writes the new corpus to a temp file in the same directory, then renames over the old one, rewriting `corpus.meta.json` in the same move. | A rename is atomic on one filesystem. An interrupted merge can never leave you with half a training set that still looks loadable. |
  | 2 | **Surgical delete.** `remove --url-key <k>`, `remove --before <date>` and `remove --source <s>` drop exactly the named rows and rewrite the rest untouched. It never wipes and regenerates. | Regenerating would need every daily file still on disk, which after `retain_days` is exactly what is not true. |
  | 3 | `remove` refuses to take the corpus under `corpus.min_rows`, and says how many rows short it would land. | The floor guard. A prune that quietly empties the training set is the failure this prevents. |
  | 4 | Subcommands: `add`, `remove`, `split`, `stats`. | These are the four operations. There is no fifth. |
  | 5 | `add` drops a row whose `url_key` is already present, keeping the newer. | The same story arrives from several feeds. Duplicates are wasted compute at best and split contamination at worst. |
  | 6 | `stats` prints row count, date range, the short/medium/long split with its warning, token totals, and the count per `source`. | Before you spend a Colab session you want to know whether you have 400 rows or 4000, whether they are all short articles, and how many are expert-written. |
  | 7 | It runs on your machine, not in CI. | Nothing here needs a runner, and unattended deletion of training data is how you lose it. |

- **Rejected alternatives:**

  | # | Option | Why rejected |
  | --- | --- | --- |
  | 1 | A database | A few thousand JSON lines. A file is the right size of tool |
  | 2 | In-place edit of the corpus file | A crash mid-write leaves a corrupt file that still parses for the first N lines |
  | 3 | Automatic pruning in CI | You find out a month later that it is gone |
  | 4 | Rebuild the corpus from daily files instead of deleting rows | After `retain_days` the daily files are gone. Rebuild is unavailable exactly when it is needed |

## Row #5 - A reference set written by an expert model

- **Scope:** Freeze a sample of articles, have a strong model author the ideal summary for each in our exact output format, and commit them as fixtures split into a training slice and a test slice.
- **Files touched:**
  - `tests/fixtures/reference/`
  - `backend/utilities/data_wrangler.py`
  - `backend/tests/test_reference_set.py`
  - `docs/concepts/evaluation.md`
  - `docs/how-to/fine-tune-the-summarizer.md`
- **Acceptance gates:** Every reference summary validates against `SummaryDraft`; the train slice and the test slice share no `url_key`; the pipeline contains no call to any hosted model; article bodies stay uncommitted.
- **Oracle:** Train/test disjointness, asserted by test. `set(train.url_key) & set(test.url_key)` is empty, and no reference-train `url_key` appears in the row 4 holdout either. A reference summary used on both sides makes the test score meaningless, and this is the only check that catches it.
- **Decisions:**

  | # | Decision | Why |
  | --- | --- | --- |
  | 1 | **Authored once, by hand, offline.** A human uses an expert model in their editor and commits the result. It is never part of a run, and no run ever calls it. | Nothing here is per-run. Refresh it when the prompt changes or the corpus drifts, which is a quarterly job at most. |
  | 2 | It is not hosted inference and it is not LLM-as-judge. | The pipeline calls nothing - this is the same category as writing the summaries by hand, only faster. And a judge *scores an output*; this *writes a target*. Different jobs. |
  | 3 | The reference set is primarily **training data**, not an eval reference. | This is what makes fine-tuning worth doing. Training on our own accepted output can only copy our own model's habits, including its mistakes. An expert-written target teaches it something it does not already do. |
  | 4 | A separate slice is held back as test references, and nothing in it is ever trained on. | See the Oracle. |
  | 5 | `corpus.reference_rows` starts at 300, stratified across length and the brief path, split about 200 train and 100 test. An estimate until row 8 measures it. | The corpus is bimodal, so an unstratified sample would teach the short band and guess at the long one. |
  | 6 | On the held-back slice, BERTScore against the references is a secondary signal. ROUGE-L is recorded and not relied on. | ROUGE-L counts word overlap, so it rewards copying the reference's phrasing rather than being right. BERTScore compares meaning. Both stay behind the blind read in row 8. |
  | 7 | Named limitation: scoring against an expert model's summaries measures "how close to that model", not "how good". | Useful for comparing our base against our tuned model, since both are measured the same way. Not an absolute quality claim. |

- **Rejected alternatives:**

  | # | Option | Why rejected |
  | --- | --- | --- |
  | 1 | Generate references from inside the pipeline | Hosted inference, a project non-goal. Authoring a fixture by hand is not |
  | 2 | Use them for training and testing both | The model would be tested on answers it memorised |
  | 3 | Have the expert model score our summaries instead of writing its own | LLM-as-judge, a project non-goal |
  | 4 | Call this the golden set | `golden_set_size` already means the qualification validation articles. One word, two meanings, is how a config gets misread |
  | 5 | Use CNN/DailyMail or XSum as references | Near-certainly inside Qwen3's pretraining, so the number is contamination. And it is not our corpus, our bands or our format |

## Row #6 - Train the 8B adapter on Colab, merge with llama.cpp

- **Scope:** A committed notebook that trains a LoRA adapter on Qwen3-8B, plus a local merge and quantise step that does not need a large-memory machine.
- **Files touched:**
  - `notebooks/finetune-summarizer.ipynb`
  - `docs/how-to/fine-tune-the-summarizer.md`
  - `docs/reference/measurements.md`
- **Acceptance gates:** The corpus holds at least `corpus.min_rows` rows before training starts; the notebook runs top to bottom on the free tier; every hyperparameter is in one cell at the top; the output is a Q4_K_M GGUF with its SHA-256 and byte count printed; the actual GPU, wall-clock and cost are recorded (Rule #10).
- **Oracle:** Loss-mask arithmetic, checked before training starts. The share of tokens contributing to the loss must equal the assistant-turn share. Measured 2026-08-24 on run `32742672105`, the median article ran 1651-2694 tokens against a median summary of 233-316 - about eight input tokens per output token. Without the mask, roughly 89 percent of the training signal goes into learning to write other people's news articles, which is not the job.
- **Decisions:**

  | # | Decision | Why |
  | --- | --- | --- |
  | 1 | Fine-tune Qwen3-8B first. Distillation is row 9, after this is proven. | Two changes at once means a regression cannot be attributed to either. And a distillation teacher that has already been improved is a better teacher. |
  | 2 | QLoRA, not a full fine-tune. | The base already knows how to summarize. It needs our house rules, which is a small change to a large model. |
  | 3 | Train on the assistant turn only. | See the Oracle. |
  | 4 | **The free tier is enough, because the merge moves off Colab.** Download the adapter - about 100-200 MB - and fold it in locally with llama.cpp's `llama-export-lora`, then quantise. | The usual path loads the whole 8B at 16-bit to merge, which wants about 16 GB of ordinary RAM against free Colab's 12 GB, so training succeeds and the save step dies. llama.cpp streams from disk and does not have that problem. It is also the toolchain already in `backend/bin/`. |
  | 5 | Free-tier T4 must train in `fp16`, not `bf16`. Enable loss scaling and watch for a loss that goes to NaN. | The T4 is a Turing card and has no `bf16` support. This is a real failure mode, not a theoretical one. An L4 or A100 on Pro avoids it. |
  | 6 | **TPU is not an option.** | 4-bit quantisation is CUDA-only. There is no working QLoRA path on a TPU. |
  | 7 | The GPU does not change what the model learns. | The trained weights are the artifact and they run identically on our CPU runner. The GPU decides how long training takes and whether it fits. `fp16` against `bf16` is the only real difference, and that is decision 5. |
  | 8 | Starting settings, all estimates until a run measures them: LoRA rank 16, alpha 32, dropout 0.05, all linear layers; learning rate 1e-4 to 2e-4, cosine, 3 percent warmup; 2 epochs; batch 1 with gradient accumulation to an effective 8-16; gradient checkpointing on; sequence length 8192. | 8192 matches the runtime's `n_ctx`. 4096 would truncate real items: the system prompt alone is 877-879 tokens (measured 2026-08-23), the article cap is 2500 and `max_output_tokens` is 900. |
  | 9 | Rough training time, all estimates: about 7 hours on a free T4, about 3 on an L4, about 1 on an A100, for 2000 examples over 2 epochs. | Recorded so you can pick a tier. Replaced by a measurement after the first run. A free session that disconnects is why checkpointing to Drive is in the notebook. |
  | 10 | The notebook is committed; the weights are not. | A notebook is a few kilobytes of instructions. Weights belong in row 7. |

- **Rejected alternatives:**

  | # | Option | Why rejected |
  | --- | --- | --- |
  | 1 | Train in CI | No GPU, 4 vCPU, 6-hour ceiling |
  | 2 | Train on the developer machine | An i7-1265U with no GPU |
  | 3 | Merge inside Colab with `transformers` | Wants about 16 GB of system RAM for an 8B at fp16 and free Colab gives about 12 |
  | 4 | Ship the adapter and load it at runtime instead of merging | llama.cpp can do it, but it adds a second file to the config, the cache and the fingerprint. A single merged GGUF keeps the swap a four-line config edit |
  | 5 | Full fine-tune | More memory for a gain nobody has measured on a format task |
  | 6 | Train the model to emit valid JSON | The constrained decoder already guarantees it |
  | 7 | DPO or RLHF | They need preference pairs, which do not exist. SFT first, and it may be enough |

## Row #7 - Give the GGUF a home the config can point at

- **Scope:** Publish the fine-tuned GGUF to a public Hugging Face repository we own, and point the config at it.
- **Files touched:** `config/idhazh.json`, `docs/how-to/fine-tune-the-summarizer.md`, `docs/reference/measurements.md`
- **Acceptance gates:** A public repo under a licence compatible with Qwen3's Apache-2.0; the upload commit recorded as `revision`; the SHA-256 in the config matching the bytes the resolve URL serves, read from the git-LFS pointer at that commit and not from the `ETag`.
- **Oracle:** A clean checkout with the config pointing at the new model downloads and starts it with no code change and no new secret. If anything but `config/idhazh.json` has to move, the row is not done.
- **Decisions:**

  | # | Decision | Why |
  | --- | --- | --- |
  | 1 | Upload to our own public Hugging Face repo. This needs **no new code and no new secret**. | Verified: `.github/workflows/digest.yml` lines 124-137 read `repo`, `revision` and `file` out of `config/idhazh.json` and download anonymously. The only secret in any workflow is `GITHUB_TOKEN`. A public repo we own drops straight into the shape PR #135 built on 2026-08-26. |
  | 2 | The whole swap is four lines - `repo`, `revision`, `file`, `sha256` under `models.summarize`. | That is the production requirement you named. It was already met for third-party models; this row only gives our own weights an address. |
  | 3 | The container analogy holds. `repo` plus `revision` is image plus digest: pinned to an immutable commit, then verified byte-for-byte by SHA-256. | Same guarantee, and the SHA-256 check is stricter than a tag, which can move. |
  | 4 | Public, not private. | A private repo would need an `HF_TOKEN` secret in three workflows and in every fork. Public costs nothing and keeps the download anonymous. |
  | 5 | A write token is needed once, on your machine, for the upload. It never goes near CI. | Upload is a human action. CI only ever reads. |
  | 6 | Read the SHA-256 from the git-LFS pointer at the commit, not the `ETag`. | The resolve URL's `ETag` is a Xet content hash. It looks exactly like a sha256 and is not one. PR #135 records this trap. |
  | 7 | Size is a swap, not an addition: the tuned Q4_K_M 8B is about the same 4.68 GiB as the file it replaces. | The cache stays inside the 10 GB repo limit because the old entry ages out. |
  | 8 | Named cost: uploading about 4.7 GB over home broadband takes a while, and Colab's disk must hold the merged file before it moves. | The only real friction in this row. Neither is a blocker. |

- **Rejected alternatives:**

  | # | Option | Why rejected |
  | --- | --- | --- |
  | 1 | Commit the GGUF to this repo | About 4.7 GB, against a 1 GB site cap |
  | 2 | A GitHub Release asset | Works, but the config speaks repository-plus-revision. A Release needs new download code in three workflows |
  | 3 | A private HF repo | An `HF_TOKEN` secret in three workflows, and in every fork, for weights that are an Apache-2.0 derivative anyway |
  | 4 | Keep it on the operator's disk | Then CI cannot run it and nobody else can reproduce it |

## Row #8 - Judge the tuned 8B and decide

- **Scope:** Put the stock and tuned 8B side by side on held-out articles, read them blind, score against the test references, run the existing gates, and decide.
- **Files touched:**
  - `backend/utilities/compare_models.py`
  - `docs/how-to/fine-tune-the-summarizer.md`
  - `docs/reference/measurements.md`
- **Acceptance gates:** Both models see identical input bytes; articles come from the holdout and the reference test slice only; model identity is hidden until after you decide; the tuned model runs through `python -m idhazh qualify` unchanged, with no gate threshold edited.
- **Oracle:** The eleven existing gates, unmodified, plus your verdict on about 20 blind pairs, plus BERTScore against the test references. A gate that had to be loosened to let the model through is a failed row, not a passed one.
- **Decisions:**

  | # | Decision | Why |
  | --- | --- | --- |
  | 1 | The blind read is the decider. BERTScore against the references is the supporting number. | No metric can answer "is this better writing". A metric can tell you whether the two models differ enough to bother looking. |
  | 2 | About 20 pairs, identity hidden. | Enough to see an obvious difference in an afternoon. **What you give up:** it shows a big difference, not a small one. That is the right trade - if fine-tuning only moves things a little, do not adopt it. |
  | 3 | Holdout and reference-test articles only. | Reading the model's own training examples back to it tells you nothing. |
  | 4 | The eleven gates still run, unchanged. | They are absolute safety checks - schema validity, no leaked reasoning, injection canaries, determinism, context fit. A better-reading model that fails a canary is not better. |
  | 5 | HHEM is read afterwards as a warning light, never as the decider. | It is the production alarm. Pick models by it and it can no longer warn you about the model you picked. |
  | 6 | "Keep the stock 8B" is an expected outcome, and it does not block row 9. | You may fine-tune and not adopt. If the tuned model is not better, row 9 distils from the stock 8B instead and only chases speed. |

- **Rejected alternatives:**

  | # | Option | Why rejected |
  | --- | --- | --- |
  | 1 | Decide on average HHEM | A model raises it by copying more or writing less. Both are worse summaries |
  | 2 | Decide on ROUGE-L | Word overlap with the reference. It rewards phrasing, not correctness |
  | 3 | Have a model judge the summaries | A judge with the same blind spots agrees for the wrong reasons. Also a project non-goal |
  | 4 | Sixty hand-labelled examples and a calibration study | About ten hours to detect a difference a blind read of twenty pairs would already show if it were worth adopting |
  | 5 | Adopt automatically on passing gates | The gates report safety, not quality |

## Row #9 - Distil the tuned 8B into the 4B and decide

- **Scope:** Train Qwen3-4B on the tuned 8B's outputs over a large corpus, then judge it the same way as row 8.
- **Files touched:**
  - `notebooks/distil-summarizer.ipynb`
  - `backend/utilities/compare_models.py`
  - `docs/how-to/fine-tune-the-summarizer.md`
  - `docs/reference/measurements.md`
- **Acceptance gates:** The teacher is the row 6 model, named by SHA-256; the student passes the same eleven gates; the measured production decode rate is recorded with hardware, date and spread; the same blind read as row 8.
- **Oracle:** Speed measured where it matters, not on a bench. The student must show its gain in a real shard with the faithfulness scorer resident and the real worker population, not only in `llama-bench`. The 8B benched at 7.28 tok/s decode and delivered 5.05 in production - a 31 percent gap - so a bench number alone would overstate the prize.
- **Decisions:**

  | # | Decision | Why |
  | --- | --- | --- |
  | 1 | Student is Qwen3-4B. Teacher is the tuned 8B from row 6. | The 4B is already `models.route` in the config, so its runner fit is measured and its cache entry exists. A tuned teacher passes on what row 6 bought. |
  | 2 | The prize is speed. Measured 2026-08-22 on EPYC 9V74 at 4 threads, the 4B decodes at 13.00 +/- 0.03 tok/s against the 8B's 7.28 +/- 0.01 - about 1.8x. The 8B delivered 5.05 tok/s in production on 2026-08-24, so a 4B could plausibly land near 9. That last figure is an estimate until this row measures it. | The digest is decode-bound. Weights are 2.33 GiB against 4.68 GiB, and every token streams them. |
  | 3 | Sequence-level distillation: train the student on the teacher's outputs. Not logit matching. | Logit matching is better in principle and needs both models resident with aligned tokenizers. On a free notebook that is not a trade worth making for a format task. |
  | 4 | Distillation wants far more data than row 6 did. Run the tuned teacher over the archive to generate it, and add it with `source: pipeline`. | Style transfer needs hundreds of examples; capability transfer needs thousands. The teacher generates them for free, and `max_rows` bounds how many are kept. |
  | 5 | Expect a quality drop and measure it. The 4B is half the size and distillation narrows the gap rather than closing it. | Stated up front so a small drop is a decision rather than a surprise. |
  | 6 | "Keep the 8B" is an expected outcome. | If the speed is real but the summaries are visibly worse, the digest is not on a deadline. |

- **Rejected alternatives:**

  | # | Option | Why rejected |
  | --- | --- | --- |
  | 1 | Distil straight from the stock 8B, skipping row 6 | Throws away whatever row 6 bought, and makes two goals into one unattributable change |
  | 2 | Distil into the 0.6B or 1.7B | Not screened. The 4B already has measured runner fit and a cache entry |
  | 3 | Fine-tune and distil in one training run | A regression could not be attributed to either |
  | 4 | Judge the student on `llama-bench` alone | See the Oracle. The bench overstated the 8B by 31 percent |
