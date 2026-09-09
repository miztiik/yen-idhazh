# I Feed Research Reference

**Last Updated**: 2026-09-09

Evidence behind the [Intelligent F.E.E.D - I Feed design](../architecture/sources/i-feed.md).
This page is a research catalog, not the implementation scope. The design page
selects what applies to this app and what to build first.

## Scope and reading depth

Search and review date: 2026-09-09. The search covered contextual/news,
nonstationary, sleeping and many-arm bandits; budgeted discovery/crawling;
off-policy/slate evaluation; drift/windowing; diversity/feedback loops; and
hybrid assessment. It included foundational and recent papers. This was a broad
targeted review, not a claim to have found every publication on the subject.

The tables retain 29 relevant arXiv records. `Methods` means the setup and
relevant method/limitation sections were inspected, sometimes through ar5iv;
it does not mean proofs or experiments were reproduced. `Abstract` means only
primary metadata and abstract were verified. Years are first arXiv submission
years. Authors are abbreviated with `et al.` where noted.

## Learning what to select

| Paper and authors | Read | Learn; limit or reason to defer |
| --- | --- | --- |
| [A Contextual-Bandit Approach to Personalized News Article Recommendation](https://arxiv.org/abs/1003.0146), Li, Chu, Langford and Schapire, 2010. | Methods | Learn shared linear context and randomized logging. Its click objective, fixed linear reward assumptions and randomized replay setup are not ours. |
| [On Upper-Confidence Bound Policies for Non-Stationary Bandit Problems](https://arxiv.org/abs/0805.3415), Garivier and Moulines, 2008. | Methods | Learn discount/window estimates and separate drift bias. Bounded independent, piecewise-stationary rewards do not describe every correlated feed observation. |
| [Optimal Exploration-Exploitation in a Multi-Armed-Bandit Problem with Non-stationary Rewards](https://arxiv.org/abs/1405.3316), Besbes, Gur and Zeevi, 2014. | Abstract | Learn that changing rewards require an adaptation budget. Do not claim we know the variation budget or inherit its regret result. |
| [Hierarchical Bayesian Bandits](https://arxiv.org/abs/2111.06929), Hong, Kveton, Zaheer and Ghavamzadeh, 2021. | Abstract | Explore shared information for sparse feeds later. Related publishers or topics are not automatically exchangeable observations. |
| [Near-optimal Per-Action Regret Bounds for Sleeping Bandits](https://arxiv.org/abs/2403.01315), Nguyen and Mehta, 2024. | Abstract | Distinguish temporarily unavailable actions from poor actions. Regret bounds do not guarantee timely observation of every rare feed. |
| [The Unreasonable Effectiveness of Greedy Algorithms in Multi-Armed Bandit with Many Arms](https://arxiv.org/abs/2002.10121), Bayati, Hamidi, Johari and Khosravi, 2020. | Abstract | Consider bounded candidate subsampling. Its prior-tail assumptions do not justify starving untested sources or ignoring drift. |
| [A Practical Algorithm for Feature-Rich, Non-Stationary Bandit Problems](https://arxiv.org/abs/2603.16755), Loh, Sinha, Agarwal and Poupart, 2026. | Abstract | Candidate contextual predictor with correlated changing rewards. Stable correlation, Bernoulli framing and click evaluations need separate qualification here. |

## Acquisition and scarce observations

| Paper and authors | Read | Learn; limit or reason to defer |
| --- | --- | --- |
| [Bandits with Knapsacks](https://arxiv.org/abs/1305.2545), Badanidiyuru, Kleinberg and Slivkins, 2013. | Abstract | Learn joint reward and consumable-resource allocation. A high rank alone does not enforce a request budget. Do not import the full solver first. |
| [Resourceful Contextual Bandits](https://arxiv.org/abs/1402.6779), Badanidiyuru, Langford and Slivkins, 2014. | Abstract | Combine source context with resource constraints when data supports it. Shared context does not eliminate exploration cost. |
| [Optimal discovery with probabilistic expert advice: finite time analysis and macroscopic optimality](https://arxiv.org/abs/1207.5259), Bubeck, Ernst and Garivier, 2012. | Methods | Good-UCB targets new useful discoveries, close to source acquisition. Independent draws and non-overlapping useful outcomes are questionable with syndication. |
| [Change Rate Estimation and Optimal Freshness in Web Page Crawling](https://arxiv.org/abs/2004.02167), Avrachenkov, Patil and Thoppe, 2020. | Methods | Learn change rates from partial observations and schedule revisits. Fixed-rate Poisson assumptions need testing for scheduled and breaking-news feeds. |
| [A Scalable Crawling Algorithm Utilizing Noisy Change-Indicating Signals](https://arxiv.org/abs/2502.02430), Busa-Fekete et al., 2025. | Methods | Use noisy change hints and per-source crawl values under a global rate. The model assumes independent Poisson processes; signals and approximate priority updates are not perfect observations. |
| [Simple regret for infinitely many armed bandits](https://arxiv.org/abs/1505.04627), Carpentier and Valko, 2015. | Abstract | Learn the trade-off between trying more sources and learning enough about existing ones. Finding one good choice is not our coverage objective. |

## Testing a different policy

| Paper and authors | Read | Learn; limit or reason to defer |
| --- | --- | --- |
| [Doubly Robust Policy Evaluation and Learning](https://arxiv.org/abs/1103.4601), Dudik, Langford and Li, 2011. | Methods | Combine outcome prediction and logging probabilities. Correctness assumptions and support still matter; two biased models are not made correct by combining them. |
| [Counterfactual Risk Minimization: Learning from Logged Bandit Feedback](https://arxiv.org/abs/1502.02362), Swaminathan and Joachims, 2015. | Methods | Penalize uncertain policy estimates rather than optimize raw logged averages. Its IID/stationary-logging assumptions and clipping bias need attention. |
| [Safe Policy Improvement with Baseline Bootstrapping](https://arxiv.org/abs/1712.06924), Laroche, Trichelair and Tachet des Combes, 2017. | Abstract | Retain baseline behavior where evidence is weak. Its fixed-batch guarantees were not checked in enough depth to transfer here. |
| [Conservative Contextual Linear Bandits](https://arxiv.org/abs/1611.06426), Kazerouni, Ghavamzadeh, Abbasi-Yadkori and Van Roy, 2016. | Methods | Learn explicit baseline protection during exploration. Fixed linear rewards and valid confidence sets are assumptions, not gifts from the algorithm. |
| [Time-uniform, nonparametric, nonasymptotic confidence sequences](https://arxiv.org/abs/1810.08240), Howard, Ramdas, McAuliffe and Sekhon, 2018. | Abstract | Candidate machinery for repeated monitoring. Time-uniform coverage does not automatically handle our multiple signals, resets or dependence. |
| [Off-policy evaluation for slate recommendation](https://arxiv.org/abs/1605.04812), Swaminathan et al., 2016. | Methods | Log set/sequence selection correctly. Its additive-position assumptions do not cover arbitrary duplicate and coverage interactions. |

## Drift and coverage

| Paper and authors | Read | Learn; limit or reason to defer |
| --- | --- | --- |
| [OPTWIN: Drift identification with optimal sub-windows](https://arxiv.org/abs/2305.11942), Tosi and Theobald, 2023. | Abstract | Candidate bounded-window error detector using means and variances. Qualification must include false alarms and dependent, sparse feed evidence. |
| [The Window Dilemma: Why Concept Drift Detection is Ill-Posed](https://arxiv.org/abs/2602.06456), Gower-Winter, Groen and Krempl, 2026. | Abstract | Test window sensitivity and scheduled recalibration baselines. A detector alarm alone does not establish a useful adaptation. |
| [Lazier Than Lazy Greedy](https://arxiv.org/abs/1409.7938), Mirzasoleiman, Badanidiyuru, Karbasi, Vondrak and Krause, 2014. | Methods | Learn diminishing returns and cheaper subset selection. Its size-constrained monotone-submodular guarantee does not cover all I Feed constraints. |
| [How Algorithmic Confounding in Recommendation Systems Increases Homogeneity and Decreases Utility](https://arxiv.org/abs/1710.11214), Chaney, Stewart and Engelhardt, 2017. | Methods | Include exposure records and unselected-source audits. Simulations show a possible feedback failure, not an inevitable outcome for this digest. |
| [Recommenders with a mission: assessing diversity in news recommendations](https://arxiv.org/abs/2012.10185), Vrijenhoek et al., 2020. | Methods | Define what coverage serves editorially. Diverse labels or clicks alone do not prove reader benefit. |
| [Leveraging Media Frames to Improve Normative Diversity in News Recommendations](https://arxiv.org/abs/2509.02266), Dattawad, Daffara and Ceron, 2025. | Methods | Consider complementary perspectives beyond topics. Offline diversity and classifier-derived frames are not validated news truth. |

## Hybrid assessments and self-correction

| Paper and authors | Read | Learn; limit or reason to defer |
| --- | --- | --- |
| [Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena](https://arxiv.org/abs/2306.05685), Zheng et al., 2023. | Abstract | Evaluate position, verbosity and self-preference biases when a model has assessment weight. Human-preference agreement is not factual verification. |
| [Large Language Models Cannot Self-Correct Reasoning Yet](https://arxiv.org/abs/2310.01798), Huang et al., 2023. | Methods | Supply external feedback and equal-budget comparisons. Its reasoning results are not a universal ban on hybrid assessment or Python tuning. |
| [Calibration-Gated LLM Pseudo-Observations for Online Contextual Bandits](https://arxiv.org/abs/2604.14961), Pershin, Golovanov, Baltabaev and Trankova, 2026. | Methods | Test assessor influence against observed errors. This preliminary single-seed, short-horizon study found calibration gating worse than its simple task-specific baseline; its title is not evidence to adopt the gate. Do not count unplayed-arm guesses as delivery. |
| [Jump Start or False Start? A Theoretical and Empirical Evaluation of LLM-initialized Bandits](https://arxiv.org/abs/2604.02527), Bayley, Zhu, Aoki, Cao and Wilson, 2026. | Methods | Audit initial-prior alignment and model-version sensitivity. Linear/noise assumptions and conjoint preference experiments do not establish our news-quality calibration. |

## Further leads

Two related non-arXiv records were located:
[Optimal Freshness Crawl Under Politeness Constraints](https://www.microsoft.com/en-us/research/publication/optimal-freshness-crawl-under-politeness-constraints/)
and [Streaming Submodular Maximization: Massive Data Summarization on the Fly](https://doi.org/10.1145/2623330.2623637).
They are not counted above or treated as verified arXiv methods. Incorrect
candidate IDs were discarded after checking their titles.

Abstract-only results justify questions and candidate experiments, not detailed
algorithm adoption. Before implementing a paper's method, read its full setup,
check its license and implementation options, and compare its assumptions with
our observations. No paper's benchmark number is an I Feed performance claim.

## See also

- [../architecture/sources/i-feed.md](../architecture/sources/i-feed.md) - the app design and selected first delivery.
- [../concepts/feed.md](../concepts/feed.md) - why a feed earns its place.
- [../concepts/evaluation.md](../concepts/evaluation.md) - existing measurements and their limits.
