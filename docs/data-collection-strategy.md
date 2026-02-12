# Data Collection Strategy for Hate-Lex v2

## 0. Document Control

- Status: Draft
- Scope: Defines how Sentinel sources, curates, and maintains the lexicon and training data that power the moderation engine
- Related: `docs/master.md` (Sec. 8), `docs/specs/rfcs/0001-v1-moderation-api.md`, `docs/specs/adr/0002-lexicon-release-lifecycle.md`

## 1. Problem

Sentinel's value is bounded by the quality and coverage of its knowledge base. The governance pipeline for updating lexicons is built (release lifecycle, audit trail, proposal workflow), but the intake funnel — where candidate terms, phrases, and annotated data actually come from — is undefined.

This document specifies the sourcing strategy, annotation standards, legal constraints, and operational workflows for populating and maintaining Hate-Lex v2.

## 2. Sourcing Tiers

Data collection is organized into three tiers based on availability, effort, and reliability.

### Tier 1: Institutional and Published Sources (Immediate)

These are existing, structured resources that can seed the lexicon before any original data collection begins.

#### 2.1.1 NCIC Hatelex

The National Cohesion and Integration Commission published a lexicon of **523 hate speech terms** covering English, Swahili, Sheng, Kikuyu, Kalenjin, and non-verbal signals. This is the single most authoritative Kenyan institutional source.

- Terms were identified through a participatory questionnaire process where Kenyans cited words used to incite hate or provoke violence.
- Includes terms like *madoadoa* ("stains/spots" — dehumanizing reference to ethnic minorities), *chunga kura*, *hatupangwingwi*, and direct English terms like *fumigation* and *eliminate* used in political context.
- Described by NCIC as a "living document" with periodic updates.
- Source: [NCIC Hatelex PDF](https://cohesion.go.ke/images/docs/downloads/Hatelex_A_Lexicon_of_Hate_Speech_Terms_In_Kenya.pdf)

**Action:** Ingest the full NCIC Hatelex as the baseline seed, mapping each entry to Hate-Lex v2 schema fields (language, severity, category, variants, positive/negative examples).

#### 2.1.2 HateBase

The Sentinel Project's HateBase contains **2,300+ hate speech terms** across 90+ languages and 175+ countries, crowdsourced with geography and target-population metadata. Includes regionality data (frequency, localization, migration of terms over time).

- Source: [hatebase.org](https://hatebase.org/)

**Action:** Extract East African entries (Kenya, Tanzania, Uganda) and cross-reference with NCIC Hatelex for coverage gaps.

#### 2.1.3 Academic Datasets

| Dataset | Size | Languages | Focus | Source |
|---|---|---|---|---|
| HateSpeech_Kenya (Ombui et al., UoN) | ~260K tweets, ~51K annotated | English, Swahili, code-switched | 2017 election political hate speech | [ResearchGate](https://www.researchgate.net/publication/334571792_Annotation_Framework_for_Hate_Speech_Identification_in_Tweets_Case_Study_of_Tweets_During_Kenyan_Elections) |
| AfriHate (2025) | ~150K annotations across 15 languages | Swahili + 14 others | Hate and abusive language, politics/ethnicity/gender targets | [arXiv](https://arxiv.org/abs/2501.08284) |
| Swahili/En-Sw Code-Switched Political Hate Speech (2025) | TBD | Swahili, English-Swahili mixed | Political hate speech with language annotation | [SciEngine](https://www.sciengine.com/DI/doi/10.3724/2096-7004.di.2025.0053) |
| PolitiKweli | 29,510 texts | Swahili, Kenyan English, code-switched | Political misinformation classification | [Springer](https://link.springer.com/chapter/10.1007/978-3-031-58495-4_1) |
| XTREMESPEECH | 20,297 passages | Swahili + 5 others | Derogatory, exclusionary, dangerous speech | Academic publication |
| RideKE | 29,000+ entries | Kenyan English, Swahili, Sheng | Sentiment/emotion in code-switched text | [arXiv](https://arxiv.org/html/2502.06180) |

**Action:** Acquire datasets with compatible licenses. Extract term-level signals (slurs, dog whistles, violence idioms) and map to Hate-Lex v2 entries. Use annotated examples as positive/negative evidence for calibration.

#### 2.1.4 Historical Commission Reports

The **Waki Commission / CIPEV (2008)** report documented how media fueled post-2007 election violence and catalogued specific hate speech terms and their deployment patterns. This is critical for historical context grounding (the "clashes", "land issues" references noted as Very High risk in the master plan).

- Source: [CIPEV Final Report (Kenya Parliament Library)](https://libraryir.parliament.go.ke/items/f5cddc2c-be79-4c23-9174-d322177cc13e)

**Action:** Extract documented hate speech terms, coded language, and incitement patterns. Tag with temporal context (2007-2008 crisis period) for historical reference calibration.

### Tier 2: Partner and Community Collection (Months 1-6)

These require active relationships but produce high-quality, contextually grounded data.

#### 2.2.1 MAPEMA Consortium Model

The MAPEMA consortium (Code for Africa, Shujaaz Inc., AIfluence) deployed during the 2022 election is the closest operational precedent:

- Maintained a machine-readable hatelex database.
- Tracked English, Swahili, and Sheng in real time.
- Identified 550,000+ toxic Facebook posts and flagged 800+ hate speech cases to platforms.
- Used ML-based sentiment analysis, social network analysis, and counter-messaging (reaching 27.9 million Kenyans).

**Action:** Seek data-sharing partnership with Code for Africa / CivicSignal for their 2022 election monitoring dataset and hatelex database. Their methodology is directly replicable for Sentinel's monitoring pipeline.

#### 2.2.2 WikiRumours / Una Hakika

The Sentinel Project's Una Hakika deployment in Kenya's Tana Delta collected community-reported rumours via SMS, phone, social media, and community ambassadors. The WikiRumours platform (MIT-licensed, open source) stores verified rumour data.

- 18,000+ SMS users in Tana Delta.
- Multi-channel intake with anonymous reporting.
- Trained community ambassador network for local verification.
- Expanded to Tana River County, Lamu County, and major Nairobi slums (1M+ population).

**Action:** Deploy WikiRumours as a community intake channel for Sentinel's monitoring pipeline. Use the existing Tana Delta and Nairobi datasets as ground-truth labels for rumour/disinfo narrative templates.

- Source: [WikiRumours GitHub (MIT)](https://github.com/thesentinelproject/WikiRumours)

#### 2.2.3 iVerify Kenya / Meedan Check

The Media Council of Kenya's iVerify system uses Meedan Check for human-in-the-loop ML fact-checking. Citizens submit claims; two independent fact-checkers evaluate each piece.

- Open source: [iVerify GitHub](https://github.com/undp/iVerify-Apps)
- Partners: MCK, UNDP, Meedan.

**Action:** Integrate with iVerify's fact-check corpus for verified disinfo narrative entries. Explore webhook-based submission of Sentinel-flagged `DISINFO_RISK` content to iVerify for human verification, feeding results back into Hate-Lex.

#### 2.2.4 Community Annotator Network

Following the models established by Masakhane NLP and the NaijaHate project:

1. **Recruit native-speaker annotators** for each Tier 1 language (English-KE, Kiswahili, Sheng, and priority mother-tongue languages).
2. **Use culture-specific controversial topic keywords** as collection seeds (replicating the NaijaHate methodology for Kenyan languages).
3. **Minimum 3 annotators per language** with inter-annotator agreement measurement.
4. **Annotation schema** aligned with Sentinel's harm taxonomy: `ETHNIC_CONTEMPT`, `INCITEMENT_VIOLENCE`, `HARASSMENT_THREAT`, `DOGWHISTLE_WATCH`, `DISINFO_RISK`, `BENIGN_POLITICAL_SPEECH`.

Priority annotator recruitment:

| Language | Community Source | Notes |
|---|---|---|
| Sheng | Nairobi youth networks, Shujaaz Inc. | Fastest lexical turnover, most opacity |
| Kikuyu | University of Nairobi linguistics dept | Highest-population vernacular |
| Luo | Maseno University, Kisumu community orgs | Critical for political balance |
| Kalenjin | Moi University, Eldoret community orgs | Rift Valley political significance |

- Masakhane community infrastructure: [masakhane.io](https://www.masakhane.io/)
- NaijaHate replicable pipeline: [GitHub](https://github.com/smaliyu/NaijaOffens)

### Tier 3: Continuous Collection (Ongoing)

These are the sustained operational feeds that keep the lexicon current during election cycles.

#### 2.3.1 Sentinel Monitoring Pipeline (Slow Path)

The async monitoring system (RFC-0002) is designed to detect emerging terms and narrative clusters. Once the worker is active (I-306), it becomes a primary intake funnel:

- Emerging term detection from permitted source feeds.
- Narrative clustering to identify new dog whistles and coded language.
- Candidate terms routed to human review via the proposal workflow.
- Approved entries promoted to lexicon releases with full audit trail.

This is the self-sustaining loop that addresses the "340+ new political terms per election cycle" risk.

#### 2.3.2 Platform-Resilient Ingestion

The CrowdTangle shutdown (August 2024) crippled iVerify and MAPEMA monitoring. Sentinel must not repeat this dependency:

- **Meta Content Library** replaces CrowdTangle but is restricted to academic/nonprofit researchers with limited export.
- **X/Twitter API** has become expensive and restrictive since 2023.
- **Connector abstraction** (master plan Sec. 14) must be enforced: every platform integration is replaceable.

Fallback channels that do not depend on platform APIs:

| Channel | Method | Resilience |
|---|---|---|
| Partner submissions | Webhook intake from fact-checkers, media houses | Platform-independent |
| Community reporting | SMS, web form, WhatsApp tip line | No platform API dependency |
| Public data feeds | RSS, government press releases, parliamentary records | Stable, open |
| Broadcast monitoring | Radio/TV transcript feeds from media partners | Covers offline rhetoric |

#### 2.3.3 Sheng-Specific Collection

Sheng presents a unique challenge: it is deliberately opaque, evolves rapidly, and serves as a primary vector for coded political speech among Nairobi youth. Dedicated collection is required:

- Partnership with Africa's Voices Foundation (Sheng NLP research).
- Leverage RideKE corpus (29K+ code-switched entries including Sheng).
- Ongoing community annotator engagement specifically for Sheng neologisms.
- Higher update frequency for Sheng pack entries during campaign periods.

## 3. Annotation Standards

### 3.1 Schema Mapping

Every collected term or phrase must map to the Hate-Lex v2 entry schema:

| Field | Required | Source |
|---|---|---|
| `term` | Yes | Collected text |
| `language` | Yes | Annotator or LID |
| `severity` | Yes | Annotator consensus (1-3 scale) |
| `category` | Yes | Harm taxonomy label |
| `variants` | Yes | Annotator-provided spelling/phonetic variants |
| `positive_examples` | Yes | In-context usage demonstrating harm |
| `negative_examples` | Yes | Benign usage of same term (critical for reducing false positives) |
| `first_seen` | Yes | Collection timestamp or historical reference date |
| `status` | Yes | `active` / `watchlist` / `deprecated` |
| `source` | Yes | Dataset, institution, or collection channel |
| `region` | Recommended | Geographic context where term carries this meaning |

### 3.2 Annotator Guidelines

1. **Minimum 3 independent annotations per entry** for severity and category.
2. **Inter-annotator agreement** measured via Krippendorff's alpha; entries below 0.67 agreement are routed to senior review.
3. **Negative examples are mandatory** — every entry must include at least one benign usage context to calibrate against false positives.
4. **Context documentation** — annotators must note whether harm depends on temporal context (election period), geographic context (specific region), or audience context (specific ethnic group).
5. **Code-switching entries** — for terms that are harmful only in mixed-language context, annotators must provide the full mixed-language example, not just the isolated term.

### 3.3 Quality Gates

Before any batch enters the release pipeline:

- Severity distribution review (flag batches that are >80% severity-3 — likely sampling bias).
- Language coverage check (no single language should dominate >60% of a batch unless intentional).
- False positive spot-check: 10% random sample tested against benign political speech corpus.
- Duplicate and variant deduplication against existing lexicon.

## 4. Legal and Ethical Constraints

### 4.1 Kenya Data Protection Act, 2019

| Requirement | Sentinel Compliance |
|---|---|
| Registration with Data Protection Commissioner | Required before any personal data processing |
| Data Protection Officer appointment | Must be designated |
| Consent for personal data | Not required for publicly posted content; required for community-submitted reports with personal identifiers |
| Purpose limitation | Data collected solely for hate speech detection and election safety |
| Retention limits | Per data retention architecture (master plan Sec. 12, ADR-0007) |

### 4.2 Computer Misuse and Cybercrimes Act, 2018

- Unauthorized access to computer systems is criminal (fines up to KES 20M / jail up to 10 years).
- Any systematic platform data collection must use authorized APIs or partner data-sharing agreements.
- No scraping of platforms without explicit authorization.

### 4.3 Platform Terms of Service

| Platform | Current Access | Constraint |
|---|---|---|
| Meta (Facebook, Instagram) | Meta Content Library | Academic/nonprofit only, limited export, no real-time tracking |
| X (Twitter) | Paid API tiers | Expensive, rate-limited, restrictive redistribution terms |
| TikTok | Research API | Geographic and institutional restrictions |
| Telegram | Bot API | Public channels only |

**Policy:** Sentinel does not scrape platforms. All platform data enters through authorized APIs, partner submissions, or public data feeds. Connector abstraction ensures no single-platform dependency.

### 4.4 Research Ethics

- Community-collected data (SMS reports, tip lines) must support anonymous submission.
- Annotators working with graphic hate speech content must have access to well-being support and rotation schedules.
- Published datasets must be anonymized: no personally identifiable information in public lexicon entries.
- Potential for hate speech laws to chill legitimate speech must be continuously evaluated. ARTICLE 19 and Human Rights Watch have documented this risk in Kenya specifically.

### 4.5 Licensing

| Source Type | Expected License | Redistribution |
|---|---|---|
| NCIC Hatelex | Government publication (public domain) | Yes |
| Academic datasets | CC-BY, CC-BY-SA, or research-only | Varies; verify per dataset |
| WikiRumours | MIT | Yes |
| HateBase | API terms | Verify redistribution rights |
| Community annotations | Contributor agreement (Apache 2.0 compatible) | Yes, with agreement |

All contributors to Hate-Lex must sign a contributor agreement granting Apache 2.0-compatible rights, consistent with the project license.

## 5. Collection Roadmap

### Phase 1: Baseline Seeding (Months 1-3)

| Action | Source | Expected Volume | Owner |
|---|---|---|---|
| Ingest NCIC Hatelex | NCIC PDF | ~523 terms | Core team |
| Extract HateBase East Africa entries | HateBase API | ~100-200 terms | Core team |
| Process HateSpeech_Kenya dataset | UoN / Ombui et al. | Term extraction from ~51K annotated tweets | Core team + UoN partnership |
| Extract Waki Commission terms | CIPEV report | ~50-100 historical terms | Core team |
| Process AfriHate Swahili subset | AfriHate dataset | ~10K annotated instances | Core team |

**Exit criteria:** Hate-Lex v2 contains 500+ entries across English, Kiswahili, and Sheng with complete schema fields, positive/negative examples, and severity ratings.

### Phase 2: Partner Integration (Months 3-6)

| Action | Source | Expected Volume | Owner |
|---|---|---|---|
| MAPEMA / Code for Africa data partnership | CfA / CivicSignal | 2022 election hatelex + monitoring data | Partnership lead |
| iVerify fact-check corpus integration | MCK / UNDP | ~5K verified claims | Partnership lead |
| WikiRumours dataset integration | Sentinel Project | Historical rumour data | Core team |
| Recruit Tier 1 community annotators | Masakhane, universities | 12+ annotators (3 per language) | Community lead |
| First community annotation sprint | Original collection | ~1000 new annotated entries | Community lead |

**Exit criteria:** Hate-Lex v2 contains 2,000+ entries across all Tier 1 languages. Community annotator pipeline producing weekly submissions. At least one partner data feed active.

### Phase 3: Continuous Operation (Months 6+)

| Action | Cadence | Owner |
|---|---|---|
| Monitoring pipeline emerging term detection | Continuous | Async worker |
| Community annotator review sprints | Biweekly (weekly during campaign) | Community lead |
| Partner feed ingestion | Continuous | Integration team |
| Sheng-specific collection sprint | Monthly | Sheng annotator team |
| Lexicon release with new entries | Weekly during campaign periods | Release manager |
| Quality audit and false-positive review | Monthly | Core team |

**Exit criteria:** Self-sustaining collection loop operational. Weekly lexicon releases during campaign periods. Emerging term detection active.

## 6. Metrics and Monitoring

| Metric | Target | Purpose |
|---|---|---|
| Lexicon entry count by language | Balanced coverage across Tier 1 | Detect language gaps |
| New entries per week | >20 during campaign periods | Measure adaptation speed |
| Annotator agreement (Krippendorff's alpha) | >0.67 per batch | Annotation quality |
| False positive rate by source | <5% on benign political speech | Source reliability |
| Time from first-seen to lexicon entry | <7 days for high-severity terms | Responsiveness |
| Partner feed uptime | >95% per active feed | Dependency health |

## 7. Open Questions

1. **NCIC partnership formalization:** Can Sentinel establish a direct data-sharing agreement with NCIC for ongoing Hatelex updates, or must we rely on published PDFs?
2. **MAPEMA data availability:** Is the 2022 election monitoring dataset available for research use, and under what terms?
3. **Annotator compensation model:** Volunteer (Masakhane model) vs. paid (NaijaHate model) vs. hybrid?
4. **Sheng lexicography partner:** Is Africa's Voices Foundation or Shujaaz Inc. available for ongoing Sheng data partnership?
5. **Historical dataset access:** Are the Ombui et al. 2017 election tweets still available for download, given platform TOS changes since collection?
