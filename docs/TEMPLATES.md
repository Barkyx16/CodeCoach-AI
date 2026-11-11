# Kit templates (Volume 11, prompt 7)

Reuse an interview kit's checklist and questions for another interview, without carrying over
anything from the first one: not what you ticked, the meeting link, location, interviewers, notes,
chosen examples, the outcome, or which interview it was.

## Supported format

Interview-day kits only (the checklist and "Questions to ask them"). Notes, stories and other
records aren't templated. There is no marketplace or sharing: templates are private to you, like
the kits.

## What a template keeps

| Kept | Never kept |
|---|---|
| A name you choose | Whether an item was ticked (done) |
| The checklist items you choose (their words) | Hidden checklist items and questions you've switched off (they aren't offered) |
| The questions you choose (their words and group) | The meeting link, location, format, interviewers |
| | Private notes, chosen examples, the date, the employer, the interview's title, any outcome |

The page shows what the template will hold before you save it ("What the template will hold"),
with every item ticked to keep by default and the line: *A template is a copy of these words, not
a link.* The server keeps only the text it's sent (any other field, such as `done`, is ignored),
with control characters removed and blank or repeated items dropped.

## Snapshot, not alias

- Changing or deleting the kit a template came from changes nothing in the template.
- Applying a template copies its items into the kit's form as the kit's own: new ids, "Yours", not
  ticked, not hidden. Words already in the kit (ignoring case) aren't added twice. Nothing is
  saved until you press **Save kit**, which saves like any other change (revision-checked, keyed).
- Changing, renaming or deleting a template changes no kit already made from it. A kit made from a
  deleted template opens as before; picking a template deleted in another tab says so.

## Plain text

There are no placeholders. `{{employer}}`, `${…}`, `<script>` or a URL in a template are kept and
shown as those characters: nothing in a template is evaluated, fetched, run or filled in. Nothing
is generated for you either: a template holds only words you wrote or kept.

## API

| | |
|---|---|
| `GET /api/v1/me/kit-templates` | Yours, newest first: name, counts, revision |
| `POST /api/v1/me/kit-templates` | `{name, checklist: [{text}], questions: [{text, group}], client_request_id}`: at least one item, up to 40 of each, up to 30 templates. The same create sent again with the same key (its reply was lost) returns the template it made; the same key with other content is 409 `idempotency_key_reused` |
| `GET /api/v1/me/kit-templates/{id}` | One template |
| `PATCH /api/v1/me/kit-templates/{id}` | Rename or replace the items against `expected_revision`; a stale one is 409 `stale_revision` with the saved template; a save sent again after a lost reply (same key) is answered `save_replay` |
| `DELETE /api/v1/me/kit-templates/{id}` | Gone; kits made from it keep their items |

Another account's template is 404 for every call. Stored in `kit_templates` (migration
`c3f7a9d2e614`), under row-level security on PostgreSQL, deleted with the account, included in your
data export (names, items, revision, dates), counted under "Interview-day kits, your kit templates,
and reflections" in Your data. Restoring a backup doesn't restore templates yet (it says so).

## On the page

- **Kit → Templates** (beside "Print or save as PDF"): *Start from one of your templates* (a
  choice, a preview, **Add to this kit**, and what was added) and **Save as a template…** (name,
  what to keep, the preview, the never-kept list, **Save template**; after a lost reply, **Save
  again**, which makes one). Optional: a kit works the same without them, and the built-in
  suggestions stay labelled "Suggested".
- **/kit-templates** ("Kit templates" in the Go to… palette): preview, rename (revision-checked:
  changed elsewhere, it says so and shows the saved name) and delete (asks first; focus moves to the
  next template, or the heading).

## Tests

`tests/test_kit_templates.py` (only the text kept and the source kit untouched; a lost create sent
again; plain text kept as typed; blank, repeated and empty; revision-checked edits and a recovered
one; kits made from a template independent of it through edits and delete; owner only; the limit,
the export and Your data), with the RLS, migration, data-summary and route-walk tests, on SQLite and
PostgreSQL as the app role. `src/test/integration/kitTemplates.test.tsx` (choosing and previewing,
what's sent, a lost reply; applying unticked and unsaved, no repeats, template text as text; a
deleted template; the list page's preview, rename, stale rename and delete with focus).
`e2e/kit-templates.spec.ts` (real API: one interview's kit to the next, the first kit's ticks, link
and notes unchanged, rename and delete, axe in both themes).

## Limits

- Kits only, and only their checklist and questions.
- No archive for templates (delete only); no editing a template's items on the list page (save a
  new one from a kit instead).
- Not restored from a backup file yet.
