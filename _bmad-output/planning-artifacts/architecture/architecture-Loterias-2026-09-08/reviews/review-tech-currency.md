# Tech-Currency Review — ARCHITECTURE-SPINE.md (Loterias, 2026-09-08)

Scope: verify every committed technical/version claim in the spine was actually checked against reality (repo file or web), not asserted from training data. No other aspect of the spine (decisions, structure, etc.) was reviewed.

Reviewed: `_bmad-output/planning-artifacts/architecture/architecture-Loterias-2026-09-08/ARCHITECTURE-SPINE.md`, Stack table (lines 100-111) and AD-2 (line 52).

## 1. Existing pins (Django, django-allauth, gunicorn, requests) — CONFIRMED

Read `requirements.txt` directly:

```
Django==5.0.6
django-allauth==0.63.3
requests==2.32.3
gunicorn==22.0.0
```

The spine's Stack table lists exactly these four values for exactly these four packages — it ratifies existing pins, it does not invent or drift from any of them. No issue.

## 2. django-crontab 0.7.1 (new dependency) — PARTIALLY WRONG, UNDERSTATES RISK

Checked PyPI's JSON API (`https://pypi.org/pypi/django-crontab/json`) directly.

- **Latest version claim: CONFIRMED.** 0.7.1 is in fact the newest release on PyPI. This part is accurate.
- **"No release in 12+ months" claim: TECHNICALLY TRUE BUT MATERIALLY MISLEADING (Medium severity).** Full release history from PyPI:

  | Version | Uploaded |
  |---|---|
  | 0.6.0 | 2014-12-07 |
  | 0.7.0 | 2015-12-02 |
  | 0.7.1 | 2016-03-07 |

  0.7.1 was released **2016-03-07** — about **10 years ago**, not "12+ months" ago. Framing a decade of abandonment as "no release in 12+ months" is a defensible-but-weak way to phrase a much bigger fact; a reader skimming the Stack table would reasonably assume "a year or two stale," not "last touched during the Obama administration, before Django 1.10 existed." This looks like the number was asserted/rounded rather than looked up — the actual PyPI data was available and shows something far more severe. Recommend the spine state the actual last-release date (2016) instead of the vaguer "12+ months," so the real level of maintenance risk is visible to whoever reads the Stack table later.

- **Django 5.x compatibility / "no known Django 5 breaking issue" claim: NOT DISPROVEN, BUT UNVERIFIABLE AS STATED (Low-Medium severity).** Checked the project's GitHub issues (`kraiz/django-crontab/issues`) via web search — no open issue explicitly reports breakage under Django 4 or 5. However, the package's own documented compatibility statement (per PyPI/README) tops out at "django (1.8+)" with no upper bound and no CI evidence of testing against Django 5 (last commit predates Django 5 by years — Django 5.0 shipped December 2023). "No known Django 5 breaking issue" is technically accurate (nothing found) but reads as more reassuring than "nobody has ever tested this combination and the maintainer stopped responding in 2016." The spine's own fallback plan (drop the package, write crontab lines directly) suggests the author already suspected this, which is good — but the Stack table prose doesn't convey how thin the "no known issue" evidence actually is.

## 3. SQLite ALTER TABLE RENAME COLUMN / RENAME TO on version ≥3.25 — CONFIRMED (with one imprecision)

Checked `sqlite.org/releaselog/3_25_0.html` directly.

- `ALTER TABLE ... RENAME COLUMN ... TO ...` was added in SQLite **3.25.0, released 2018-09-15**. Confirmed accurate — this is exactly what AD-2 and the Stack table claim.
- Minor imprecision (Low severity, not a correctness bug): the spine's phrasing bundles "RENAME COLUMN/RENAME TO" as if both arrived together at 3.25. `ALTER TABLE ... RENAME TO ...` (renaming a *table*) is much older than 3.25 — it predates that release by a wide margin; what 3.25.0 (and the 3.26.0 follow-up) actually changed for table-rename was fixing it to correctly update references inside triggers and views, not introducing the syntax. The spine's underlying claim ("≥3.25 supports both natively, no table rebuild") is still true, so this doesn't invalidate AD-2's safety argument — it's just loosely worded in a way that overstates how new `RENAME TO` is.

## 4. Python 3.11 bundled SQLite version "well above 3.25" — CONFIRMED

Web-checked Python 3.11.x release changelogs. Python 3.11's bundled/Windows-installer SQLite versions range from **3.39.4** (early 3.11.x) up to **3.45.1** (3.11.9, released 2024-04-02) across the 3.11 patch series. Both bounds are comfortably above 3.25.0 (2018), so the spine's "well above 3.25" claim for Python 3.11's bundled sqlite3 is accurate. (Exact patch-level version depends on which 3.11.x is actually installed/pinned in the project's venv, which wasn't verified locally — no `python3.11` interpreter was found in this environment to check `sqlite3.sqlite_version` directly — but every 3.11.x data point found is well clear of the 3.25 threshold, so the claim holds regardless of exact patch version.)

## 5. Other named technologies in the Stack section

- **Python 3.11 pin rationale** ("Django 5.0.6 não suporta 3.13+"): not independently re-verified in this pass (out of the four explicitly assigned items plus the crontab/SQLite claims) — flagging as unchecked rather than confirmed. Low priority to chase since it's a widely-documented, easily-falsifiable claim about Django's own support matrix, but it wasn't in this review's explicit checklist and no search was run against it.
- **celery / redis removal**: stack table just says to remove them per PRD §5 non-objective — no version/currency claim being made here, nothing to verify.
- No other version numbers appear in the Stack table or surrounding prose beyond the six covered above.

## Summary of severities

| # | Claim | Verdict | Severity |
|---|---|---|---|
| 1 | Django/allauth/gunicorn/requests pins match requirements.txt | Confirmed | — |
| 2a | django-crontab 0.7.1 is latest on PyPI | Confirmed | — |
| 2b | "No release in 12+ months" | True but understates a ~10-year-stale package | Medium |
| 2c | "No known Django 5 breaking issue" | Accurate as stated but evidence is thin (no Django 4/5 CI ever run) | Low-Medium |
| 3 | SQLite ≥3.25 supports RENAME COLUMN/RENAME TO natively | Confirmed (RENAME TO predates 3.25; wording conflates the two) | Low |
| 4 | Python 3.11 bundled SQLite "well above 3.25" | Confirmed (3.39.4–3.45.1 across 3.11.x) | — |
| 5 | Python 3.11 pin rationale (Django 5.0.6 vs 3.13+) | Not checked in this pass | Unverified (out of scope of explicit checklist) |
