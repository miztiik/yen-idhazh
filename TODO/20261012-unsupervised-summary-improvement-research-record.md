# Improving the news summarizer without human labels: evidence and a staged plan

**Last Updated**: 2026-10-12

Research record for plan 65 (Table Q, Q65), grounded in the plan's North Star. Evidence, not rulings: the owner rules on what plan 65.2 takes from it.

**Correction, 2026-10-12.** Where this record gives Granite Guardian about 5 minutes per summary, that figure is the plan's nightly budget (8 summaries in 40 minutes), not a measurement. Its speed on the council's runners is still unmeasured; Stage 0 measures it.

Brief D1. Written 2026-10-12. Scope: the digest's summarizer (Qwen3.5-9B, Q4_K_M GGUF, pinned llama.cpp, 4-vCPU CPU runners), the nightly council (4 jobs of up to 200 minutes), and the approved second model (Granite Guardian 3.3 8B).

**How to read this.** Confidence tags are [high], [moderate] and [low]. "(estimate)" marks a number I derived; nobody measured or published it. Citations are numbered links; the full list is at the end. Facts about this system come from the brief or from the project record (TODO/20261012-summary-fidelity-judge-hard-look-record.md section 4, docs/how-to/fine-tune-a-model.md, TODO/20261011-65-summary-fidelity-judge-plan.md; source 65) and are labelled "project record". North Star lines are named:

- NS1 unsupervised; every automatic step bounded, recorded, with an off switch.
- NS2 quality over brevity; length recorded, never targeted or penalised.
- NS3 built for 10,000 a day, longer summaries and new models.
- NS4 sample, never check everything; a different-family second model; the writer does no extra work.
- NS5 config-driven; lifecycle states; append-only ledgers.
- NS6 metrics, not messages.

## Executive summary (answer first)

1. **Build the instrument before the optimiser.** The first thing to build is a paired champion/challenger harness in the nightly council. The challenger re-summarizes stored sample articles. One pinned judge build scores both arms. A group-sequential paired test with non-inferiority guards decides, and code promotes or holds. Pairing on the same articles is the largest variance cut available. [high on method; moderate on fit]
2. **The judge, not the optimiser, limits what can be learned.** Granite Guardian 3.3 8B is third on LLM-AggreFact at 76.5 balanced accuracy, but scores 67.0 on its CNN news subset. Two MIT-licensed checkers under 1B parameters score 70.1 and 69.9 there; on the XSum news subset Granite leads by under one point ([50](https://llm-aggrefact.github.io/)). A judge with balanced accuracy $b$ shrinks every measured difference by $J = 2b-1$. At $b = 0.67$, $J = 0.34$, so a test needs about 9 times the articles a perfect judge would need. [high on arithmetic; moderate on transfer to this news mix]
3. **Worked numbers.** With a paired SD of 0.15 on the per-summary share of unsupported sentences, the 80%-power detectable effect is 0.059, 0.042, 0.030 and 0.019 at 50, 100, 200 and 500 pairs, on the judge's scale. A true 3-point gain needs about 700 pairs at $b = 0.765$ and about 1,700 at $b = 0.669$ (estimate). Covariates (CUPED, prediction-powered inference) save 10 to 50 percent of samples, not more.
4. **Decide across nights with a group-sequential test.** Five looks cost about 2 percent more maximum sample than a fixed test, and save about 19 percent of the expected sample when the gain is real (simulation, estimate).
5. **Optimising against a faithfulness judge buys copying, omission and vagueness.** It already happened here once: faithfulness rose because summaries copied more (project record). Guards with evidence: several metrics as constraints, a held-out judge never used for training, KL/reference anchoring, conservative ensembles, fresh article sets, and planted faults with unaltered controls.
6. **Fine-tuning from judge labels works in published summarization studies, but over-optimises early.** RLAIF matched RLHF on summarization ([13](https://arxiv.org/abs/2309.00267)). DPO on LLM feedback lifted a composite summary score from 0.632 to 0.735, and 5K pairs already reached 0.702 ([24](https://arxiv.org/abs/2410.13116)). Direct alignment methods degrade "often before even a single epoch" ([30](https://arxiv.org/abs/2406.02900)), and supervised tuning on "best" summaries caused copy bias ([24](https://arxiv.org/abs/2410.13116)). Use DPO on judged pairs harvested from the champion/challenger runs, one epoch, promoted only past a held-out judge. [moderate]
7. **Training is cheap, but the GPU needs at least 24 GB.** Unsloth advises against QLoRA on Qwen3.5 and lists 22 GB for a 9B bf16 LoRA ([59](https://unsloth.ai/docs/models/qwen3.5/fine-tune)). That rules out 16 GB cards, including GitHub's T4 GPU runner ([62](https://docs.github.com/en/actions/reference/runners/larger-runners)). A round is about 1 to 3 GPU-hours, roughly 2 to 10 US dollars at listed prices (estimate). A CI job can start it through a GPU provider's API, so no person is needed. [moderate]
8. **Precision, not volume, sets sample size.** A +/-3-point interval on a 10 percent rate needs 178 of 330 summaries, or 370 of 10,000. Sampled judging stays flat in cost; per-summary scoring in the writer does not (estimate).
9. **Completeness from key facts with a 4B-class model is unproven.** In FineSurE, even GPT-4-extracted key facts tracked human completeness at only 0.571 ([25](https://arxiv.org/abs/2407.00908)). Use completeness as a guard with a wide margin until planted-omission tests support more. [moderate]
10. **Where evidence is weak:** transfer of benchmark accuracy to this news mix; DPO with 2,000 to 6,000 pairs on a 9B hybrid model; gains surviving Q4_K_M; key-fact extraction by small models; bandits and BO for summarization. [low]

## Findings table

| # | Finding | Confidence | Evidence | North Star |
|---|---|---|---|---|
| F1 | Paired tests on the same articles give the cheapest power; useful effects need hundreds of pairs | high | [1](https://arxiv.org/abs/2411.00640), Q2 arithmetic | NS4 |
| F2 | Judge error shrinks effects by $J = 2b-1$; sample need grows by $1/J^2$ | high (math) | [10](https://doi.org/10.1093/oxfordjournals.aje.a112510), [50](https://llm-aggrefact.github.io/) | NS4 |
| F3 | Two MIT checkers under 1B match or beat Granite 3.3 on news at a tenth of the size | moderate | [50](https://llm-aggrefact.github.io/), [51](https://huggingface.co/lytang/MiniCheck-Flan-T5-Large), [53](https://arxiv.org/abs/2501.17144) | NS4 |
| F4 | Nightly group-sequential looks cost little power | high | [4](https://engineering.atspotify.com/2023/03/choosing-sequential-testing-framework-comparisons-and-discussions), [3](https://arxiv.org/abs/1512.04922), simulation | NS1 |
| F5 | Label-free preference optimisation improves summaries | moderate | [13](https://arxiv.org/abs/2309.00267), [15](https://arxiv.org/abs/2305.18290), [22](https://arxiv.org/abs/2311.08401), [23](https://arxiv.org/abs/2409.18618), [24](https://arxiv.org/abs/2410.13116) | NS1 |
| F6 | Preference training over-optimises early; KL and ensembles help | high | [27](https://arxiv.org/abs/2210.10760), [28](https://arxiv.org/abs/2310.02743), [30](https://arxiv.org/abs/2406.02900) | NS1 |
| F7 | Faithfulness-only optimisation buys copying, omission, vagueness | high | [26](https://arxiv.org/abs/2306.00186), [32](https://arxiv.org/abs/2211.08412), [24](https://arxiv.org/abs/2410.13116), project record | NS2 |
| F8 | Constraints on several metrics and held-out or panel judges reduce gaming | moderate | [29](https://arxiv.org/abs/2310.04373), [28](https://arxiv.org/abs/2310.02743), [38](https://arxiv.org/abs/2404.18796) | NS1 |
| F9 | Judges favour their own and similar models; errors correlate across families | high / moderate | [34](https://arxiv.org/abs/2404.13076), [35](https://arxiv.org/abs/2311.09766), [36](https://arxiv.org/abs/2502.04313), [37](https://arxiv.org/abs/2506.07962) | NS4 |
| F10 | Planted faults measure catches only, and edits differ from real errors | moderate | [33](https://arxiv.org/abs/2305.14540), [51](https://huggingface.co/lytang/MiniCheck-Flan-T5-Large), project record | NS1 |
| F11 | Training on own outputs is safe only with verification and accumulation | moderate | [44](https://www.nature.com/articles/s41586-024-07566-y), [45](https://arxiv.org/abs/2404.01413), [46](https://arxiv.org/abs/2406.07515) | NS1 |
| F12 | Qwen3.5-9B LoRA needs a 24 GB+ GPU; about 2 to 10 dollars a round | moderate | [59](https://unsloth.ai/docs/models/qwen3.5/fine-tune), [62](https://docs.github.com/en/billing/reference/actions-runner-pricing), [63](https://modal.com/pricing), [64](https://www.runpod.io/pricing) | NS1, NS3 |
| F13 | Sample size follows precision, so judge cost is flat in volume | high | Q6 arithmetic, [8](https://arxiv.org/abs/2406.04291), [9](https://arxiv.org/abs/2403.03208) | NS3, NS4 |
| F14 | Key-fact completeness by small models is unproven | low | [25](https://arxiv.org/abs/2407.00908), [24](https://arxiv.org/abs/2410.13116) | NS4 |

## Q1. Which methods improve a summarizer without human labels?

### (a) Champion/challenger tests of configuration changes

**What it is.** A challenger is any change: prompt, decoding settings, input budget (how much article text the model sees), model, quantization or runtime build. It runs on the same stored sample articles as the champion, so each article is its own control. Evaluations are experiments; one guide gives "formulas for analyzing evaluation data, measuring differences between two models, and planning an evaluation experiment" ([1](https://arxiv.org/abs/2411.00640)). [high]

**Evidence that the knobs matter.**
- Model choice: for news, "instruction tuning, and not model size, is the key to the LLM's zero-shot summarization capability" ([40](https://arxiv.org/abs/2301.13848)). A bigger or newer model must be tested, not assumed better. [moderate]
- Decoding: "decoding method performance is notably task-dependent and influenced by factors such as alignment, model size, and quantization" ([41](https://arxiv.org/abs/2402.06925)). Test decoding on the Q4_K_M file that serves. [moderate]
- Input budget: summaries show a "U-shaped" faithfulness trend over document position, and "as context increases, summaries become less faithful" up to a point ([39](https://arxiv.org/abs/2410.23609)). LLM faithfulness metrics also "remain sensitive to document order" ([39](https://arxiv.org/abs/2410.23609)). [moderate]

**Design for this system.**
- Unit: one stored sample article (source text kept about 31 days). Arms: the published champion summary and a challenger summary generated in the council. The writer does no extra work (NS4).
- Both arms are judged by the same judge build, prompt and runtime. Reuse champion labels only when the judge hash is identical; otherwise judge drift masquerades as a treatment effect.
- An output-length cap is never an arm or an objective (NS2); a cap stays only as a safety ceiling.
- Run an A/A test first: the champion against a fresh run of itself. It yields the real paired SD and checks that false alarms run at the nominal rate. The CUPED study used a 3-week A/A experiment the same way ([2](https://exp-platform.com/Documents/2013-02-CUPED-ImprovingSensitivityOfControlledExperiments.pdf)).

**Failure modes.** Judge drift between nights; a judge that errs differently on the two arms (Q3); reuse of the same articles across many tests; the winner's curse when the best of several challengers is picked ([11](https://doi.org/10.1145/3219819.3219905)); and churn (a dated pipeline change about every 9 days, project record).

**Cost.** Each pair needs one challenger generation and one or two judge passes. Granite currently costs about 5 minutes per summary (8 checks in 40 minutes, project record), so one 200-minute job judges about 40 summaries (estimate). Decoding runs at about 4 tokens per second on the runner (project record): 25 seconds per 100 output tokens, plus prefill.

### (b) Fine-tuning from judge-labelled data

Foundation: training a summarizer against a learned preference model beat "both human reference summaries and much larger models fine-tuned with supervised learning alone" ([12](https://arxiv.org/abs/2009.01325)). The question here is whether a judge model can replace the human preferences.

| Method | Evidence (summarization or close) | Reported gains | Failure modes | Cost |
|---|---|---|---|---|
| Rejection sampling / best-of-n distillation (RAFT, ReST, ReST-EM, BOND) | ReST-EM on math and code ([20](https://arxiv.org/abs/2312.06585)); BOND on abstractive summarization ([21](https://arxiv.org/abs/2407.14622)); FeedSum SFT on the best of 13 summarizers ([24](https://arxiv.org/abs/2410.13116)) | ReST-EM "significantly surpasses fine-tuning only on human data"; FeedSum SFT-best composite 0.651 vs 0.632 base | Every FeedSum SFT variant lost abstractiveness ("copy bias"): 0.696 to 0.588 for SFT-best; single-dimension SFT sacrificed completeness ([24](https://arxiv.org/abs/2410.13116)) | n generations and n judgings per article |
| DPO on AI-feedback pairs | RLAIF on TL;DR ([13](https://arxiv.org/abs/2309.00267)); DPO on TL;DR ([15](https://arxiv.org/abs/2305.18290)); FeedSum ([24](https://arxiv.org/abs/2410.13116)); factuality DPO ([22](https://arxiv.org/abs/2311.08401)) | RLAIF and RLHF preferred over SFT 71% and 73% of the time, "not statistically significantly different"; FeedSum 0.632 to 0.735, human evaluation agrees; factual error rate down 58% (biographies) and 40% (medical QA) | Over-optimisation within one epoch ([30](https://arxiv.org/abs/2406.02900)); length exploitation ([31](https://arxiv.org/abs/2403.19159)); feedback from an 8B judge cut faithfulness by 0.028 ([24](https://arxiv.org/abs/2410.13116)) | About 2 to 3 times SFT per example (estimate) |
| MPO: pairs from the model's own decoding strategies | Standard summarization sets, no external judge ([23](https://arxiv.org/abs/2409.18618)) | "significantly enhances the quality of generated summaries without relying on human feedback" | Learns only its own decoding preferences; nothing independent checks it | As DPO |
| KTO (binary desirable/undesirable labels) | Chat benchmarks ([17](https://arxiv.org/abs/2402.01306)); FeedSum ([24](https://arxiv.org/abs/2410.13116)) | "matches or exceeds the performance of preference-based methods at scales from 1B to 30B"; FeedSum average 0.730 vs DPO 0.735 | In FeedSum, faithfulness fell from 0.864 to 0.809 while conciseness jumped | As DPO |
| ORPO, SimPO (no reference model) | Chat benchmarks only ([16](https://arxiv.org/abs/2403.07691), [18](https://arxiv.org/abs/2405.14734)) | SimPO beat DPO "by up to 6.4 points on AlpacaEval 2" | No reference model, so no explicit KL anchor; SimPO's reward is a length-normalised average log-probability (touches NS2) | Slightly below DPO |
| Self-rewarding | Llama 2 70B judging itself over three DPO rounds, instruction following ([19](https://arxiv.org/abs/2401.10020)) | Beat several large systems on AlpacaEval 2.0 | The model judges itself (breaks NS4's family line); self-preference ([34](https://arxiv.org/abs/2404.13076)) | As DPO plus self-judging |
| Self-training on own outputs | Collapse when generated data replaces real data ([44](https://www.nature.com/articles/s41586-024-07566-y)); avoided by accumulating ([45](https://arxiv.org/abs/2404.01413)); news-summarization collapse prevented by verifiers ([46](https://arxiv.org/abs/2406.07515)) | Verifiers "can indeed be harnessed to prevent model collapse" | Loss of diversity; drift toward judge quirks | n/a |

**Synthesis.** Across studies, pairwise preference training on fine-grained, multi-dimensional judge feedback beats imitation of "best" outputs, and it needs a strong judge. RLAIF's evidence comes from one model family; an ICLR 2024 meta-review found "The experiments, based solely on PaLM, lack convincing power" ([14](https://openreview.net/forum?id=AAxIs3D2ZZ)) before the paper appeared at ICML 2024 ([13](https://arxiv.org/abs/2309.00267)). FeedSum, MPO and factuality DPO corroborate it on other models. [moderate]

### (c) Bandits and black-box optimisation (BO) over configurations

- Offline tests on stored articles show no reader a bad summary, so there is no regret to minimise. The right frame is best-arm identification: spend a fixed budget to find the best of a few configs. TRIPLE treats prompt selection as fixed-budget best-arm identification and reports "remarkable performance improvement" over baselines within a budget ([43](https://arxiv.org/abs/2402.09723)). [moderate]
- EcoOptiGen tunes "inference hyperparameters such as the number of responses, temperature and max tokens" under a cost budget ([42](https://arxiv.org/abs/2303.04673)). Max tokens is a length knob, so it stays out of the search (NS2).
- I found no study of bandits or BO for summarization faithfulness. [low]
- Failure modes: judge noise (Q2) lets BO chase noise; the best of k configs looks better than it is ([11](https://doi.org/10.1145/3219819.3219905)). Confirm the winner on fresh articles before promotion.
- Practical form: successive elimination over 3 to 6 arms on paired samples, then one confirmatory test.

## Q2. How to tell a real gain from noise without labels

**Unit and test.** The unit is the article, because sentences within a summary are correlated. Let $Y$ be a per-summary judge metric, such as the share of sentences judged unsupported. For article $i$:

$$d_i = Y_i^{(B)} - Y_i^{(A)}, \qquad \hat\Delta = \bar d, \qquad \widehat{SE} = s_d/\sqrt{n}$$

$$\sigma_d^2 = \sigma_A^2 + \sigma_B^2 - 2\rho\,\sigma_A\sigma_B$$

$$\mathrm{MDE} = (z_{1-\alpha/2} + z_{1-\beta})\frac{\sigma_d}{\sqrt n} \approx 2.80\,\frac{\sigma_d}{\sqrt n}, \qquad n = \left(\frac{2.80\,\sigma_d}{\delta}\right)^2$$

These hold for two-sided $\alpha = 0.05$ and power 0.8. For a one-sided non-inferiority guard at $\alpha = 0.05$ the factor is 2.49. For a yes/no outcome per summary (any unsupported sentence), $\mathrm{Var}(d_i) = p_{10} + p_{01} - (p_{10} - p_{01})^2$, where $p_{10}$ and $p_{01}$ are the discordant shares; test on the discordant pairs. A paired t-test, a signed-rank test or an article-level bootstrap all fit.

**Worked numbers** (80% power, two-sided 0.05, judge scale). The A/A run supplies $\sigma_d$; the rows show a plausible range.

| Paired articles $n$ | 50 | 100 | 200 | 500 |
|---|---|---|---|---|
| $\sigma_d = 0.10$ | 0.040 | 0.028 | 0.020 | 0.013 |
| $\sigma_d = 0.15$ | 0.059 | 0.042 | 0.030 | 0.019 |
| $\sigma_d = 0.20$ | 0.079 | 0.056 | 0.040 | 0.025 |
| Yes/no, discordant share 0.10 | 0.125 | 0.089 | 0.063 | 0.040 |
| Yes/no, discordant share 0.20 | 0.177 | 0.125 | 0.089 | 0.056 |
| Yes/no, unpaired, $p = 0.2$ (contrast) | 0.224 | 0.159 | 0.112 | 0.071 |

One night of 100 pairs detects only big changes (about 4 points on the sentence share). Gains of 1 to 2 points need 300 to 1,000 pairs, so tests must span nights. Pairing shrinks the yes/no MDE by 1.3 to 1.8 times here, and continuous shares beat yes/no flags. [high]

**Variance reduction.**
- CUPED: $Y^{cv}_i = Y_i - \theta(X_i - \bar X)$ with $\theta = \mathrm{cov}(Y,X)/\mathrm{var}(X)$, so $\mathrm{var}(\bar Y^{cv}) = \mathrm{var}(\bar Y)(1-\rho^2)$. At Bing it reduced variance "by about 50%" ([2](https://exp-platform.com/Documents/2013-02-CUPED-ImprovingSensitivityOfControlledExperiments.pdf)). In a paired test, regress $d_i$ on pre-treatment article covariates: article length, source, density of numbers and names, and the champion's own HHEM and judge scores. The rule is "Never use covariates that could be affected by the treatment" ([2](https://exp-platform.com/Documents/2013-02-CUPED-ImprovingSensitivityOfControlledExperiments.pdf)); the challenger's own HHEM score is such a covariate. [high]
- Stratification is the same tool with categorical covariates ([2](https://exp-platform.com/Documents/2013-02-CUPED-ImprovingSensitivityOfControlledExperiments.pdf)). Source and article-length band are natural strata.
- Prediction-powered inference (PPI) combines a cheap predictor on everything with an expensive judge on a sample. It is valid "without making any assumptions on the machine-learning algorithm that supplies the predictions" ([6](https://arxiv.org/abs/2301.09633)). It suits level estimates (Q6) better than paired tests, because challenger summaries exist only where they were generated. For model evaluation it raised "the effective human-labeled sample size by up to 50%" ([7](https://arxiv.org/abs/2403.07008)).
- What covariates buy: the MDE scales by $\sqrt{1-R^2}$. $R^2$ = 0.1, 0.3 and 0.5 give 0.95, 0.84 and 0.71, worth 1.1, 1.4 and 2.0 times the sample. Expect the low end until measured (estimate).

**Judge error shrinks effects.** Let the judge flag an unsupported sentence with sensitivity $Se$ and pass a supported one with specificity $Sp$. The observed flag rate is $q = (1-Sp) + J\,p$ with $J = Se + Sp - 1$. If both arms see the same error rates, $\Delta q = J\,\Delta p$. With balanced accuracy $b = (Se+Sp)/2$, $J = 2b-1$; the needed sample grows by $1/J^2$; and a corrected rate is $\hat p = (\hat q - (1-Sp))/J$ ([10](https://doi.org/10.1093/oxfordjournals.aje.a112510)).

| Judge | $b$ | $J$ | Sample multiplier | MDE multiplier |
|---|---|---|---|---|
| Granite 3.3, CNN news subset, no-think (project record) | 0.669 | 0.34 | 8.8 | 3.0 |
| FactCG-DeBERTa-L, CNN news subset ([50](https://llm-aggrefact.github.io/)) | 0.701 | 0.40 | 6.2 | 2.5 |
| Granite 3.3, all 11 sets ([50](https://llm-aggrefact.github.io/)) | 0.765 | 0.53 | 3.6 | 1.9 |
| GPT-4 in FineSurE, sentence level ([25](https://arxiv.org/abs/2407.00908)) | 0.864 | 0.73 | 1.9 | 1.4 |

Worked example (estimate): a true 3-point cut in the unsupported share, with $\sigma_d = 0.15$, needs 196 pairs with a perfect judge, 699 at $b = 0.765$, 1,214 at $b = 0.701$ and 1,718 at $b = 0.669$. At 100 pairs a night that is 2, 7, 12 and 17 nights. The arithmetic assumes the judge errs the same way on both arms. A challenger that copies more breaks that assumption, because LLM scorers prefer inconsistent summaries when they "occur verbatim in the document" ([32](https://arxiv.org/abs/2211.08412)). The guards in Q3 exist for this case.

**Sequential decisions.** Stopping at the first nightly p < 0.05 inflates false alarms. Always-valid p-values allow continuous monitoring ([3](https://arxiv.org/abs/1512.04922)). For batched data with a known maximum sample, group-sequential tests give "the highest power" ([4](https://engineering.atspotify.com/2023/03/choosing-sequential-testing-framework-comparisons-and-discussions)). One practitioner guide advises non-sequential tests for primary metrics and sequential tests "for detecting degradations early" ([5](https://confidence.spotify.com/docs/experiments/stats/sequential-tests)). My simulation (400,000 runs; estimate) for 5 equal looks, two-sided 0.05, 80% power:
- A conservative boundary $c_k = 2.04\sqrt{5/k}$ raises the maximum sample by 2.3 percent. The expected sample under a real gain falls to 0.81 of a fixed test.
- A flat boundary ($c = 2.41$ at every look) raises the maximum sample by 22 percent.

Use the conservative boundary for promotion, and an always-valid test for the post-promotion watch.

**Many tests.** Each guard is a one-sided non-inferiority test, and promotion needs all of them to pass. Across many challengers, control the false-discovery rate, as the drift judge already does. After selection, re-estimate the gain on fresh articles, because selected winners are biased upward ([11](https://doi.org/10.1145/3219819.3219905)).

## Q3. How optimisers game faithfulness and completeness judges, and the guards that work

| Gaming mode | Evidence | Guard |
|---|---|---|
| Copying | LLM scorers rank inconsistent summaries higher when they "occur verbatim in the document" ([32](https://arxiv.org/abs/2211.08412)); entailment rewards risk "more extractive summaries" ([26](https://arxiv.org/abs/2306.00186)); SFT on best summaries caused "copy bias" ([24](https://arxiv.org/abs/2410.13116)); here, faithfulness rose because summaries copied more (project record) | Copy metrics (verbatim run, extractiveness) as non-inferiority constraints; keep the existing copy ceiling |
| Vagueness, omission | Consistency gains "may come at the cost of less informative" summaries ([26](https://arxiv.org/abs/2306.00186)); single-dimension DPO lowered other dimensions, e.g. conciseness-only cut completeness by 0.090 ([24](https://arxiv.org/abs/2410.13116)) | Completeness as a constraint, with key facts shared across arms |
| Hedging | Hedged claims are harder to falsify; not studied directly [low] | Count hedges added and dropped, both as guards |
| Length | DPO shows "significant exploitation" of length, and GPT-4 judges have a "well-known verbosity bias" ([31](https://arxiv.org/abs/2403.19159)); a sentence share can be diluted with easy sentences | Record length; never reward or penalise it (NS2); require the gain to hold within article-length strata |
| Judge quirks | LLM faithfulness metrics are sensitive to document order ([39](https://arxiv.org/abs/2410.23609)); here the whole-summary score marks long articles down (project record); sentence splitting changes counts | Segmentation fixed in config; judge prompt pinned by hash; anchor panel re-judged nightly |
| Self- and similarity preference | Judges score their own outputs higher ([34](https://arxiv.org/abs/2404.13076)); reference-free metrics favour their own model in summarization ([35](https://arxiv.org/abs/2311.09766)); judges favour similar models ([36](https://arxiv.org/abs/2502.04313)) | Judge family differs from both arms (NS4) |
| Over-optimisation in general | Optimising an imperfect proxy "too much can hinder ground truth performance" ([27](https://arxiv.org/abs/2210.10760)); direct alignment degrades "often before even a single epoch" ([30](https://arxiv.org/abs/2406.02900)) | The five guards below |

**Guards that work.**
1. **Several metrics as constraints, not one weighted score.** Constrained RLHF keeps "each RM ... within the range at which it is an effective proxy" ([29](https://arxiv.org/abs/2310.04373)). Multi-dimensional, fine-grained feedback beat single-dimension feedback ([24](https://arxiv.org/abs/2410.13116)). Here: one primary metric, every other metric non-inferior. [moderate]
2. **A held-out judge, and conservative ensembles.** The over-optimisation studies keep the optimised proxy apart from the judge that measures ([27](https://arxiv.org/abs/2210.10760)). Worst-case ensemble optimisation "practically eliminates overoptimization and improves performance by up to 70% for BoN sampling" ([28](https://arxiv.org/abs/2310.02743)). A panel of smaller judges from "disjoint model families" shows "less intra-model bias" and is "over seven times less expensive" than one large judge ([38](https://arxiv.org/abs/2404.18796)). Here: judge P builds training pairs and serves as the primary metric. Promotion also needs held-out judge H to be non-inferior. Rotate H when a new approved judge appears. [moderate]
3. **KL or reference anchoring.** Ensembles plus "a small KL penalty successfully prevents overoptimization at no performance cost" ([28](https://arxiv.org/abs/2310.02743)). DPO keeps a reference model; ORPO and SimPO drop it ([16](https://arxiv.org/abs/2403.07691), [18](https://arxiv.org/abs/2405.14734)). Direct alignment still degrades at larger KL budgets ([30](https://arxiv.org/abs/2406.02900)), so train for at most one epoch with a conservative $\beta$. LoRA itself helps: it "better maintains the base model's performance on tasks outside the target domain" ([48](https://arxiv.org/abs/2405.09673)). [moderate]
4. **Held-out article sets.** Train on the past and measure on the future (the existing date-trailing holdout, project record). Keep a fresh confirmation set that no test or training run has touched. Keep near-duplicate stories from different outlets on one side of a split (recommendation; not tested here).
5. **Planted-fault checks of the judge itself.** Edit-based sets are "20 times more cost-effective per sample", and "Most LLMs struggle on SummEdits, with performance close to random chance" ([33](https://arxiv.org/abs/2305.14540)). But the MiniCheck authors warn that edited claims "do not reflect LLMs' actual behaviors" ([51](https://huggingface.co/lytang/MiniCheck-Flan-T5-Large)). The project record notes that planted variants "measure catches only". So plant faults, and also run unaltered and meaning-preserving controls to measure false alarms. [moderate]

## Q4. Fine-tuning in practice: a 9B GGUF summarizer with no GPU in CI

**The base model.** Qwen3.5-9B is a dense hybrid: "eight blocks of three Gated DeltaNet linear-attention layers followed by one gated full-attention layer", released March 2026 under Apache 2.0 ([58](https://modal.com/library/qwen/qwen3-5-9b), [57](https://huggingface.co/Qwen/Qwen3.5-9B)).

**Hardware and tools.** Unsloth lists 22 GB of VRAM for a 9B bf16 LoRA ([59](https://unsloth.ai/docs/models/qwen3.5/fine-tune)). It warns: "It is not recommended to do QLoRA (4-bit) training on the Qwen3.5 models, no matter MoE or dense, due to higher than normal quantization differences". It needs transformers v5. It exports straight to GGUF (`model.save_pretrained_gguf(..., quantization_method = "q4_k_m")`). It names a wrong chat template or EOS token as the most common cause of a worse export ([59](https://unsloth.ai/docs/models/qwen3.5/fine-tune)). So: rent a GPU with 24 GB or more. The current Colab notebook path (project record) needs a paid runtime of that size. A rented machine also has the RAM to merge, which today happens on the owner's machine (project record). [moderate]

**How many examples.** LIMA tuned a 65B model on "only 1,000 carefully curated prompts and responses" ([49](https://arxiv.org/abs/2305.11206)), so format and style are learned fast. For summarization DPO, FeedSum's composite rose from 0.632 to 0.707 with 13K pairs and "nearly plateaus after 46K". 5K pairs reached 0.702, and 1K human pairs reached 0.666 ([24](https://arxiv.org/abs/2410.13116)). So 2,000 to 6,000 well-judged pairs may capture much of the gain (estimate). That result was on Llama3-8B with a 70B judge, not on this system. [low] Measure a learning curve: train on 25, 50 and 100 percent of the pairs and test each through the harness.

**Keeping the data clean.**
- Separation: the date-trailing holdout (exists); a confirmation set never used for training or selection; story-level de-duplication across outlets (recommendation).
- Source of pairs: the champion/challenger runs already produce two judged summaries of the same article. A pair is (better, worse) by the primary judge, with completeness no worse. This keeps training data inside the sample (NS4).
- Mixing: accumulate; never replace. Replacing real data with generated data "does indeed tend towards model collapse", while "accumulating the successive generations of synthetic data alongside the original real data avoids model collapse" ([45](https://arxiv.org/abs/2404.01413)). Filter with a verifier: news-summarization collapse was prevented by "verifiers, even imperfect ones" ([46](https://arxiv.org/abs/2406.07515)). [moderate]
- Safety nets: keep the existing loss mask on the assistant turn, the injection-marker refusal and the over-length check (project record).
- Judges: the judge that builds pairs never decides promotion alone (Q3, guard 2).

**Merging and converting.** There are two routes, both scriptable.
1. Merge the adapter into bf16 weights, then convert and quantize to Q4_K_M ([59](https://unsloth.ai/docs/models/qwen3.5/fine-tune)). The output is a new pinned GGUF candidate.
2. Keep the pinned base GGUF and load the adapter at run time. llama.cpp's server takes `--lora FNAME`, and `--lora-init-without-apply` loads adapters "without applying them (apply later via POST /lora-adapters)" ([60](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)). Rollback means dropping the flag. CPU overhead of an unmerged adapter was not measured here. [low]

Either way, qualify the quantized artifact that will serve, not the bf16 model.

**Cadence.** Train on triggers held in config, not on a calendar:
- enough new judged pairs since the last round;
- the champion's base model unchanged for some days;
- a few rounds at most per base model, and one round per window;
- a spend cap.

Each round must beat the current champion. ReST-EM repeats its loop only "a few times" ([20](https://arxiv.org/abs/2312.06585)). The pipeline changes about every 9 days (project record), and a base-model change restarts the fine-tune lineage.

**Automatic promotion with guards.** A fine-tuned model is just another challenger (brief). To be promoted it must:
1. beat the champion on the primary metric under the group-sequential test, on articles dated after its training cutoff;
2. be non-inferior on the held-out judge, completeness, copying, unsupported numbers, hedges (both ways) and HHEM;
3. show the gain within article-length strata;
4. pass that week's planted-fault and control checks for both judges;
5. have its CPU seconds per summary recorded (NS3).

After promotion the drift judge watches with an always-valid test and rolls back on degradation. Every decision is a ledger row, and one config flag stops the loop (NS1, NS5).

**Price of the training step (estimate).** LoRA costs about $4N$ FLOPs per training token (forward pass plus backward through frozen weights), with $N = 9\times10^9$. For $T$ tokens per epoch, GPU time is about $4NT/F$, where $F$ is effective throughput. Take $T = 4\times10^6$ tokens (for example 2,000 rows of 2,000 tokens; illustrative). An epoch then takes about 0.4 hours at 100 TFLOP/s (A100-class) and about 1.1 hours at 35 TFLOP/s (L4-class). DPO costs about 2 to 3 times SFT per example. One round is about 1 to 3 GPU-hours, or about 2 to 10 dollars at the prices below. Even five times worse stays under 50 dollars. Money is not the constraint; evaluation is.

| Option | GPU (VRAM) | Listed price | Fits 22 GB bf16 LoRA? | No person in the loop? |
|---|---|---|---|---|
| GitHub GPU larger runner | 1 Tesla T4 (16 GB), 4 vCPU, 28 GB RAM ([62](https://docs.github.com/en/actions/reference/runners/larger-runners)) | USD 0.052/min (3.12/h); Team or Enterprise plans only; "not free for public repositories" ([62](https://docs.github.com/en/billing/reference/actions-runner-pricing)) | No | Yes, but too small |
| Modal, billed per second | L4 / A100 80 GB / H100 | USD 0.000222/s (0.80/h) / 0.000694/s (2.50/h) / 0.001097/s (3.95/h); Starter includes 30 USD/month of compute ([63](https://modal.com/pricing)) | Yes (L4 is tight) | Yes: CI calls the API |
| RunPod pods | L4 24 GB / RTX 3090 24 GB / A100 80 GB / H100 PCIe | USD 0.59 / 0.50 / 1.79 / 2.89 per hour, updated 2026-09-27 ([64](https://www.runpod.io/pricing)) | Yes | Yes: API, with a hard teardown |
| Free notebook GPUs | 16 GB class | free | No | No: needs a person |

Options that keep a person out of the loop, best first:
1. A CI workflow calls a pay-per-second GPU function with a spend cap. The job trains, exports the GGUF or adapter, uploads it to a private store, writes a ledger row and registers a challenger.
2. The same through a pod API, with a hard timeout.
3. A self-hosted GPU runner that the owner maintains.

In every option, training runs outside CI's CPU runners, as the brief requires; only the trigger lives in CI (NS1).

## Q5. Judges

### (a) Sentence-level faithfulness classifiers with permissive licences

| Checker | Size | Licence | LLM-AggreFact avg | CNN (news) | XSum (news) | Notes |
|---|---|---|---|---|---|---|
| Granite Guardian 3.3 | 8B | Apache 2.0 ([54](https://huggingface.co/ibm-granite/granite-guardian-3.3-8b)) | 76.5 | 67.0 | 74.9 | 3rd on the board; figure from think mode; single-pass path reproduces about 0.758 ([55](https://github.com/ibm-granite/granite-guardian/tree/main/evaluation)); project record: 0.669 news no-think, about 5 min per summary |
| Granite Guardian 4.1 (April 2026) | 8B | Apache 2.0 | "RAG groundedness (Avg BAcc 0.76 think)" ([56](https://github.com/ibm-granite/granite-guardian/blob/main/cookbooks/granite-guardian-4.1/detailed_guide.ipynb)) | n/a | n/a | Official Q4_K_M GGUF listed ([56](https://ai.azure.com/catalog/models/ibm-granite-granite-guardian-4.1-8b-gguf)) |
| FactCG-DeBERTa-L | 0.4B | MIT ([53](https://huggingface.co/yaxili96/FactCG-DeBERTa-v3-Large)) | 75.6 | 70.1 | 73.9 | Encoder classifier, not GGUF; would run like HHEM (estimate); authors prefer per-dataset thresholds ([53](https://github.com/derenlei/FactCG)) |
| MiniCheck-Flan-T5-L | 0.8B | MIT ([51](https://huggingface.co/lytang/MiniCheck-Flan-T5-Large)) | 75.0 | 69.9 | 74.3 | Authors: "on par with GPT-4, but 400x cheaper" |
| Bespoke-MiniCheck-7B | 7B | CC BY-NC 4.0 ([52](https://huggingface.co/bespokelabs/Bespoke-MiniCheck-7B)) | 77.4 | 65.5 | 77.8 | Not permissive: excluded |

Scores are from the leaderboard ([50](https://llm-aggrefact.github.io/)). Overall rank and news rank differ. On CNN the two small MIT checkers lead Granite 3.3 by about 3 points; on XSum Granite leads by under 1 point. They are a tenth of its size or less. All are from families other than Qwen, so all meet NS4's family line, but adding one needs the owner's approval as a second model. [moderate]

### (b) Key-fact extraction and alignment for completeness

FineSurE scores completeness as the share of key facts a summary covers ([25](https://arxiv.org/abs/2407.00908)).
- With human key facts, GPT-4 completeness tracked human scores at 0.688 (linear correlation); with GPT-4-extracted key facts, at 0.571.
- Open models varied with size: 0.755 for Llama3-70B-Instruct, 0.585 for Gemma2-27B-Instruct, 0.439 for Mixtral-8x7B-Instruct and 0.093 for Phi-2 (2.7B). Phi-2 also followed the prompt only 52.1% of the time.

FeedSum found an 8B judge's feedback much weaker than a 70B judge's: summary-level rank correlation with humans of 0.358 against 0.649 ([24](https://arxiv.org/abs/2410.13116)). Gemma 4 E4B is Apache 2.0 with 4.5B effective parameters ([61](https://ai.google.dev/gemma/docs/core/model_card_4)). I found no evaluation of it on key-fact extraction. [low]

A design that limits the damage:
- Extract key facts once per article, cache them, and score both arms against the same list. Extraction errors are then shared and partly cancel in the paired difference (estimate).
- Validate with planted omissions: delete the sentence that carries a key fact, and completeness must fall.
- Check stability by extracting twice.
- Until these pass, use completeness only as a non-inferiority guard with a wide margin.

### (c) Self-preference when the judge shares the summarizer's family

- Self-preference is when "an LLM evaluator scores its own outputs higher than others' while human annotators consider them of equal quality" ([34](https://arxiv.org/abs/2404.13076)).
- In summarization, LM-based metrics favour their own model, a bias "particularly pronounced when such evaluation metrics are used in a reference-free manner" ([35](https://arxiv.org/abs/2311.09766)).
- "LLM-as-a-judge scores favor models similar to the judge", and "model mistakes are becoming more similar with increasing capabilities" ([36](https://arxiv.org/abs/2502.04313)).
- Across 350+ models, "models agree 60% of the time when both models err" on one dataset, and accurate models correlate "even with distinct architectures and providers" ([37](https://arxiv.org/abs/2506.07962)).

So the current plan to have the 9B summarizer grade its own completeness (project record) conflicts with NS4; that check should move to Gemma. A different family lowers shared blind spots but does not remove them. Pairing a decoder judge (Granite) with an encoder checker (FactCG or MiniCheck) adds diversity of architecture as well as family. [hypothesis] [high on the bias; moderate on the remedy]

### (d) Validating a judge without labels

1. **Planted faults with controls, nightly.** Start from sentences judged supported. Plant faults: swap entities, numbers and dates; negate; insert a sentence from another article. Add unaltered sentences and meaning-preserving rewrites as controls. Report the catch rate per fault type and the false-alarm rate on controls. These estimate $Se$ and $Sp$ on synthetic faults. They give a floor and a drift alarm, not real-world accuracy ([33](https://arxiv.org/abs/2305.14540), [51](https://huggingface.co/lytang/MiniCheck-Flan-T5-Large)).
2. **Agreement between independent judges on real sentences.** Report chance-corrected agreement and its trend, and send disagreements to a triage set. Agreement is not accuracy, because errors correlate ([37](https://arxiv.org/abs/2506.07962)).
3. **Calibration.** Use the judge's yes-probability, not only its label. Set the threshold on the planted faults and controls, and watch for calibration drift.
4. **An anchor panel.** Re-judge a fixed set of items every night. Any change means the judge or its runtime changed.
5. **Corrected rates.** Apply the screening-test correction with the planted-fault $Se$ and $Sp$, and report the wide interval it implies ([10](https://doi.org/10.1093/oxfordjournals.aje.a112510)).

## Q6. Designs whose cost stays flat from hundreds to 10,000 a day

**Sample size from precision.** For a rate $p$ and a 95% margin $E$: $n_0 = z^2 p(1-p)/E^2$. With a population of $N$ summaries: $n = n_0/(1 + (n_0-1)/N)$.

| Target | $n_0$ | N = 330 (a day now) | N = 2,310 (a week now) | N = 10,000 (a day at target) | N = 70,000 (a week at target) |
|---|---|---|---|---|---|
| $p = 0.05$, +/-0.02 | 456 | 192 | 381 | 436 | 453 |
| $p = 0.10$, +/-0.03 | 384 | 178 | 329 | 370 | 382 |
| $p = 0.20$, +/-0.05 | 246 | 141 | 222 | 240 | 245 |

From 330 to 10,000 a day the needed sample barely moves. Judge cost is flat in volume. It moves only with the precision wanted and with the judge's $J$ (Q2). [high]

**Clustering.** Sentences in one summary are correlated. With $m$ sentences the design effect is $1 + (m-1)\rho_{icc}$; for $m$ = 5, 10, 20 and $\rho_{icc} = 0.1$ it is 1.4, 1.9 and 2.9 (a grid of cases, not an assumed length). Sample summaries, not sentences, and judge every sentence of a sampled summary.

**Stratification.** Allocate by source and article-length band. Optimal allocation sets $n_h \propto N_h S_h$. Stratified PPI gives "substantially tighter confidence intervals" when the cheap scorer's accuracy varies by stratum ([8](https://arxiv.org/abs/2406.04291)). [moderate]

**Importance weighting.** Oversample risky summaries (low HHEM, new source, long article) with a known inclusion probability $\pi_i$, and weight each by $1/\pi_i$ so estimates stay unbiased. Active inference picks labels where the cheap model is uncertain and keeps "provably valid confidence intervals and hypothesis tests" ([9](https://arxiv.org/abs/2403.03208)). Cap the weights to bound variance.

**PPI for levels.** The estimate is $\hat\theta = \frac{1}{N}\sum_{j=1}^{N} f(X_j) + \frac{1}{n}\sum_{i=1}^{n}\big(Y_i - f(X_i)\big)$, where $f$ is a calibrated map from HHEM and lexical scores to the judge's label ([6](https://arxiv.org/abs/2301.09633)). Expect up to about 1.5 times the effective sample ([7](https://arxiv.org/abs/2403.07008)).

**What to keep.**

| Per summary (every one) | Per sampled summary |
|---|---|
| Article and summary IDs; config hash (prompt, decoding, input budget, model sha, quant, runtime build) | Source text as seen (rolling, about 31 days) |
| Input tokens seen; truncation flag | Sentence segmentation and its version |
| Output tokens and sentences (recorded, never targeted: NS2) | Per-sentence judge label and yes-probability |
| HHEM score and lexical counterweights | Judge model sha, prompt hash, runtime build |
| CPU seconds | Key-fact list (per article, cached) and its alignment |
| Stratum, inclusion probability $\pi_i$, random draw, sampled flag | That night's planted-fault and control results |
| | Pair ID, arm, test ID, night |

**CPU budget (estimate).**
- Per-summary scoring in the writer grows linearly. HHEM takes about 12.5 minutes a day at about 330 summaries (project record), so about 6.3 hours a day at 10,000. Only sampled judging is flat, so plan the writer's own scoring for 10,000 a day now (NS3).
- In the council, Granite at about 5 minutes per summary caps one job at about 40 summaries a night.
- Making a cheap encoder checker the primary judge, with Granite on a subsample as the held-out judge, is what makes 200 to 500 pairs a night reachable. Challenger generation then becomes the binding cost.

## Q7. Recommendation: a ranked, staged design

**Stage 0: measure the measuring (weeks 0 to 2; CPU only).**
- Pin the judges by hash. Measure seconds per sentence with the article cached and not. llama.cpp caches prompts by default and evaluates only the "unseen" suffix ([60](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)), so put the article before the sentence where the judge's template allows it. [low until measured]
- Run Granite 3.3 and, with approval, FactCG-DeBERTa-L or MiniCheck-Flan-T5-L on the same nightly sample, with planted faults and controls. Record agreement, catch and false-alarm rates, calibration and cost.
- Run an A/A test on 100 to 200 stored articles. It gives $\sigma_d$, the clustering and the false-alarm rate.
- Evidence: Q2, Q5. Risk: synthetic faults flatter judges. North Star: NS4 holds if the new checker is approved.

**Stage 1: the champion/challenger harness (weeks 2 to 6; CPU).**
- Every config change enters as a challenger on stored sample articles, under a group-sequential test with up to 5 looks.
- Primary metric: the unsupported-sentence share from judge P. Guards: held-out judge H, completeness (wide margin), copying, unsupported numbers, hedges both ways and HHEM. Length is recorded, and the gain is checked within article-length strata.
- Code promotes, holds or rejects; the gain is confirmed on fresh articles. After promotion an always-valid watch can trigger automatic rollback.
- CPU (estimate): two jobs generate challenger summaries; one runs judge P on both arms plus the planted items; one runs judge H on a subsample, plus key facts.
- Evidence: Q1(a), Q2, Q3. Risk: the pipeline changes about every 9 days, so tests may run out of nights. Run at most one or two challengers at a time.

**Stage 2: bounded search (months 2 to 3).**
- Successive elimination over 3 to 6 arms of prompt, decoding and input budget; never output-length caps. Then one confirmatory test on fresh articles.
- Evidence: Q1(c). Risk: the winner's curse; evidence for summarization is weak. [low]

**Stage 3: the first fine-tune (month 3 onward; GPU).**
- DPO with LoRA on pairs harvested in Stages 1 and 2: one epoch, reference model kept, bf16, on a rented 24 GB+ GPU started from CI by API, with a spend cap.
- Export a merged GGUF or a llama.cpp adapter. Qualify it through Stage 1 with judge H held out, check the learning curve, and allow only a few rounds per base model.
- Cost: about 1 to 3 GPU-hours and 2 to 10 dollars a round (estimate).
- Evidence: Q1(b), Q4. Risk: gains vanish after quantization, or the model fits judge P's quirks. [moderate]

**Later.** KTO only if pairs are scarce and the faithfulness guard holds ([24](https://arxiv.org/abs/2410.13116)); a three-judge panel ([38](https://arxiv.org/abs/2404.18796)); active sampling ([9](https://arxiv.org/abs/2403.03208)).

**Not recommended now.**
- Self-rewarding or same-family judging (NS4).
- Length penalties, or SimPO-style length normalisation as a first choice (NS2).
- QLoRA on Qwen3.5 ([59](https://unsloth.ai/docs/models/qwen3.5/fine-tune)).
- PPO: in FeedSum it scored 0.619, below the untuned 0.632 ([24](https://arxiv.org/abs/2410.13116)).
- Judging extra best-of-n candidates beyond the sample, which bends NS4.

**North Star check.** No stage breaks a line. Two need care: adding a checker needs approval as a second model (NS4); and the rented GPU sits outside CI but is started, bounded, recorded and stoppable from CI (NS1).

## Contradictions and how they were resolved

| Topic | One side | Other side | Resolution |
|---|---|---|---|
| Training on own outputs | Collapse ([44](https://www.nature.com/articles/s41586-024-07566-y)) | No collapse when accumulating ([45](https://arxiv.org/abs/2404.01413)) or verified ([46](https://arxiv.org/abs/2406.07515)) | Different setups. Accumulate, verify, bound the rounds |
| Judge choice | Granite 3.3 is 3rd overall ([55](https://github.com/ibm-granite/granite-guardian)) | Behind two small checkers on CNN news ([50](https://llm-aggrefact.github.io/)) | Choose on news-like data with planted faults, cost and licence |
| SFT on the best outputs | Gains in math and code ([20](https://arxiv.org/abs/2312.06585)) | Copy bias in summarization ([24](https://arxiv.org/abs/2410.13116)) | Task-dependent. For summaries, prefer pairwise DPO with copy guards |
| KTO vs DPO | KTO matches DPO ([17](https://arxiv.org/abs/2402.01306)) | KTO lost faithfulness ([24](https://arxiv.org/abs/2410.13116)) | Prefer DPO; use KTO only with a faithfulness guard |
| 4-bit training | QLoRA preserves "full 16-bit finetuning task performance" ([47](https://arxiv.org/abs/2305.14314)) | Not recommended for Qwen3.5 ([59](https://unsloth.ai/docs/models/qwen3.5/fine-tune)) | Architecture-specific. Follow the newer guidance for this model |
| Planted edits | Cheap and reproducible ([33](https://arxiv.org/abs/2305.14540)) | Do not reflect real behaviour ([51](https://huggingface.co/lytang/MiniCheck-Flan-T5-Large)) | Use as a floor and drift alarm, with controls; never as accuracy |
| Sequential method | Always-valid allows continuous monitoring ([3](https://arxiv.org/abs/1512.04922)) | Group-sequential has more power with a known maximum ([4](https://engineering.atspotify.com/2023/03/choosing-sequential-testing-framework-comparisons-and-discussions)) | Group-sequential for promotion; always-valid for the post-promotion watch |
| Agreement as validation | Diverse panels reduce bias ([38](https://arxiv.org/abs/2404.18796)) | Errors correlate across providers ([37](https://arxiv.org/abs/2506.07962)) | Treat disagreement as a signal, never agreement as accuracy |
| Strength of RLAIF | Accepted at ICML 2024 ([13](https://arxiv.org/abs/2309.00267)) | ICLR 2024 meta-review: one model family ([14](https://openreview.net/forum?id=AAxIs3D2ZZ)) | Moderate confidence; corroborated by [22](https://arxiv.org/abs/2311.08401), [23](https://arxiv.org/abs/2409.18618) and [24](https://arxiv.org/abs/2410.13116) |
| Data needed | 1,000 examples teach format ([49](https://arxiv.org/abs/2305.11206)) | DPO gains plateau near 46K pairs ([24](https://arxiv.org/abs/2410.13116)) | Start at 2K to 6K pairs and measure a learning curve |

## Limitations and residual risks

- Benchmark numbers come from different protocols (think vs no-think; tuned vs fixed thresholds) and partly from other domains. This news mix may rank the judges differently.
- Most cost figures are formula estimates resting on two project measurements. Runner throughput must be measured.
- No study covers Qwen3.5-9B summarization fine-tuning, LoRA on its hybrid layers served at Q4_K_M, or Gemma 4 E4B key-fact quality.
- I read abstracts, model cards and key tables. I re-ran nothing except the sample-size arithmetic and the group-sequential simulation.
- Pre-mortem: if this advice has failed in six months, the likeliest reasons are:
  1. The judge errs differently on the two arms, so the harness rewards a style (copying, paraphrase) rather than faithfulness.
  2. A fine-tune fits judge P's quirks and loses its gain after quantization.
  3. Pipeline churn never leaves enough nights to finish a test.

  The guards target exactly these: a held-out judge, copy constraints, qualification of the quantized artifact, and a cap on concurrent challengers.

## Conclusion

The binding constraint is measurement, not optimisation. A judge's informedness $J$ sets the exchange rate between CPU minutes and detectable quality. At Granite's news accuracy, each true point of improvement costs about nine times the articles a perfect judge would need. So the first effort should go to a paired harness and to cheaper, validated judges. That harness is not a detour: it produces the judged pairs that make fine-tuning possible. Published gains from label-free preference training on summaries are real but modest, and they turn into gaming when one proxy is pushed hard. Multi-metric constraints, a held-out judge and short, anchored training keep them honest. Cost stays flat because sample size follows precision, not volume.

## Sources

1. Miller, E. (2024). Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations. https://arxiv.org/abs/2411.00640
2. Deng, A., Xu, Y., Kohavi, R., Walker, T. (2013). Improving the Sensitivity of Online Controlled Experiments by Utilizing Pre-Experiment Data. WSDM. https://exp-platform.com/Documents/2013-02-CUPED-ImprovingSensitivityOfControlledExperiments.pdf
3. Johari, R., Pekelis, L., Walsh, D. (2019). Always Valid Inference: Bringing Sequential Analysis to A/B Testing. https://arxiv.org/abs/1512.04922
4. Spotify Engineering (2023). Choosing a Sequential Testing Framework: Comparisons and Discussions. https://engineering.atspotify.com/2023/03/choosing-sequential-testing-framework-comparisons-and-discussions
5. Spotify Confidence documentation. Sequential Tests. https://confidence.spotify.com/docs/experiments/stats/sequential-tests
6. Angelopoulos, A. N. et al. (2023). Prediction-Powered Inference. https://arxiv.org/abs/2301.09633
7. Boyeau, P. et al. (2024). AutoEval Done Right: Using Synthetic Data for Model Evaluation. https://arxiv.org/abs/2403.07008
8. Fisch, A. et al. (2024). Stratified Prediction-Powered Inference for Hybrid Language Model Evaluation. https://arxiv.org/abs/2406.04291
9. Zrnic, T., Candes, E. J. (2024). Active Statistical Inference. https://arxiv.org/abs/2403.03208
10. Rogan, W. J., Gladen, B. (1978). Estimating prevalence from the results of a screening test. American Journal of Epidemiology 107(1):71-76. https://doi.org/10.1093/oxfordjournals.aje.a112510
11. Lee, M. R., Shen, M. (2018). Winner's Curse: Bias Estimation for Total Effects of Features in Online Controlled Experiments. KDD. https://doi.org/10.1145/3219819.3219905
12. Stiennon, N. et al. (2020). Learning to summarize from human feedback. NeurIPS. https://arxiv.org/abs/2009.01325
13. Lee, H. et al. (2024). RLAIF vs. RLHF: Scaling Reinforcement Learning from Human Feedback with AI Feedback. ICML. https://arxiv.org/abs/2309.00267
14. OpenReview (2024). ICLR 2024 reviews and decision for the earlier RLAIF version. https://openreview.net/forum?id=AAxIs3D2ZZ
15. Rafailov, R. et al. (2023). Direct Preference Optimization: Your Language Model is Secretly a Reward Model. https://arxiv.org/abs/2305.18290
16. Hong, J., Lee, N., Thorne, J. (2024). ORPO: Monolithic Preference Optimization without Reference Model. https://arxiv.org/abs/2403.07691
17. Ethayarajh, K. et al. (2024). KTO: Model Alignment as Prospect Theoretic Optimization. ICML. https://arxiv.org/abs/2402.01306
18. Meng, Y., Xia, M., Chen, D. (2024). SimPO: Simple Preference Optimization with a Reference-Free Reward. NeurIPS. https://arxiv.org/abs/2405.14734
19. Yuan, W. et al. (2024). Self-Rewarding Language Models. ICML. https://arxiv.org/abs/2401.10020
20. Singh, A. et al. (2024). Beyond Human Data: Scaling Self-Training for Problem-Solving with Language Models. TMLR. https://arxiv.org/abs/2312.06585
21. Sessa, P. G. et al. (2024). BOND: Aligning LLMs with Best-of-N Distillation. https://arxiv.org/abs/2407.14622
22. Tian, K. et al. (2023). Fine-tuning Language Models for Factuality. https://arxiv.org/abs/2311.08401
23. Choi, J. et al. (2024). Model-based Preference Optimization in Abstractive Summarization without Human Feedback. EMNLP. https://arxiv.org/abs/2409.18618
24. Song, H. et al. (2025). Learning to Summarize from LLM-generated Feedback. NAACL. https://arxiv.org/abs/2410.13116
25. Song, H. et al. (2024). FineSurE: Fine-grained Summarization Evaluation using LLMs. ACL. https://arxiv.org/abs/2407.00908
26. Roit, P. et al. (2023). Factually Consistent Summarization via Reinforcement Learning with Textual Entailment Feedback. ACL. https://arxiv.org/abs/2306.00186
27. Gao, L., Schulman, J., Hilton, J. (2022). Scaling Laws for Reward Model Overoptimization. https://arxiv.org/abs/2210.10760
28. Coste, T. et al. (2024). Reward Model Ensembles Help Mitigate Overoptimization. ICLR. https://arxiv.org/abs/2310.02743
29. Moskovitz, T. et al. (2023). Confronting Reward Model Overoptimization with Constrained RLHF. https://arxiv.org/abs/2310.04373
30. Rafailov, R. et al. (2024). Scaling Laws for Reward Model Overoptimization in Direct Alignment Algorithms. NeurIPS. https://arxiv.org/abs/2406.02900
31. Park, R. et al. (2024). Disentangling Length from Quality in Direct Preference Optimization. https://arxiv.org/abs/2403.19159
32. Tam, D. et al. (2023). Evaluating the Factual Consistency of Large Language Models Through News Summarization. https://arxiv.org/abs/2211.08412
33. Laban, P. et al. (2023). LLMs as Factual Reasoners: Insights from Existing Benchmarks and Beyond. https://arxiv.org/abs/2305.14540
34. Panickssery, A., Bowman, S. R., Feng, S. (2024). LLM Evaluators Recognize and Favor Their Own Generations. https://arxiv.org/abs/2404.13076
35. Liu, Y., Moosavi, N. S., Lin, C. (2024). LLMs as Narcissistic Evaluators: When Ego Inflates Evaluation Scores. https://arxiv.org/abs/2311.09766
36. Goel, S. et al. (2025). Great Models Think Alike and this Undermines AI Oversight. https://arxiv.org/abs/2502.04313
37. Kim, E. et al. (2025). Correlated Errors in Large Language Models. ICML. https://arxiv.org/abs/2506.07962
38. Verga, P. et al. (2024). Replacing Judges with Juries: Evaluating LLM Generations with a Panel of Diverse Models. https://arxiv.org/abs/2404.18796
39. Wan, D. et al. (2025). On Positional Bias of Faithfulness for Long-form Summarization. NAACL. https://arxiv.org/abs/2410.23609
40. Zhang, T. et al. (2023). Benchmarking Large Language Models for News Summarization. https://arxiv.org/abs/2301.13848
41. Shi, C. et al. (2024). A Thorough Examination of Decoding Methods in the Era of LLMs. EMNLP. https://arxiv.org/abs/2402.06925
42. Wang, C., Liu, S. X., Awadallah, A. H. (2023). Cost-Effective Hyperparameter Optimization for Large Language Model Generation Inference. https://arxiv.org/abs/2303.04673
43. Shi, C. et al. (2024). Efficient Prompt Optimization Through the Lens of Best Arm Identification. https://arxiv.org/abs/2402.09723
44. Shumailov, I. et al. (2024). AI models collapse when trained on recursively generated data. Nature. https://www.nature.com/articles/s41586-024-07566-y
45. Gerstgrasser, M. et al. (2024). Is Model Collapse Inevitable? Breaking the Curse of Recursion by Accumulating Real and Synthetic Data. https://arxiv.org/abs/2404.01413
46. Feng, Y. et al. (2024). Beyond Model Collapse: Scaling Up with Synthesized Data Requires Verification. https://arxiv.org/abs/2406.07515
47. Dettmers, T. et al. (2023). QLoRA: Efficient Finetuning of Quantized LLMs. https://arxiv.org/abs/2305.14314
48. Biderman, D. et al. (2024). LoRA Learns Less and Forgets Less. TMLR. https://arxiv.org/abs/2405.09673
49. Zhou, C. et al. (2023). LIMA: Less Is More for Alignment. https://arxiv.org/abs/2305.11206
50. LLM-AggreFact leaderboard (accessed 2026-10-12), from Tang, L. et al. (2024), MiniCheck, EMNLP. https://llm-aggrefact.github.io/ and https://arxiv.org/abs/2404.10774
51. MiniCheck-Flan-T5-Large model card (MIT licence). https://huggingface.co/lytang/MiniCheck-Flan-T5-Large
52. Bespoke-MiniCheck-7B model card and licence (CC BY-NC 4.0). https://huggingface.co/bespokelabs/Bespoke-MiniCheck-7B
53. Lei, D. et al. (2025). FactCG: Enhancing Fact Checkers with Graph-Based Multi-Hop Data. NAACL. https://arxiv.org/abs/2501.17144 ; model card (MIT) https://huggingface.co/yaxili96/FactCG-DeBERTa-v3-Large ; code https://github.com/derenlei/FactCG
54. IBM. Granite Guardian 3.3 8B model card. https://huggingface.co/ibm-granite/granite-guardian-3.3-8b
55. IBM. granite-guardian repository README and evaluation README. https://github.com/ibm-granite/granite-guardian and https://github.com/ibm-granite/granite-guardian/tree/main/evaluation
56. IBM. Granite Guardian 4.1 8B model card, detailed guide and GGUF catalog listing. https://huggingface.co/ibm-granite/granite-guardian-4.1-8b ; https://github.com/ibm-granite/granite-guardian/blob/main/cookbooks/granite-guardian-4.1/detailed_guide.ipynb ; https://ai.azure.com/catalog/models/ibm-granite-granite-guardian-4.1-8b-gguf
57. Qwen. Qwen3.5-9B model card. https://huggingface.co/Qwen/Qwen3.5-9B
58. Modal. Qwen3.5 9B library page (architecture, release date, licence). https://modal.com/library/qwen/qwen3-5-9b
59. Unsloth. Qwen3.5 Fine-tuning Guide. https://unsloth.ai/docs/models/qwen3.5/fine-tune
60. llama.cpp. Server README (prompt cache, LoRA adapters). https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
61. Google. Gemma 4 model card. https://ai.google.dev/gemma/docs/core/model_card_4
62. GitHub Docs. Actions runner pricing; Larger runners reference. https://docs.github.com/en/billing/reference/actions-runner-pricing and https://docs.github.com/en/actions/reference/runners/larger-runners
63. Modal. Pricing (accessed 2026-10-12). https://modal.com/pricing
64. RunPod. GPU Cloud Pricing (updated 2026-09-27). https://www.runpod.io/pricing
65. Project record: TODO/20261012-summary-fidelity-judge-hard-look-record.md (section 4); docs/how-to/fine-tune-a-model.md; TODO/20261011-65-summary-fidelity-judge-plan.md.
