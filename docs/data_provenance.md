# Data Provenance

## Source owner and collection

The source owner is the U.S. Department of Labor, Mine Safety and Health
Administration (MSHA). Mine operators submit the Quarterly Mine Employment and
Coal Production Report, Form 7000-2, under 30 CFR Part 50. The form states that
reports are due within 15 days after the end of each calendar quarter.

Official references:

- MSHA Open Government Data portal:
  https://arlweb.msha.gov/OpenGovernmentData/OGIMSHA.asp
- Quarterly source definition:
  https://arlweb.msha.gov/OpenGovernmentData/DataSets/MineSProdQuarterly_Definition_File.txt
- Mine master definition:
  https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines_Definition_File.txt
- Form 7000-2:
  https://www.msha.gov/sites/default/files/Support_Resources/Forms/7000-2.pdf
- Data.gov quarterly dataset record:
  https://catalog.data.gov/dataset/msha-operator-employment-and-production-data-set-quarterly

## Observation semantics

Each raw quarterly row represents operator-reported employment, hours, and
coal production for a mine subunit and calendar quarter. The quarter is a
period label, not the publication timestamp. `MINE_ID` links quarterly records
to the mine master.

The mine master is a current-state table. Current mine status, controller,
operator, and related fields are not historical snapshots and must not be used
as if they were known at past forecast origins.

## Availability and reporting lag

Form 7000-2 is due 15 days after quarter end. Public availability occurs later
and may change as MSHA processes submissions. The forecasting origin must
therefore represent the date a quarterly snapshot is available, not merely the
last day of the target quarter.

The project snapshot was acquired on 2026-09-20, 82 days after `2026Q2` ended
and 67 days after the form due date. Completeness evidence is documented in
[`data_quality_policy.md`](data_quality_policy.md).

## Updates and revisions

MSHA states that Open Government Data files are normally updated weekly and
that updates are complete replacements. The portal does not provide the
historical file vintages needed to reconstruct exactly what was visible at
every past forecast origin.

Consequences:

- the project uses a frozen, hashed snapshot;
- backtesting must be described as latest-vintage chronological evaluation,
  not true vintage or pseudo-real-time evaluation;
- a future download is a new snapshot, not an in-place overwrite;
- row-level and aggregate changes must be compared before accepting an update;
  and
- published metrics remain tied to the documented snapshot and code revision.

## Representativeness

The data cover U.S. mines under MSHA jurisdiction. They do not directly
represent another country's geology, regulation, mine planning, contractor
structure, equipment fleet, or market conditions. The defensible external
claim is transferability of the forecasting workflow, not equivalence of
operating environments.
