# RAG Held-out Evaluation Report

Generated: 2026-11-09T11:15:28.926832+00:00

Held-out fixture: `evaluation/questions_heldout_v1.json`; chunking: `hierarchical`; judge: `v1.2`; models: `text-embedding-3-small` and `gpt-4.1-mini`; generation temperature: `0`; cost guard: `$2.00`.

The same validated 612-chunk hierarchical collection was reused for both configurations. No ingestion or indexing API calls were made during this held-out run.

## Configurations

| Configuration | Retrieval | Top-k | Document hint | Grounding prompt | RRF k | Candidate multiplier |
|---|---|---:|---|---|---:|---:|
| Embedding k=5 (baseline) | embedding | 5 | none | off | 60 | 4 |
| Hybrid k=10 + document hint + grounded prompt | hybrid | 10 | boost | on | 60 | 4 |

## Results side by side

| Metric | Embedding k=5 (baseline) | Hybrid k=10 + document hint + grounded prompt |
|---|---:|---:|
| Questions | 20 | 20 |
| Correct / partial / incorrect | 13/1/6 | 12/2/6 |
| Correct rate | 65.0% | 60.0% |
| Retrieval hit rate | 50.0% | 50.0% |
| Mean first-hit rank | 1.62 | 1.25 |
| Answerable refusals | 5 | 5 |
| Answerable refusal rate | 31.2% | 31.2% |
| Not-in-documents correct | 4 | 4 |
| Not-in-documents correct rate | 100.0% | 100.0% |
| Citations: all correct | 43.8% | 50.0% |
| Citations: at least one correct | 50.0% | 50.0% |
| Mean latency / question (s) | 3.02 | 3.03 |
| Total question latency (s) | 60.45 | 60.67 |
| Question input tokens | 50792 | 83954 |
| Question output tokens | 2455 | 2086 |
| Question cost (USD) | $0.024059 | $0.036734 |
| Not-in-documents C/P/I | 4/0/0 | 4/0/0 |

Citation rates use sourced questions as their denominator. An answer with no parsed citation fails both citation measures.

## Refusals on answerable questions

| Configuration | Count | Question IDs |
|---|---:|---|
| Embedding k=5 (baseline) | 5 | h007, h013, h014, h015, h016 |
| Hybrid k=10 + document hint + grounded prompt | 5 | h007, h012, h013, h014, h015 |

## Not-in-documents results

| Configuration | ID | Label | Answer | Judge reason |
|---|---|---|---|---|
| Embedding k=5 (baseline) | h017 | correct | The supplied sources do not contain information about any fine imposed by the FCA on Starling Bank for financial crime control failings. | The candidate answer correctly states that the supplied sources do not contain information about the FCA fine on Starling Bank, matching the expected answer that the documents do not cover this. |
| Embedding k=5 (baseline) | h018 | correct | The sources do not provide specific information on how much APP fraud Monzo reimbursed to its customers in 2025. They mention that since October 2024, banks have been mandatorily reimbursing losses where victims are deceived into willingly transferring money (APP fraud), and in the first year of the scheme, 88% (£173 million) of money lost to in-scope APP fraud was reimbursed to victims overall, but no breakdown by individual banks such as Monzo is given [Source 1]. | The candidate correctly states that the sources do not provide specific information on Monzo's APP fraud reimbursements in 2025, aligning with the expected answer that the documents do not cover this. |
| Embedding k=5 (baseline) | h019 | correct | The sources provided do not specify the maximum amount reimbursed per claim under the mandatory APP fraud reimbursement scheme. They mention that since October 2024, banks have been mandatorily reimbursing losses where victims are deceived into willingly transferring money (APP fraud), and that 88% (£173m) of money lost to in-scope APP fraud was reimbursed to victims in the first year of the scheme [Source 1]. However, no details on the maximum reimbursement amount per claim are given. | The candidate answer correctly states that the sources do not specify the maximum reimbursement amount per claim and accurately reflects the information given about the scheme without adding unsupported details. |
| Embedding k=5 (baseline) | h020 | correct | The sources do not provide information on the total UK loss to APP (Authorized Push Payment) fraud for the full calendar year 2026. The latest data available is for the first half of 2025, where at least £629.3 million was stolen, with a significant portion related to APP fraud, but no figures for 2026 are given. Therefore, the total UK loss to APP fraud for the full calendar year 2026 is not available in the provided sources. | The candidate correctly states that the sources do not provide information on the total UK loss to APP fraud for 2026, aligning with the expected answer that the documents do not cover this. |
| Hybrid k=10 + document hint + grounded prompt | h017 | correct | The sources provided do not state the specific fine imposed by the FCA on Starling Bank for financial crime control failings. | The candidate correctly states that the sources do not provide information about the fine imposed by the FCA on Starling Bank, aligning with the expected answer that the documents do not cover this. |
| Hybrid k=10 + document hint + grounded prompt | h018 | correct | The sources do not state how much APP fraud Monzo reimbursed to its customers in 2025. | The candidate correctly states that the sources do not provide information on the amount of APP fraud Monzo reimbursed in 2025, matching the expected answer that the documents do not cover this. |
| Hybrid k=10 + document hint + grounded prompt | h019 | correct | The sources do not state the maximum amount reimbursed per claim under the mandatory APP fraud reimbursement scheme. | The candidate answer correctly states that the sources do not provide information about the maximum reimbursement amount, matching the expected answer that the documents do not cover this. |
| Hybrid k=10 + document hint + grounded prompt | h020 | correct | The sources do not state the total UK loss to APP (Authorised Push Payment) fraud for the full calendar year 2026. The closest data available is that at least £629.3 million was stolen in the first half of 2025 alone, with APP fraud losses reimbursed at 88% (£173 million) in the first year of the reimbursement scheme starting October 2024 [Source 1]. However, no figures for the full year 2026 are provided in the sources. | The candidate correctly states that the sources do not provide the total UK loss to APP fraud for the full calendar year 2026 and appropriately notes related data from other periods without inventing information. |

## Index reuse and total cost

- Reused indexed chunks: `612`
- Held-out indexing calls: `0`
- Held-out indexing API cost: `$0.000000`
- Total held-out API spend: `$0.060793`
- Cost limit: `$2.00`

## Document hint audit

| Configuration | Applied | Question IDs |
|---|---:|---|
| Embedding k=5 (baseline) | 0 | None |
| Hybrid k=10 + document hint + grounded prompt | 8 | h005, h006, h007, h011, h012, h013, h014, h016 |

## Wrong or partially correct answers

### h005 - Embedding k=5 (baseline) - partially correct

**Question:** What results does Economic Crime Plan 2 attribute to the JMLIT+ public-private partnership model since 2015?

**Answer:** The Economic Crime Plan 2 attributes significant results to the JMLIT+ public-private partnership model since 2015. Specifically, a case study highlights that in February 2022, the Joint Money Laundering Intelligence Taskforce (JMLIT+) Operations Group, a public-private partnership hosted in the National Crime Agency's National Economic Crime Centre, supported the Ministry of Defence Police in an investigation into fraud, bribery, and money laundering. As a direct result of intelligence provided through this public-private collaboration under JMLIT+, 45 previously unknown accounts were identified, and £53 million of funds were restrained [Source 5].

This demonstrates the effectiveness of the JMLIT+ model in uncovering hidden financial accounts and restraining substantial illicit funds through collaborative intelligence sharing between public and private sectors.

**Expected:** 1,000 requests from law enforcement, contributing to over 300 arrests and the identification, seizure or restraint of over £146 million.

**Judge reason:** The candidate answer provides a relevant example of JMLIT+ results, including identification of accounts and restraint of £53 million, but it does not mention the total 1,000 law enforcement requests, over 300 arrests, or the total £146 million seized or restrained as stated in the expected answer.

**Retrieval:** hit=False; first-hit rank=None.

### h007 - Embedding k=5 (baseline) - incorrect

**Question:** According to the 2020 Economic Crime Survey cited in Economic Crime Plan 2, what share of businesses in the surveyed sectors had been a victim of fraud in the previous three years?

**Answer:** According to the 2020 Economic Crime Survey cited in the Economic Crime Plan 2, one in four UK businesses with more than one employee experienced fraud in the previous twelve months. This amounts to approximately 25% of businesses in the surveyed sectors being victims of fraud in that period [Source 1]. 

The exact share over the previous three years is not explicitly stated in the provided sources, but the 1 in 4 figure for the previous twelve months gives a clear indication of the scale of fraud victimization among businesses.

**Expected:** Around one in five (18%).

**Judge reason:** refused an answerable question

**Retrieval:** hit=False; first-hit rank=None.

### h012 - Embedding k=5 (baseline) - incorrect

**Question:** How did the 2025 NRA's money-laundering risk rating for the casino sector change?

**Answer:** The 2025 NRA's money-laundering risk rating for the casino sector remained high. Specifically, the remote casino sector continued to demonstrate a high risk of non-compliance with money laundering regulations due to issues such as customers not being physically present for identification and verification, which poses a high risk related to stolen or fraudulent identification. The non-remote casino sector also continued to be rated as having a higher money laundering risk relative to other gambling sectors, with widespread compliance failings enabling high levels of suspicious transactions [Source 1].

There is no indication in the sources that the risk rating for the casino sector changed from previous assessments; rather, the high risk rating persisted in the 2023-24 reporting period. The methodology used to assess risk remains consistent with previous NRAs, meaning that while numerical scores may have shifted, the overall risk level for the casino sector stayed at high [Source 2].

**Expected:** It increased from low to medium.

**Judge reason:** The expected answer states the risk rating increased from low to medium, but the candidate answer says the rating remained high with no change, which contradicts the expected answer.

**Retrieval:** hit=False; first-hit rank=None.

### h013 - Embedding k=5 (baseline) - incorrect

**Question:** How did the 2025 NRA's money-laundering risk rating for the regulated e-money and payment services sector change?

**Answer:** The supplied sources do not contain specific information about how the 2025 NRA's money-laundering risk rating for the regulated e-money and payment services sector changed.

**Expected:** It increased from medium to high.

**Judge reason:** refused an answerable question

**Retrieval:** hit=False; first-hit rank=None.

### h014 - Embedding k=5 (baseline) - incorrect

**Question:** What money-laundering risk rating did the 2025 NRA give accountancy service providers?

**Answer:** The provided sources do not contain the specific money-laundering risk rating given to accountancy service providers in the 2025 National Risk Assessment (NRA).

**Expected:** High (it remains high).

**Judge reason:** refused an answerable question

**Retrieval:** hit=False; first-hit rank=None.

### h015 - Embedding k=5 (baseline) - incorrect

**Question:** How many incidents of computer misuse did individuals experience in the year ending December 2024, and how did that compare with the previous year?

**Answer:** The sources do not provide specific data on the number of incidents of computer misuse experienced by individuals in the year ending December 2024, nor do they offer a direct comparison with the previous year.

However, related information on fraud incidents experienced by individuals is available: Over 4 million offences of fraud against individuals were estimated in the year ending September 2025, representing 45% of all crime in the Crime Survey of England and Wales (CSEW). Around 1 in 14 adults were victims of fraud in this period. There was a slight drop in fraud between September 2019 and September 2023, but fraud is believed to have increased during the COVID-19 pandemic and is growing as a proportion of CSEW crime. Bank and credit account fraud rose 36% between the years ending September 2023 and 2025 [Source 1].

No specific figures or comparisons for computer misuse incidents are given in the sources.

**Expected:** 757,000 incidents, a 23% decrease on the prior year.

**Judge reason:** refused an answerable question

**Retrieval:** hit=False; first-hit rank=None.

### h016 - Embedding k=5 (baseline) - incorrect

**Question:** What money-laundering risk rating did the 2025 NRA give the non-profit organisation sector, and how had it changed?

**Answer:** The provided sources do not contain information about the money-laundering risk rating given to the non-profit organisation sector in the 2025 NRA, nor how that rating had changed.

**Expected:** Low, though the risk was judged to have risen within the low banding.

**Judge reason:** refused an answerable question

**Retrieval:** hit=False; first-hit rank=None.

### h002 - Hybrid k=10 + document hint + grounded prompt - partially correct

**Question:** How many applications for AML/CTF supervision did the FCA receive in 2023-24, and how many did it approve?

**Answer:** The FCA received 275 applications for AML/CTF supervision in 2023-24 and approved 154 of those applications (56%), with 120 applications rejected, withdrawn, or refused [Source 3].

**Expected:** 275 applications received and 154 approved (6 cryptoasset firms and 148 other firms).

**Judge reason:** The candidate answer correctly states the total applications received (275) and approved (154), but it omits the detailed breakdown of approved firms into 6 cryptoasset firms and 148 other firms as given in the expected answer.

**Retrieval:** hit=True; first-hit rank=3.

### h005 - Hybrid k=10 + document hint + grounded prompt - partially correct

**Question:** What results does Economic Crime Plan 2 attribute to the JMLIT+ public-private partnership model since 2015?

**Answer:** The Economic Crime Plan 2 attributes significant results to the JMLIT+ public-private partnership model since 2015, highlighting its pivotal role in progress against economic crime. Specifically, the first Economic Crime Plan (2019-2022) built on the foundations of public-private collaboration, bringing together capabilities, expertise, and intelligence from both sectors for the first time to deliver a holistic plan against economic crime. This partnership improved understanding of threats through joint public-private threat assessments and strengthened law enforcement responses and regulatory frameworks [Source 3].

A concrete example of JMLIT+'s impact is a February 2022 investigation supported by the JMLIT+ Operations Group, which identified 45 previously unknown accounts and restrained £53 million of funds in a fraud case against the Ministry of Defence. This was a direct result of intelligence provided through public-private collaboration under JMLIT+ [Source 1].

The second Economic Crime Plan builds on this foundation by expanding the public-private partnership to a truly multi-stakeholder approach, focusing more directly on impact and outcomes to cut crime, protect national security, and support legitimate economic growth. It emphasizes a new approach to public-private prioritization to maximize resources for preventing, detecting, and disrupting economic crime [Source 3, Source 5].

In summary, since 2015, the JMLIT+ model has led to improved threat understanding, enhanced law enforcement and regulatory frameworks, and tangible operational successes such as the identification and restraint of significant criminal funds, demonstrating the added value of voluntary private sector efforts going beyond legal duties [Source 1, Source 3, Source 5].

**Expected:** 1,000 requests from law enforcement, contributing to over 300 arrests and the identification, seizure or restraint of over £146 million.

**Judge reason:** The candidate answer provides a detailed explanation of the JMLIT+ model's impact and mentions specific operational successes, but it does not include the key quantitative results from the expected answer: 1,000 law enforcement requests, over 300 arrests, and identification/seizure/restraint of over £146 million. Instead, it only cites one example of £53 million restrained, missing the broader statistics.

**Retrieval:** hit=False; first-hit rank=None.

### h007 - Hybrid k=10 + document hint + grounded prompt - incorrect

**Question:** According to the 2020 Economic Crime Survey cited in Economic Crime Plan 2, what share of businesses in the surveyed sectors had been a victim of fraud in the previous three years?

**Answer:** The 2020 Economic Crime Survey cited in the Economic Crime Plan 2 found that one quarter (25%) of UK businesses with more than one employee had experienced fraud in the previous twelve months. This amounts to approximately 389,000 businesses experiencing fraud [Source 7]. However, the sources do not explicitly state the share of businesses in the surveyed sectors that had been a victim of fraud in the previous three years.

**Expected:** Around one in five (18%).

**Judge reason:** refused an answerable question

**Retrieval:** hit=False; first-hit rank=None.

### h012 - Hybrid k=10 + document hint + grounded prompt - incorrect

**Question:** How did the 2025 NRA's money-laundering risk rating for the casino sector change?

**Answer:** The sources do not state how the 2025 NRA's money-laundering risk rating for the casino sector changed.

**Expected:** It increased from low to medium.

**Judge reason:** refused an answerable question

**Retrieval:** hit=False; first-hit rank=None.

### h013 - Hybrid k=10 + document hint + grounded prompt - incorrect

**Question:** How did the 2025 NRA's money-laundering risk rating for the regulated e-money and payment services sector change?

**Answer:** The sources do not state how the 2025 NRA's money-laundering risk rating for the regulated e-money and payment services sector changed.

**Expected:** It increased from medium to high.

**Judge reason:** refused an answerable question

**Retrieval:** hit=False; first-hit rank=None.

### h014 - Hybrid k=10 + document hint + grounded prompt - incorrect

**Question:** What money-laundering risk rating did the 2025 NRA give accountancy service providers?

**Answer:** The sources do not state the specific money-laundering risk rating given to accountancy service providers in the 2025 National Risk Assessment (NRA).

**Expected:** High (it remains high).

**Judge reason:** refused an answerable question

**Retrieval:** hit=False; first-hit rank=None.

### h015 - Hybrid k=10 + document hint + grounded prompt - incorrect

**Question:** How many incidents of computer misuse did individuals experience in the year ending December 2024, and how did that compare with the previous year?

**Answer:** The sources do not state the exact number of incidents of computer misuse experienced by individuals in the year ending December 2024, nor do they provide a comparison with the previous year. The provided sources focus primarily on fraud incidents and economic crime statistics, but do not specifically mention computer misuse incidents.

**Expected:** 757,000 incidents, a 23% decrease on the prior year.

**Judge reason:** refused an answerable question

**Retrieval:** hit=False; first-hit rank=None.

### h016 - Hybrid k=10 + document hint + grounded prompt - incorrect

**Question:** What money-laundering risk rating did the 2025 NRA give the non-profit organisation sector, and how had it changed?

**Answer:** The 2025 National Risk Assessment (NRA) gave the non-profit organisation sector a medium money-laundering risk rating. This rating had decreased from the previous NRA in 2020, where the sector was rated as high risk. This change reflects a reduction in the assessed money laundering risk for the non-profit organisation sector between 2020 and 2025 [Source 5, Section 5 - Sector Specific Risks, Non-Profit Organisations].

**Expected:** Low, though the risk was judged to have risen within the low banding.

**Judge reason:** The expected answer states the risk rating was low and had risen within the low banding, while the candidate answer incorrectly states the rating was medium and had decreased from high in 2020, which contradicts the expected facts.

**Retrieval:** hit=False; first-hit rank=None.

