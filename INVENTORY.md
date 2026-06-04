# Question Bank — Feature Inventory

## Architecture

**Stack:** FastAPI + Jinja2 + SQLAlchemy + SQLite  
**Auth:** Session-based (cookie), role enum: `teacher` / `admin`  
**i18n:** Per-session language toggle (UK / EN); all UI strings in `app/i18n.py`  
**Database tables:** `teachers`, `faculties`, `disciplines`, `modules`, `topics`, `topic_learning_outcomes`, `questions`, `question_revisions`, `votes`, `tests`, `test_questions`, `test_results`, `settings`, `org_settings`

---

## 1. Authentication

| Route | Template | Features |
|---|---|---|
| `GET /login` | `login.html` | Login form with email + password |
| `POST /login` | — | Validates credentials, sets session; redirects to `/` |
| `POST /logout` | — | Clears session |
| `GET /set-lang/uk` or `/en` | — | Switches session language, redirects back |
| `GET /profile/password` | `profile_password.html` | Form to change own password |
| `POST /profile/password` | — | Validates old password, saves new hash |

---

## 2. Dashboard — Faculty List (`/`)

**Template:** `dashboard.html`  
**Access:** All authenticated users

- Lists all faculties as cards
- Each card shows discipline count
- Admin: "Add faculty" button, edit/delete per-card actions

---

## 3. Curriculum Structure

### Faculty (`/faculties/{id}`)

**Template:** `faculty.html`

- Lists disciplines belonging to this faculty
- Breadcrumb: Home → Faculty name
- Admin: new/edit/delete discipline; new/edit/delete faculty

### Discipline (`/disciplines/{id}`)

**Template:** `discipline.html`

- Lists modules in the discipline
- Per-module: question pool health table — columns: topic number, topic name, total questions, active questions, pending questions, facility index badge (color-coded p-band, tooltip with n + Wilson CI), discrimination badge
- Admin: new/edit/delete module; toggle high-stakes flag per topic

### Module (`/modules/{id}`)

**Template:** `module.html`

- Full topic list table with pool health stats (same metrics as discipline view)
- Links to generate a new module test and view all tests
- Admin: new/edit/delete topic

---

## 4. Topic (`/topics/{id}`)

**Template:** `topic.html`  
**Access:** All authenticated users

### Sections

- **Topic header** — name, number, hours weight, high-stakes badge (admin toggle)
- **Learning Outcomes (ILOs)** — numbered list; each ILO shows its Bloom level badge; any user can add ILOs; admin can edit/delete; "edit ILO" goes to `ilo_edit.html`
- **Question pool** — table of all questions (pending + active + retired); columns: text preview, type, difficulty badge, status, facility/discrimination badges; each row links to `question.html`
- **Add question** button → `question_form.html`
- **Формативні квізи section** — "Згенерувати квіз" → `quiz_form.html`
- **Export/Import** — download `topic_{id}.json` (all active+pending questions + ILOs); upload JSON to bulk-import questions
- Admin: edit/delete topic button

**Context data:** `q_metrics` dict (per-question facility + discrimination), `P_BAND_CSS`, `D_BAND_CSS`

---

## 5. Questions

### Question Form — New (`/topics/{id}/questions/new`)

**Template:** `question_form.html`

- Text area for question body
- Proposed difficulty: radio buttons (Базовий / Середній / Важкий)
- Question type: select (multiple choice, open-ended, etc.)
- ILO: radio cards — **mandatory** if topic has LOs; validation error shown inline if skipped; if topic has no LOs, submit is disabled + warning shown
- Model answer: textarea (optional)
- On submit: creates `Question` with status `pending`, redirects to topic page

### Question Detail (`/questions/{id}`)

**Template:** `question.html`  
**Access:** All authenticated users

**Sections (top to bottom):**

1. **Header** — question text, topic breadcrumb, author name, created date, status badge (pending/active/retired)
2. **Metadata row** — question type, proposed difficulty, final difficulty (if set), ILO reference
3. **Vote form** — hidden for author; hidden for retired questions; contains:
   - Approve / Reject toggle
   - Difficulty vote buttons (B/M/H), Bloom-guided suggestion shown as hint
   - 5 quality criteria with labeled radio buttons and visible anchor text (Wording, LO alignment, Bloom level, Model answer, Clinical accuracy)
   - Comment textarea
4. **Item Analysis panel** (CTT) — shown when test data exists:
   - Facility index: mean p, n tests, color band, Wilson 95% CI
   - Discrimination index: D (Ebel 1965), color band
   - Difficulty mismatch recommendation (if final difficulty mismatches observed p-range)
5. **Exposure** — total uses, uses within horizon window
6. **Review profile** (most recent voting round only):
   - Per-criterion aggregate bar (mean score 1–3, color-coded)
   - Inter-rater reliability per criterion (SD + agreement band: high/moderate/low)
   - Reviewer recommendation (accept / revise / reject)
   - Bloom suggestion
7. **Voting rounds** (collapsible history) — one panel per round, newest first:
   - Current round: open, amber border
   - Past rounds: collapsed, grey border; includes revision snapshot (text at that round)
   - Per-voter rows: approve/reject, difficulty vote, criteria scores as color chips, comment
   - Reviewer name shown if admin OR question is active (anonymous otherwise)
8. **Edit / Retire** buttons (author or admin only)

### Question Edit (`/questions/{id}/edit`)

**Template:** `question_edit.html`  
**Access:** Author or admin

- Same fields as create form, pre-filled
- **On save:** snapshots current text/answer/difficulty to `question_revisions`, increments `current_round`, resets status to `pending`, clears `final_difficulty`
- **Quality criteria history panel** — shows last voting round's criteria results per reviewer (criteria bars + per-voter chips)

### Retire (`POST /questions/{id}/retire`)

- Sets status to `retired`; redirects to topic page
- Access: author or admin

---

## 6. Voting Queue (`/vote`)

**Template:** `vote_queue.html`  
**Access:** All authenticated users

**Two sections:**
- **To vote** — questions where user hasn't yet voted this round, and author ≠ current user
- **Already voted** — questions where user has a vote for current round

**Per-question card:**
- Question text + topic/ILO breadcrumb
- Proposed difficulty badge
- Approve / Reject toggle
- 5 quality criteria: radio groups 1/2/3 with anchor text panel (appears on selection, shows full behavioral descriptor from `CRIT_ANCHORS`)
- Difficulty vote: three buttons (B/M/H), visually highlighted on selection
- Bloom-guided difficulty suggestion — auto-calculated from `crit_bloom` rating; shows `↓ занижений` / `↑ завищений` / `↕ вручну`; can be manually overridden
- Comment field

**JSON endpoint:** `GET /vote/count` — returns `{"count": N}` of pending votes for sidebar badge

---

## 7. Tests

### Test List (`/modules/{id}/tests`)

**Template:** `tests_list.html`

- Chronological list of all tests and quizzes for this module
- Columns: test name, date, variant label, question count, creator

### New Test (`/modules/{id}/tests/new`)

**Template:** `test_form.html`

- Test name (auto-filled from module name)
- Total questions (numeric input)
- Number of variants (1–3)
- "Avoid recently used" toggle — excludes questions used in last N formal tests, where N = `exposure_horizon_n` setting
- On submit: `draw_multiple_variants()` selects questions by blueprint (topic weight × difficulty distribution); creates `Test` + `TestQuestion` records; if >1 variant, groups under shared `batch_id`; redirects to test detail (single) or test list (multi)

### Test Detail (`/tests/{id}`)

**Template:** `test.html`

1. **Header** — test name, module, date, creator, variant badge, quiz flag
2. **Batch siblings** — links to other variants in the same batch
3. **Question list** — ordered table: #, text, topic, difficulty, facility badge, discrimination badge (if results entered)
4. **LO coverage matrix** — per-topic grid: which ILOs are covered by ≥1 question (green check / grey dash)
5. **Reliability** — KR-20 value + band badge (excellent/acceptable/poor); requires results + SD
6. **Expected pass rate** — estimated % of students expected to pass, based on B+M item facilities
7. **Actions:** Enter results, Export DOCX, Export PDF

### Results Entry (`/tests/{id}/results`)

**Template:** `test_results.html`

- Total students (single input at top)
- Per-question: correct count; optional upper/lower 27% group counts for discrimination
- Test-level: score mean + SD (needed for KR-20)
- Upserts `TestResult` rows; upper/lower group size = floor(total × 0.27)

### Export DOCX (`GET /tests/{id}/export`)

- Generated via `python-docx`
- Header: org name, discipline, module, test name, variant, date, pass threshold % + standard-setting method note
- Body: numbered questions, question type, model answer (if present)
- Language-aware (UK/EN)

### Export PDF (`GET /tests/{id}/export.pdf`)

- Same content as DOCX rendered as PDF via `reportlab`

### Formative Quiz New (`/topics/{id}/quiz/new`)

**Template:** `quiz_form.html`

- Shows each ILO with count of active questions available (green checkmark if >0, red if 0)
- Quiz name (optional, auto-filled)
- On submit: `draw_topic_quiz()` picks one active question per ILO; creates `Test` with `is_quiz=True`; redirects to test detail

---

## 8. Admin

### Teacher Management (`/admin/teachers`)

**Template:** `admin_teachers.html`  
**Access:** Admin only

- Table of all teachers: name, email, role, active status
- Add teacher form (name, email, temp password, role)
- Delete teacher (POST)
- Reset password (POST)

### Settings (`/admin/settings`)

**Template:** `admin_settings.html`  
**Access:** Admin only

**Organisation branding** (POST `/admin/org-settings`):

| Key | Description |
|---|---|
| `org_name` | Institution name used in exports |
| `discipline_label` | Discipline display name |
| `pass_threshold_method` | Standard-setting method note (appended to pass threshold line in DOCX/PDF) |

**Voting thresholds** (POST `/admin/settings`):

| Key | Type | Description |
|---|---|---|
| `quorum` | int | Minimum votes before auto-activation |
| `approve_threshold_pct` | pct | % approval required for activation |
| `difficulty_agreement_pct` | pct | % difficulty consensus required |
| `pass_threshold_pct` | pct | Student pass score threshold for exports |

**Exposure control**:

| Key | Type | Description |
|---|---|---|
| `exposure_horizon_n` | int (1–10) | Number of recent formal tests to check for recently-used questions |

---

## 9. Help (`/help`)

**Template:** `help.html`  
**Access:** All authenticated users

4 tabs:

| Tab | Content |
|---|---|
| Голосування / Voting | Quality criteria, scoring, Bloom guidance, approval logic |
| Генерація тестів / Test Generation | Blueprint algorithm, variants, exposure control |
| Питання / Questions | Question lifecycle (pending → active → retired), rounds, revisions |
| Модуль/Теми / Module & Topics | Curriculum hierarchy, pool health indicators, ILOs |

---

## 10. Key Business Logic

| Component | File | Description |
|---|---|---|
| `activate_question()` | `app/draw.py` | After each vote: checks quorum + approval % + difficulty agreement; if met → sets `status=active`, calculates `final_difficulty` from median vote |
| `draw_multiple_variants()` | `app/draw.py` | Stratified random draw by topic+difficulty blueprint; returns N variant question lists |
| `draw_topic_quiz()` | `app/draw.py` | One active question per ILO; returns `(questions, missing_lo_ids)` |
| `build_blueprint_from_matrix()` | `app/draw.py` | Computes per-topic question count proportional to `hours_weight`; splits by B/M/H ratio |
| `recently_used_ids()` | `app/draw.py` | Returns question IDs used in last N formal (non-quiz) tests for a module |
| `facility_stats()` | `app/item_analysis.py` | Mean p, n_tests, total_n, Wilson 95% CI (`ci_lo`, `ci_hi`), p-band |
| `discrimination_stats()` | `app/item_analysis.py` | Ebel D, d-band |
| `review_profile()` | `app/item_analysis.py` | Per-criterion mean + SD + agreement; overall approve%, difficulty mode; reviewer recommendation |
| `item_recommendation()` | `app/item_analysis.py` | Generates recommendation list + severity; checks facility vs. expected p-range for declared difficulty |
| `kr20()` / `kr20_band()` | `app/item_analysis.py` | Kuder-Richardson 20 reliability from p-values + test SD |
| `expected_pass_rate()` | `app/item_analysis.py` | Estimates % passing from B+M item facilities |
| `export_test_docx()` / `export_test_pdf()` | `app/export.py` | Generates test documents with org branding, pass threshold + method note, model answers |
| `CRIT_ANCHORS` | `app/i18n.py` | Behaviorally-anchored rating scales for 5 voting criteria, returned via `crit_anchors()` Jinja2 global |
| `SETTINGS_SCHEMA` | `app/config.py` | Defines voting + exposure settings with defaults, min/max, units, labels |
| `ORG_SETTINGS_SCHEMA` | `app/config.py` | Defines org branding fields with placeholders |
| `QuestionRevision` | `app/models.py` | Snapshot of question text/answer/difficulty before each edit round |

---

## 11. Access Control

| Action | Teacher | Admin |
|---|---|---|
| View all pages | ✓ | ✓ |
| Add question | ✓ | ✓ |
| Vote (not own questions) | ✓ | ✓ |
| Edit own question | ✓ | ✓ |
| Retire own question | ✓ | ✓ |
| Edit any question | — | ✓ |
| Retire any question | — | ✓ |
| Add/edit ILOs | ✓ | ✓ |
| Delete ILOs | — | ✓ |
| Manage curriculum (faculty/discipline/module/topic) | — | ✓ |
| Manage teachers | — | ✓ |
| Configure settings | — | ✓ |
| Generate tests | ✓ | ✓ |
| Enter test results | ✓ | ✓ |
| Export tests | ✓ | ✓ |
| See reviewer names on pending questions | — | ✓ |
| See reviewer names on active questions | ✓ | ✓ |
