# RAG Evaluation Report v2

Generated: 2026-11-08T11:46:09.020673+00:00

Development fixture: `evaluation/questions_v1.json`; chunking: `hierarchical`; judge: `v1.2`; models: `text-embedding-3-small` and `gpt-4.1-mini`; generation temperature: `0`; cost guard: `$2.00`.

The corpus was indexed once and the same hierarchical collection was used for every configuration.

## Configurations

| Configuration | Retrieval | Top-k | Document hint | Grounding prompt | RRF k | Candidate multiplier |
|---|---|---:|---|---|---:|---:|
| Embedding k=5 (baseline) | embedding | 5 | none | off | 60 | 4 |
| Hybrid k=5 | hybrid | 5 | none | off | 60 | 4 |
| Hybrid k=10 | hybrid | 10 | none | off | 60 | 4 |
| Hybrid k=10 + document hint + grounded prompt | hybrid | 10 | boost | on | 60 | 4 |

## Results side by side

| Metric | Embedding k=5 (baseline) | Hybrid k=5 | Hybrid k=10 | Hybrid k=10 + document hint + grounded prompt |
|---|---:|---:|---:|---:|
| Questions | 40 | 40 | 40 | 40 |
| Correct / partial / incorrect | 29/3/8 | 29/2/9 | 30/2/8 | 31/2/7 |
| Correct rate | 72.5% | 72.5% | 75.0% | 77.5% |
| Retrieval hit rate | 67.6% | 67.6% | 70.6% | 70.6% |
| Mean first-hit rank | 2.04 | 1.91 | 2.21 | 2.04 |
| Answerable refusals | 7 | 7 | 6 | 7 |
| Answerable refusal rate | 20.6% | 20.6% | 17.6% | 20.6% |
| Not-in-documents correct | 6 | 6 | 5 | 6 |
| Not-in-documents correct rate | 100.0% | 100.0% | 83.3% | 100.0% |
| Citations: all correct | 44.1% | 52.9% | 44.1% | 50.0% |
| Citations: at least one correct | 64.7% | 70.6% | 64.7% | 67.6% |
| Mean latency / question (s) | 2.81 | 2.88 | 3.22 | 2.88 |
| Total question latency (s) | 112.50 | 115.39 | 128.79 | 115.13 |
| Question input tokens | 100460 | 103658 | 173469 | 169245 |
| Question output tokens | 6284 | 6398 | 7085 | 5575 |
| Question cost (USD) | $0.049970 | $0.051431 | $0.080455 | $0.076349 |
| Not-in-documents C/P/I | 6/0/0 | 6/0/0 | 5/0/1 | 6/0/0 |

Citation rates use sourced questions as their denominator. An answer with no parsed citation fails both citation measures.

## Refusals on answerable questions

| Configuration | Count | Question IDs |
|---|---:|---|
| Embedding k=5 (baseline) | 7 | q008, q011, q016, q028, q029, q031, q032 |
| Hybrid k=5 | 7 | q008, q011, q027, q028, q031, q032, q034 |
| Hybrid k=10 | 6 | q008, q011, q029, q031, q032, q034 |
| Hybrid k=10 + document hint + grounded prompt | 7 | q008, q011, q027, q028, q029, q031, q032 |

## Not-in-documents results

| Configuration | ID | Label | Answer | Judge reason |
|---|---|---|---|---|
| Embedding k=5 (baseline) | q035 | correct | The provided sources do not specify which commercial vendor or algorithm Companies House uses for identity verification. They mention that the Economic Crime and Corporate Transparency Act 2023 introduced mandatory identity verification for directors, persons with significant control, and those filing information with Companies House, and that Companies House is rolling out ID verification capabilities. However, no details about the specific commercial vendor or algorithm employed for this identity verification are given in the sources [Source 1], [Source 2], [Source 3], [Source 4], [Source 5]. | The candidate answer correctly states that the sources do not specify the commercial vendor or algorithm used by Companies House for identity verification, aligning with the expected answer that the documents do not cover this information. |
| Embedding k=5 (baseline) | q036 | correct | The sources do not provide information on how many convictions the National Fraud Squad secured during calendar year 2026. Source 1 discusses convictions up to the year ending September 2025 but does not specify data for 2026 or specifically for the National Fraud Squad. Source 2 mentions that the Home Office will deliver an impact evaluation of the National Fraud Squad in 2027, implying that detailed outcomes for 2026 may not yet be available. Source 3 describes the role and planned improvements for the National Fraud Squad but does not include conviction statistics for 2026. Therefore, the number of convictions secured by the National Fraud Squad during calendar year 2026 is not stated in the provided sources. | The candidate answer correctly states that the documents do not provide information on convictions secured by the National Fraud Squad during 2026, aligning with the expected answer that the documents do not cover this. |
| Embedding k=5 (baseline) | q037 | correct | The sources provided do not contain specific information about the total fraud loss recorded in Scotland in October 2025. They provide data on fraud incidents and losses in broader time frames (such as yearly or half-yearly) and for the UK or Scotland generally, but not for the specific month of October 2025. Therefore, the total fraud loss recorded in Scotland in October 2025 is not available from the supplied sources. | The candidate correctly states that the supplied sources do not contain specific information about the total fraud loss in Scotland for October 2025, aligning with the expected answer that the documents do not cover this. |
| Embedding k=5 (baseline) | q038 | correct | The sources provided do not contain information about which blockchain analytics vendor the FCA procured in 2025 or the contract price for such procurement. | The candidate answer correctly states that the sources do not contain information about the vendor or contract price, matching the expected answer that the documents do not cover this. |
| Embedding k=5 (baseline) | q039 | correct | The supplied sources do not contain information about the percentage reduction in AML false positives achieved by a named UK bank using AI. | The candidate answer correctly states that the supplied sources do not contain the requested information, matching the expected answer for a not-in-documents question. |
| Embedding k=5 (baseline) | q040 | correct | The supplied sources do not provide information on the number of sanctions-evasion prosecutions completed in Northern Ireland in 2024-25. | The candidate answer correctly states that the supplied sources do not provide information on the number of sanctions-evasion prosecutions in Northern Ireland for 2024-25, matching the expected answer. |
| Hybrid k=5 | q035 | correct | The provided sources do not specify which commercial vendor or algorithm Companies House uses for identity verification. They mention that the Economic Crime and Corporate Transparency Act 2023 introduced mandatory identity verification for directors, persons with significant control, and those filing information with Companies House, and that Companies House will roll out ID verification to new and existing directors, partners, presenters, and People with Significant Control. However, no details about the commercial vendor or the specific algorithm used for this identity verification are given in the sources [Source 1], [Source 2], [Source 3], [Source 4], [Source 5]. | The candidate answer correctly states that the sources do not specify the commercial vendor or algorithm used by Companies House for identity verification, aligning with the expected answer that the documents do not cover this information. |
| Hybrid k=5 | q036 | correct | The sources provided do not contain information on the number of convictions secured by the National Fraud Squad during calendar year 2026. | The candidate answer correctly states that the sources do not contain information on the number of convictions secured by the National Fraud Squad in 2026, matching the expected answer that the documents do not cover this. |
| Hybrid k=5 | q037 | correct | The sources provided do not contain information about the total fraud loss recorded specifically in Scotland in October 2025. | The candidate correctly states that the sources do not contain information about the total fraud loss in Scotland in October 2025, matching the expected answer that the documents do not cover this. |
| Hybrid k=5 | q038 | correct | The sources provided do not contain information about which blockchain analytics vendor the FCA procured in 2025 or the contract price for such procurement. | The candidate answer correctly states that the sources do not contain information about the vendor or contract price, matching the expected answer that the documents do not cover this. |
| Hybrid k=5 | q039 | correct | The supplied sources do not contain information about the percentage reduction in AML false positives achieved by a named UK bank using AI. | The candidate answer correctly states that the supplied sources do not contain the requested information, matching the expected answer for a not-in-documents question. |
| Hybrid k=5 | q040 | correct | The sources provided do not contain specific information on the number of sanctions-evasion prosecutions completed in Northern Ireland in 2024-25. | The candidate answer correctly states that the sources do not contain the requested information, matching the expected answer for a not-in-documents question. |
| Hybrid k=10 | q035 | correct | The provided sources do not specify which commercial vendor or algorithm Companies House uses for identity verification. While the Economic Crime and Corporate Transparency Act 2023 introduces mandatory identity verification for company directors, persons with significant control, and those filing information with Companies House, and Companies House is rolling out ID verification capabilities, no details about the specific commercial vendor or algorithm employed are mentioned in the sources [Source 1], [Source 2], [Source 3], [Source 4], [Source 5], [Source 6], [Source 7]. | The candidate answer correctly states that the provided sources do not specify the commercial vendor or algorithm used by Companies House for identity verification, aligning with the expected answer that the documents do not cover this information. |
| Hybrid k=10 | q036 | correct | The sources provided do not contain information on the number of convictions secured by the National Fraud Squad during calendar year 2026. | The candidate answer correctly states that the sources do not contain information on the number of convictions secured by the National Fraud Squad in 2026, matching the expected answer. |
| Hybrid k=10 | q037 | correct | The sources provided do not contain specific information about the total fraud loss recorded in Scotland in October 2025. They provide data on fraud losses in the UK generally and some statistics for Scotland over broader time periods, but no exact figure for Scotland's fraud loss in October 2025 is given. For example: - Source 1 mentions £629.3 million stolen in the first half of 2025 in the UK but does not break this down by region or month. - Source 2 states Scotland had 456,000 fraud offences in 2023/24 but does not provide financial loss figures or data for October 2025. - Other sources discuss fraud types, impacts, and law enforcement responses but do not specify fraud losses for Scotland in October 2025. Therefore, the total fraud loss recorded in Scotland in October 2025 is not provided in the supplied sources. | The candidate answer correctly states that the documents do not contain specific information about the total fraud loss in Scotland in October 2025 and supports this with relevant details, matching the expected answer that the documents do not cover this information. |
| Hybrid k=10 | q038 | incorrect | The FCA procured the blockchain analytics vendor Chainalysis in 2025 under a contract priced at £1.5 million. This procurement was part of the FCA's efforts to enhance its technological capabilities to combat illicit use of cryptoassets and strengthen regulatory enforcement action against unlawful cryptoasset activity in the UK [Source 3]. | The question is not covered by the documents, but the candidate answer provides specific details not supported by the documents, making it incorrect. |
| Hybrid k=10 | q039 | correct | The supplied sources do not contain information about a specific percentage reduction in AML false positives achieved by a named UK bank using AI. | The candidate answer correctly states that the supplied sources do not contain the requested information, matching the expected answer for a not-in-documents question. |
| Hybrid k=10 | q040 | correct | The sources provided do not contain specific information on the number of sanctions-evasion prosecutions completed in Northern Ireland in 2024-25. While there is detailed information about the responsibilities of the Police Service of Northern Ireland (PSNI) and the Public Prosecution Service for Northern Ireland in investigating and prosecuting economic crime, including sanctions evasion, no exact figures or data on prosecutions completed in 2024-25 are given. Therefore, the answer to the question "How many sanctions-evasion prosecutions were completed in Northern Ireland in 2024-25?" is not available in the supplied sources. | The candidate answer clearly states that the supplied sources do not contain specific information on the number of sanctions-evasion prosecutions completed in Northern Ireland in 2024-25, aligning with the expected answer that the documents do not cover this. |
| Hybrid k=10 + document hint + grounded prompt | q035 | correct | The sources do not state which commercial vendor and algorithm Companies House uses for identity verification. | The candidate answer correctly states that the sources do not provide information about the commercial vendor and algorithm used by Companies House for identity verification, matching the expected answer. |
| Hybrid k=10 + document hint + grounded prompt | q036 | correct | The sources do not state how many convictions the National Fraud Squad secured during calendar year 2026. | The candidate answer correctly states that the sources do not provide information on the number of convictions secured by the National Fraud Squad in 2026, matching the expected answer that the documents do not cover this. |
| Hybrid k=10 + document hint + grounded prompt | q037 | correct | The sources do not state the total fraud loss recorded in Scotland in October 2025. | The candidate answer correctly states that the sources do not provide information on the total fraud loss in Scotland in October 2025, matching the expected answer that the documents do not cover this. |
| Hybrid k=10 + document hint + grounded prompt | q038 | correct | The sources do not state which blockchain analytics vendor the FCA procured in 2025, nor the contract price for such procurement. | The candidate answer correctly states that the sources do not provide information about the vendor or contract price, matching the expected answer that the documents do not cover this. |
| Hybrid k=10 + document hint + grounded prompt | q039 | correct | The sources do not state the percentage reduction in AML false positives achieved by a named UK bank using AI. | The candidate correctly states that the sources do not provide the percentage reduction in AML false positives achieved by a named UK bank using AI, matching the expected answer that the documents do not cover this information. |
| Hybrid k=10 + document hint + grounded prompt | q040 | correct | The sources do not state how many sanctions-evasion prosecutions were completed in Northern Ireland in 2024-25. | The candidate answer correctly states that the sources do not provide information on the number of sanctions-evasion prosecutions completed in Northern Ireland in 2024-25, matching the expected answer's indication that the documents do not cover this. |

## Shared indexing and total cost

- Indexing duration: `1313.22` seconds
- Indexing API cost: `$0.001146`
- Final result-set API cost: `$0.259351`
- Cost limit: `$2.00`

## Validation rerun accounting

The document-hint configuration was rerun after correcting generic short-title matching. It reused the identical chunks and embeddings; the first three configurations were unaffected.

- Discarded pre-fix question cost (USD): 0.078687
- Actual cumulative API spend (USD): 0.338038
- Cost limit (USD): 2.00
