# RAG Evaluation Report v1

Generated: 2026-11-06T10:09:16.108169+00:00

Models: `text-embedding-3-small` and `gpt-4.1-mini`; generation temperature: `0`; cost guard: `$2.00`.

Citation accuracy is reported over sourced questions only; not-in-documents questions have no expected document/page target.

## Overall results

| Metric | Hierarchical | Semantic |
|---|---:|---:|
| Questions | 40 | 40 |
| Correct | 33 | 30 |
| Partially correct | 2 | 5 |
| Incorrect | 5 | 5 |
| Correct rate | 82.5% | 75.0% |
| Retrieval hit rate | 61.8% | 61.8% |
| Mean first-hit rank | 2.00 | 1.81 |
| Citation accuracy | 44.1% | 29.4% |

## Results by question type

| Type | H C/P/I | S C/P/I | H correct | S correct | H retrieval | S retrieval | H citations | S citations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| factual | 11/0/2 | 10/1/2 | 84.6% | 76.9% | 69.2% | 69.2% | 38.5% | 15.4% |
| multi-part | 8/1/2 | 6/3/2 | 72.7% | 54.5% | 54.5% | 54.5% | 36.4% | 36.4% |
| not-in-documents | 6/0/0 | 6/0/0 | 100.0% | 100.0% | n/a | n/a | n/a | n/a |
| numeric | 8/1/1 | 8/1/1 | 80.0% | 80.0% | 60.0% | 60.0% | 60.0% | 40.0% |

## Not-in-documents results

| Strategy | ID | Label | Answer | Judge reason | Latency (s) | Cost (USD) |
|---|---|---|---|---|---:|---:|
| hierarchical | q035 | correct | The sources do not specify which commercial vendor and algorithm Companies House uses for identity verification. They mention that the Economic Crime and Corporate Transparency Act 2023 introduced mandatory identity verification for directors, persons with significant control, and those filing information with Companies House, and that Companies House will roll out ID verification capabilities. However, no details about the specific commercial vendor or algorithm employed are provided in the supplied sources [Source 1], [Source 2], [Source 3], [Source 4], [Source 5]. | The candidate answer correctly states that the supplied sources do not specify the commercial vendor or algorithm used by Companies House for identity verification, aligning with the expected answer that the documents do not cover this information. | 3.88 | $0.001431 |
| hierarchical | q036 | correct | The supplied sources do not provide information on how many convictions the National Fraud Squad secured during calendar year 2026. | The candidate answer correctly states that the supplied sources do not provide the requested information, matching the expected answer for a not-in-documents question. | 2.39 | $0.000942 |
| hierarchical | q037 | correct | The sources do not provide the total fraud loss recorded specifically in Scotland in October 2025. They give broader data on fraud incidents and losses in the UK and Scotland over longer periods, but no specific monthly figure for Scotland in October 2025 is mentioned. | The candidate correctly states that the sources do not provide the specific fraud loss figure for Scotland in October 2025, aligning with the expected answer that the documents do not cover this information. | 2.25 | $0.000935 |
| hierarchical | q038 | correct | The sources provided do not contain information about which blockchain analytics vendor the FCA procured in 2025 or the contract price for such procurement. | The candidate answer correctly states that the sources do not contain information about the vendor or contract price, matching the expected answer that the documents do not cover this. | 2.54 | $0.001051 |
| hierarchical | q039 | correct | The supplied sources do not contain information about the percentage reduction in AML false positives achieved by a named UK bank using AI. | The candidate answer correctly states that the supplied sources do not contain the requested information, matching the expected answer for a not-in-documents question. | 2.78 | $0.001442 |
| hierarchical | q040 | correct | The provided sources do not contain information on the number of sanctions-evasion prosecutions completed in Northern Ireland in 2024-25. | The candidate answer correctly states that the provided sources do not contain the requested information, matching the expected answer for a not-in-documents question. | 2.73 | $0.002022 |
| semantic | q035 | correct | The sources provided do not specify which commercial vendor or algorithm Companies House uses for identity verification. They mention that the Economic Crime and Corporate Transparency Act 2023 introduces mandatory identity verification for directors, persons with significant control, and those filing information with Companies House, and that Companies House will roll out ID verification capabilities. However, no details about the specific commercial vendor or algorithm employed are given in the sources [Source 1], [Source 2], [Source 3], [Source 4], or [Source 5]. | The candidate answer correctly states that the sources do not specify the commercial vendor or algorithm used by Companies House for identity verification, aligning with the expected answer that the documents do not cover this information. | 3.01 | $0.001331 |
| semantic | q036 | correct | The sources provided do not contain information on how many convictions the National Fraud Squad secured during calendar year 2026. | The candidate answer correctly states that the sources do not contain the requested information, matching the expected answer for a not-in-documents question. | 2.82 | $0.001294 |
| semantic | q037 | correct | The sources do not provide the total fraud loss recorded specifically in Scotland in October 2025. While there is data on the number of fraud offences in Scotland (456,000 offences in 2023/24) and overall UK fraud losses (£14.4 billion in 2023-2024), no specific figure for total fraud loss in Scotland for October 2025 is given. Therefore, the answer is not available from the supplied sources. | The candidate correctly states that the sources do not provide the total fraud loss for Scotland in October 2025 and explains the available related data, aligning with the expected answer that the documents do not cover this information. | 2.52 | $0.001400 |
| semantic | q038 | correct | The sources provided do not contain information about which blockchain analytics vendor the FCA procured in 2025 or the contract price for such procurement. | The candidate answer correctly states that the sources do not contain information about the FCA's procurement in 2025, matching the expected answer for a not-in-documents question. | 2.91 | $0.000942 |
| semantic | q039 | correct | The supplied sources do not contain information about the percentage reduction in AML false positives achieved by a named UK bank using AI. | The candidate answer correctly states that the supplied sources do not contain the requested information, matching the expected answer for a not-in-documents question. | 2.49 | $0.000934 |
| semantic | q040 | correct | The sources provided do not contain information on the number of sanctions-evasion prosecutions completed in Northern Ireland in 2024-25. | The candidate answer correctly states that the sources do not contain the requested information, matching the expected answer for a not-in-documents question. | 2.30 | $0.001228 |

## Cost and latency

| Metric | Hierarchical | Semantic |
|---|---:|---:|
| Mean latency / question (s) | 3.44 | 3.47 |
| Total question latency (s) | 137.46 | 138.98 |
| Input tokens | 101160 | 97737 |
| Cached input tokens | 0 | 0 |
| Output tokens | 6417 | 7256 |
| Total tokens | 107577 | 104993 |
| Question cost (USD) | $0.050463 | $0.050436 |
| Indexing cost (USD) | $0.000906 | $0.001868 |
| Total strategy cost (USD) | $0.051368 | $0.052304 |

Total evaluation spend including indexing: **$0.103672**.

## Wrong or partially correct answers

### q003 — hierarchical — incorrect

**Question:** What was the total AML/CTF supervised population in 2023-24?

**Answer:** The total AML/CTF supervised population in 2023-24 can be estimated from the data on applications and rejections. According to the summary, supervisors received 13,058 applications for AML/CTF supervision in 2023-24, with 954 of those rejected. This implies that the supervised population would be the number of accepted applications, which is:

13,058 applications - 954 rejected = 12,104 supervised businesses.

Therefore, the total AML/CTF supervised population in 2023-24 was approximately 12,104 firms [Source 1].

**Expected:** 94,937 businesses.

**Judge reason:** The candidate answer provides a supervised population of approximately 12,104 businesses based on applications and rejections, which is significantly different from the expected answer of 94,937 businesses, indicating a factual error or misunderstanding.

### q008 — hierarchical — incorrect

**Question:** How many requests, referrals, or requirements were reported under Regulations 50, 52, and 66?

**Answer:** The sources provided do not contain specific information on the number of requests, referrals, or requirements reported under Regulations 50, 52, and 66. Therefore, I cannot provide an answer to this question based on the supplied sources.

**Expected:** 768 requests under Regulation 50, 2,580 referrals under Regulation 52, and 844 information requirements under Regulation 66.

**Judge reason:** The candidate answer states that the sources do not contain the information, but the expected answer provides specific numbers for requests, referrals, and requirements under Regulations 50, 52, and 66, indicating that the information is available.

### q013 — hierarchical — partially correct

**Question:** How many additional full-time equivalent posts did the plan promise for money laundering and asset recovery?

**Answer:** The plan promised 475 new full-time equivalent financial crime investigator posts dedicated to tackling money laundering and asset recovery [Source 1].

**Expected:** More than 475 FTE posts.

**Judge reason:** The candidate answer specifies 475 posts exactly, while the expected answer states 'more than 475,' indicating a slight discrepancy in the number of posts promised.

### q017 — hierarchical — incorrect

**Question:** What two 2021-22 outcomes did the plan attribute to Suspicious Activity Reports?

**Answer:** The two 2021-22 outcomes attributed to Suspicious Activity Reports (SARs) by the plan are:

1. SARs intelligence was identified as a critical tool in the ability to identify and disrupt criminal activity and recover criminal assets.
2. The SARs Reform Programme delivered a new SARs Digital Service (SDS) and provided an uplift of staff to Regional Organised Crime Units (ROCUs) and the UK Financial Intelligence Unit (UKFIU), enabling enhanced data exploitation, improved feedback and engagement to the regulated sector, timelier intelligence sharing with law enforcement agencies, improved capacity and capability across government, and more efficient and effective reporting by the regulated sector [Source 1].

**Expected:** They identified just under 16,500 potentially vulnerable people and denied over £300 million to suspected criminals through DAML SARs.

**Judge reason:** The candidate answer describes general benefits and improvements related to SARs but does not mention the specific 2021-22 outcomes of identifying just under 16,500 potentially vulnerable people and denying over £300 million to suspected criminals, which are the key facts in the expected answer.

### q027 — hierarchical — incorrect

**Question:** What kind of cryptoasset did the 2025 NRA say is now most commonly used to launder money, and which example did it give?

**Answer:** The 2025 NRA states that cryptoassets are increasingly associated with money laundering risks. However, the sources provided do not specify what kind of cryptoasset is now most commonly used to launder money, nor do they give a specific example of such a cryptoasset. The information focuses on regulatory changes, law enforcement efforts, and the general threat posed by cryptoassets in money laundering, but does not identify a particular type or example of cryptoasset used for laundering money [Source 1, Source 2].

**Expected:** Stablecoins, such as Tether.

**Judge reason:** The candidate answer incorrectly states that the sources do not specify the type of cryptoasset most commonly used for money laundering, whereas the expected answer clearly identifies stablecoins, such as Tether, as the example given by the 2025 NRA.

### q028 — hierarchical — incorrect

**Question:** What money-laundering risk rating did the 2025 NRA give retail banking?

**Answer:** The 2025 National Risk Assessment (NRA) gave retail banking a "medium" money-laundering risk rating. This is indicated by the use of the MoRiLE methodology which translates overall risk scores into low, medium, or high ratings, and the NRA's identification of banking and financial services as a high-risk sector overall, but retail banking specifically is rated medium risk within that sector [Source 2]. However, the exact rating for retail banking specifically is not explicitly stated in the provided excerpts, so this conclusion is based on the general risk ratings methodology and sector risk context given. 

If you need the precise rating for retail banking from the 2025 NRA, the supplied sources do not explicitly provide that detail.

**Expected:** High.

**Judge reason:** The expected answer states the 2025 NRA gave retail banking a high money-laundering risk rating, but the candidate answer claims it is medium risk, which contradicts the expected answer and lacks explicit support from the sources.

### q033 — hierarchical — partially correct

**Question:** What did the NRA say about fraud's share of crime, the number of incidents and the annual increase in the year ending December 2024, and what share of Action Fraud reports were cyber-enabled in the year ending March 2025?

**Answer:** The NRA stated that fraud accounted for 45% of all crime in the Crime Survey of England and Wales (CSEW) in the year ending September 2025, with over 4 million offences estimated during that period. Around 1 in 14 adults were victims of fraud. The economic and social cost of fraud in England and Wales was significant, reaching at least £14.4 billion in 2023-2024. Despite a slight drop in fraud between September 2019 and September 2023, fraud is believed to have increased during the COVID-19 pandemic and is growing as a proportion of CSEW crime. Specifically, bank and credit account fraud rose 36% between the years ending September 2023 and 2025 [Source 2].

Regarding cyber-enabled crime, the sources do not provide specific information on the share of Action Fraud reports that were cyber-enabled in the year ending March 2025.

Therefore, the NRA highlighted fraud's large share of crime (45%), the number of incidents (over 4 million offences), and the annual increase in bank and credit account fraud (36% rise between 2023 and 2025), but there is no information on the share of cyber-enabled Action Fraud reports for the year ending March 2025 in the provided sources.

**Expected:** Over 43% of crime in England and Wales, about 4.1 million incidents, a 33% increase on the previous year, and 63% of Action Fraud reports cyber-enabled (year ending March 2025).

**Judge reason:** The candidate correctly identifies fraud's large share of crime (45%) and the number of incidents (over 4 million), and notes an increase in bank and credit account fraud (36%), but these figures differ from the expected answer's 43%, 4.1 million incidents, and 33% increase. Additionally, the candidate states there is no information on the share of cyber-enabled Action Fraud reports for the year ending March 2025, whereas the expected answer specifies 63%. Thus, the candidate's answer has minor factual discrepancies and omits the cyber-enabled crime statistic.

### q003 — semantic — partially correct

**Question:** What was the total AML/CTF supervised population in 2023-24?

**Answer:** The total AML/CTF supervised population in 2023-24 can be estimated from the data on direct supervision actions and the percentage of supervised firms subject to these actions. According to the summary, there were 9,013 direct supervision actions conducted across all 25 supervisors in 2023-24, representing 10% of the supervised firms. Using this, the total supervised population can be calculated as:

Total supervised population = Number of direct supervision actions / Percentage of supervised firms subject to action  
= 9,013 / 0.10  
= approximately 90,130 firms.

Therefore, the total AML/CTF supervised population in 2023-24 was approximately 90,130 firms [Source 5].

**Expected:** 94,937 businesses.

**Judge reason:** The candidate answer provides a calculated estimate of approximately 90,130 firms, which is close but not equal to the expected answer of 94,937 businesses, indicating a minor factual discrepancy.

### q008 — semantic — incorrect

**Question:** How many requests, referrals, or requirements were reported under Regulations 50, 52, and 66?

**Answer:** The sources provided do not contain information on the number of requests, referrals, or requirements reported under Regulations 50, 52, and 66.

**Expected:** 768 requests under Regulation 50, 2,580 referrals under Regulation 52, and 844 information requirements under Regulation 66.

**Judge reason:** The expected answer provides specific numbers for requests, referrals, and requirements under the regulations, but the candidate answer incorrectly states that the sources do not contain this information.

### q013 — semantic — incorrect

**Question:** How many additional full-time equivalent posts did the plan promise for money laundering and asset recovery?

**Answer:** The plan promised an increase of 200 additional full-time equivalent posts for money laundering and asset recovery. This is part of the Anti-Money Laundering and Asset Recovery (AMLAR) Programme (2023-2026), which has been established and funded by the economic crime levy to increase law enforcement capacity and capabilities [Source 1].

**Expected:** More than 475 FTE posts.

**Judge reason:** The candidate answer states 200 additional posts, whereas the expected answer specifies more than 475 FTE posts, indicating a significant discrepancy in the number provided.

### q014 — semantic — partially correct

**Question:** What were the three headline outcomes of Economic Crime Plan 2?

**Answer:** The three headline outcomes of Economic Crime Plan 2 are:

1. Limit abuse of UK corporate structures: This includes legislation such as the Economic Crime (Transparency and Enforcement) Act 2022, which allows the government to impose sanctions faster, created a Register of Overseas Entities to crack down on foreign criminals using UK property to launder money, and reformed the Unexplained Wealth Order regime to better support law enforcement investigations [Source 3].

2. Transform the UK's response to money laundering and terrorist financing (ML and TF): The plan sets out a whole system approach to tackling economic crime, supported by additional funding via the economic crime levy, targeting high-risk areas identified in the National Risk Assessment [Source 4].

3. Improve the effectiveness of the AML/CTF regulatory and supervisory regime: This includes actions such as AML/CTF supervisors improving their effectiveness, HM Treasury and OPBAS strengthening oversight of supervisors, and consulting on changes to improve the Money Laundering Regulations and reform the UK's AML/CTF supervisory regime [Source 5].

**Expected:** Reduce money laundering and recover more criminal assets; combat kleptocracy and sanctions evasion; and cut fraud.

**Judge reason:** The candidate answer correctly identifies key areas related to Economic Crime Plan 2, such as limiting abuse of corporate structures, transforming the response to money laundering and terrorist financing, and improving AML/CTF regulatory effectiveness, but it does not explicitly mention combating kleptocracy and sanctions evasion or cutting fraud as headline outcomes, which are part of the expected answer.

### q017 — semantic — incorrect

**Question:** What two 2021-22 outcomes did the plan attribute to Suspicious Activity Reports?

**Answer:** The plan attributed two 2021-22 outcomes to Suspicious Activity Reports (SARs):

1. SARs intelligence was identified as a critical tool in the ability to identify and disrupt criminal activity and recover criminal assets. The SARs Reform Programme delivered a new SARs Digital Service (SDS) and increased staff to Regional Organised Crime Units (ROCUs) and the UK Financial Intelligence Unit (UKFIU). This enabled enhanced data exploitation, improved feedback and engagement with the regulated sector, timelier intelligence sharing with law enforcement agencies, improved capacity and capability across government, and more efficient and effective reporting by the regulated sector [Source 1].

2. The 2020-22 AML/CFT supervision report showed improvements in enforcement measures against non-compliant firms, including a significant increase in sanctions and fines in 2021-22 compared to 2020-21. This reflects the impact of supervisory interventions, which rely on intelligence including SARs, to strengthen the UK's AML regime [Source 2].

Thus, the two outcomes attributed to SARs in 2021-22 are:  
- Enhanced intelligence capabilities leading to better identification and disruption of criminal activity and asset recovery.  
- Improved enforcement outcomes against non-compliant firms, demonstrated by increased sanctions and fines.

**Expected:** They identified just under 16,500 potentially vulnerable people and denied over £300 million to suspected criminals through DAML SARs.

**Judge reason:** The candidate answer does not mention the specific outcomes of identifying just under 16,500 potentially vulnerable people and denying over £300 million to suspected criminals through DAML SARs, which are the key facts in the expected answer.

### q027 — semantic — incorrect

**Question:** What kind of cryptoasset did the 2025 NRA say is now most commonly used to launder money, and which example did it give?

**Answer:** The 2025 National Risk Assessment (NRA) states that the kind of cryptoasset now most commonly used to launder money is not explicitly detailed in the provided sources. However, it mentions that since 2023, the scope of the wire transfer information-sharing regime was extended to cryptoassets, and law enforcement has enhanced capabilities to investigate the criminal use of cryptoassets, including blockchain analytics tools and a crypto-specific public-private partnership within the Joint Money Laundering Intelligence Taskforce (JMLIT) [Source 1].

No specific example of a cryptoasset used for money laundering is given in the supplied sources. Therefore, the exact type of cryptoasset and an example cited by the 2025 NRA are not available in the provided information.

**Expected:** Stablecoins, such as Tether.

**Judge reason:** The candidate answer incorrectly states that the 2025 NRA does not specify the type of cryptoasset used for money laundering, while the expected answer clearly identifies stablecoins, such as Tether, as the most commonly used.

### q028 — semantic — partially correct

**Question:** What money-laundering risk rating did the 2025 NRA give retail banking?

**Answer:** The 2025 National Risk Assessment (NRA) gave retail banking a rating indicating it remains particularly vulnerable to financial crime and poses one of the greatest risks of being exploited for money laundering. Specifically, retail banking was identified alongside e-money, wholesale banking, wealth management, and cryptoasset firms as sectors with the greatest money laundering risk in the 2023-24 reporting period, which informs the 2025 NRA assessment. However, the exact risk rating (low, medium, or high) assigned to retail banking in the 2025 NRA is not explicitly stated in the provided sources.

The FCA's risk assessment data for 2023-24 shows that approximately 3,000 firms were categorized as high risk, with retail banking among the sectors considered particularly vulnerable to financial crime and money laundering exploitation [Source 1]. The methodology used for risk ratings in the NRA follows the MoRiLE model, which translates risk scores into low, medium, or high ratings based on vulnerabilities, scale, and mitigations [Source 2]. The 2025 NRA is currently being prepared and will be published in 2025, building on previous assessments including the 2020 NRA [Source 4].

In summary, retail banking is considered a high-risk sector for money laundering in the context of the 2025 NRA, but the precise risk rating assigned in the 2025 NRA document is not explicitly provided in the supplied sources.

**Expected:** High.

**Judge reason:** The candidate correctly identifies retail banking as a high-risk sector for money laundering and explains the context, but notes that the exact 2025 NRA rating is not explicitly stated in the sources, which is a minor omission compared to the expected answer stating simply 'High.'

### q029 — semantic — incorrect

**Question:** How did the money-laundering risk rating for art market participants change since the previous NRA?

**Answer:** The sources provided do not contain specific information on how the money-laundering risk rating for art market participants has changed since the previous National Risk Assessment (NRA). While the methodology for risk scoring and the general approach to NRAs are described, there is no direct mention or comparison of the risk rating for art market participants between the current and previous NRAs.

Therefore, based on the supplied sources, the answer to how the money-laundering risk rating for art market participants has changed since the previous NRA is not available.

**Expected:** It decreased from high to medium.

**Judge reason:** The expected answer states that the risk rating decreased from high to medium, but the candidate answer claims the sources do not contain this information, which contradicts the expected answer's factual content.

### q033 — semantic — partially correct

**Question:** What did the NRA say about fraud's share of crime, the number of incidents and the annual increase in the year ending December 2024, and what share of Action Fraud reports were cyber-enabled in the year ending March 2025?

**Answer:** The NRA stated the following regarding fraud and cyber-enabled crime:

- Fraud accounted for 45% of all crime in the Crime Survey of England and Wales (CSEW) for the year ending September 2025, with over 4 million offences estimated in that period. This represents a significant share of crime overall [Source 2].

- Around 1 in 14 adults were victims of fraud in the year ending September 2025 [Source 2].

- Bank and credit account fraud rose by 36% between the years ending September 2023 and 2025, indicating an annual increase in fraud incidents [Source 2].

- The Economic Crime Survey 2024 found that 1 in 4 UK businesses with more than one employee experienced fraud in the previous twelve months, amounting to approximately 389,000 businesses and an estimated 6.04 million instances of fraud [Source 2].

- Regarding cyber-enabled crime, in the year ending March 2025, 62% of Action Fraud reports were cyber-enabled [Source 1, Figure 2].

Thus, the NRA highlights that fraud constitutes nearly half of all crime, with millions of incidents annually and a notable increase in certain types such as bank and credit account fraud. Additionally, a majority of Action Fraud reports are cyber-enabled, reflecting the significant role of technology in fraud crimes.

References:
- Fraud's share of crime and number of incidents: 45% of all crime, over 4 million offences, 1 in 14 adults victims, 6.04 million instances in businesses [Source 2].
- Annual increase: Bank and credit account fraud rose 36% between years ending September 2023 and 2025 [Source 2].
- Share of Action Fraud reports cyber-enabled: 62% in year ending March 2025 [Source 1].

**Expected:** Over 43% of crime in England and Wales, about 4.1 million incidents, a 33% increase on the previous year, and 63% of Action Fraud reports cyber-enabled (year ending March 2025).

**Judge reason:** The candidate answer provides detailed statistics close to the expected figures but differs in key numbers: it states fraud accounts for 45% (vs. 43%), mentions over 4 million incidents (vs. about 4.1 million), cites a 36% increase in bank and credit account fraud (vs. a 33% overall increase), and 62% cyber-enabled reports (vs. 63%). These discrepancies and additional details mean the answer is mostly accurate but not fully aligned with the expected answer.

### q034 — semantic — partially correct

**Question:** How could AI both help money launderers and improve AML controls?

**Answer:** AI can both help money launderers and improve Anti-Money Laundering (AML) controls in the following ways:

1. Helping Money Launderers:
- Criminals exploit available technology, including AI, to communicate, commit crimes, and hide their profits, making money laundering more complex and harder to detect [Source 2, 2.3].
- The scale and complexity of money laundering threats are growing as criminals use advanced technology, which could include AI, to facilitate illicit activities [Source 2, 2.3].

2. Improving AML Controls:
- AI and data-led approaches enhance the effectiveness of AML supervision by enabling more proactive and risk-based customer due diligence and supervision [Source 4, 2.13, 2.15].
- Law enforcement uses specialist tooling such as blockchain analytics tools, which may incorporate AI, to investigate the criminal use of cryptoassets and improve capacity and capability in detecting illicit finance [Source 5, 2.19].
- Public-private partnerships like the Joint Money Laundering Intelligence Taskforce (JMLIT) use data sharing and advanced analytics, potentially AI-driven, to better understand and combat money laundering threats [Source 5, 2.19].

In summary, while AI and related technologies can be exploited by criminals to enhance money laundering methods, they also provide powerful tools for regulators and law enforcement to strengthen AML controls through improved detection, supervision, and investigation capabilities [Sources 2, 4, 5].

**Expected:** AI can be misused for synthetic bank account creation, fraud and impersonation, phishing and onboarding money mules, but AI-enhanced analytics could reduce false positives, better identify suspicious behaviour and map networks of connected individuals.

**Judge reason:** The candidate answer correctly explains that AI can be exploited by criminals and can improve AML controls through enhanced detection and supervision, but it lacks specific mention of synthetic bank account creation, fraud and impersonation, phishing, onboarding money mules, and mapping networks of connected individuals as detailed in the expected answer.
