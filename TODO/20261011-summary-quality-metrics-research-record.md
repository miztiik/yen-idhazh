# Evaluating LLM-written news summaries without references: dimensions, metrics, composite decisions and drift monitoring

**Record**: research for plan 65, the summary-fidelity judge (TODO/20261011-65-summary-fidelity-judge-plan.md), made on 2026-10-11 at the owner's request to survey recent research on news and long-form summary metrics and on combining metrics into one decision. Written by a research agent; every cited work was checked to exist; quotations are kept short and the rest is summarised. It is evidence for the owner's rulings, not a ruling.

Research review for the yen-idhazh summary-fidelity judge ("hard look"), 2026-10-11.

Scope: work from arXiv, ACL, EMNLP, NAACL, EACL, TACL, COLM and related venues (mostly 2022-2025), plus the statistics literature on composite indicators and process monitoring. All 76 cited works were checked to exist (title, first author, year, venue or ID, URL). Items that could not be verified are listed at the end and are not used. Quotations are kept to one short phrase per source at most. Statements marked [inference] are my reasoning, not a paper's finding. Statements marked [estimate] are unmeasured cost guesses.

> **Key finding:** For LLM-written news summaries, recent work treats two dimensions as essential: faithfulness and completeness (coverage of the key facts). Conciseness matters but is hard to measure. Fluency is near ceiling, and coherence matters mainly for book-length output. The best always-on faithfulness signal is a cheap, CPU-friendly, reference-free sentence-level fact checker (HHEM, MiniCheck, FactCG, AlignScore). This holds only if it scores each summary sentence against windows of the source. Scoring the whole summary against each window gives worse results. Completeness and conciseness need an LLM judge, which you can afford only on a sample.
> **Confidence:** MODERATE-HIGH for the dimensions and the faithfulness tooling, because several independent benchmarks agree. MODERATE for the completeness and conciseness tooling. LOW for anything about a 9B local judge, because no published evaluation of such a judge exists.
> **Action:**
> - Rebuild faithfulness at sentence level and add entity and date checks.
> - Demote three weak metrics to diagnostics: self-judged fluency, adjacent-sentence cosine and top-20-word coverage.
> - Decide drift with two things: non-compensatory charts of gate-failure rates, and a correlation-aware weighted composite of covariate-adjusted daily residuals. Watch the composite with EWMA/CUSUM and add a MEWMA/Hotelling omnibus check.

---

## (a) Executive summary - the one-paragraph answer

Recent work on evaluating summaries has moved away from SummEval's four axes (coherence, consistency, fluency, relevance) to a smaller set centred on facts: faithfulness, completeness and conciseness (FineSurE, UniSumEval). Fluency was dropped because LLM output is already fluent, and coherence matters mainly at book length (BooookScore). Reference-based scores such as ROUGE and BERTScore stopped tracking human preference once LLMs wrote the summaries (Goyal et al. 2022; Zhang et al. 2024; Pu et al. 2023), and they need reference summaries you do not have. For faithfulness, small sentence-level fact checkers that run on CPU (HHEM-2.1-Open, MiniCheck, FactCG, AlignScore) roughly match GPT-4-class balanced accuracy on the LLM-AggreFact benchmark at a small fraction of the cost. However, every metric loses accuracy on long inputs, GPT-4 included. One benchmark of human-labelled LLM summaries (UniSumEval) found that these checkers correlate weakly with human judgement at summary level while a GPT-4 judge correlates well, so the evidence is mixed. How a checker is applied matters as much as which checker is used. Scoring each summary sentence against windows of the source and keeping the best window per sentence works better than scoring the whole summary against each window, which mixes up coverage with faithfulness. That mix-up is the likely cause of your long-article dip. Completeness and conciseness need LLM judging based on key facts. That works with strong models but is unproven with a 9B local model, so it belongs on a daily sample. LLM judges are biased by position, length and familiar wording, and they prefer their own output, which makes "the summariser grades its own fluency" the weakest item in your plan. For the drift decision, the literature on composite indicators and on optimising several objectives warns that weighted sums let a strong dimension hide a failing one and double-count correlated metrics. The defensible design has two parts: non-compensatory gates for hard failures, and a correlation-aware weighted composite of covariate-adjusted daily residuals monitored with EWMA/CUSUM. Add a MEWMA/Hotelling check for unexpected patterns, and a p-value combination that tolerates dependence (Cauchy) when many tests run. The main risk is that, with no human labels, none of this can be checked against quality on your own data. Alarms may then follow metric artefacts (copying, length, chunking, input mix) rather than real quality changes. The available safeguards are replays with injected changes and agreement between two checkers.

## Key findings at a glance

| # | Finding | Confidence | Main evidence |
|---|---|---|---|
| 1 | Faithfulness and completeness are essential, and conciseness comes third. Fluency is near ceiling, and coherence is secondary for short summaries. | HIGH | [FineSurE](https://aclanthology.org/2024.acl-long.51/), [UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/), [SEAHORSE](https://aclanthology.org/2023.emnlp-main.584/), [FABLES](https://arxiv.org/abs/2404.01261), [BooookScore](https://arxiv.org/abs/2310.00785) |
| 2 | ROUGE- and BERTScore-style reference metrics no longer track human judgement for LLM news summaries. | HIGH | [Goyal 2022](https://arxiv.org/abs/2209.12356), [Zhang 2024](https://aclanthology.org/2024.tacl-1.3/), [Pu 2023](https://arxiv.org/abs/2309.09558), [FineSurE](https://aclanthology.org/2024.acl-long.51/) |
| 3 | Small sentence-level checkers reach about GPT-4-class balanced accuracy (about 75) on LLM-AggreFact and run on CPU. | HIGH | [MiniCheck](https://arxiv.org/abs/2404.10774), [FactCG](https://aclanthology.org/2025.naacl-long.258/), [LLM-AggreFact board](https://llm-aggrefact.github.io/), [HHEM card (vendor)](https://huggingface.co/vectara/hallucination_evaluation_model) |
| 4 | On one large benchmark of human-labelled LLM summaries, the same checkers correlate weakly with humans at summary level, while a GPT-4 judge does much better. | MODERATE (conflicting evidence) | [UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/) versus [TofuEval](https://aclanthology.org/2024.naacl-long.251/) and [MiniCheck](https://arxiv.org/abs/2404.10774) |
| 5 | Long inputs hurt every faithfulness metric. The best aggregation takes the maximum over chunks for each summary sentence, then the mean over sentences. Scoring the whole summary against each chunk mixes coverage into faithfulness. | MODERATE-HIGH | [Wan 2025](https://aclanthology.org/2025.naacl-long.442/), [SummaC](https://arxiv.org/abs/2111.09525), [AlignScore](https://arxiv.org/abs/2305.16739), [UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/) |
| 6 | LLM judges show biases (position, verbosity, familiarity, self-preference) and are less reliable on good summaries. Small open models often fail the required output format or are inaccurate. | HIGH | [Zheng 2023](https://arxiv.org/abs/2306.05685), [Panickssery 2024](https://arxiv.org/abs/2404.13076), [Liu-Moosavi-Lin 2024](https://arxiv.org/abs/2311.09766), [Stureborg 2024](https://arxiv.org/abs/2405.01724), [Shen 2023](https://arxiv.org/abs/2305.13091), [FineSurE](https://aclanthology.org/2024.acl-long.51/) |
| 7 | Faithfulness metrics reward copying, yet extractive summaries are not automatically faithful. | HIGH (one benchmark disagrees for proprietary LLMs) | [Ladhak 2022](https://arxiv.org/abs/2108.13684), [Dreyer 2023](https://aclanthology.org/2023.findings-eacl.156/), [Zhang-Wan-Bansal 2023](https://arxiv.org/abs/2209.03549), [UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/) |
| 8 | Compensatory aggregation hides failures and double-counts correlated metrics. Non-compensatory gates or constraints avoid this. | HIGH (general, not specific to NLP) | [OECD/JRC Handbook](https://www.unescap.org/sites/default/files/JRC-OECD_Handbook%20Composite%20Indicators.pdf), [HDI notes](https://data.un.org/_Docs/HDR%20Technical%20Notes.pdf), [Vote'n'Rank](https://arxiv.org/abs/2210.05769), [Moskovitz 2024](https://arxiv.org/abs/2310.04373) |
| 9 | Drift monitoring should chart residuals adjusted for input covariates, account for autocorrelation and for control limits that were estimated rather than known, and combine metrics in a way that respects their correlation. | HIGH for the statistics; LOW for validation specific to LLM-summary metrics | [Steiner 2000](https://doi.org/10.1093/biostatistics/1.4.441), [Alwan & Roberts 1988](https://doi.org/10.1080/07350015.1988.10509640), [Lucas & Saccucci 1990](https://www.jstor.org/stable/1269835), [Lowry 1992](https://doi.org/10.1080/00401706.1992.10485232), [Jensen 2006](https://doi.org/10.1080/00224065.2006.11918623), [Liu & Xie 2020](https://doi.org/10.1080/01621459.2018.1554485) |

---

## 1. Which quality dimensions recent papers evaluate (Q1)

### 1.1 Frameworks (each verified)

| Framework (venue, year) | Data and input length | Dimensions | Take-away for us |
|---|---|---|---|
| [SummEval](https://aclanthology.org/2021.tacl-1.24/) (TACL 2021) | CNN/DailyMail news; 100 articles x 16 pre-LLM systems; expert and crowd ratings | Coherence, consistency, fluency, relevance (1-5) | The "four standard axes". Still the default set for testing metrics against human ratings (G-Eval reports on it), but its summaries pre-date LLMs. |
| [FRANK](https://aclanthology.org/2021.naacl-main.383/) (NAACL 2021) | CNN/DM and XSum; pre-LLM systems | A typology of factual errors: semantic-frame errors (predicate, entity, circumstance), discourse errors (coreference, discourse link) and verifiability errors (out-of-article, grammatical) | Faithfulness is several error types. Entity, number and date checks each target a specific class. |
| [FineSurE](https://aclanthology.org/2024.acl-long.51/) (ACL 2024) | FRANK (news) and REALSumm (news with key facts) | Faithfulness (share of summary sentences without an error), completeness (share of key facts covered), conciseness (share of summary sentences that align with key facts) | Drops fluency. Replaces Likert scores with judgements at sentence and key-fact level. |
| [UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/) (Findings EMNLP 2024) | 9 domains including news; inputs of 21-10,462 words; summaries from recent LLMs | Faithfulness, completeness, conciseness (fine-grained human labels) | Completeness collapses on long inputs. Non-LLM checkers do poorly on LLM errors. Conciseness is the hardest dimension to evaluate. |
| [SEAHORSE](https://aclanthology.org/2023.emnlp-main.584/) (EMNLP 2023) | 6 languages; summaries from 9 systems | Comprehensibility, repetition, grammar, attribution, main ideas, conciseness | Releases a learned mT5 metric for each dimension. |
| [LongEval](https://aclanthology.org/2023.eacl-main.121/) (EACL 2023) | Long-form summarisation | Faithfulness (a protocol for human evaluation) | Judging finer units reduces annotator disagreement, and annotating only some units preserves the rankings. |
| [FABLES](https://arxiv.org/abs/2404.01261) (COLM 2024) | 26 books; 3,158 annotated claims | Claim-level faithfulness; content selection (omissions, emphasis) | No LLM rater correlated strongly with humans on unfaithful claims. |
| [BooookScore](https://arxiv.org/abs/2310.00785) (ICLR 2024) | Book-length summaries | Coherence errors (score = share of sentences with none) | Coherence becomes a primary problem at book length. |
| [TofuEval](https://aclanthology.org/2024.naacl-long.251/) (NAACL 2024) | Topic-focused dialogue summaries | Sentence-level factual consistency, with explanations | LLMs, GPT-4 included, were weak binary judges. Specialised checkers were better and cheaper. |
| [InFusE / DiverSumm](https://aclanthology.org/2024.eacl-long.102/) (EACL 2024) | Long and diverse tasks | Faithfulness | The size of the source passage and the length of the claim being checked both matter. |
| [DiverseSumm](https://aclanthology.org/2024.naacl-long.32/) (NAACL 2024) | Multi-document news | Coverage of diverse information; faithfulness | GPT-4 covered under 40% of the diverse information. Metrics built on GPT-4 showed position and verbosity bias. |
| [RoSE / ACU](https://aclanthology.org/2023.acl-long.228/) (ACL 2023) | News and other domains | Salience via atomic content units | Human ratings made without a reference reflect annotators' general preferences rather than the input. Length differences confound metrics. |
| [InstruSum](https://aclanthology.org/2024.findings-naacl.280/) (Findings NAACL 2024) | Summaries that follow instructions | Several aspects | No LLM evaluator aligned strongly with humans. |
| [Fair Abstractive Summarization](https://aclanthology.org/2024.naacl-long.187/) (NAACL 2024) | Sources with several perspectives | Fair representation of perspectives | Fairness metrics that need no reference exist. |
| [AggreFact](https://arxiv.org/abs/2205.12854) (ACL 2023); [LLM-AggreFact](https://arxiv.org/abs/2404.10774) (EMNLP 2024); [SummEdits](https://arxiv.org/abs/2305.14540) (EMNLP 2023) | Factuality benchmarks | Binary consistency | Benchmarks for testing fact checkers against human labels. AggreFact found "no one metric is superior in all settings". |

### 1.2 Essential versus secondary

**Essential everywhere: faithfulness (factual consistency).** Every framework above includes it.
- Within it, the [FRANK](https://aclanthology.org/2021.naacl-main.383/) subtypes are where news summaries go wrong: entity errors, circumstance errors (time, place, numbers), predicate errors, and errors in who said what.
- Cheap targeted checks exist for some of these subtypes.

**Essential in LLM-era frameworks: completeness, i.e. coverage of the key facts.**
- It appears in FineSurE and UniSumEval, as SEAHORSE's "main ideas", as FABLES' content selection, as DiverseSumm's coverage and as RoSE's atomic content units.
- It is the dimension where LLM summaries degrade most as inputs get longer ([UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/)).

**Important but hardest to measure: conciseness.** It appears in FineSurE, UniSumEval and SEAHORSE.

**Secondary for short LLM summaries:**
- **Fluency, grammar and comprehensibility.** FineSurE omits fluency, noting that "modern AI models typically generate highly fluent outputs".
- **Coherence.** It is central at book length (BooookScore). It has little room to vary in a 2-4 sentence, 65-word summary [inference].
- **Redundancy.** SEAHORSE scores it as "repetition"; it is useful as a failure detector.

**Properties of a summary, not measures of quality:** abstractiveness or extractiveness, compression and length. Papers use them as controls or confounders ([Ladhak 2022](https://arxiv.org/abs/2108.13684), [Dreyer 2023](https://aclanthology.org/2023.findings-eacl.156/), [Grusky 2018](https://aclanthology.org/N18-1065/), [RoSE](https://aclanthology.org/2023.acl-long.228/)).

**Relevant only in some settings:**
- **Neutrality or balance of perspectives** ([Fair Abstractive Summarization](https://aclanthology.org/2024.naacl-long.187/)).
- **Preservation of certainty.** [Pei & Jurgens 2021](https://arxiv.org/abs/2109.14776) provide a model that measures it, but no summarisation framework treats it as a core axis.

**Relevance (SummEval) has been split in two.** FineSurE and UniSumEval separate it into completeness (did the summary include what matters?) and conciseness (did it leave out what does not?).

**On the owner's "four standard metrics".**
- In the literature the four are SummEval's: coherence, consistency, fluency and relevance.
- The LLM-era replacements are faithfulness, completeness and conciseness.
- Your current four (faithfulness, coverage, coherence, fluency) keep two axes that recent work demotes (coherence and fluency), and they do not measure conciseness.

---

## 2. Metrics per dimension: evidence, failure modes and cost (Q2) - table (b)

### 2.1 Table (b): dimensions x metrics x evidence x cost x fit for us

All metrics listed need no reference summary unless noted. "bAcc" means balanced accuracy against human labels.

| Dimension | Metric(s), no reference needed | Evidence against human judgement | Known failure modes | Cost class; runs on CPU at your volume? | Fit for us |
|---|---|---|---|---|---|
| Faithfulness | Sentence-level NLI or alignment checkers: HHEM-2.1-Open (flan-T5-base), MiniCheck (RoBERTa-L, DeBERTa-L, Flan-T5-L with 770M parameters), FactCG-DeBERTa-v3-L (0.4B), AlignScore (RoBERTa, 355M), SummaC-ZS/Conv | LLM-AggreFact bAcc: FactCG 75.6 and MiniCheck-FT5 75.0, against GPT-4 at 75.3 in the paper and GPT-4o at 75.9 on the leaderboard; AlignScore 70.4; SummaC-ZS 67.9. HHEM (vendor-reported): 76.6 on AggreFact-SOTA, 64.4 on RAGTruth-Summ. UniSumEval news, summary-level Pearson: AlignScore 0.18, MiniCheck 0.24 | Weak on subtle LLM errors. About 60 bAcc on long documents. Reward copying. Scoring the whole summary against a chunk mixes in coverage. | NLI cross-encoder. Yes: HHEM takes under 1.5 s per 2k-token input (vendor figure). The 0.4-0.8B checkers are several times slower [estimate]. | **High.** The core daily metric, re-aggregated per sentence. |
| Faithfulness | QA-based: QAFactEval, QuestEval (precision part) | QAFactEval scores 66.5 bAcc on LLM-AggreFact. Goyal 2022 found QA- and entailment-based factuality metrics unreliable on GPT-3 summaries. | Errors in the question-generation and answering pipeline; heavy | Several models, about 1.4B parameters in total; slow | Low |
| Faithfulness | Splitting into atomic facts and checking each (FActScore-style) | Designed for biographies checked against a knowledge source. UniSumEval found evaluation by decomposition weak. | Decomposition errors; many LLM calls per item | LLM, many calls per item | Low (too costly for the gain) |
| Faithfulness | LLM judge: FineSurE sentence fact-check, G-Eval consistency, fine-tuned checkers (Bespoke-MiniCheck-7B, Granite Guardian 3.3 8B), Prometheus 2 | FineSurE (FRANK, sentence-level bAcc): GPT-4-turbo 86.4, Llama-3-70B 92.0, Gemma-2-27B 90.8, Mixtral 78.7, Phi-2 48.1. LLM-AggreFact: Bespoke-MiniCheck-7B 77.4, Granite Guardian 3.3 76.5, Qwen2.5-72B 75.6, QwQ-32B 71.8. UniSumEval: G-Eval with GPT-4-turbo reaches 0.65 Pearson on news. TofuEval: LLMs were poor binary judges. | Position, verbosity and familiarity biases; self-preference; small models fail the output format; less reliable on good summaries | LLM judge: 1-4 s or more per item | **Medium.** A sampled adjudicator, preferably not the summariser itself. |
| Entity, number and date consistency | Checks that each item in the summary appears in the source: your unsupported-numbers check, plus entities and dates; entity-level precision ([Nan 2021](https://arxiv.org/abs/2102.09130)) | FRANK treats entity errors and circumstance errors as distinct error classes. Quantity hallucination is studied separately ([Zhao 2020](https://arxiv.org/abs/2009.13312)). | Misses derived values (unit conversions, rounding, "dozens"); NER mistakes | Lexical or NER; milliseconds | **High.** Hard gate. |
| Certainty, hedging, attribution | Your hedge-dropped check and evidential/speculative density; a certainty model ([Pei & Jurgens 2021](https://arxiv.org/abs/2109.14776)) | The certainty model was trained and validated on science findings in papers and news, not on general news summaries. | Gaps in the word lists; may not transfer | Small encoder | **Medium.** Gate on hedge-dropped; use the certainty shift as an index. |
| Completeness / coverage | Key facts extracted and aligned by an LLM (FineSurE) | GPT-4: Pearson 0.688 with human key facts and 0.571 with LLM-extracted key facts (REALSumm). | Depends on the quality of the key-fact list; small models unreliable | LLM; sample only | **Medium-high** (sampled) |
| Completeness / coverage | QuestEval recall; SEAHORSE "main ideas" (mT5); UniEval relevance (needs a reference) | Evidence is pre-LLM or from the same data the metric was trained on. UniEval was weak on LLM summaries in FineSurE and UniSumEval. | May not transfer to your domain | T5/mT5 encoder-decoders (about 0.8-1.2B); slow but feasible | Low-medium (trial) |
| Coverage, lexical (yours) | Recall of the article's top-20 frequent words; entity coverage anchored on the lead | No validation found in the literature. Your own analysis shows coverage over the whole article has little dynamic range. | Penalises paraphrase; moves with copying and with article length | Lexical | Low as a primary signal; keep lead coverage as a diagnostic |
| Coverage by position | Which source window supports each summary sentence (a free by-product of sentence-level faithfulness) | LLM summarisers lean on the start and end of the input ([Ravaut 2024](https://arxiv.org/abs/2310.10570)). Faithfulness varies with position in a U-shape ([Wan 2025](https://aclanthology.org/2025.naacl-long.442/)). Book summaries over-emphasise endings (FABLES). | Emphasis on the lead is legitimate in news | Free | Medium (diagnostic) |
| Conciseness | FineSurE conciseness; SEAHORSE conciseness | UniSumEval: the hardest dimension for automatic evaluators | Depends on the key-fact list | LLM (sampled) or mT5 | Medium (sampled) |
| Coherence | Your adjacent-sentence cosine; UniEval coherence; G-Eval coherence; BooookScore | [Steen & Markert 2022](https://aclanthology.org/2022.coling-1.527/): no automatic coherence measure was reliable across evaluation settings. BooookScore is validated only for books. | Cosine rewards sentences on the same topic, including repetition [inference] | Small encoder or LLM | Low (diagnostic only) |
| Fluency | G-Eval fluency; SEAHORSE grammar and comprehensibility; your planned self-judged score | FineSurE drops fluency. G-Eval reports a bias towards text written by LLMs. | Self-preference; familiarity bias; scores bunched at the top | LLM | **Low.** Do not have the summariser judge itself. |
| Redundancy | Your self-repetition; SEAHORSE repetition | SEAHORSE scores repetition as a dimension of its own | - | Lexical | High, as a loop detector |
| Abstractiveness | Your extractiveness and longest verbatim run; Grusky's density and coverage | Faithfulness metrics correlate with extractiveness ([Ladhak 2022](https://arxiv.org/abs/2108.13684)). Factuality adjusted for abstractiveness ([Dreyer 2023](https://aclanthology.org/2023.findings-eacl.156/)). Extractive summaries can still be unfaithful ([Zhang 2023](https://arxiv.org/abs/2209.03549)). No such relation for proprietary LLMs (UniSumEval). | Not a quality target in itself | Lexical | Covariate and guard rail |
| Length and compression | Summary word count; compression ratio | Automatic metrics do not reflect length differences (RoSE). LLM judges favour longer outputs, which can be corrected by regression ([Dubois 2024](https://arxiv.org/abs/2404.04475)). | Compression mostly measures article length (your own analysis) | Lexical | Covariate; length bounds as a gate |
| Neutrality and perspectives | Coverage of perspectives as in fair summarisation ([Zhang 2024](https://aclanthology.org/2024.naacl-long.187/)) | Reference-free metrics have been proposed but not tested on 65-word news digests. | Needs perspective or stance detection | Small classifier or LLM | Low (optional, sampled) |
| Input quality | Your page-furniture flag | Operational; no paper | - | Lexical | Gate: exclude flagged items and chart their rate as input drift |

### 2.2 Faithfulness: what the numbers say

**LLM-AggreFact** combines 11 datasets of text generated from a source, including summarisation ([MiniCheck](https://arxiv.org/abs/2404.10774)).
- MiniCheck-Flan-T5-L (770M parameters) reached 74.7% balanced accuracy, against 75.3% for GPT-4, at roughly 400 times lower cost.
- Other checkers scored lower: AlignScore 70.4, SummaC-ZS 67.9, QAFactEval 66.5.
- Mid-size LLMs did worse than these small checkers: Mixtral-8x7B 67.3, Gemini-Pro 66.2.
- The [live leaderboard](https://llm-aggrefact.github.io/) now lists [FactCG-DeBERTa-L](https://aclanthology.org/2025.naacl-long.258/) (0.4B) at 75.6, level with Qwen2.5-72B (75.6) and close to GPT-4o (75.9).
- Fine-tuned 7-8B checkers lead the board: Bespoke-MiniCheck-7B 77.4, Granite Guardian 3.3 at 76.5.

**AggreFact's lesson still holds.** Metric gains came mostly on older summarisers, and "no one metric is superior in all settings" ([AggreFact](https://arxiv.org/abs/2205.12854)).

**HHEM-2.1-Open's figures come only from the vendor.** It scores 76.6 on AggreFact-SOTA and 64.4 on RAGTruth-Summ ([model card](https://huggingface.co/vectara/hallucination_evaluation_model)). I found no independent LLM-AggreFact entry for it. Treat it as a capable checker whose validation comes from a single source.

**The evidence conflicts on LLM judges versus checkers.**
- [UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/) used human-labelled LLM summaries across domains. On news, the summary-level correlation with human faithfulness ratings was 0.18 for AlignScore and 0.24 for MiniCheck, against 0.65 for G-Eval with GPT-4-turbo.
- [TofuEval](https://aclanthology.org/2024.naacl-long.251/) found the opposite on dialogue: GPT-4 was a poor binary judge, and specialised checkers were better and cheaper.
- The two studies differ in granularity: UniSumEval correlated summary-level scores on mostly-correct summaries, while TofuEval measured sentence-level binary accuracy. They also differ in domain and in how strong the judge was.

**Practical reading.** A small checker is the right always-on instrument. A strong LLM judge does better at summary level, but you cannot run a GPT-4-class judge, and the accuracy of a 9B judge is unknown.

### 2.3 LLM judges: where they help, and their biases

**G-Eval** asks GPT-4 to fill in an evaluation form and weights the score by token probabilities. It reached a Spearman correlation of 0.514 on SummEval and warned of a bias towards text written by LLMs ([G-Eval](https://arxiv.org/abs/2303.16634)).

**Documented biases:**
- **Position, verbosity and self-enhancement** ([Zheng 2023](https://arxiv.org/abs/2306.05685)).
- **Self-preference**, which rises with the model's ability to recognise its own text. It was measured on news summarisation ([Panickssery 2024](https://arxiv.org/abs/2404.13076)).
- **Stronger self-bias when no reference is used** ([Liu, Moosavi & Lin 2024](https://arxiv.org/abs/2311.09766)).
- **Preference for low-perplexity text, skewed score distributions, anchoring** when several attributes are rated in one prompt, and **low agreement between samples** ([Stureborg 2024](https://arxiv.org/abs/2405.01724), preprint).
- **Less reliable as summary quality rises** ([Shen 2023](https://arxiv.org/abs/2305.13091)).
- **Length bias**, which can be removed by regression adjustment ([Dubois 2024](https://arxiv.org/abs/2404.04475)).

**Model size matters.**
- In FineSurE's comparison, the 2.7B Phi-2 performed at chance (48.1 bAcc). Small models often failed to produce the required output format (50-89% success).
- Open models of 27-70B were strong on FRANK.
- On LLM-AggreFact's harder, LLM-generated claims, open models of 32-72B were no better than checkers of 0.4-0.8B.

**Implication for "the summariser judges its own fluency".** Every documented bias points the same way: inflated, compressed, self-favouring scores on a dimension that is already near ceiling. Do not build it as specified.

### 2.4 Coverage, completeness and conciseness

- **FineSurE's key-fact method** lists the article's key facts and aligns summary sentences to them. It gave the best completeness correlation: 0.688 with human key facts and 0.571 with key facts extracted by GPT-4.
- **UniSumEval:**
 - Completeness is where LLM summaries lose ground on long inputs. For non-dialogue inputs it fell from 67.0% (short) to 31.7% (long), while human-judged faithfulness stayed flat (92.1 versus 93.1).
 - Conciseness was the hardest dimension for automatic evaluators.
- **[DiverseSumm](https://aclanthology.org/2024.naacl-long.32/):** GPT-4 covered under 40% of the diverse information in multi-document news. Coverage metrics built on GPT-4 showed position and verbosity bias.
- **[LongEval](https://aclanthology.org/2023.eacl-main.121/):**
 - Judging finer units (clauses) reduced annotator spread, with the standard deviation falling from 18.5 to 6.8.
 - Judging half the units preserved system rankings (Kendall's $\tau = 0.89$).
 - This supports sampling sentences or key facts rather than judging everything.
- **No paper validated a top-k frequent-word recall proxy.** It is a reference-free cousin of ROUGE-1 and moves with copying and article length [inference].

### 2.5 Coherence and fluency

- [Steen & Markert (COLING 2022)](https://aclanthology.org/2022.coling-1.527/) found that none of the automatic coherence measures they tested gave reliable scores across evaluation settings. Even strong measures were biased towards particular summarisers.
- [BooookScore](https://arxiv.org/abs/2310.00785) shows that coherence errors matter at book length.
- For a 65-word summary, adjacent-sentence cosine mostly measures how similar two to four sentences are in topic, and a repetitive summary maximises that [inference].
- On fluency: FineSurE dropped it, and SEAHORSE keeps grammar and comprehensibility mainly for multilingual and weaker systems.

### 2.6 What the literature says about your counterweights

**Extractiveness.**
- Both automatic faithfulness metrics and human faithfulness ratings rise as summaries copy more ([Ladhak 2022](https://arxiv.org/abs/2108.13684)).
- [Dreyer 2023](https://aclanthology.org/2023.findings-eacl.156/): factuality usually falls as abstractiveness rises, at a rate that depends on the system. The paper proposes factuality metrics adjusted for abstractiveness.
- [Zhang, Wan & Bansal 2023](https://arxiv.org/abs/2209.03549): extractive summaries can still be unfaithful.
- UniSumEval found no trade-off between abstractiveness and faithfulness for proprietary LLMs.
- So monitor faithfulness and extractiveness jointly.

**Your 2026-09-07 step.** Your brief records a step on that date: HHEM p25 rose from about 0.81 to 0.88 while median extractiveness rose from about 0.11 to 0.18. This is the pattern Ladhak et al. warn about: a faithfulness gain that may have been bought by copying. The cause is not established.

**Numbers and entities.**
- [Zhao 2020](https://arxiv.org/abs/2009.13312) treats hallucinated quantities as an error class of their own. Your unsupported-numbers check verifies the same thing.
- For entities, see the entity-level precision of [Nan 2021](https://arxiv.org/abs/2102.09130) and FRANK's entity and circumstance categories.

**Hedging.** [Pei & Jurgens 2021](https://arxiv.org/abs/2109.14776) released models of certainty at sentence and aspect level, built for science communication. They are a candidate for measuring "certainty inflation" beyond a word list. Whether they transfer to general news is unverified.

**Length.**
- [RoSE](https://aclanthology.org/2023.acl-long.228/) found that automatic metrics do not reflect length differences between systems.
- Length-controlled AlpacaEval corrects judge preferences for length by regression. That is the same idea as the covariate (risk) adjustment in section 6.

### 2.7 What runs on 4 vCPU at 280-450 summaries a day

All figures here are estimates; benchmark them before relying on them. Volume is at most 450 summaries a day, with a median article of about 480 words and about three sentences per summary.

| Metric | Expected cost |
|---|---|
| Lexical and NER checks | Negligible. |
| HHEM, each summary sentence against each source window | A median article spans 1-2 windows, giving 3-6 pairs per summary. A 3,300-word article spans 10 or more windows, giving about 30 pairs, or 6 or fewer if an embedding prefilter keeps only the best two windows per sentence. The vendor reports under 1.5 s for a 2k-token input on a modern Xeon, and shorter pairs cost less. Rough total: tens of minutes a day on 4 vCPU [estimate]. |
| FactCG-DeBERTa-L or MiniCheck-Flan-T5-L (0.4-0.8B) | Several times HHEM's cost per pair [estimate]. All items may fit in a nightly batch; if not, use a stratified sample of 100 a day. |
| 9B judge | You measured 1-4 s per short item. Prompts that include the full article cost more for long articles, because prompt processing scales with prompt length [inference]. |

---

## 3. What LLM-era news-summarisation papers found about classic metrics (Q3)

**[Goyal, Li & Durrett (2022)](https://arxiv.org/abs/2209.12356):**
- Humans strongly preferred zero-shot GPT-3 news summaries, even though these scored about 7 ROUGE-L points lower than fine-tuned systems.
- Neither reference-based nor reference-free metrics evaluated them reliably. This included the QA-based and entailment-based factuality metrics.

**[Zhang et al. (TACL 2024)](https://aclanthology.org/2024.tacl-1.3/):**
- Across ten LLMs, instruction tuning, not model size, drove the quality of zero-shot news summaries.
- The reference summaries in CNN/DM and XSum were judged worse than LLM outputs. Their low quality weakens the correlation between metrics and humans.
- The best LLM summaries were on a par with those of freelance writers.

**[Pu, Gao & Wan (2023, arXiv)](https://arxiv.org/abs/2309.09558):**
- Human evaluators preferred LLM summaries over human-written ones and over those from fine-tuned models, across five tasks including single-article news.
- The LLM summaries had better factual consistency and fewer hallucinations of facts absent from the source.

**[FineSurE](https://aclanthology.org/2024.acl-long.51/):** ROUGE-style metrics correlate poorly with human judgement. BERTScore's correlation with faithfulness on FRANK was near zero.

**[RoSE](https://aclanthology.org/2023.acl-long.228/):** even the human protocol matters. Human ratings made without a reference reflect annotators' general preferences rather than the input.

**An older exception that does not apply here.** In a pre-LLM study with references, [Koh et al. (2022)](https://arxiv.org/abs/2210.16732) found ROUGE still the best of the tested metrics for relevance on long documents, while factuality metrics struggled. This does not apply without references.

**What replaced reference metrics:**
- Fact checkers that compare the summary with the source, needing no reference.
- Fine-grained LLM judging: fact checks per sentence plus key facts.
- Learned evaluators covering several dimensions (UniEval, SEAHORSE). These older evaluators transfer poorly to LLM summaries ([FineSurE](https://aclanthology.org/2024.acl-long.51/); [UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/)).
- Pairwise preference judgements by humans or LLMs.

---

## 4. Long documents: chunking, aggregation, position and length (Q4)

### 4.1 What the literature found

**Granularity.**
- A single NLI judgement over the whole document misses unsupported sentences. [SummaC](https://arxiv.org/abs/2111.09525) instead scores sentence pairs and aggregates them; SummaC-Conv reached 74.4 bAcc on its own benchmark.
- [AlignScore](https://arxiv.org/abs/2305.16739) splits the source into chunks and the summary into sentences, then aggregates.
- [MiniCheck](https://arxiv.org/abs/2404.10774) checks each summary sentence against the chunks and keeps the best chunk.
- [InFusE](https://aclanthology.org/2024.eacl-long.102/) varies how much source text is used as evidence and splits long summary sentences into shorter claims.

**Accuracy on long documents is low for every metric.**
- [Wan et al. 2025](https://aclanthology.org/2025.naacl-long.442/) found all metrics weak on long-form summaries. MiniCheck scored about 60 bAcc with fixed chunks and 61.4 with chunks at natural document boundaries; GPT-4o given the full context scored 64.1.
- The best way to combine scores was the maximum over chunks for each summary sentence, then the mean over sentences.
- Scoring each chunk against the whole summary confuses faithfulness with coverage.
- How faithful summaries are varies with position in the source in a U-shape.

**Ways to save cost.**
- [SCALE](https://arxiv.org/abs/2310.13189) uses large chunks with Flan-T5 to reduce the number of calls.
- [LongDocFACTScore](https://aclanthology.org/2024.lrec-main.941/) uses sentence embeddings to find the most similar source sentences for each summary sentence.
- [Extract-then-Evaluate](https://arxiv.org/abs/2309.07382) extracts key source sentences before LLM evaluation, which lowers cost and raised the correlation with humans.

**Position and coverage.**
- LLM summarisers draw disproportionately on the start and end of long inputs ([Ravaut 2024](https://arxiv.org/abs/2310.10570), which also introduced the MiddleSum benchmark). This is consistent with "lost in the middle" in question answering ([Liu 2024](https://arxiv.org/abs/2307.03172)).
- Book summaries omit content and over-emphasise endings ([FABLES](https://arxiv.org/abs/2404.01261)).

**Length and human judgement.** In [UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/), human-judged faithfulness did not drop for long non-dialogue inputs, while completeness did. An automatic faithfulness score that falls on long articles is therefore at least partly a measurement artefact [inference from Wan et al. and UniSumEval].

### 4.2 What this means for your `hhem` column

**Why the score falls on long articles.**
- Your own documentation says the score is the best of overlapping windows, with the whole summary scored against each window.
- When a 65-word summary draws on two or more windows, which is common for long articles, no single window supports all of it.
- The maximum therefore drops even when every sentence is supported. This is exactly the confound Wan et al. describe.

**The fix:**
1. Build a sentence x window matrix of scores.
2. For each summary sentence, keep its best window.
3. Summarise per item with two numbers: the mean over sentences (an index) and the minimum, or the count of sentences below a threshold (a gate).
4. Record which window won for each sentence. This gives the position profile for free.
5. Keep `hhem_full` and `hhem_delta` as diagnostics.
6. Optionally add an embedding prefilter, as in LongDocFACTScore, to cap the cost.

**Afterwards.** Check whether any length dependence remains. If it does, adjust for it as a covariate, not as a judged metric.

---

## 5. (c) Combining several quality metrics into one decision (Q5, part 1)

### 5.1 Methods and their pitfalls

| Method | How it combines | Where it is used | Documented pitfalls | Fit for us |
|---|---|---|---|---|
| Weighted arithmetic mean (including a plain average) | Weighted sum of normalised scores | UniEval's "overall" score is the plain mean of its dimensions ([UniEval](https://aclanthology.org/2022.emnlp-main.131/)). UniSumEval's domain-stability composite is the mean of three percentages. Most leaderboards. | Full compensation: a strong dimension hides a failing one. Double-counts correlated metrics. Depends on normalisation. Weights are arbitrary ([OECD/JRC](https://www.unescap.org/sites/default/files/JRC-OECD_Handbook%20Composite%20Indicators.pdf)). A mean assumes the metrics are comparable ([Vote'n'Rank](https://arxiv.org/abs/2210.05769)). | Display only |
| Weighted geometric mean | Product of scores, each raised to its weight | The Human Development Index since 2010, for "imperfect substitutability" between dimensions ([HDI notes](https://data.un.org/_Docs/HDR%20Technical%20Notes.pdf)) | Needs positive, comparable scales. Some compensation remains. | Display |
| Desirability functions | Map each metric to a 0-1 desirability, then combine. Commonly by geometric mean, so any zero vetoes the whole; the 1980 abstract confirms only the map-and-combine idea. | [Derringer & Suich 1980](https://doi.org/10.1080/00224065.1980.11980968) (process optimisation) | The desirability curves are judgement calls, and there are no labels to fit them. | Display, with gates |
| Min / any-fail (non-compensatory) | Fail if any metric fails its threshold | Plan 36's veto chain; the OECD handbook's non-compensatory multi-criteria analysis; per-component thresholds in [constrained RLHF](https://arxiv.org/abs/2310.04373) | Many gates add up false alarms. Thresholds need calibration. The noisiest metric dominates. | **Per-item gates** |
| Constraints first, then optimise (lexicographic) | Must pass the thresholds, then rank on the main metric | [Moskovitz 2024](https://arxiv.org/abs/2310.04373) | Where to put the thresholds | For model or prompt changes |
| Pareto / dominance | Keep the options that no other option beats on every dimension | Comparing options against several objectives | Only a partial order; gives no single decision | For comparing two configurations |
| Social-choice rules (Borda, Copeland) | Aggregate rankings | [Vote'n'Rank 2023](https://arxiv.org/abs/2210.05769) | Built for ranking systems, not for monitoring one system | Low |
| Learned aggregator | Fit weights to human preferences or labels | [QAFactEval](https://arxiv.org/abs/2112.08542) combines QA and NLI signals; [SEAHORSE](https://aclanthology.org/2023.emnlp-main.584/) learns its metrics; [EvalGen](https://arxiv.org/abs/2404.12272) aligns checks with users' grades | Needs labels, which you forbid. Using an LLM judge as the teacher is circular. Goodhart effects. | Not available |
| Statistical distance (Mahalanobis / Hotelling $T^2$) | Distance of today's vector from the reference period, using the covariance | MEWMA and $T^2$ charts ([Lowry 1992](https://doi.org/10.1080/00401706.1992.10485232)) | Does not say which direction moved; harder to interpret | Omnibus drift check |
| Correlation-aware weighted $z$ (Stouffer-type) | $C = \frac{\sum_k w_k z_k}{\sqrt{w^\top R w}}$ | Standard statistics; recommended here (section 7.4) | Needs $R$ estimated over a stable window; only detects shifts in the weighted direction | **Main drift composite** |

**Fit for us** names the most a method may do here. **Display**: a number a person reads on the console; no gate, alarm or publish decision reads it. **Display only**: shown at most, never used to decide, because a strong metric hides a failing one. **Display, with gates**: the shown number drops to 0 when any per-summary gate fails (section 7.4, item 6).

### 5.2 Documented pitfalls

1. **Compensation.** A composite "may disguise serious failings in some dimensions" ([OECD/JRC Handbook](https://www.unescap.org/sites/default/files/JRC-OECD_Handbook%20Composite%20Indicators.pdf)). The HDI moved to a geometric mean because a linear formula allowed perfect substitution between dimensions.
2. **Correlated metrics.**
  - The handbook asks builders to decide whether correlation and compensability between indicators should be corrected for or kept as features.
  - In your stack, HHEM, lexical coverage, longest verbatim run and extractiveness all move with copying. A plain sum would count copying several times [inference].
  - Correlation between reward components shifts the point at which optimising a composite starts to hurt ([Moskovitz 2024](https://arxiv.org/abs/2310.04373)).
3. **Scale and skew.**
  - The choice of normalisation changes the result, and skewed indicators must be transformed (OECD handbook).
  - HHEM is bounded and close to its ceiling (p25 about 0.88), so raw z-scores are unstable. Use logit or rank-based transforms [inference].
4. **Weights are value judgements.** The handbook calls for sensitivity analysis on weights and aggregation. Different users value dimensions differently ([Ethayarajh & Jurafsky 2020](https://arxiv.org/abs/2009.13888)).
5. **Goodhart effects.**
  - Optimising a proxy beyond a certain point lowers true quality ([Gao 2023](https://arxiv.org/abs/2210.10760)). Manheim & Garrabrant describe four variants: regressional, extremal, causal and adversarial ([Manheim & Garrabrant 2018](https://arxiv.org/abs/1803.04585)).
  - If prompts or models are tuned against the composite, the cheapest moves will show up first: more copying, shorter summaries [inference].
6. **Criteria drift.** Evaluators' criteria change as they see more outputs ([Shankar 2024](https://arxiv.org/abs/2404.12272)).
7. **Opacity.** A composite should be decomposable into its parts (OECD handbook). System rankings change from one dimension to another ([FineSurE](https://aclanthology.org/2024.acl-long.51/)).

**Gap.** I found little published evidence on how production LLM-summary systems combine metrics into one decision. Documented practice is mostly sets of pass/fail checks (EvalGen) plus dashboards.

---

## 6. (d) Monitoring quality drift over time (Q5, part 2)

### 6.1 Methods

| Method | What it detects | Key assumption | Pitfall or mitigation | Fit for us |
|---|---|---|---|---|
| Shewhart charts ($p$-chart, $\bar{X}$-chart) on daily rates or means | Large sudden shifts | Days are independent; in-control mean and SD known | Insensitive to small shifts | Gate rates. Low-volume days need limits that widen as the day's row count $n$ shrinks. |
| EWMA (Roberts 1959; [Lucas & Saccucci 1990](https://www.jstor.org/stable/1269835)) | Small persistent shifts. A small $\lambda$ suits small shifts. Optional fast-initial-response feature and combined Shewhart-EWMA. | Independence | Inertia. The authors advise that "a statistical control scheme should always be applied to the residuals from the model". | Daily residual mean of each metric |
| CUSUM ([Page 1954](https://doi.org/10.1093/biomet/41.1-2.100)) | A sustained shift of a chosen size | In-control parameters known | You must choose the shift size; one-sided | Gate rates |
| Risk-adjusted CUSUM ([Steiner 2000](https://doi.org/10.1093/biostatistics/1.4.441)) | A change in outcomes after adjusting each case for its risk | The per-case risk model is valid | Model misspecification | **Your input-mix problem** |
| Residual (special-cause) charts ([Alwan & Roberts 1988](https://doi.org/10.1080/07350015.1988.10509640)) | Shifts in an autocorrelated series | A fitted time-series model | Must be refitted | Day-to-day correlation from the news cycle |
| Self-starting CUSUM ([Hawkins 1987](https://doi.org/10.2307/2348827)) | Drift from start-up conditions, using the running mean and SD as the baseline | A stable start | Slow drifts can be absorbed into the baseline | Fits the "no golden set" rule |
| Effects of estimated parameters ([Jensen 2006](https://doi.org/10.1080/00224065.2006.11918623)) | - | - | Limits estimated from short reference windows change the false-alarm rate | Use long windows; calibrate by simulation or bootstrap |
| MEWMA plus Hotelling $T^2$ ([Lowry 1992](https://doi.org/10.1080/00401706.1992.10485232)) | Joint shifts in correlated metrics; $T^2$ catches large shifts | Multivariate normal; covariance taken from the reference period | Inertia; pair the MEWMA with $T^2$ | Omnibus check |
| Two-sample tests such as KS or MMD ([Rabanser 2019](https://arxiv.org/abs/1810.11953)) | A change in distribution between two windows | Independent samples | Items within a day are correlated, so permute whole days [inference] | Input drift (length, source mix, page-furniture rate); quantile shifts |
| Benjamini-Hochberg FDR ([1995](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)) | Controls false discoveries across many tests | Independence or positive dependence. Wilson 2019 notes that BH is robust to positive correlation. | - | Many metrics x strata |
| Fisher / Stouffer p-value combination | Combine p-values | Independence | Too liberal (more false alarms than $\alpha$) when tests are positively correlated [standard result] | Avoid unless the metrics are independent |
| Cauchy combination ([Liu & Xie 2020](https://doi.org/10.1080/01621459.2018.1554485)) | Combine p-values under arbitrary dependence | A tail approximation | Accurate when p is small | Global "something is wrong" test |
| Harmonic mean p-value ([Wilson 2019](https://doi.org/10.1073/pnas.1814092116)) | Combine dependent tests | - | Debated: a published letter disputes strong versus weak error control | Second choice |
| Confidence sequences ([Howard 2021](https://arxiv.org/abs/1810.08240)) | Inference that stays valid when you check the data at any time | - | Wider intervals | If you run a fixed-$\alpha$ test every day |
| LLM behaviour drift ([Chen, Zaharia & Zou 2024](https://arxiv.org/abs/2307.09009)) | The behaviour of hosted LLMs changed within months | - | - | Motivation. Pinning a self-hosted model reduces drift but does not remove it (prompts, runtime, inputs). |

### 6.2 Combining several monitored metrics

Ranked options:

1. **Weighted composite with known direction (matches the owner's request).**
  - Let $z_{d,k}$ be the standardised daily residual of metric $k$ on day $d$, oriented so that positive means worse.
  - Compute the composite for day $d$, where $w_k$ is the weight of metric $k$ and $R$ is the correlation matrix of the $z$ values in the reference window:

    $$C_d = \frac{\sum_k w_k z_{d,k}}{\sqrt{w^\top R w}}$$

  - When nothing has changed, $C_d$ is roughly standard normal however many metrics are added or re-weighted. Correlated metrics are therefore not double-counted [standard algebra; assumes approximate normality and a stable $R$].
  - Chart $C_d$ with an EWMA.
  - If a degradation is expected to move the metrics in direction $\delta$, the most powerful linear weights are $w \propto R^{-1} \delta$ [standard result for a mean shift with known direction under multivariate normality]. This gives a principled way to tune weights from injected changes.
2. **MEWMA with Hotelling $T^2$** ([Lowry 1992](https://doi.org/10.1080/00401706.1992.10485232)). An omnibus check that catches shifts in directions nobody anticipated.
3. **Cauchy combination** ([Liu & Xie 2020](https://doi.org/10.1080/01621459.2018.1554485)) of one-sided p-values per metric, when you want a single p-value that stays valid under dependence.
4. **Fisher or Stouffer combination** only if the metrics are close to independent. Yours are not.

### 6.3 Design rules for a setting with no golden set and trailing windows

**Unit of judgement.** The unit is the day, across all summaries, not the site. Sites enter only as a covariate, consistent with the owner's ruling.

**What to adjust for.**
- Adjust for input-side covariates only: article length, page type, the cut flag, language, the source (as a random effect) and optionally a topic cluster.
- Do not adjust for output-side behaviour such as extractiveness or summary length. That would hide real changes [inference].
- Chart the residuals, as Lucas & Saccucci and Steiner advise.

**Estimating the in-control spread.** Estimate the in-control SD from the variation of daily residual means between days, not from the within-day standard error. The news cycle correlates items within a day and across nearby days ([Alwan & Roberts 1988](https://doi.org/10.1080/07350015.1988.10509640)); using the within-day error would give too many false alarms.

**Reference window.**
- Use a lagged trailing window with a gap, for example days -63 to -8, so that a slow drift does not become its own baseline.
- Add a long-baseline anchor made of stored score quantiles. Scores survive after articles are deleted, so this is compatible with the no-golden-set rule.

**Calibration.**
- Limits estimated from about 8 weeks of data carry their own error ([Jensen 2006](https://doi.org/10.1080/00224065.2006.11918623)).
- Calibrate the false-alarm rate by bootstrapping days or by simulation.
- Aim for an in-control average run length chosen by a person, for example about one false alarm per quarter.

**Low-volume days.** Use limits that depend on the day's row count $n$, or weight days by $n$.

**Version boundaries.** A change of model, prompt, quantisation, llama.cpp build or scorer starts a new series, consistent with your P14.

**Separating evaluator drift from summary drift.** Chart how often the two checkers disagree and the LLM judge's parse-success rate.

---

## 7. (e) Recommendation for yen-idhazh (Q6)

### 7.1 Ranked metrics to monitor daily (every summary)

| Rank | Metric | Role | Why (evidence) | Cost |
|---|---|---|---|---|
| 1 | Sentence-level faithfulness: HHEM-2.1-Open per summary sentence, best window. Report mean support, minimum support and the count of sentences below threshold. | Index and gate | The essential dimension. The best-supported way to aggregate ([Wan 2025](https://aclanthology.org/2025.naacl-long.442/); [SummaC](https://arxiv.org/abs/2111.09525); [AlignScore](https://arxiv.org/abs/2305.16739); [MiniCheck](https://arxiv.org/abs/2404.10774)). Removes the long-article artefact. | NLI cross-encoder; about 3-6 pairs for a median item |
| 2 | Unsupported numbers, named entities and dates (each checked against the source) | Gate | FRANK's entity and circumstance errors ([FRANK](https://aclanthology.org/2021.naacl-main.383/)); [Nan 2021](https://arxiv.org/abs/2102.09130); [Zhao 2020](https://arxiv.org/abs/2009.13312) | Milliseconds |
| 3 | A second checker on the same sentence x window matrix: FactCG-DeBERTa-v3-L or MiniCheck-Flan-T5-L. Run it on all items if the nightly budget allows, otherwise on a stratified 100 a day. | Index (ensemble with rank 1) and evaluator health (disagreement rate) | The top small checkers on LLM-AggreFact (75.0-75.6), independent of the vendor's own figures for HHEM ([leaderboard](https://llm-aggrefact.github.io/)) | 0.4-0.8B cross-encoder |
| 4 | Hedge dropped; shift in certainty and evidential language, optionally using the Pei & Jurgens model | Gate (hedge dropped) and index | Preserving certainty and attribution matters in news ([Pei & Jurgens 2021](https://arxiv.org/abs/2109.14776)). Validated only on science news. | Lexical or small encoder |
| 5 | Coverage by attribution: the existing lead coverage, plus a position profile (for long articles, the share of summary sentences supported beyond the first window) | Index, low weight | Completeness is what degrades with length ([UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/)); position bias ([Ravaut 2024](https://arxiv.org/abs/2310.10570); [Wan 2025](https://aclanthology.org/2025.naacl-long.442/)) | Free, from rank 1 |
| 6 | Self-repetition; length bounds | Gate | Detect loops and truncation ([SEAHORSE](https://aclanthology.org/2023.emnlp-main.584/) scores repetition as its own dimension) | Lexical |
| 7 | Extractiveness, longest verbatim run, compression | Guard rail (copying ceiling) and monitored behaviour, not quality | Faithfulness metrics reward copying ([Ladhak 2022](https://arxiv.org/abs/2108.13684); [Dreyer 2023](https://aclanthology.org/2023.findings-eacl.156/)) | Lexical |
| 8 | Page-furniture flag | Input gate. Exclude flagged items from quality statistics and chart their rate as input drift. | Operational | Lexical |

### 7.2 Metrics to sample with an LLM judge (30-100 a day)

**Sample design.**
- Stratify by article-length tercile.
- Oversample items where the two checkers disagree and items that hit a gate.
- Rate one attribute per prompt, because rating several at once causes anchoring ([Stureborg 2024](https://arxiv.org/abs/2405.01724)).
- Where a scale is used, weight the score by token probabilities ([G-Eval](https://arxiv.org/abs/2303.16634)).
- Log the parse-success rate.

**J1 - key-fact completeness and conciseness** (the [FineSurE](https://aclanthology.org/2024.acl-long.51/) protocol).
- Extract a bounded list of key facts from the article.
- Mark each key fact as present or absent in the summary.
- Mark each summary sentence as aligned with a key fact or not.
- Use the results as completeness and conciseness trends, and to validate the cheap proxy in rank 5.
- How well a 9B judge does this is unknown, so read its output as a trend, not as absolute truth.

**J2 - sentence-level fact-check adjudication on disagreements.**
- Prefer a fine-tuned checker from a different model family over the summariser. Candidates are Bespoke-MiniCheck-7B (77.4) or Granite Guardian 3.3 8B (76.5) on the [LLM-AggreFact board](https://llm-aggrefact.github.io/).
- This avoids self-preference ([Panickssery 2024](https://arxiv.org/abs/2404.13076)), and these checkers have better published accuracy.
- Check their licences and whether llama.cpp/GGUF builds are available; neither was verified here.

**J3 (optional) - coherence and attribution check** on summaries of long articles.

**Do not** have the summariser judge its own fluency.

### 7.3 Drop, demote, or use only as covariates

**Drop:**
- Self-judged fluency, as currently designed.
- ROUGE, BERTScore and other metrics that need references.
- QA-based and atomic-fact pipelines (QAFactEval, QuestEval, FActScore): high cost for weak evidence on LLM summaries.

**Demote to diagnostics:**
- Adjacent-sentence cosine coherence ([Steen & Markert 2022](https://aclanthology.org/2022.coling-1.527/)).
- Top-20-word lexical coverage (unvalidated, and confounded by length and copying).
- `hhem_full` and `hhem_delta`.

**Covariates only (never judged):**
- Article length (log words or a length band).
- Page type, the cut flag and extraction quality.
- Source or site, as a random effect.
- Language, optionally topic cluster, and weekday and volume.

**Monitored as behaviour but never adjusted for:** extractiveness, verbatim run, compression and summary length.

### 7.4 Recommended composite and decision approach

1. **Stamp every row with versions.** Record model, prompt, quantisation, llama.cpp build and scorer versions. Any change starts a new series (your P14).
2. **Gates per summary, non-compensatory.**
  - Gates: unsupported number, entity or date; a sentence that both checkers fail; hedge dropped; a repetition loop; length out of bounds; the copying ceiling exceeded; page furniture (input).
  - These keep their role as publish vetoes. Plan 36's "veto chain, never a composite" stays right at item level.
  - At fleet level, chart each daily gate rate with a risk-adjusted Bernoulli CUSUM or EWMA ([Steiner 2000](https://doi.org/10.1093/biostatistics/1.4.441)). The expected rates come from an input-covariate model fitted on the lagged reference window.
3. **Daily indices per dimension.**
  - Dimensions: faithfulness (mean sentence support, logit-transformed), completeness proxy (lead coverage and position profile), certainty preservation, extractiveness (as behaviour) and length conformity.
  - For each, take the day's mean of per-summary residuals (observed minus expected given the input covariates).
  - Standardise by the between-day SD in the reference window.
4. **Two combined statistics.**
  - **"Quality got worse"** (the owner's weighted composite): $C_d = \frac{\sum_k w_k z_{d,k}}{\sqrt{w^\top R w}}$ (section 6.2), smoothed with an EWMA and tested one-sided. The weights are tunable.
  - **"Something changed"**: MEWMA plus Hotelling $T^2$ ([Lowry 1992](https://doi.org/10.1080/00401706.1992.10485232)).
  - If you instead compute many per-metric tests, combine them with the Cauchy test and apply BH within strata.
5. **Decision levels.** None of these actions is automatic; a person decides (your P15).
  - **Watch:** any single chart signals.
  - **Drift:** the composite or the MEWMA signals on two consecutive days, or a CUSUM crosses its limit.
  - **Evaluator check:** checker disagreement or the judge's parse-success rate shifts. Resolve this before calling the change a summary drift.
6. **A single display number, for dashboards only.** Take the weighted geometric mean of per-dimension percentiles relative to the reference window (desirability-style), forced to zero on any gate. Always show its decomposition, as the OECD handbook advises.

**Setting the weights (your P17).**
- Replay injected changes on recent items: swap numbers or entities, negate predicates, drop hedges, truncate, copy the lead, inject repetition. These follow FRANK's error types and SummEdits-style seeded edits ([SummEdits](https://arxiv.org/abs/2305.14540)).
- Estimate each change's shift vector $\delta$.
- Choose the weights $w$ to maximise the worst-case detection rate across the change types at a fixed in-control false-alarm rate.
- A person commits the result.

### 7.5 How to validate without human labels

- **Injected-change replays**, as above. They measure each metric's sensitivity to each error type and the composite's power to detect them. AggreFact and FRANK both show that detectors differ by error type.
- **Agreement between independent instruments:** HHEM versus FactCG or MiniCheck, and checkers versus the judge sample. Chart the disagreement rate.
- **Invariance tests.** For example, faithfulness should not change when you reorder the summary's sentences or paraphrase them without changing content [inference].
- **Reports stratified by length tercile.** These separate a genuine change from a change in input mix [inference].

### 7.6 Main risk

**There are no labels, so nothing ties the metrics to quality on your own data.** The system will detect changes in metric distributions, which can come from:
- a shift in the news mix,
- extraction changes,
- evaluator artefacts (copying inflating faithfulness, chunking deflating it),
- or real changes in summary quality.

Mitigations: input-covariate adjustment, two independent checkers, the judge sample, injected-change replays, and decomposition of every alarm, all with a person deciding (P15).

**Secondary risk: Goodhart effects.** If prompts or models are tuned against the composite, copying and length will move first ([Gao 2023](https://arxiv.org/abs/2210.10760); [Moskovitz 2024](https://arxiv.org/abs/2310.04373)).

---

## 8. Contradictions and how they were resolved

| Topic | Side A | Side B | Resolution |
|---|---|---|---|
| LLM judge versus specialised checker | Checkers match or beat most LLMs on binary claim accuracy ([TofuEval](https://aclanthology.org/2024.naacl-long.251/); [MiniCheck](https://arxiv.org/abs/2404.10774)) | A GPT-4-turbo judge correlates far better with humans at summary level on LLM summaries ([UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/)); at book length no LLM rater correlates strongly ([FABLES](https://arxiv.org/abs/2404.01261)) | The result depends on judge strength, granularity and domain. For a 9B local judge, use checkers daily and the judge on a sample. |
| ROUGE | Best for relevance on long documents (pre-LLM, with references; [Koh 2022](https://arxiv.org/abs/2210.16732)) | Unreliable for LLM summaries ([Goyal](https://arxiv.org/abs/2209.12356); [Zhang](https://aclanthology.org/2024.tacl-1.3/); [FineSurE](https://aclanthology.org/2024.acl-long.51/)) | The difference is the era and the use of references. The question is moot here, because you have no references. |
| Abstractiveness versus faithfulness | Trade-off exists, and metrics reward copying ([Ladhak](https://arxiv.org/abs/2108.13684); [Dreyer](https://aclanthology.org/2023.findings-eacl.156/)) | No relation for proprietary LLMs ([UniSumEval](https://aclanthology.org/2024.findings-emnlp.227/)) | Depends on the model. Treat extractiveness as monitored behaviour and watch the joint pattern. |
| Harmonic mean p-value under dependence | Valid for dependent tests ([Wilson 2019](https://doi.org/10.1073/pnas.1814092116)) | A published letter disputes strong versus weak error control | Prefer the Cauchy combination ([Liu & Xie 2020](https://doi.org/10.1080/01621459.2018.1554485)). |
| Lead emphasis | Concentration on position is a bias ([Ravaut](https://arxiv.org/abs/2310.10570); [Wan](https://aclanthology.org/2025.naacl-long.442/)) | News is written as an inverted pyramid, so emphasising the lead is partly legitimate (your lead-anchored coverage) | Monitor the position profile as a diagnostic, not as a target. |

---

## 9. Verification summary

| Metric | Value |
|---|---|
| Sources cited | 76, all verified to exist (title, first author, year, venue or ID, URL) |
| Key atomic claims | About 43: 31 supported by two or more sources; 9 single-source and flagged (vendor HHEM figures; FineSurE's open-model numbers; UniSumEval's news correlations; Wan's merge result; BooookScore; fair-summarisation metrics; transfer of the Pei & Jurgens model; LongEval's partial annotation; Stureborg's biases); 3 removed |
| Removed or unverified, not cited | Benjamini-Yekutieli 2001 (search withheld); Steen & Markert 2024 on bias in news summarisation (search withheld); details of HELM's summarisation metrics (not verified) |
| Methods | SIFT on vendor and leaderboard sources; re-reading primary sources; searches for counter-evidence; analysis of competing hypotheses on the checker-versus-judge question |

---

## 10. Limitations and residual risks (pre-mortem)

Suppose that six months from now these recommendations have turned out wrong. The likeliest reasons:

1. **Benchmarks differ from your data.** Most evidence comes from CNN/DM, XSum or GPT-4-era summaries, not from 65-word summaries written by a 9B model of heterogeneous web news. AggreFact shows that metric quality depends on the summariser, so the ranking of checkers may differ on your data.
2. **No labels.** Every metric's validity on your data stays unproven. Alarms may track artefacts. The injected-change replay is a proxy for real degradations, not a substitute for them.
3. **Vendor-only and estimated numbers.** HHEM's accuracy and latency are vendor-reported. All CPU costs here are estimates. A 9B judge's reliability is unknown. FineSurE suggests small models may fail the format or perform at chance.
4. **Statistical assumptions.** Correlation between days, days with few summaries, limits estimated from about 8 weeks of data, and trailing windows that absorb slow drift can each distort false-alarm rates.
5. **Recency.** The coverage is strongest for 2023-2025. Work from 2026 may exist that was not found.

---

## 11. Conclusion

**Why the newer frameworks changed the axes.** LLMs made fluency nearly free and turned summary errors into subtle, factual and selective ones: a wrong number or name, a dropped hedge, an omitted key fact. That is why recent frameworks rebuilt evaluation around faithfulness and completeness at the level of sentences and key facts. It is also why reference metrics lost their meaning: once LLM output is better than the references, overlap with the reference measures the wrong thing.

**What this means for your stack.**
- The strongest cheap instrument is the one you already have, a small NLI checker. Its value depends on asking it the right question: is each sentence supported somewhere in the source?
- The current "best window for the whole summary" asks a different question, and that difference is a plausible cause of the dip on long articles.
- Completeness cannot be measured cheaply and reliably, so it needs a sampled judge, ideally not the summariser grading itself.

**Why the drift decision should be built this way.**
- No human labels exist, so the decision cannot be a learned quality score.
- It has to be a statistical statement that today's covariate-adjusted metrics differ from a recent baseline, made without letting one strong metric cover for a failing one and without counting correlated metrics twice.
- Non-compensatory gates plus a correlation-aware composite with EWMA/CUSUM and MEWMA meet those requirements with well-understood statistics.
- The open question is whether the metrics mean what we hope, so the system's real safeguards are instrument agreement, injected-change replays and a person reading the decomposed alarm.

---

## (f) Sources - full reference list

Notes: [vendor] marks a vendor document, [preprint] a paper not peer-reviewed at the time of checking, and [leaderboard] a live web page.

**Frameworks, benchmarks and meta-evaluation**
1. Fabbri, A. R. et al. (2021). SummEval: Re-evaluating Summarization Evaluation. TACL 9. arXiv:2007.12626. https://aclanthology.org/2021.tacl-1.24/
2. Pagnoni, A., Balachandran, V., Tsvetkov, Y. (2021). Understanding Factuality in Abstractive Summarization with FRANK: A Benchmark for Factuality Metrics. NAACL 2021. ACL 2021.naacl-main.383; arXiv:2104.13346. https://aclanthology.org/2021.naacl-main.383/
3. Song, H. et al. (2024). FineSurE: Fine-grained Summarization Evaluation using LLMs. ACL 2024. ACL 2024.acl-long.51; arXiv:2407.00908. https://aclanthology.org/2024.acl-long.51/
4. Lee, Y. et al. (2024). UniSumEval: Towards Unified, Fine-Grained, Multi-Dimensional Summarization Evaluation for LLMs. Findings of EMNLP 2024. ACL 2024.findings-emnlp.227; arXiv:2409.19898. https://aclanthology.org/2024.findings-emnlp.227/
5. Kim, Y. et al. (2024). FABLES: Evaluating faithfulness and content selection in book-length summarization. COLM 2024. arXiv:2404.01261. https://arxiv.org/abs/2404.01261
6. Krishna, K. et al. (2023). LongEval: Guidelines for Human Evaluation of Faithfulness in Long-form Summarization. EACL 2023. ACL 2023.eacl-main.121; arXiv:2301.13298. https://aclanthology.org/2023.eacl-main.121/
7. Tang, L. et al. (2024). TofuEval: Evaluating Hallucinations of LLMs on Topic-Focused Dialogue Summarization. NAACL 2024. ACL 2024.naacl-long.251; arXiv:2402.13249. https://aclanthology.org/2024.naacl-long.251/
8. Zhang, H., Xu, Y., Perez-Beltrachini, L. (2024). Fine-Grained Natural Language Inference Based Faithfulness Evaluation for Diverse Summarisation Tasks (InFusE; DiverSumm). EACL 2024. ACL 2024.eacl-long.102; arXiv:2402.17630. https://aclanthology.org/2024.eacl-long.102/
9. Huang, K.-H. et al. (2024). Embrace Divergence for Richer Insights: A Multi-document Summarization Benchmark and a Case Study on Summarizing Diverse Information from News Articles (DiverseSumm). NAACL 2024. ACL 2024.naacl-long.32; arXiv:2309.09369. https://aclanthology.org/2024.naacl-long.32/
10. Clark, E. et al. (2023). SEAHORSE: A Multilingual, Multifaceted Dataset for Summarization Evaluation. EMNLP 2023. ACL 2023.emnlp-main.584; arXiv:2305.13194. https://aclanthology.org/2023.emnlp-main.584/
11. Zhong, M. et al. (2022). Towards a Unified Multi-Dimensional Evaluator for Text Generation (UniEval). EMNLP 2022. ACL 2022.emnlp-main.131. https://aclanthology.org/2022.emnlp-main.131/
12. Liu, Y. et al. (2023). Revisiting the Gold Standard: Grounding Summarization Evaluation with Robust Human Evaluation (RoSE/ACU). ACL 2023. ACL 2023.acl-long.228. https://aclanthology.org/2023.acl-long.228/
13. Liu, Y. et al. (2024). Benchmarking Generation and Evaluation Capabilities of Large Language Models for Instruction Controllable Summarization (InstruSum). Findings of NAACL 2024. ACL 2024.findings-naacl.280. https://aclanthology.org/2024.findings-naacl.280/
14. Zhang, Y. et al. (2024). Fair Abstractive Summarization of Diverse Perspectives. NAACL 2024. ACL 2024.naacl-long.187; arXiv:2311.07884. https://aclanthology.org/2024.naacl-long.187/
15. Chang, Y. et al. (2024). BooookScore: A systematic exploration of book-length summarization in the era of LLMs. ICLR 2024. arXiv:2310.00785. https://arxiv.org/abs/2310.00785
16. Tang, L. et al. (2023). Understanding Factual Errors in Summarization: Errors, Summarizers, Datasets, Error Detectors (AggreFact). ACL 2023. arXiv:2205.12854. https://arxiv.org/abs/2205.12854
17. Laban, P. et al. (2023). SummEdits: Measuring LLM Ability at Factual Reasoning Through The Lens of Summarization. EMNLP 2023. arXiv:2305.14540. https://arxiv.org/abs/2305.14540
18. Steen, J., Markert, K. (2022). How to Find Strong Summary Coherence Measures? A Toolbox and a Comparative Study for Summary Coherence Measure Evaluation. COLING 2022. ACL 2022.coling-1.527; arXiv:2209.06517. https://aclanthology.org/2022.coling-1.527/

**Faithfulness and consistency metrics**

19. Laban, P. et al. (2022). SummaC: Re-Visiting NLI-based Models for Inconsistency Detection in Summarization. TACL 10. arXiv:2111.09525. https://arxiv.org/abs/2111.09525
20. Zha, Y. et al. (2023). AlignScore: Evaluating Factual Consistency with a Unified Alignment Function. ACL 2023. arXiv:2305.16739. https://arxiv.org/abs/2305.16739
21. Tang, L., Laban, P., Durrett, G. (2024). MiniCheck: Efficient Fact-Checking of LLMs on Grounding Documents (introduces LLM-AggreFact). EMNLP 2024. arXiv:2404.10774. https://arxiv.org/abs/2404.10774
22. LLM-AggreFact leaderboard (accessed 2026-10-11) [leaderboard]. https://llm-aggrefact.github.io/
23. Lei, D. et al. (2025). FactCG: Enhancing Fact Checks via Graph-Based Multi-Hop Data. NAACL 2025. ACL 2025.naacl-long.258; arXiv:2501.17144. https://aclanthology.org/2025.naacl-long.258/
24. Vectara. HHEM-2.1-Open model card (hallucination_evaluation_model) [vendor]. https://huggingface.co/vectara/hallucination_evaluation_model
25. Fabbri, A. R. et al. (2022). QAFactEval: Improved QA-Based Factual Consistency Evaluation for Summarization. NAACL 2022. arXiv:2112.08542. https://arxiv.org/abs/2112.08542
26. Scialom, T. et al. (2021). QuestEval: Summarization Asks for Fact-based Evaluation. EMNLP 2021. arXiv:2103.12693. https://arxiv.org/abs/2103.12693
27. Min, S. et al. (2023). FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation. EMNLP 2023. arXiv:2305.14251. https://arxiv.org/abs/2305.14251
28. Nan, F. et al. (2021). Entity-level Factual Consistency of Abstractive Text Summarization. EACL 2021. arXiv:2102.09130. https://arxiv.org/abs/2102.09130
29. Zhao, Z., Cohen, S. B., Webber, B. (2020). Reducing Quantity Hallucinations in Abstractive Summarization. Findings of EMNLP 2020. arXiv:2009.13312. https://arxiv.org/abs/2009.13312
30. Pei, J., Jurgens, D. (2021). Measuring Sentence-Level and Aspect-Level (Un)certainty in Science Communications. EMNLP 2021. arXiv:2109.14776. https://arxiv.org/abs/2109.14776
31. Ladhak, F. et al. (2022). Faithful or Extractive? On Mitigating the Faithfulness-Abstractiveness Trade-off in Abstractive Summarization. ACL 2022. arXiv:2108.13684. https://arxiv.org/abs/2108.13684
32. Dreyer, M. et al. (2023). Evaluating the Tradeoff Between Abstractiveness and Factuality in Abstractive Summarization. Findings of EACL 2023. ACL 2023.findings-eacl.156; arXiv:2108.02859. https://aclanthology.org/2023.findings-eacl.156/
33. Zhang, S., Wan, D., Bansal, M. (2023). Extractive is not Faithful: An Investigation of Broad Unfaithfulness Problems in Extractive Summarization. ACL 2023. arXiv:2209.03549. https://arxiv.org/abs/2209.03549
34. Grusky, M., Naaman, M., Artzi, Y. (2018). Newsroom: A Dataset of 1.3 Million Summaries with Diverse Extractive Strategies. NAACL 2018. ACL N18-1065. https://aclanthology.org/N18-1065/

**LLM judges and their biases**

35. Liu, Y. et al. (2023). G-Eval: NLG Evaluation using GPT-4 with Better Human Alignment. EMNLP 2023. arXiv:2303.16634. https://arxiv.org/abs/2303.16634
36. Zheng, L. et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. NeurIPS 2023 Datasets and Benchmarks. arXiv:2306.05685. https://arxiv.org/abs/2306.05685
37. Panickssery, A., Bowman, S. R., Feng, S. (2024). LLM Evaluators Recognize and Favor Their Own Generations. NeurIPS 2024. arXiv:2404.13076. https://arxiv.org/abs/2404.13076
38. Liu, Y., Moosavi, N. S., Lin, C. (2024). LLMs as Narcissistic Evaluators: When Ego Inflates Evaluation Scores. Findings of ACL 2024. arXiv:2311.09766. https://arxiv.org/abs/2311.09766
39. Stureborg, R., Alikaniotis, D., Suhara, Y. (2024). Large Language Models are Inconsistent and Biased Evaluators. arXiv:2405.01724 [preprint]. https://arxiv.org/abs/2405.01724
40. Dubois, Y. et al. (2024). Length-Controlled AlpacaEval: A Simple Way to Debias Automatic Evaluators. COLM 2024. arXiv:2404.04475. https://arxiv.org/abs/2404.04475
41. Shen, C. et al. (2023). Large Language Models are Not Yet Human-Level Evaluators for Abstractive Summarization. Findings of EMNLP 2023. arXiv:2305.13091. https://arxiv.org/abs/2305.13091
42. Kim, S. et al. (2024). Prometheus 2: An Open Source Language Model Specialized in Evaluating Other Language Models. EMNLP 2024. arXiv:2405.01535. https://arxiv.org/abs/2405.01535

**News summarisation with LLMs**

43. Goyal, T., Li, J. J., Durrett, G. (2022). News Summarization and Evaluation in the Era of GPT-3. arXiv:2209.12356 [preprint]. https://arxiv.org/abs/2209.12356
44. Zhang, T. et al. (2024). Benchmarking Large Language Models for News Summarization. TACL 12. ACL 2024.tacl-1.3; arXiv:2301.13848. https://aclanthology.org/2024.tacl-1.3/
45. Pu, X., Gao, M., Wan, X. (2023). Summarization is (Almost) Dead. arXiv:2309.09558 [preprint]. https://arxiv.org/abs/2309.09558

**Long documents**

46. Wan, D., Vig, J., Bansal, M., Joty, S. (2025). On Positional Bias of Faithfulness for Long-form Summarization. NAACL 2025. ACL 2025.naacl-long.442; arXiv:2410.23609. https://aclanthology.org/2025.naacl-long.442/
47. Ravaut, M. et al. (2024). On Context Utilization in Summarization with Large Language Models. ACL 2024. arXiv:2310.10570. https://arxiv.org/abs/2310.10570
48. Liu, N. F. et al. (2024). Lost in the Middle: How Language Models Use Long Contexts. TACL 12. arXiv:2307.03172. https://arxiv.org/abs/2307.03172
49. Lattimer, B. M. et al. (2023). Fast and Accurate Factual Inconsistency Detection Over Long Documents (SCALE). EMNLP 2023. arXiv:2310.13189. https://arxiv.org/abs/2310.13189
50. Bishop, J. A., Xie, Q., Ananiadou, S. (2024). LongDocFACTScore: Evaluating the Factuality of Long Document Abstractive Summarisation. LREC-COLING 2024. ACL 2024.lrec-main.941; arXiv:2309.12455. https://aclanthology.org/2024.lrec-main.941/
51. Koh, H. Y. et al. (2022). How Far are We from Robust Long Abstractive Summarization? EMNLP 2022. arXiv:2210.16732. https://arxiv.org/abs/2210.16732
52. Wu, Y. et al. (2024). Less is More for Long Document Summary Evaluation by LLMs (Extract-then-Evaluate). EACL 2024 (short). arXiv:2309.07382. https://arxiv.org/abs/2309.07382

**Composites, aggregation and Goodhart effects**

53. Nardo, M. et al. (OECD/JRC) (2008). Handbook on Constructing Composite Indicators: Methodology and User Guide. OECD Publishing. ISBN 978-92-64-04345-9. https://www.unescap.org/sites/default/files/JRC-OECD_Handbook%20Composite%20Indicators.pdf
54. UNDP. Human Development Report Technical Notes (geometric-mean HDI since 2010). https://data.un.org/_Docs/HDR%20Technical%20Notes.pdf
55. Derringer, G., Suich, R. (1980). Simultaneous Optimization of Several Response Variables. Journal of Quality Technology 12(4):214-219. https://doi.org/10.1080/00224065.1980.11980968
56. Ethayarajh, K., Jurafsky, D. (2020). Utility is in the Eye of the User: A Critique of NLP Leaderboards. EMNLP 2020. arXiv:2009.13888. https://arxiv.org/abs/2009.13888
57. Rofin, M. et al. (2023). Vote'n'Rank: Revision of Benchmarking with Social Choice Theory. EACL 2023. arXiv:2210.05769. https://arxiv.org/abs/2210.05769
58. Moskovitz, T. et al. (2024). Confronting Reward Model Overoptimization with Constrained RLHF. ICLR 2024. arXiv:2310.04373. https://arxiv.org/abs/2310.04373
59. Gao, L., Schulman, J., Hilton, J. (2023). Scaling Laws for Reward Model Overoptimization. ICML 2023. arXiv:2210.10760. https://arxiv.org/abs/2210.10760
60. Manheim, D., Garrabrant, S. (2018). Categorizing Variants of Goodhart's Law. arXiv:1803.04585 [preprint]. https://arxiv.org/abs/1803.04585
61. Shankar, S. et al. (2024). Who Validates the Validators? Aligning LLM-Assisted Evaluation of LLM Outputs with Human Preferences (EvalGen). UIST 2024. arXiv:2404.12272. https://arxiv.org/abs/2404.12272

**Drift monitoring and statistics**

62. Page, E. S. (1954). Continuous Inspection Schemes. Biometrika 41(1/2):100-115. https://doi.org/10.1093/biomet/41.1-2.100 (+)
63. Lucas, J. M., Saccucci, M. S. (1990). Exponentially Weighted Moving Average Control Schemes: Properties and Enhancements. Technometrics 32(1):1-12 (with discussion). JSTOR 1269835; doi 10.1080/00401706.1990.10484583. https://www.jstor.org/stable/1269835
64. Lowry, C. A., Woodall, W. H., Champ, C. W., Rigdon, S. E. (1992). A Multivariate Exponentially Weighted Moving Average Control Chart. Technometrics 34(1):46-53. https://doi.org/10.1080/00401706.1992.10485232 (+)
65. Alwan, L. C., Roberts, H. V. (1988). Time-Series Modeling for Statistical Process Control. Journal of Business & Economic Statistics 6(1):87-95. https://doi.org/10.1080/07350015.1988.10509640 (+)
66. Steiner, S. H., Cook, R. J., Farewell, V. T., Treasure, T. (2000). Monitoring surgical performance using risk-adjusted cumulative sum charts. Biostatistics 1(4):441-452. https://doi.org/10.1093/biostatistics/1.4.441 (+)
67. Hawkins, D. M. (1987). Self-Starting Cusum Charts for Location and Scale. Journal of the Royal Statistical Society Series D (The Statistician) 36(4):299-316. https://doi.org/10.2307/2348827
68. Jensen, W. A., Jones-Farmer, L. A., Champ, C. W., Woodall, W. H. (2006). Effects of Parameter Estimation on Control Chart Properties: A Literature Review. Journal of Quality Technology 38(4):349-364. https://doi.org/10.1080/00224065.2006.11918623
69. Benjamini, Y., Hochberg, Y. (1995). Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing. JRSS-B 57(1):289-300. https://doi.org/10.1111/j.2517-6161.1995.tb02031.x (+)
70. Wilson, D. J. (2019). The harmonic mean p-value for combining dependent tests. PNAS 116(4):1195-1200. https://doi.org/10.1073/pnas.1814092116 (+)
71. Liu, Y., Xie, J. (2020). Cauchy Combination Test: A Powerful Test With Analytic p-Value Calculation Under Arbitrary Dependency Structures. JASA 115(529):393-402. https://doi.org/10.1080/01621459.2018.1554485 (+)
72. Howard, S. R., Ramdas, A., McAuliffe, J., Sekhon, J. (2021). Time-uniform, nonparametric, nonasymptotic confidence sequences. Annals of Statistics 49(2):1055-1080. arXiv:1810.08240. https://arxiv.org/abs/1810.08240 (+)
73. Rabanser, S., Guennemann, S., Lipton, Z. C. (2019). Failing Loudly: An Empirical Study of Methods for Detecting Dataset Shift. NeurIPS 2019. arXiv:1810.11953. https://arxiv.org/abs/1810.11953
74. Chen, L., Zaharia, M., Zou, J. (2024). How Is ChatGPT's Behavior Changing over Time? Harvard Data Science Review 6(2). arXiv:2307.09009. https://arxiv.org/abs/2307.09009

**Internal context (not literature)**

75. yen-idhazh, plan 65, the summary-fidelity judge (TODO/20261011-65-summary-fidelity-judge-plan.md) and the daily records under state/day-metrics/: source for the 2026-09-07 step, the owner's rulings and the P14, P15 and P17 references.
76. yen-idhazh, "What one summary number means": docs/concepts/summary-metrics.md. Source for the statement that `hhem` is the best of overlapping windows.

(+) These papers' existence and bibliographic details were confirmed by web search during this review. The DOI links themselves could not be click-tested from the sandbox, which has no network access. Lucas & Saccucci, Hawkins, Jensen et al. and Derringer & Suich had their DOI or stable URL confirmed in search results.

**Not cited because they could not be verified:** Benjamini & Yekutieli (2001) on FDR under dependence; Steen & Markert (2024) on bias in news summarisation; details of HELM's summarisation metrics.
