# Retired contract rationale, September 2026

**Last Updated**: 2026-09-12

Moved out of [../../CLAUDE.md](../../CLAUDE.md) on 2026-09-12, when the contract
was made subject to the fence rule it already sets for every other page
([../reference/documentation-structure.md](../reference/documentation-structure.md)).
Each `### Design rationale` section in the contract now carries fences - the rule
now in force, the alternative named, the cost that alternative would carry, and
who decided and when. The full argument that produced each ruling is here.

**Nothing on this page is in force.** `CLAUDE.md` is. Where the two disagree, the
contract governs and this page is the older wording. Entries are newest first
within each section.

**Two entries were deleted rather than moved here**, because a later entry in the
same section corrects each of them, and a section a later section corrects is a
second answer rather than history. They are the 2026-08-23 rename of "Holy Laws"
to "Rules", corrected by the 2026-09-12 rename to "Adaptive Guardrails", and the
2026-08-23 reading of Guardrail #1 as "a service, not an origin", corrected on
2026-09-12 by the finding that the guardrail was false about this project. Both
rulings survive as one clause of the fence that replaced them, and git holds the
rest.

## Section 0a - Non-Goals

**The article-bodies clause was narrowed on 2026-08-28, and it cost something.** What is worth protecting is what a reader is served, so the clause names that and carves out `corpus/`. The cost is stated rather than hidden: this repository is public, so source text under `corpus/` is readable by anyone. Owner weighed that against a second private repository and took it. A source that forbids storage is still out of scope, and nothing under `corpus/` may reach a published page.

**The clause was restated as a property on 2026-09-11, and no answer moved.** It was a list of banned mechanisms with a carve-out bolted on, so a plan that adds ten model-written labels had to argue each label separately against a rule that never said what it was protecting - and every one of those arguments ends in one more carve-out. The property was already written down, in the paragraph above, where only somebody reading the rationale would find it. Three cases check the restatement and each returns what it returned before: the prompt loop's model judge is permitted, model-assisted labelling under E1 is permitted, and a model grading a published summary is refused. **The summary-faithfulness clause is written into the amended text rather than left to follow from the property**, because a guardrail is usually lost in a rewrite that forgot it rather than in an argument (Fowler, 2026-09-10). **The two bans stand in addition to the property, never as instances of it**, and the witness is a model pre-label sitting in the human label queue: it reaches no reader and it selects nothing, so the property on its own would permit a grade of a published summary. A first draft of this restatement said the two bans were the only ways to fail the property, and Fowler and Andre both refused it on that case (2026-09-11). What it costs, stated rather than hidden: a property is a judgement where a list was a lookup, so a case near the line now needs a person to rule on it and a `git grep` for a banned mechanism no longer answers. Authority: owner, 2026-09-11.

**The LLM-as-judge clause took a narrow, offline-only exception on 2026-09-07, and it is the clause working rather than bending.** The summariser prompt was argued in prose and never measured - which is the failure the clause exists to prevent, read from the other side: with no instrument, every prompt change is a matter of taste, and taste is exactly what a judge sharing the summary's failure modes supplies. The prompt loop inverts who decides (O28, O33). A model judge and the Editor rubric PROPOSE a revised prompt; the deterministic, model-free scorers in `backend/idhazh/evals/metrics.py` DISPOSE, over a frozen committed article set - a candidate replaces the incumbent only when it beats it on all four gate targets, and the judge's preference promotes nothing. The four gate targets, what computes each of them, and the scorer that does not exist under the name a reader expects are in [`docs/concepts/evaluation.md`](docs/concepts/evaluation.md). The exception is narrow because the hazard is narrow: a model that graded a published summary, graded a published visual, or selected what publishes would be the banned thing, and all three stay banned. It is the same principle E1 settled for model-assisted labelling - a model verdict that reaches no reader and selects nothing to publish is not a section-0a deviation. The load-bearing guard is a test: when the judge prefers a candidate the scorers refuse, the incumbent stands (`backend/tests/test_prompt_loop.py`). Authority: owner, 2026-09-07. The restatement below folds this exception into the property, so the loop is an instance of the rule rather than a carve-out from it; what the loop may do did not change.

**The fine-tuning clause was narrowed on 2026-08-27.** The hazard is a build step the runner cannot execute, not a fine-tuned model. Training elsewhere costs the runner nothing - it only opens a finished GGUF and reads bytes. The old wording made an ordinary model swap look like a rule reversal, and a rule that fires on ordinary work stops being read.

## Section 0b - Voice

**The number clause exists because the rest of the section cannot fail.** "Write in plain language" is advice, and advice catches nothing. "Say what the number means, next to the number" is a check a reader applies to a sentence and gets a yes or a no.

**"Every answer" was added on 2026-08-25** because the three copies of this rule disagreed and the canonical one was the weakest. An agent reporting `1.055x aggregate decode, spread 0.022, prefill flat` at a user who asked what happened was inside the letter of it.

## Section 0d - Intent, Contract, Code

**The rejected alternative was a clause reading "a sentence that declines carries a price".** It was refused because it demands a number on exactly the days no number exists, which Guardrail #10 forbids - a hard rule wearing a guardrail's clothes. The third move does the same job without that cost: a labelled estimate that names what would settle it is the answer when a measurement is not available today. Authority: owner, 2026-09-12.

**This section was added on 2026-09-12, on the owner's instruction, because citing a constraint had become a way to decline work rather than price it.** An agent that named a guardrail, a budget or a schema and stopped there was reporting a fact and calling it an answer, and nothing in this contract said what it owed instead. The three moves are that missing clause: do it, price it, or name the measurement that would settle it.

## Section 1 - Adaptive Guardrails

This resolves a contradiction rather than creating room. [`docs/reference/measurements.md`](docs/reference/measurements.md) carried a house rule saying no figure names its machine unless that machine is a runner, and a worker with a developer-machine duration could not tell which page governed. **The contract governs; a page under `docs/` may say how a rule's intent is met and may not contradict it.** Authority: owner, 2026-09-12, under section 0, which requires the conflicting rule to be amended in the same commit.

**What "carries the hardware" means was settled on 2026-09-12, and it is not a second exception.** The rule's intent is that a reader can tell what produced a number and therefore what would move it. **So a figure names what could have moved it, and naming anything else is noise that invites a reader to discount a good number.** A duration and a memory figure belong to the machine that took them, so they name it - a runner where a runner took them, a developer box where one did, with a developer-machine duration labelled an order-of-magnitude check. A byte count, a token count, a pixel and a row count do not move between machines, so what they name is the runtime and its version: node's zlib and python's `gzip` differ by about 2 percent at one level, and an interpreter change moved a `tracemalloc` figure by 30 percent, which a processor model would not have predicted either way. Date and spread are unconditional in every case.

**Guardrail #10 took its one exception on 2026-08-30, and that is section 0 working rather than a rule bending.** Actions minutes are free, so wall clock is the only budget the site can show, and wall clock cannot say whether four hours was a good trade. Priced at a hosted rate, the same run gets a second unit. The exception is narrow because the hazard is narrow: a money figure reads as a fact about a bank account, so this one prints the rate it used and is labelled a counterfactual. **We are not billed, and presenting it as a bill is the one way to make it a lie.** Authority: owner, 2026-08-30.

**Where the escape hatch is written down, from 2026-09-08.** The rule permits a growing read where a person agrees and says why, and until now that agreement lived in whatever docstring the author happened to write. [`docs/concepts/growing-reads.md`](docs/concepts/growing-reads.md) is its address: the question to ask of any read, the three shapes a cover can take, and `-1` as the value that says a person chose not to bound this one. It adds no rule and changes nothing here - it is where the choosing is recorded, and it is a page of dated examples under one property rather than a list of paths, for the reason the paragraph above gives.

**The same day, a mechanical guard was written for it and then deleted.** `backend/tests/test_archive_readers.py` scanned every test file for two hand-written path patterns and held the matches against a list of twelve approved names. It failed for three reasons and each one is worth remembering, because the next person to reach for a guard here will reach for the same one. **It enumerated the hazard rather than the safe set**, so it covered two collections out of nineteen and looked finished - `corpus/`, `assist/`, `source-health.json` and three ledgers that grow for ever were never in it. **Its own maintenance cost grew with the number of collections**, which is the defect it existed to catch. And **it was a list of paths with no escape hatch**: the only way past it was to edit the list, so it made a judgement call look like a permission slip. A rule stated as a property survives a collection nobody has invented yet; a rule stated as a list is wrong the day after it is written. This one is enforced by review, and the reviewer's question is the one sentence in the rule: does a run that changed no code make it slower. Cost, stated rather than hidden: nothing fails automatically now, so a growing step can merge if nobody asks. Authority: owner, 2026-09-06.

**The default-and-exception wording was added 2026-09-06, because the rule as first written could be read as advice.** It said what not to do and named no bar for doing it anyway, so every growing step was arguable on its own merits and the arguments were always locally reasonable - the archive was right there, and walking it was the shortest code. Naming constant cost as the default inverts who carries the burden: an O(1) design needs no defence and a growing one needs a person's name against it.

**Guardrail #12 was added 2026-09-05, and it is about cost rather than correctness.** Measured that day on an Intel Core i7-1265U: two frontend checks spent 270 s and 93 s asserting once per published story, while reading and parsing the whole archive took 0.15 s and running the function under test on every story took a further 0.02 s. The work was never the archive - it was the same handful of cases re-checked tens of thousands of times. Those 6,539 stories carried six distinct cases between them, so the corpus stopped teaching anything on about day one while the bill went on arriving every four hours. A published day is frozen once it is written, so re-reading it later cannot find a fault that `idhazh validate-days` and the contract models did not already refuse. Authority: owner, 2026-09-05.

**Guardrail #6 gained feature flags on 2026-09-12, and the removal condition is the load-bearing half.** A flag with no stated exit is a permanent second implementation - two code paths, two test matrices, and nobody able to say which one is real. Requiring the exit condition on the line that declares the flag makes deleting it a scheduled act rather than an archaeology project. The cost is one more thing to write when a flag is added, which is the cheapest moment it will ever be written. Authority: owner, 2026-09-12.

**Guardrail #5 was proposed for softening and the softening was refused.** The proposal was to permit a named, dated stopgap that carries its own structural fix. The sibling project's owner refused exactly that and recorded the reason this project now adopts: a temporary fix is a permanent fix with a note attached, and the note is what gets lost. The adapt path for #5 is escalation under section 6 and nothing else, which is why its text says so in the guardrail rather than leaving it to be inferred. Authority: owner, 2026-09-12; sibling owner, 2026-09-11.

**Guardrail #1 was corrected rather than reworded, because it was false about this project.** It said "no runtime telemetry" while the pipeline commits telemetry every run and the operator console fetches a browser-safe projection of it at runtime, and it implied no runtime model fetch while search has had a second origin since 2026-09-10 (section 0a). A constraint that misdescribes the system is obeyed into a wrong design or quietly ignored, and both cost more than the constraint saves. The reframing keeps every prohibition and moves the line to where the hazard actually is - **the ban is on automatic transmission, not on measurement.** Nothing new is permitted: telemetry was already committed and already rendered, and this is the clause catching up with the repository. Authority: owner, 2026-09-12.

**Guardrail #10 was reconciled with section 0d on 2026-09-12, and the distinction is one word.** Section 0d's third move lets a labelled estimate carry a design forward on a day no measurement exists; #10 as committed said an unmeasured number "may not be used to justify a design". The contract was telling an agent to keep going and to stop in the same breath, and a contradiction like that is always resolved by whichever sentence the reader found first. The word that separates them is **settle** against **carry**: an estimate may not settle a design, and it may carry one to the next step when it is labelled, when it names the measurement that would settle it, and when it names the smallest step that makes progress meanwhile. Nothing about a published number moved - the counterfactual-cost exception of 2026-08-30 and the "what carries the hardware" amendment below both stand unchanged. What moved is what an agent owes on the day the measurement is not there yet. Authority: owner, 2026-09-12.

## Section 14 - Agent Roster

Giving Jony the demand mandate too was rejected: one head holding both "remove before adding" and "this is not enough" resolves to the veto every time. Making sufficiency advisory was rejected because an advisory check is the one skipped on the day it would have bitten. Authority: owner, 2026-08-29.

**Susan was added on 2026-08-29 because the roster was six vetoes and no demand.** A system of pure vetoes converges on the minimum that passes every veto - measured 2026-08-28 as a published surface using 40.6 percent of a 1536px screen, two responsive breakpoints in the whole frontend, no elevation scale, two icons and no interactive chart. Every one of those passed a review.

## See also

- [../../CLAUDE.md](../../CLAUDE.md) - the contract these fences are in.
- [../reference/documentation-structure.md](../reference/documentation-structure.md) - the fence rule, the delete test, and the six classes not cut at any budget.
- [../concepts/growing-reads.md](../concepts/growing-reads.md) - Guardrail #12's address, and the measurement behind it.
- [../concepts/evaluation.md](../concepts/evaluation.md) - the prompt loop the LLM-as-judge exception was written for.
- [measurements-2026-08.md](measurements-2026-08.md) - the sibling archive page, for retired numbers rather than retired rulings.
