# Compare offers in a private workspace

Volume 10, prompt 9. A private workspace for comparing two or three offers whose terms the learner
enters by hand, next to the factors that matter to them. It organises facts and personal tradeoffs.
It doesn't manufacture certainty about future pay or about the right decision, and it never calls
an offer "best".

## Where it is

`/offers/compare` (signed in): your comparisons, **New comparison**, and **Start with a fictional
example** (two made-up offers with gaps, to try before entering real terms). One comparison is
`/offers/compare/<id>`. Also in the command palette ("Compare offers") and Help.

## What you enter (`backend/app/schemas/offer_comparisons.py`)

Per offer, each field optional; **missing is unknown, never zero**:

| Field | Notes |
|---|---|
| name, linked application | the application must be yours; it's only read for its name |
| where the terms came from, terms as of (date) | kept with the terms |
| pay, per (year / month / week / hour), currency | three-letter code |
| monthly payments a year; hours a week; weeks paid a year | the basis for a yearly figure, entered by you |
| guaranteed one-off cash | e.g. a signing bonus; 0 if none, blank if unknown |
| conditional bonus (up to) and its conditions | never counted as guaranteed |
| equity | described in words, never valued |
| benefits | notes |

Your factors (suggested: schedule, commute, learning opportunities, role scope, flexibility,
benefits; or your own) get a rating per offer: 1 to 5, **unknown** or **not comparable**, with a
note. Ratings are yours and subjective; nothing infers anything about an employer. An optional
weight (0 to 5) per factor is used only when **Use my weights** is on.

Currency rates: from, to, the rate and the date it applies to, entered by you. No market rate is
looked up.

## Supported calculations (`backend/app/offercompare/calc.py`)

Every figure shows its formula in words and units, and its assumptions:

- **Yearly pay:** per year as entered; per month × the monthly payments a year you entered; per
  week × the weeks paid a year you entered; per hour × hours a week × weeks paid a year. With the
  basis missing, the figure is unknown and says what to enter (for example "Enter the weeks paid a
  year to put hourly pay on a yearly basis.").
- **Guaranteed first-year cash:** yearly pay + guaranteed one-off cash, only when both are known.
- **Another currency:** only with a rate you entered for exactly that pair (or used the other way),
  showing the rate and its date. Offers in different currencies are otherwise shown in their own.
- **Weighted ordering (optional):** each contribution is your weight × your rating, listed; unknown,
  not-comparable and unweighted factors aren't counted and are listed; offers with different numbers
  of rated factors are flagged as not like for like. It's labelled "your weighted ordering… not a
  recommendation or an objectively best offer" and can be switched off. Pay isn't in it unless you
  add a pay factor and rate it yourself.

**Not estimated, ever:** tax or take-home pay, the value of equity or benefits, the chance a
conditional bonus pays out, overtime, future raises or returns, market rates.

## Saving, devices and privacy

- `offer_comparisons` (migration `a5d3e9c1b7f2`; `archived` added by `b8e4c2a7d915`, see ARCHIVE.md): the title, the document and a revision. Figures are
  derived on every read, never stored. Saves are revision-checked: a save from an older version is
  refused with the saved version, shown side by side, and you choose; a save whose reply was lost
  is recognised by its update receipt (`offer_comparison`). The page shows figures for your unsaved
  edits through a preview that stores nothing.
- Unsaved changes stay on this device (`offer-compare-draft:<account>:<id>`, cleared at sign-out)
  and are offered back after a reload; leaving with unsaved changes asks first.
- **Hide amounts on screen** blurs pay figures and inputs, for screens others can see.
- **Copy as text** shows exactly the text first; copying puts it on your clipboard only. Nothing is
  sent, shared or published.
- Owner-only under PostgreSQL row-level security (`rls.ADDED_TABLES`); another account gets 404 and
  can't link your applications. Ids appear in URLs, never amounts. In the data export as
  `offer_comparisons`; deleted with the account; not restored from a backup file (re-enter them).
- Linking an application never changes its stage or history, and choosing an offer here doesn't
  mark anything accepted. A negotiation rehearsal doesn't fill a comparison (that would need a
  preview and your confirmation, not built yet).

## Limits

- Hand-entered terms only: nothing is imported from documents, employers or payroll systems.
- One basis per offer (no shift differentials, overtime rules or variable hours).
- At most three offers, twelve factors and six rates per comparison.
