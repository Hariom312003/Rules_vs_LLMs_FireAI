| Problem | Detector | Detection | Batch hit | FA rows (clean) | FA batches (clean) | $ / M rows | Rows/s | Clarity |
|---|---|---|---|---|---|---|---|---|
| a Renamed or dropped column | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 25,444,214 | 1.00 |
| b Column type change | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 4,981,630 | 1.00 |
| c Date format switch partway through batch | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 400,760 | 1.00 |
| d Latitude/longitude swapped | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 974,936 | 1.00 |
| e Exact duplicates | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 524,122 | 0.50 |
| f Near-duplicates | rules | 1.00 | 1.00 | 0.0005 | 1.00 | 0.0001 | 179,442 | 1.00 |
| g Null spike in one agency's records | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0001 | 174,119 | 0.50 |
| h Closed date earlier than created date | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 600,580 | 1.00 |
| i ZIP inconsistent with borough | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 575,324 | 1.00 |
| j Complaint Type inconsistent with Descriptor | rules | 1.00 | 1.00 | 0.0045 | 1.00 | 0.0000 | 411,441 | 1.00 |
| k Resolution Description contradicting Status | rules | 1.00 | 1.00 | 0.0245 | 1.00 | 0.0001 | 129,573 | 1.00 |
| l Personal data in free-text fields | rules | 1.00 | 1.00 | 0.0045 | 1.00 | 0.0002 | 67,940 | 1.00 |
| a Renamed or dropped column | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 18,493,575 | 1.00 |
| b Column type change | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 576,544 | 1.00 |
| c Date format switch partway through batch | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0001 | 166,441 | 0.75 |
| d Latitude/longitude swapped | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 304,231 | 0.75 |
| e Exact duplicates | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 511,422 | 0.25 |
| f Near-duplicates | stats | 0.87 | 1.00 | 0.0010 | 1.00 | 0.0005 | 21,617 | 0.75 |
| g Null spike in one agency's records | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0003 | 42,450 | 0.50 |
| h Closed date earlier than created date | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 569,392 | 0.75 |
| i ZIP inconsistent with borough | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 406,485 | 0.75 |
| j Complaint Type inconsistent with Descriptor | stats | 0.99 | 1.00 | 0.0018 | 1.00 | 0.0000 | 377,355 | 0.75 |
| k Resolution Description contradicting Status | stats | 0.02 | 1.00 | 0.0007 | 0.67 | 0.0002 | 58,158 | 0.75 |
| l Personal data in free-text fields | stats | 0.00 | 0.00 | 0.0000 | 0.00 | 0.0001 | 77,869 | n/a |
| a Renamed or dropped column | llm | 0.50 | 0.50 | 0.0000 | 0.00 | 0.0000 | 3 | 0.75 |
| b Column type change | llm | 0.50 | 0.50 | 0.0000 | 0.00 | 0.0000 | 2 | 0.75 |
| c Date format switch partway through batch | llm | 0.00 | 1.00 | 0.0000 | 1.00 | 0.0000 | 2 | 0.75 |
| d Latitude/longitude swapped | llm | 0.70 | 1.00 | 0.0000 | 0.00 | 0.0000 | 4 | 0.75 |
| e Exact duplicates | llm | 0.06 | 0.50 | 0.0000 | 0.00 | 0.0000 | 2 | 0.75 |
| f Near-duplicates | llm | 0.00 | 0.00 | 0.0000 | 0.00 | 0.0000 | 3 | n/a |
| g Null spike in one agency's records | llm | 0.33 | 1.00 | 0.0200 | 0.50 | 0.0000 | 3 | 0.75 |
| h Closed date earlier than created date | llm | 0.65 | 1.00 | 0.0100 | 1.00 | 0.0000 | 3 | 0.75 |
| i ZIP inconsistent with borough | llm | 0.10 | 1.00 | 0.0000 | 0.00 | 0.0000 | 3 | 0.75 |
| j Complaint Type inconsistent with Descriptor | llm | 0.10 | 1.00 | 0.0050 | 0.50 | 0.0000 | 2 | 0.75 |
| k Resolution Description contradicting Status | llm | 0.35 | 1.00 | 0.0000 | 0.00 | 0.0000 | 4 | 0.75 |
| l Personal data in free-text fields | llm | 0.30 | 1.00 | 0.0000 | 0.00 | 0.0000 | 6 | 0.75 |