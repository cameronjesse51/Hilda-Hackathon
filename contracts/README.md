# College recommendation contract

`college-recommendations.v2.schema.json` is the current canonical boundary between the
college-search backend and the web client. The backend will emit its payload as
the data of an SSE event named `college_results`.

Version 2 separates sourced institution facts from student-specific calculations
using explicit `facts` and `personalized` objects. Version 1 remains available for
historical persisted recommendation sets.

Contract rules:

- Rates are decimal values from `0` to `1`, not percentages.
- Monetary values are USD; net price and student budget are annual, while debt and earnings use their labeled reporting horizons.
- `budget_difference` is `student_budget - net_price`; positive is under budget.
- `fit.score` measures Halda fit and must never be presented as an admission probability.
- Source years preserve the raw reporting label supplied by the source; they are never inferred from `retrieved_at`.
- Unknown factual data is `null`; unknown program availability is `"unknown"`.
- Every factual card includes at least one source with retrieval time and the fields it supports.
- Reach/target/likely is an estimate and always includes both its reason and its calculation basis.

Breaking changes require a new schema file and `schema_version`. Additive changes
should still be deliberate because the schema rejects unknown properties.
