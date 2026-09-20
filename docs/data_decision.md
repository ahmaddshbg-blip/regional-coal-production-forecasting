# Dataset Decision Record

Status: Approved; Gate 1 passed

Decision date: 2026-09-20

## Decision

Use the MSHA quarterly employment and production dataset as the primary source,
joined to the MSHA mine master by `MINE_ID`.

The source passes the provenance, schema, coverage, granularity, reuse, and
computational-feasibility checks. The raw files remain outside Git because of
their size and replacement-based update behavior, not because the project
depends on private data.

## Source

- Owner: U.S. Department of Labor, Mine Safety and Health Administration
  (MSHA).
- Portal: https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp
- Quarterly data ZIP:
  https://arlweb.msha.gov/OpenGovernmentData/DataSets/MinesProdQuarterly.zip
- Quarterly definition:
  https://arlweb.msha.gov/OpenGovernmentData/DataSets/MineSProdQuarterly_Definition_File.txt
- Mine master ZIP:
  https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines.zip
- Mine master definition:
  https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines_Definition_File.txt
- Local acquisition date: 2026-09-20.
- Published update pattern: MSHA states that portal files are normally updated
  weekly and that updates replace the previous complete files.

## Local snapshot

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `MinesProdQuarterly.txt` | 261,773,843 | `1B3A84245EA17A267BA34B642F0A3513FCEAEAF764D95774ED1D318612817B12` |
| `Mines.txt` | 39,363,960 | `38776A237EB6B99A39A1F64C0CA5B8E42B5C320ACE3FCDDB2E6C6C2F508A22F4` |

Both files are headered, pipe-delimited text extracted from the official ZIP
distributions. The ingestion encoding must be declared explicitly because some
free-text fields contain legacy byte values. The initial audit used `latin-1`
to preserve all bytes; identifier and numeric fields are unaffected.

## Initial audit evidence

- Raw quarterly rows: 2,761,471.
- Coal rows: 344,473.
- Coverage: 2000Q1 through 2026Q2.
- Aggregated mine-quarter rows: 183,301 across 6,321 historical mines.
- Mine IDs matched to the master: 6,321 of 6,321.
- Duplicate `MINE_ID`-quarter-subunit keys: 0.
- Negative coal-production values: 0.
- Mine-quarter values after subunit aggregation: 90,207 positive, 87,076
  zero, and 6,018 null.
- Candidate state panel: 27 states; 26 have at least 80 observed quarters and
  at least 90 percent temporal coverage; 23 report in 2026Q2.
- Mine-level sensitivity set: 348 mines reporting in 2026Q2 have at least 40
  observed quarters, at least 90 percent coverage, and at least 12 positive
  production quarters. This is diagnostic evidence, not the primary target
  definition.

## Data-generating process

Mine operators report quarterly employment, hours, and coal production by mine
subunit. `COAL_PRODUCTION` is reported in tons and may be zero or null. Metal
and nonmetal operators are not required to report production, so the project
must filter to coal records before constructing the target.

The calendar quarter is a period label, not the date on which the observation
became available. Publication occurs after quarter end, and source files may be
replaced as MSHA updates them. Historical revisions are therefore possible and
the local snapshot hash matters.

## Target construction candidate

For each state and calendar quarter:

1. retain records where `COAL_METAL_IND == "C"`;
2. parse `CAL_YR` and `CAL_QTR` as the period;
3. sum `COAL_PRODUCTION` across subunits and mines using null-preserving
   aggregation;
4. distinguish reported zero from null production; and
5. retain mine counts and reporting coverage as quality indicators.

The approved null and zero rules are recorded in
[`data_quality_policy.md`](data_quality_policy.md). The modeling start date
remains a Gate 2 evaluation-design decision.

## Computational scope

The complete 2,761,471-row source snapshot is retained for traceability. It is
not the modeling table:

| Layer | Approximate scale | Purpose |
| --- | ---: | --- |
| Complete quarterly source | 2,761,471 rows | Immutable source and audit scope |
| Coal records after domain filter | 344,473 rows | Relevant transformation input |
| Mine-quarter panel | 183,301 rows | Quality, entry/exit, and coverage diagnostics |
| State-quarter panel | At most 2,862 rows | Forecasting unit of analysis |

No calendar years will be removed merely to satisfy an arbitrary row-count
limit. A shorter modeling window may still be selected because of missingness,
structural relevance, or evaluation design, but that requires analytical
evidence. Column projection, early coal filtering, and checkpoint reuse provide
the required computational reduction without discarding temporal history.

## Known risks and controls

| Risk | Required control |
| --- | --- |
| Most raw production nulls occur in 2000-2002 | Treat early years as an audit segment; justify the modeling start date rather than silently dropping them. |
| Zeros are common and can be legitimate reports | Preserve zeros; never convert them to missing values automatically. |
| The mine master stores current attributes | Do not use current status, owner, or operator as historical features. |
| Mine entry, closure, and temporary idling change the panel | Measure entry and exit at every forecast origin; avoid survivorship filtering based on the latest snapshot. |
| Publication follows period end | Define forecast origins by information availability, not by quarter labels alone. |
| Source files are complete replacements | Preserve acquisition date and hashes; do not silently overwrite the reviewed snapshot. |
| U.S. public data do not represent every mining market | Limit external-validity claims to transferable analytical practice, not direct operating equivalence. |
| Government data and project code have different reuse boundaries | Attribute MSHA/DOL data separately; apply the MIT License only to original project code and documentation. |

## Alternatives held in reserve

Other candidates considered included electric-vehicle adoption, company-level
copper production, palm-oil production, and retail demand. They remain valid
fallbacks, but switching now would add search cost without resolving a failure
in the approved MSHA candidate. The mining dataset currently offers the clearest
combination of source authority, temporal depth, panel structure, and portfolio
distinctiveness.

## Gate result

Gate 1 passed on 2026-09-20. Source reuse terms, latest-quarter completeness,
revision behavior, and missing-value treatment are documented in the focused
provenance, attribution, and data-quality files. Gate 2 must now freeze the
chronological evaluation design before feature engineering or modeling.
