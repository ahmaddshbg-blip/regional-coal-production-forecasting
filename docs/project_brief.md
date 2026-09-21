# Project Brief

Status: Approved; Gate 2 evaluation contract frozen

Last reviewed: 2026-09-21

## Context

Coal production is reported quarterly for mines operating under U.S. Mine
Safety and Health Administration jurisdiction. Production levels differ across
states and change through mine entry, closure, temporary idling, market
conditions, and operational constraints.

A regional planning team at a mining contractor, equipment supplier, or
industrial services provider must decide where future production activity may
justify closer capacity review. Public data cannot support site dispatch or
company-specific commitments, but it can support a reproducible forecasting
demonstration at regional level.

## Problem

The latest observed production is not a sufficient planning estimate. The team
needs forecasts that distinguish normal quarter-to-quarter movement from
larger changes and that quantify how forecast error grows across planning
horizons.

## Objective

Forecast total coal production for each U.S. state for the next one to four
calendar quarters using only information that would have been available at
each historical forecast origin.

The forecast is intended to support regional contractor-capacity planning,
market prioritization, workforce review, and heavy-equipment service readiness.
It does not directly estimate required headcount, fleet size, or maintenance
inventory; those would require additional operational data and separate target
definitions.

## Decision owner

A regional capacity-planning or market-planning analyst working for a mining
contractor, equipment supplier, or industrial services provider.

## Supported decision

Prioritize regional contractor-capacity review, market attention, workforce
planning, and heavy-equipment service readiness for the coming one to four
quarters. The forecast informs review priority; it does not autonomously
allocate equipment or labor.

## Forecast target and unit of analysis

- Target: quarterly coal production reported by mine operators, aggregated to
  state-quarter totals.
- Unit: U.S. state by calendar quarter.
- Units: reported tons.
- Frequency: quarterly.
- Horizon: one through four quarters ahead.
- Forecast origin: each quarterly data release after the reporting period has
  closed.

## Consequences of error

- Underprediction can lead to insufficient service, workforce, or equipment
  readiness in a region.
- Overprediction can lead to idle capacity or misplaced planning attention.
- No defensible monetary cost ratio is currently available. Evaluation must
  therefore report both absolute and signed errors rather than inventing an
  asymmetric loss function.

## Success criteria

The project will be considered analytically useful only if it:

1. beats meaningful naive and seasonal-naive baselines under rolling-origin
   evaluation for decision-relevant horizons;
2. reports performance by horizon and region instead of only one pooled score;
3. quantifies uncertainty and identifies material failure modes;
4. produces an interpretable regional planning output; and
5. remains reproducible from documented raw inputs.

Numeric acceptance thresholds were frozen at Gate 2 after measuring baseline
variability on development origins only. They are recorded in
[`forecasting_contract.md`](forecasting_contract.md) and cannot be changed
after seeing final holdout results.

## Scope

Included:

- operator-reported coal production;
- state-quarter aggregation;
- a grouped panel with a natural national total;
- one-to-four-quarter forecasts;
- chronological validation, baseline comparison, uncertainty, and error
  analysis.

Excluded:

- metal and nonmetal production;
- mine-level production as the primary published forecast target;
- causal inference;
- mine scheduling or equipment dispatch;
- company-specific operating recommendations;
- financial return or cost-savings claims;
- spatial models or maps as the central analytical contribution;
- advanced model classes without baseline evidence.

## Portfolio contribution

This project owns forecasting, multi-horizon temporal evaluation, uncertainty,
and forecast error analysis. Unlike Project 01, it must predict observations
that were genuinely unavailable at each forecast origin; a dashboard alone is
not the final contribution.
