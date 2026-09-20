# Data Quality Policy

Status: Approved for Gate 1

Snapshot: 2026-09-20

## Purpose

This policy distinguishes real zero production, null production, structurally
nonproducing facilities, and possible incomplete reporting before the
state-quarter target is built.

## Audit evidence

The coal-only source produces 183,301 mine-quarter observations:

| Mine-quarter classification | Count |
| --- | ---: |
| Positive production | 90,207 |
| Reported zero production | 87,076 |
| All production fields null | 6,018 |
| At least one null and one non-null subunit | 10,557 |

Partial-null observations overlap the positive and zero classifications because
a mine may report several subunits and production does not apply equally to
every subunit.

Of the 6,018 all-null mine-quarters, 5,997 occur during 2000-2002. Only 21
occur after 2002, across seven records currently classified as facilities such
as loadouts, shops, preparation plants, and refuse areas. The final affected
quarter is 2012Q1. This pattern differs materially from the broad early-period
missingness.

## Approved missing and zero rules

1. Preserve reported zero as zero. Do not convert it to null.
2. Preserve raw null as null. Do not impute it to zero in the raw or
   mine-quarter layer.
3. Aggregate subunits with null-preserving `SUM` semantics. If all subunit
   production values are null, mine-quarter production remains null.
4. Retain counts for total subunit rows, non-null production rows, null
   production rows, positive mines, zero mines, and all-null mines.
5. At state-quarter level, sum available reported mine production and carry
   coverage flags. Never present an aggregate as fully observed without its
   reporting indicators.
6. If every mine-quarter contributing to a state-quarter is null, the target is
   null rather than zero.
7. Do not apply interpolation, forward filling, backward filling, or global
   mean imputation to the target.

## Modeling-window recommendation

The complete raw history remains preserved. Gate 2 should evaluate `2003Q1` as
the primary modeling start because the widespread null regime ends after
2002Q4. The 21 later all-null facility observations remain flagged and do not
justify discarding all 2003-2012 history.

A sensitivity evaluation beginning `2013Q1`, after the final all-null
mine-quarter, should test whether the longer window materially changes
conclusions. The final start date must be frozen before candidate-model
evaluation.

## 2026Q2 completeness assessment

`2026Q2` is accepted as the latest available snapshot quarter, with a revision
caveat:

- 946 mine reporters across 23 states;
- 125,349,730 reported tons;
- no all-null or partial-null mine-quarter production records;
- 940 reporters overlap with `2026Q1`;
- production is 4.9 percent below `2026Q1` but remains inside the observed
  `Q2` range for 2021-2025;
- the reporter count is 2.5 percent below `2026Q1`, consistent with the recent
  downward reporter trend; and
- Arkansas is the only state seen during the preceding five quarters but absent
  in `2026Q2`; its reported production had been zero in every quarter from
  `2022Q2` through `2026Q1`.

These checks find no material sign of a truncated download. They do not prove
that MSHA will never revise the quarter. Gate 2 must decide whether `2026Q2`
belongs in the final untouched holdout or is reserved as the latest forecast
origin.

## Validation requirements

The future pipeline must fail or warn on:

- unexpected schema changes;
- invalid year or quarter values;
- duplicate mine-quarter-subunit keys;
- negative production;
- missing state or mine identifiers;
- a latest-quarter reporter or state count outside a documented tolerance;
- snapshot checksum mismatch; and
- target aggregation that loses the null and coverage indicators above.
