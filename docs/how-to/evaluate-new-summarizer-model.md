# Swap the Summarizer Model

**Last Updated**: 2026-09-22
The swap is one line in `config/idhazh.json`:

```json
"models_file": "models/qwen3.5-9b-q4km.json"
```

Point it at another file in `config/models/` and everything follows it: the
daily run, the qualification case and the bench all read the entry that file
holds. **The revert is the same line back.**

The rest of this page is what to do before you write that line and what to check
after. It covers the build-time summary model, which also decides the picture.
The faithfulness scorer and the browser search model have their own contracts
and are not changed here.

## What is one command, and what is not

| | |
| --- | --- |
| The swap | one line in the committed config |
| The revert | the same line back |
| The walk | one dispatch, about 106 minutes. It says whether the real path runs at all |
| The bench | one dispatch. It says how fast |
| The qualification | one dispatch, hours of runner time, ten gates on a frozen corpus. It says how good |
| The decision | a person's, and it stays one |

**Qualification will never be one command.** Ten gates on a frozen corpus is
the price of knowing whether a model is good, and no arrangement of the harness
makes that cheap. What the harness buys is that the price is paid the same way
every time.

Adoption is a Level 5 decision ([../../CLAUDE.md](../../CLAUDE.md) section 6).
The gates inform it; they do not make it.

Three blocks follow: **measure the candidate**, **adopt**, **revert**.

---

## The cheapest check is the pipeline tests, and it uses the real prompts

Reach for `idhazh-pipeline-tests.yaml` first. It draws two real articles and
runs the production path over them - the real fetcher, the real extractor, the
real prompts, the real two calls, the real model server - and it takes a models
file, so it runs that path on a candidate:

```bash
gh workflow run idhazh-pipeline-tests.yaml \
 --ref '<the branch holding the candidate file>' \
 -f candidate_models_file='models/<name>.json'
```

Type nothing and it runs the configured model, which is what it did before the
field existed.

**What it costs.** One dispatch took 106 minutes on 2026-09-15 - three cases
over two articles, of which 105 minutes were the cases themselves and under a
minute was setup. One dispatch, so there is no spread. A bench dispatch of
`measure.yml` on 2026-09-16 took 189 minutes, and one of the four that day took
288. A candidate is always a cache miss, so it pays its own download: the same
fetch in `Model validation` took 25 to 74 seconds on 2026-08-26, which is about
one percent of the dispatch.

**What it settles.** Whether the weights load, whether the server serves the
alias the config names, whether both calls come back inside the schema, and what
one article costs end to end on a stock runner. A model that cannot do those
things has failed, and it has failed for 106 minutes rather than for 189.

**What it does not settle, and this is the larger half.** Two articles say
nothing about quality. There is no gate, no frozen corpus, no repeat, no
faithfulness scorer, and no comparison against the incumbent's recorded numbers.
A green dispatch is permission to spend the bench and the qualification, never a
substitute for them. It publishes nothing either: what the cases produced leaves
as a 90-day artifact.

The workflow is described in
[../reference/github-actions.md](../reference/github-actions.md#pipeline-tests).

---

## Block 1 - Measure the candidate

```mermaid
%%{init: {"theme": "base", "themeVariables": {"background": "#0f1117", "primaryColor": "#222834", "primaryTextColor": "#e6e9f0", "primaryBorderColor": "#4b5468", "lineColor": "#8b93a7", "textColor": "#e6e9f0", "clusterBkg": "#1a1e27", "clusterBorder": "#3a4254", "titleColor": "#e6e9f0", "edgeLabelBackground": "#1a1e27", "fontSize": "14px"}}}%%
flowchart TB
 subgraph FACTS["1.1 - read the facts, never recall them"]
  HUB["the hub's own API<br/>commit, SHA-256, byte count"] --> FILE
  HDR["the GGUF header itself<br/>general.architecture"] --> FILE
  TMPL["the model's chat template<br/>the four turn markers"] --> FILE
  FILE[("config/models/NAME.json")]
 end

 subgraph BENCH["1.3 - Measurements, measure.yml target bench"]
  FILE --> RAW["case one: raw throughput<br/>llama-bench, no server"]
  RAW --> SERVE["case two: a real server<br/>five fixed articles"]
  SERVE --> DOSSIER["a dossier body,<br/>ready to paste"]
 end

 subgraph READ["1.4 - measure.yml target budgets"]
  FILE --> BUDGETS["target budgets<br/>three tokenizer readings"]
 end

 subgraph QUAL["1.5 - Model validation, validate.yml"]
  FILE --> SCRATCH["scratch config:<br/>the committed tree,<br/>models_file moved"]
  SCRATCH --> PROVE{"server proves<br/>five claims?"}
  PROVE -->|"no"| STOP["stop before the first item"]
  PROVE -->|"yes"| REPLAY["freeze a corpus,<br/>replay it three times"]
  REPLAY --> GATES{"every gate green?"}
 end

 subgraph CALL["1.6 - Decide"]
  DECIDE{"a person reads<br/>the gates"} -->|"adopt"| ADOPT["Block 2:<br/>move models_file"]
  DECIDE -->|"no"| REJECT["not adopted"]
 end

 DOSSIER --> DECIDE
 BUDGETS --> DECIDE
 GATES -->|"yes"| DECIDE
 GATES -->|"no"| REJECT

 classDef stage fill:#222834,stroke:#4b5468,stroke-width:1px,color:#e6e9f0;
 classDef decision fill:#11141c,stroke:#5b6477,stroke-width:1.5px,color:#ffffff;
 classDef yes fill:#176032,stroke:#2ea04f,stroke-width:1.5px,color:#ffffff;
 classDef no fill:#a32020,stroke:#d23b3b,stroke-width:1.5px,color:#ffffff;
 classDef store fill:#1b3a5c,stroke:#2d6ca3,stroke-width:1.5px,color:#ffffff;
 classDef ext fill:#2a2233,stroke:#6b5480,stroke-width:1px,stroke-dasharray:5 3,color:#e6e9f0;
 classDef sysEval fill:#1a1e27,stroke:#c79a2e,stroke-width:1.5px,color:#f0d79a;
 classDef sysOps fill:#1a1e27,stroke:#8b93a7,stroke-width:1.5px,color:#c8cdd8;

 class RAW,SERVE,DOSSIER,BUDGETS,SCRATCH,REPLAY stage;
 class HUB,HDR,TMPL ext;
 class PROVE,GATES,DECIDE decision;
 class FILE store;
 class ADOPT yes;
 class STOP,REJECT no;
 class FACTS,CALL sysOps;
 class BENCH,READ,QUAL sysEval;
```

**Every node sits inside a box, and that is deliberate rather than tidy.** A box
paints the surface the palette assumes, so a node left outside one is drawn on
whatever the page behind it happens to be - fine on a dark page, and a dark
node stranded on white anywhere else.

**The three dashed boxes are somebody else's.** Every fact in 1.1 is read out of
the model publisher's own bytes rather than out of a model card or a memory, and
that is the whole reason the first step is not "fill in the form".

### 1.1 Write the candidate's model file

A candidate is a file under `config/models/` before it is a dispatch. Copy the
incumbent's file, rename it for the new weights, and change every field that is
a fact about them.

| Field | Why it is there |
| --- | --- |
| `id` | the alias published summaries and the ledger carry |
| `repo`, `revision` | the repository and the 40-character commit. A branch name is not a pin, because `main` moves |
| `file`, `quantisation` | two files from one model are two candidates |
| `sha256` | the runtime opens bytes, not a model-card name |
| `byte_count` | the size the hub reports, cross-checked against the file the run opened |
| `hf_base_repo` | the base an adapter is trained against, which the fine-tuning notebook checks |
| `arch` | the architecture name inside the GGUF |
| `inference` | every runtime knob, including the window and the sampler |
| `turns` | where the system text goes, what opens and closes a turn, and which keyword turns thinking off |

#### Where each fact comes from

**None of these is recalled or copied off a model card.** A card is prose a
human wrote; every field below is read out of the bytes the run will open, or
out of the metadata the hub computed from them.

**The commit, the digest and the byte count** come from the hub's own API. The
`lfs.oid` a tree listing returns IS the SHA-256, so no download is needed:

```powershell
$repo = 'publisher/NAME-GGUF'
(Invoke-RestMethod "https://huggingface.co/api/models/$repo").sha
Invoke-RestMethod "https://huggingface.co/api/models/$repo/tree/main" |
  Where-Object { $_.path -like '*.gguf' } |
  ForEach-Object { '{0}  size={1}  sha256={2}' -f $_.path, $_.size, $_.lfs.oid }
```

**`arch` is read out of the GGUF itself, not inferred.** `general.architecture`
is the first key in the header, so a range request for the first megabyte
answers it - a few kilobytes of transfer against five gigabytes of weights. Read
it rather than guessing from the family name: Gemma 4's main weights read
`gemma4` and its MTP head reads `gemma4-assistant`, which are two different
answers from one repository. Row #5's fourth case compares this field against the
file the server opened, so a wrong value fails the run rather than degrading it.

**The four turn markers come from the model's own chat template**, which the
publisher ships as `chat_template.jinja` in the safetensors repository. Read the
literals it emits - the strings inside `{{- '...' -}}` - rather than assuming a
family convention. Two traps, both seen: a model can share an architecture with
the incumbent and still write different markers, and a template can change
between major versions of the same model. Gemma 3 had no system role; Gemma 4
emits `<|turn>system`, so `system_role` is `own_turn` for it and
`fold_into_first_user` would have been wrong.

**When in doubt, let the start-up probe settle it.** The five claims in 1.5 are
checked against the running server before the first item, so a marker read wrong
here refuses the shard with a named cause instead of quietly producing worse
summaries. That is the difference between a guess that costs a dispatch and a
guess that costs a month of degraded output.

**`inference` is the one block with no external source, and one external
ceiling.** Nothing about a candidate has been measured yet, so start from the
incumbent's numbers with the window matched - a throughput comparison at two
different windows measures the window, not the model - and let 1.3 and 1.4
replace them with readings. The ceiling is `max_position_embeddings` in the base
repository's `config.json`: a candidate whose base declares less than the window
you were going to match cannot be compared like for like, and the only other
place that fact turns up is a server that quietly serves a shorter context than
the entry asked for. Both candidates written on 2026-09-14 cleared it with room
- 262,144 and 131,072 against a matched 65,536.

**`declared_for` is the safety catch, and it holds this model's own digest.**
Config load refuses an entry whose
block is declared for one set of weights while the entry names another, and it
says which repair it wants: re-derive the numbers, because every one of them was
measured against one model on one runner, or re-record the markers, because
every one of them was read off the server that renders those turns. So a
half-finished candidate cannot run - not in the bench, not in qualification, and
not in a daily run.

The sanitizer reads `turns` too. It proves it strips every marker the entry
declares and **refuses an entry whose control tokens it does not recognise**, so
a model from an unknown template family is a refused config rather than a silent
hole in Guardrail #11.

Do not point `models_file` at the new file yet. Nothing below needs it, and
keeping the pointer still means the adopt arrives later as a one-line diff a
reviewer can read at a glance.

### 1.2 Hold the control

One changed input a run, or the run measures a bundle. Hold constant:

- the llama.cpp build;
- the prompt template and the rendered band values;
- the output schema;
- the extraction and sanitization versions; and
- the truncation cap.

The candidate's own `inference` block is not a control - it is part of the
candidate. If a model needs a different sampler to work at all, that is a second
candidate configuration and it is measured separately. Do not adopt a vendor
default silently.

### 1.3 Bench it - how fast

One dispatch, two cases, and one field naming the candidate:

```bash
gh workflow run measure.yml \
 --ref '<the branch holding the candidate file>' \
 -f target=bench \
 -f candidate_models_file='models/<name>.json' \
 -f threads='4'
```

**`--ref` is what lets a candidate be measured before it is merged.** The
dispatch reads the file out of the ref it runs on, so the candidate file only
has to be committed and pushed - not on `main`. That matters because the reading
is what decides whether the file is worth keeping: merging first would put an
unmeasured candidate in the tree, and a candidate that measures badly is then a
revert rather than a closed pull request. Omit `--ref` and the run reads `main`,
which is right for a re-measurement of something already adopted.

**The file is the only thing the form asks for.** Write the candidate's
`config/models/<name>.json` first and commit it - the repository, the
40-character commit, the weights filename, the SHA-256, the byte count, the
alias and the quantisation all live there, and the dispatch reads them out. A
form that asked for them again was a second copy of the same seven facts, and
two copies can disagree: the bench measures one set of bytes, the adoption
points at another, and every gate is green.

Leave the box empty and the bench measures the model `config/idhazh.json`
already points at. That is the calibration dispatch: the page it emits has to
reproduce that model's committed dossier inside the spread both sides declare.

The digest in that file is not optional. Without it the harness benches whatever
the repository holds today and says nothing about it, and a number filed under a
model that never ran is worse than no number (CLAUDE.md Guardrail #10).

**One box, because the file you wrote in 1.1 already holds the answer.** Both
dispatches used to repeat six or seven fields the model file carries - and two
copies of the same facts can disagree, which means benching one set of bytes and
adopting another with every gate green. They now take the models file and read
the rest out of it, which is the same string the swap itself writes.

**Case one can be turned off, and a model evaluation never turns it off.** Add
`-f model_speed_case=skip` and the `llama-bench` job does not run: the dispatch
loses the prefill and decode rates, the `bench-raw` artifact, and the raw-case
block of the dossier, and case two runs on regardless and says in the dossier
that the block is missing and why. That is between a tenth and a third of the
dispatch - 9.1 to 87.6 minutes of the four measured on 2026-09-16
([../reference/benchmarks/what-a-bench-dispatch-costs.md](../reference/benchmarks/what-a-bench-dispatch-costs.md)).
It exists so somebody changing the workflow can exercise the flow without paying
for a measurement nobody will read. A candidate adopted on a dossier with no
raw-case block has not been measured on the axis this step exists to measure, so
leave the box alone here. `bench.run_model_speed_case` in `config/idhazh.json` is
the same switch for every dispatch.

**Case one, artifact `bench-raw`** - raw prefill and decode with nothing else in
the process:

- `hardware.txt`: CPU topology, cgroup limits and runtime identity;
- `weights.txt`: exact GGUF size and SHA-256;
- `llm.json`: prefill and decode rates with spread;
- `resources.json`: wall time, CPU pressure, throttling and memory events.
 Cgroup `memory.peak` can be absent or cumulative; it is not a per-model RSS
 comparison; and
- `bench/raw-case.json`: the same numbers as readings, which is what case two
 folds into the page.

**Case two, artifact `bench-server-<runtime_candidate>`** - a real llama-server,
real fetches, real summaries over a fixed corpus of `bench.corpus_items`
articles, which is **three** in `config/idhazh.json` today:

- `runtime-summary.json`: per-repeat startup, work and per-item timings, the
 resident-set samples, the input and output drift verdicts, and **the summary
 each candidate wrote** - title, summary and key points, beside the digest of
 each;
- `cache-state.txt`: whether the weights were already on the machine, and the
 digests of the binary and the weights that ran;
- `readings.json`: every quantity the page carries, machine-readable; and
- `dossier.md`: **the page body, numbers already in it.** Paste it into
 `docs/reference/models/<model>.md`. It is also printed to the run summary, so
 the numbers are readable without downloading anything.

**The summary text is in the artifact from 2026-09-17, and it is the only
evidence here a person can judge directly.** Until then the sweep kept the output
digest and the token counts and threw the prose away, so four dispatches proved
that a candidate wrote something different and left nothing to read. Owner
approval, 2026-09-16. The corpus times the repeats times two candidates is about
17 KB of text at the median and 36 KB at the worst article this project has
published, against a 500 MB artifact ceiling - so it needs no retention knob and
has none.

**It is a bench artifact and it reaches no reader.** Nothing writes it into the
published tree; it is our own words about a source, and it stays a value in one
JSON file rather than an argument, a path or a URL (Guardrail #11).

The bench never writes the committed config, never publishes, and never grades a
summary. It says how fast, not how good.

**One thing a bench dispatch does commit, from 2026-09-17: the machine it drew.**
One row lands on `main` under
`state/pipeline-tests/host-fingerprint/<YYYY>/<MM>/<DD>.csv`, and nothing else
from the dispatch is written back. A bench reading is about a machine, and until
that date the processor it ran on expired with the artifact. The rows are kept
apart from the daily run's for the reason on
[../reference/host-metrics.md](../reference/host-metrics.md#design-rationale).

Two readings are cold on purpose. The **first download** is what a cache miss
costs, which is what the first run after a swap draws on every shard at once.
The **first server start of the job** is the model load with the page cache
holding none of the weights; every start after it is warm. Averaging the two
would hide the one that hurts.

What the resident-set rows do not say is how much of the peak is anonymous and
how much is file-backed pages the kernel can drop, so they cannot answer how
much headroom a second process has. `Rss_Anon` and `Rss_File` from
`/proc/<pid>/smaps_rollup`, sampled by the same thread that already samples
`VmHWM`, would settle it. It is unmeasured today and nothing gates on it.

To compare one dispatch against another, compare the readings rather than the
prose:

```bash
python backend/utilities/measure_llm.py compare \
 --observed <new>/readings.json \
 --declared <baseline>/readings.json
```

A quantity reproduces when the two values are closer than the two spreads added.
A reading taken once carries no spread, so it is printed rather than judged.

**Two dispatches are two machines, and that is usually the larger effect.**
GitHub puts each job where it likes. On 2026-09-15 two dispatches of the same
weights differed by 8.8 percent on the same `llama-bench` decode test, on
machines both reporting EPYC 7763 - so a 5 percent difference read across two
runs says nothing at all. **When the question is what one setting is worth,
dispatch a paired case instead**: `runtime_candidate` alternates a baseline
against a named variant inside one job, on one machine, which cancels the
machine.

```bash
gh workflow run measure.yml --ref <branch> \
 -f target=bench \
 -f candidate_models_file='models/<name>.json' \
 -f runtime_candidate=kv_q8 \
 -f runtime_repeats=2
```

`runtime_repeats` is 2 here and not 3 to buy a cheaper dispatch, and it is not a
correction to the knob. Repeats multiply the corpus and the job timeout is what
the product is spent against, so the two numbers sit beside each other in config:
`bench.repeats` is three and `bench.corpus_items` is three, which is six passes
and 236 minutes against a 330-minute timeout (Guardrail #2 - the limit is
GitHub's, so the design is what gives). Leave the input empty to take the knob.

**When the question is not what a setting costs but whether it changes the
words, dispatch a case set.** A named candidate runs the unchanged server and
one variant, and reads the variant against the baseline. A case set runs every
value of one setting and reads them against whichever case has the setting off -
so it runs no baseline at all, because the unchanged server is already one of the
values. **No case set is declared today.** The one that was - four drafted
depths against a server with the head off - went with the draft head on
2026-09-21, and what follows is what declaring another one costs.

```bash
gh workflow run measure.yml --ref <branch> \
 -f target=bench \
 -f candidate_models_file='models/gemma-4-e4b-qat.json' \
 -f runtime_candidate=<case set> \
 -f runtime_repeats=2 \
 -f runtime_corpus_items=2 \
 -f model_speed_case=skip
```

Three of those arguments are load-bearing.

- **`runtime_corpus_items=2`.** Four cases at two repeats is eight passes, where
 a named candidate costs four. At the 13.1 minutes an article the slowest pass
 has recorded, eight passes over the committed three articles is 314 minutes
 against a 330-minute timeout, and two articles is 210. Empty follows
 `bench.corpus_items`, which is sized for a named candidate.
- **`model_speed_case=skip`.** The dossier emitter reads the `baseline` label,
 and a case set writes none. Skipping the speed case skips the emit step with
 it; the sweep, the machine record and the artifact are unaffected.
- **A case set pins `temperature` to 0 for every case, and the dispatch cannot
 overrule it.** Every committed entry runs at 0.2, where the seed decides which
 token is drawn - so two readings of one configuration can differ on the
 sampler alone, and the setting's effect and the sampler's noise arrive as one
 number nobody can split.

#### Breadth comes from several jobs, not a longer one

**Five articles cannot share one job with four cases.** Eight passes over five
articles is about 524 minutes, against a platform ceiling of 360 that no setting
moves (Guardrail #2). So a question that wants more articles than one job holds
is answered by dispatching the same case set several times, each with a
different slice:

```bash
for offset in 0 2 4; do
  gh workflow run measure.yml --ref main \
    -f target=bench \
    -f candidate_models_file='models/gemma-4-e4b-qat.json' \
    -f runtime_candidate=<case set> \
    -f runtime_repeats=2 \
    -f runtime_corpus_items=2 \
    -f runtime_corpus_offset="$offset" \
    -f model_speed_case=skip
done
```

Six articles, three jobs, each about 230 minutes, and they run at once - the
concurrency ceiling is 20 jobs, so three is a queue nobody waits in.

**`runtime_corpus_offset` is what makes them different articles.** The plan is
ranked, so without it all three dispatches take the same top two and report two
articles as six. The plan step caps itself at the slice plus what the slice
skips, so an offset dispatch builds a longer plan and freezes a later window of
it.

**This does not weaken the pairing.** Every case still runs inside one job, so
every case-against-case comparison is on one machine, which is the whole reason
the cases alternate. What crosses jobs is a different article, and no reading
compares one article with another - the text comparison is per article, against
the same article's head-off case.

**A difference between the cases is the reading, not a rejection.** A named
candidate refuses the run when its variant writes different words, because the
question was whether the setting is free. A case set records the difference and
still passes, because the question was whether the words change. Two repeats of
ONE case that disagree is still the model being unstable, and still fatal.

**Every case's prompts and replies land in the artifact**, under
`captures/<case>-<repeat>/`, one file per call per item. That is what to open
when two cases disagree and the digests alone cannot say how.

#### Why the bench corpus is three articles

**Three is a fit, not thrift.** Measured 2026-09-17 over the four dispatches of
2026-09-16 (`35086403868`, `35086407071`, `35086409972`, `35086412536`) on stock
`ubuntu-latest` runners, `n = 4`. A named candidate runs two cases, so three
repeats is six passes over the corpus, and the slowest pass measured took 65.6
minutes for five articles.

| Corpus | Six passes | Of the 330-minute job timeout |
| :--- | ---: | ---: |
| 5 articles | 393.7 min | **119% - the job dies** |
| 4 articles | 315.0 min | 95.5% - no headroom |
| **3 articles** | **236.2 min** | **71.6% - it fits** |

**There is nothing to win outside the model.** In the same four dispatches the
`runtime` job is 69 to 94 percent of the wall clock, prefill is 48.2 percent of
it and decode 49.5 percent; everything else - provisioning, cache restore, digest
verify, corpus build, artifact upload - is 3.06 minutes of 161.0, which is 1.9
percent. So the corpus is the only lever with anything on it.

**What five to three saves is a band, not a point: 28.7 to 37.0 percent of a
dispatch.** The five articles were not equal - 519.7 to 715.8 seconds, a spread
of 1.38 times - and the plan drops by rank rather than by length, so which two go
decides where in the band you land. The saving is also slightly sub-linear,
because fewer items amortise the shared prompt prefix over fewer calls; **that
last clause is an estimate**, and one dispatch at three articles compared against
the same job's per-item prefill would settle it.

**What it costs, named rather than implied.** A per-article output-drift finding
weakens from p = 0.03 at five articles to p = 0.125 at three under an exact
binomial. That is still a finding and no longer an overwhelming one, and it is
the thing this change gives up.

**What it buys beyond time.** Article text drifted on 5 of 15
article-observations across three dispatches - 33 percent, with a 95 percent
range of roughly 15 to 58 percent - and a repeat whose text moved is dropped.
Fewer articles means a better chance a dispatch produces a usable reading at all:
roughly 13 percent at five against 30 percent at three. **That pair is an
estimate under an assumption of independence which is certainly too pessimistic;
the direction is certain and the size is not.**

**The qualification corpus does not move, and must not.** `validate.yml` keeps
30 articles. At 30 a clean canary sweep bounds an undetected defect rate at about
10 percent under the rule of three; at 10 it is 30 percent, and the injection
canaries are the Guardrail #11 control, where "most of them survived" is not a
passing grade. The grader also has a measured length bias of 0.40 (2026-08-29,
117 pairs), so a smaller qualification corpus would preferentially drop the long
tier - exactly where the instrument is already known to be wrong.

**The pairing is worth far more than the corpus, so nothing here touches it.**
The bench alternates baseline and candidate inside one job, on one machine. The
same comparison made across two dispatches needs 17 to 66 dispatches before its
median is worth quoting, because two dispatches are two machines. Cutting the
corpus keeps the pairing intact; cutting the pairing to afford a bigger corpus
would trade a reading for a rumour.

Set it in `config/idhazh.json` under `bench.corpus_items`. The workflow reads it,
and nothing in the tree spells the number twice.

**A repeat whose article a publisher edited is dropped, not fatal.** Every
repeat refetches, and a news page moving inside a multi-hour job is ordinary: on
2026-09-15 it happened to two of five articles on both of two dispatches. The
bench times the largest set of repeats that read the same text, names the rest
in `problems` as `input_drift_dropped`, and records `repeats_timed` beside
`repeats` so the dossier says which denominator it had. It refuses the run only
when an case has fewer than two agreeing repeats left, because a median over one
reading is not a reading.

**Dropping a repeat is the answer, and freezing the text was declined.** The
alternative was to keep repeat 1's articles and replay them, which is what
`idhazh qualify` already does and the reason its own docstring gives for existing.
The bench could not do it today in any case: replaying needs `stage_work` to
accept an article it already holds, and no stage exposes that - a stage contract
change rather than a workflow one. The owner declined it on 2026-09-16 for a
reason that outranks the cost: **text changing is how the real world works**, so a
bench that never meets an edited page measures a world the pipeline does not run
in. So a repeat that read edited text is dropped rather than replayed, `problems`
names it `input_drift_dropped`, and a long run loses readings a frozen corpus
would have kept. That loss is the price of measuring the live web, and it is paid
rather than hidden.

A laptop result is a laptop result. It can reject a candidate quickly and cannot
select production.

### 1.4 Retake the three readings a vocabulary sizes

Token counts do not transfer between model families, and three constants in
`backend/idhazh/measured.py` are sized by a tokenizer: the taxonomy definition
block, the empty encoding roles, and tokens a word at the truncation cut. Every
window sum in the project is spent at that last one.

```bash
gh workflow run measure.yml -f target=budgets \
 -f candidate_models_file='models/<name>.json'
```

The run summary carries a paste block: the three values, their subject and their
date, ready for `measured.py`, plus the dossier section they belong in. On any
box already serving the candidate, the same print is
`python backend/utilities/measure_budgets.py read --runner <where you ran it>`.

Do not paste them while the candidate is still a candidate. **The readings go in
with the swap, not before it**, because a reading names the weights it was taken
against and the repository holds one current reading of each. What tells you
they are due is:

```bash
python backend/utilities/measure_budgets.py check
```

It exits 1 and names every constant whose subject is not the configured model's
digest. After a swap it is red until the paste lands; that is the point of it.

### 1.5 Qualify it - how good

```bash
gh workflow run validate.yml \
 -f candidate_models_file='models/<name>.json' \
 -f shards='3' \
 -f corpus_per_shard='10' \
 -f job_budget_minutes='330'
```

**The form no longer asks how many times each article is replayed.** That count is
`run.qualification_repeats` in `config/idhazh.json`, it is at least three, and the
report names it beside the job bound. `idhazh qualify --repeats` overrides it for
one invocation and is refused below the same floor.

The case builds a candidate config under gitignored
`backend/var/candidate-config` - the committed tree with `models_file` moved and
nothing else touched, so it runs the exact line an adoption later moves - checks
the SHA-256 and the entry's declared byte count **before
the server starts**, freezes each shard's slice and hashes the model-visible
bytes before the first inference call, replays those bytes, interleaves the
repeats so none lands on a warm prompt cache, runs every injection canary on
live candidate calls, and counts every failed call in the denominator. It never
touches the committed config.

**A run always writes its verdict, even when the corpus came out thin.** The
shape `evaluation.qualification_min_per_band` and its two siblings ask for is
recorded on the report as `corpus_shortfalls` and blocks nothing: a length tier
with no articles means the run says nothing about that tier, in either direction,
which is a fact about the measuring stick rather than about the model. The gate
that refuses a run for too little evidence is `scored_denominator`.

Before 2026-09-18 a thin corpus exited before the report was written, discarding
gate verdicts that had already been computed. Four dispatches on 2026-09-17 cost
about eleven hours of runner time and produced no verdict for that reason.

Then read the verdict:

```bash
python -m idhazh qualify-decide
```

The ten gates and what each one refuses are in
[../concepts/qualification.md](../concepts/qualification.md). **Every run asks
every one of them**, and a report missing an outcome is refused by name. There
was an eleventh, `determinism`, which asked whether repeated calls produced
identical words; it was retired on 2026-09-18 because a summarizer does not need
to say a thing the same way twice, and what a run records instead is a
`wording_spread` diagnostic that blocks nothing. Three gates are
hard in a way worth repeating here, because they are the ones a fast model
fails:

- **every injection canary survives**, all of them, not most (Guardrail #11);
- **no reasoning text reaches the reply** - no non-empty `reasoning_content`, no
 inline `<think>` block, and the parser reads every block, so an empty opening
 one cannot hide a second that reasoned; and
- **the whole corpus is scored** - `scored_denominator` refuses a verdict drawn
 from fewer items than the run planned.

**Do not raise a timeout or lower a threshold to make a candidate pass.** Find
the cause or reject the candidate. **And do not read the missing `determinism`
row as one of those**: the gate did not move, it was not asked, and a run that
pins temperature 0 gets it back unchanged.

**You do not have to download an artifact to read any of this.** Each qualify
shard prints what it measured to its own job page, and `decide` prints the gates
it asked with failures first, counting the ones it asked rather than the whole
register. Both pages are rendered from the payload the stage already wrote, so
nothing there is a second measurement that could disagree with the artifact -
and neither page spells a model name, so it cannot describe a model the run did
not serve.

What the shard page carries that the gates do not: **which articles the sampler
worded more than one way**. `wording_spread` reports a count, and a count sends
the next reader to the artifact to diff digests by hand. The shard page names
them. Nothing there is a defect - above zero temperature a second wording is the
sampler working, and no gate reads it.

Both steps run under `if: always()`, on purpose. A run that died half way is
exactly the one whose counts somebody wants, and `decide` exits non-zero on an
ESCALATE - which is precisely the verdict the reader opened the page for.

**When a page is not enough, the run kept the text.** Each shard uploads
`captures-<shard>`: every prompt sent and every reply received, one file per
call per item per repeat, for 30 days. That is what to open when a score is bad
and the page cannot say why - a count never can.
[analyze-a-pipeline-artifact.md](analyze-a-pipeline-artifact.md) is the
procedure. Note what it costs: a prompt carries the article body, this
repository is public, and GitHub asks only for read access to download an
artifact (owner decision, 2026-09-18).

### 1.6 Decide

**Register the rule before you look at the outputs.** For every deterministic
hard metric, write down the direction, the paired statistic and the tolerance
first. No generic "no regression" threshold exists, and one invented after the
numbers are visible is a description of the numbers.

Compare: summarize success rate and failure codes; mean HHEM and HHEM-full;
unsupported numbers; dropped hedges; lead coverage; extractiveness and longest
verbatim run; compression; word-band compliance; generated-title fallback rate;
brief, abstract and truncated handling; and a human blind review of the same
source-summary pairs. Compression is a recorded diagnostic and never a
pass/fail.

**HHEM alone is insufficient.** A model can raise faithfulness by copying more
or by writing less. It is the production alarm, so it screens and does not
select:

- fewer than `evaluation.validation_articles` scored outputs -> no verdict;
- gain below `evaluation.validation_switch_margin` -> no automatic switch; and
- gain at or above the margin -> `switch_and_pause`.

**A model swap is a new series, not a new point on the old one.** Segment every
model-dependent metric by `model_id` and do not recompute a long run's date
between plan, model runs and decision.

What the decision still cannot have: the human label queue records one summary's
support verdict and cannot record paired informativeness, title quality or
key-point correctness. Until a typed pairwise label shape and a human-paced CLI
exist, a blind human review can describe a trade and cannot name a winner.

**The owner can approve a model for reasons outside the automated margin**
([../../CLAUDE.md](../../CLAUDE.md) section 0). Record the approval and the
measured trade in the pull request and in the living docs. A failing gate stays
failing and stays written down - do not re-score a run or move a threshold to
make an approval look automatic. That has happened once, and what it left is in
[../concepts/evaluation.md](../concepts/evaluation.md).


---

## Block 2 - Adopt

### 2.1 The line

```json
"models_file": "models/<candidate>.json"
```

That is the swap. No workflow changes: `digest.yml`, `validate.yml` and
`measure.yml` each follow the pointer and read the entry it names, and a test
refuses a model repository, a weights filename or a moving revision written into
any of them.

### 2.2 The two status lines

What is in force is printed by two commands, and they are the check that the
edit did what you meant:

```text
git grep -n '"models_file"' -- config/idhazh.json
git grep -n -E '"(id|file|sha256)"' -- config/models/
```

The first names the active file. The second prints the id, the weights filename
and the SHA-256 the runtime checks the downloaded bytes against.

### 2.3 What else the swap carries

| | |
| --- | --- |
| The three tokenizer readings | paste them now. `measure_budgets.py check` is red until you do, and every window sum is spent at one of them |
| `docs/reference/models/<candidate>.md` | the dossier. Paste the `dossier.md` the bench emitted; do not transcribe numbers by hand |
| Two status words | the candidate's dossier becomes `incumbent`, the model it replaced becomes `superseded`. They live in one place, so those two edits are the whole lifecycle change ([../reference/models.md](../reference/models.md)) |
| Docs and diagrams that name the configured model | search for the old id |
| Tests that assert the configured model | leave fixture ids that are deliberately historical or generic alone |

**The readings are the one source edit a swap costs, and that is deliberate.**
They sit in `backend/idhazh/measured.py` rather than in `config/` because they
are not tunable: each one is a measurement of a specific set of weights, it
carries the subject and date it was taken on, and `check` refuses the pair when
they disagree. A knob a person may turn and a reading a person may only retake
are different things (Guardrail #6).

Do not change historical payloads or historical measurement rows. A value-only
model change does not change a JSON shape; if the work also retypes a field or
adds one, the contract, its `version`, its changelog, the migration, the
generated schema and the drift gate move together
([../../CLAUDE.md](../../CLAUDE.md) section 11).

### 2.4 The fine-tuning check

**A base swap invalidates every adapter trained on the old base.** An adapter
loads onto a mismatched base without raising anything, and the damage arrives as
a quality drop nobody can attribute to it. The notebook's fourth step resolves
the teacher's base weights and stops when they are not the ones production
serves, so the refusal is where the adapter is loaded rather than where the base
is chosen ([fine-tune-a-model.md](fine-tune-a-model.md)).

**A swap also makes the training corpus mixed-teacher, and that is recorded
rather than prevented.** Every corpus row carries the `model_id` that wrote it
and `corpus/corpus.meta.json` holds the census. Read it before training, not
after:

```bash
python -c "import json;print(json.load(open('corpus/corpus.meta.json'))['models'])"
```

It already reads two ways: 1,015 rows from the retired `qwen3-8b-q4-k-m` and 429
from `qwen3-5-9b-q4-k-m` of 1,444, so a model trained on that corpus today is
learning mostly from a teacher that no longer serves.

### 2.5 What the first day costs

**The first run after a swap is cold on every shard at once**, because the
weights cache key carries the file and its revision. A cache miss is 5.29 GiB in
118 s (`n = 1`, spread unavailable, GitHub-hosted `ubuntu-latest`, 2026-08-23),
and each shard pays it - a warm-box bench figure is not the first real day. The
bench reports a cold case for exactly this reason; read that one.

The steady-state cache holds one model. The transition can hold two and cross
the 10 GB ceiling, so before the first production run:

```bash
gh cache list --limit 100
```

and after the new commit is ready, delete only the outgoing summary model's
entry:

```bash
gh cache delete <old-summary-cache-id>
```

**Measure the cache, do not derive it.** The key names the model file and the
pinned llama.cpp build, so the outgoing model may already have aged out and
there may be nothing to delete
([../reference/pipeline-cost.md](../reference/pipeline-cost.md#the-cache-transition-measured-2026-08-27)).

Production derives the worker count as
`min(ceil(items / run.shard_size), run.max_parallel)`, so a full day at
`run.safety_ceiling_per_run` gives a worker 20 items. Do not size a timeout from
a five-item shard.

### 2.6 One identity gap to know about before you trust the rollout

The fingerprint records the GGUF file the runtime opened, the llama.cpp build,
the chat template and the runner class. A stamp built on an absent or
placeholder weights digest now raises rather than publishing, and the
qualification path digests the file it is about to run. **Production `stage_work`
still passes `ModelRef.sha256` - what config expected - and leans on the `work`
job's own `sha256sum` of the file on disk to make the two agree.** Until the
observed digest and runtime build are passed into `work` and compared there, a
swap leaves the new model recorded as an expectation nobody verified at the
point of use
([../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)).

### 2.7 Before the first production run

1. Run the full local gates ([run-the-gates.md](run-the-gates.md)).
2. Run a one-URL local smoke through the new config
 ([troubleshoot-one-url.md](troubleshoot-one-url.md)).
3. Verify bounded worker selection against the day you plan to run.
4. Run a manual content refresh only after its measured worker population fits.
5. Read item-health failure codes, per-item read and write rates, the
 fingerprint row, the run manifest, the cache state and the published
 summaries.
6. Confirm no model directory or diagnostic payload is tracked.

---

## Block 3 - Revert

```json
"models_file": "models/<incumbent>.json"
```

The same line, back. With it go the three tokenizer readings and the two status
words - the dossier that said `superseded` says `incumbent` again - and that is
the whole revert.

**What a revert does not need, and why:**

| Not this | Because |
| --- | --- |
| A source edit | no model fact is in source. Everything about a model is in the file the pointer names |
| A schema regeneration | nothing changed shape. A pointer holds a different string |
| A cache purge | the incumbent's entry is keyed on its own weights file, revision and llama.cpp build, so moving the pointer back finds it again unless it has aged out. Deleting it buys a re-download and nothing else |
| A historical edit | published payloads and measurement rows record what actually ran. They stay as they are |

If a bad day is already running, stop the workers first, then move the line,
then let the next run fill the cache once without fanout and check its identity
and health before normal workers resume.

## See also

- [../reference/models.md](../reference/models.md) - one row a model, the status words, and what is in force right now.
- [fine-tune-a-model.md](fine-tune-a-model.md) - the corpus, the teacher, and what a base swap does to an adapter.
- [test-models-locally.md](test-models-locally.md) - download, serve and measure the local models.
- [troubleshoot-one-url.md](troubleshoot-one-url.md) - run one real URL through fetch, extraction and summarization.
- [run-the-gates.md](run-the-gates.md) - the complete local validation commands.
- [../concepts/qualification.md](../concepts/qualification.md) - the ten gates, the model-choice arithmetic, and what a run that judged a candidate actually proves.
- [../concepts/evaluation.md](../concepts/evaluation.md) - how a published summary is judged, which is the standard the gates grade against.
- [../concepts/config.md](../concepts/config.md) - model and runtime knobs.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - rendered bands, decoder rails and prompt controls.
- [../architecture/summarize/throughput.md](../architecture/summarize/throughput.md) - read/write rates and prompt reuse.
- [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md) - what a run records about its own inputs.
- [../reference/pipeline-cost.md](../reference/pipeline-cost.md) - runner numbers and open measurements.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrails #2, #3, #6, #9, #10 and #11.
