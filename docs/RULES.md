# Engineering Constitution (RULES.md)

## 1. Engineering Principles

### Always
*   Build production-quality code.
*   Prefer existing architecture over introducing parallel implementations.
*   Reuse existing services before creating new ones.
*   Keep code modular, observable, and testable.
*   Keep code documented and maintainable.
*   Design for scalability and performance.
*   Write deterministic behavior whenever possible.
*   Always write docstrings for Python classes and functions.
*   Always declare strict types in TypeScript and avoid using `any`.
*   Always handle exceptions with explicit `try-except` blocks.

### Never
*   Hardcode telemetry or metrics.
*   Leave placeholder values or mock implementations.
*   Duplicate logic or imports.
*   Leave dead or unreachable code.
*   Bypass authentication or RBAC controls.
*   Swallow exceptions silently.
*   Leave debug code in production environments.
*   Allow documentation to drift from the actual implementation.

---

## 2. Mandatory Session Lifecycle
Every AI coding session must strictly follow this lifecycle:

```
  PLAN
   │
  READ
   │
  UNDERSTAND
   │
  IMPLEMENT
   │
  VERIFY
   │
  TEST
   │
  DOCUMENT
   │
  UPDATE MEMORY
   │
  UPDATE CHANGELOG
   │
  UPDATE JOURNAL
   │
  SELF REVIEW
   │
  FINAL REPORT
```
No implementation is considered complete if any stage is skipped.

---

## 3. Mandatory Self Review
Before declaring completion, the AI must verify:
*   [ ] Mock values removed
*   [ ] Duplicate code and imports removed
*   [ ] Dead and unreachable code removed
*   [ ] Documentation updated
*   [ ] Memory, Changelog, and Journal updated
*   [ ] Tests executed and verification completed
*   [ ] Production risks evaluated
*   [ ] Remaining technical debt documented
*   [ ] Recommended next milestone documented

---

## 4. Repository Cleanup Policy
Whenever a file is modified:
*   Clean surrounding code and remove obsolete comments.
*   Remove outdated `TODO`s or `FIXME`s.
*   Remove deprecated implementations and normalize formatting.
*   Improve naming consistency and type safety.
*   **Always leave the repository cleaner than you found it.**

---

## 5. Living Documentation Policies

### Living Documentation Policy
The `/docs` directory is the single source of truth for LetaTec’s architecture, engineering decisions, implementation history, and current project state.
Whenever any code is added, modified, refactored, or removed, the AI agent must determine which documentation files are affected and update them in the same session.
Documentation updates are part of the implementation—not a separate task. A task is not complete until both the codebase and the documentation are synchronized.

### Automatic Documentation Update Matrix
For every change, update only the relevant files:

| If you change... | Update... |
|---|---|
| Project scope or features | **[PRD.md](./PRD.md)** |
| Architecture or data flow | **[ARCHITECTURE.md](./ARCHITECTURE.md)** |
| AI/RAG logic, models, or caching | **[AI_SYSTEM.md](./AI_SYSTEM.md)** |
| API endpoints, routes, or payload formats | **[API_REFERENCE.md](./API_REFERENCE.md)** |
| Database schema, relationships, or indexes | **[DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)** |
| Security, auth, or RBAC logic | **[SECURITY.md](./SECURITY.md)** |
| UI/UX layouts, styles, or styling guidelines | **[DESIGN.md](./DESIGN.md)** |
| Coding rules, guidelines, or constitutional steps | **[RULES.md](./RULES.md)** |
| Project milestone phases | **[PHASES.md](./PHASES.md)** |
| Current project status | **[MEMORY.md](./MEMORY.md)** |
| Feature completion | **[CHANGELOG.md](./CHANGELOG.md)** |
| Engineering session log | **[DEVELOPMENT_JOURNAL.md](./DEVELOPMENT_JOURNAL.md)** |
| Architectural decisions | **[DECISIONS.md](./DECISIONS.md)** |
| Testing procedures, boundary tests | **[TESTING.md](./TESTING.md)** |
| Local/prod deployment details | **[DEPLOYMENT.md](./DEPLOYMENT.md)** |
| Operations, backups, diagnostics | **[OPERATIONS.md](./OPERATIONS.md)** |
| Technical debt, outstanding issues | **[KNOWN_ISSUES.md](./KNOWN_ISSUES.md)** |
| Future plans, research directions | **[ROADMAP.md](./ROADMAP.md)** |

*Only update what changed rather than touching every document every time.*

### Mandatory Change Log for Every Session
At the end of every implementation session, append a structured entry to **[DEVELOPMENT_JOURNAL.md](./DEVELOPMENT_JOURNAL.md)** using the Session template.

### Memory Synchronization Policy
After every completed task, update **[MEMORY.md](./MEMORY.md)** with:
*   Current milestone
*   Current version
*   Last completed feature
*   Active branch
*   Current blockers
*   Active technical debt
*   Immediate next task
*   Recommended next milestone

### Changelog Policy
Every completed feature, bug fix, refactor, optimization, or architectural change must be recorded in **[CHANGELOG.md](./CHANGELOG.md)**. Each entry should include:
*   Version
*   Date
*   Summary
*   Files affected
*   Breaking changes (if any)

### Decision Log Policy
If a change affects the architecture or involves choosing between multiple approaches, record it in **[DECISIONS.md](./DECISIONS.md)** as an Architecture Decision Record (ADR), including:
*   Status
*   Context
*   Options considered
*   Decision
*   Rationale
*   Consequences

### The "No Lost Work" Rule
No implementation may exist only in code or only in chat. Every meaningful engineering decision, code change, architectural modification, bug fix, optimization, or milestone must be reflected in the repository documentation before the task is considered complete.

### The "Explanation, Not Copy" Rule
Do not copy every line of code into the documentation. Instead, record what changed, why it changed, which files changed, how it works now, how it was verified, and what the next steps are. The source code remains the authoritative implementation, while the documentation is the authoritative explanation and history.

### Documentation Ownership Rule
Every pull request, implementation session, refactor, bug fix, optimization, or architectural change must leave the documentation in a fully synchronized state. If documentation is outdated, the implementation is considered incomplete and fails the Definition of Done.

---

## 6. Documentation Preservation Constitution
The documentation of LetaTec is a permanent engineering knowledge base. Documentation must preserve engineering history, architectural reasoning, implementation evolution, and operational knowledge across the lifetime of the project.

### Preservation Rules
*   **Append-Only**: Documentation is append-only unless correcting factual inaccuracies.
*   **Never Delete History**: Never delete previous engineering history or overwrite previous implementation summaries.
*   **Never Remove Sessions**: Never remove previous Development Journal sessions or completed roadmap milestones.
*   **Never Remove Changelog/ADRs**: Never remove previous changelog entries or replace/overwrite previous Architecture Decision Records (ADRs).
*   **Never Remove Schema/API Versions**: Never remove previous API versions or schema revisions.
*   **No Collapsing**: Never collapse multiple engineering sessions into one summary.
*   **Instead**: Append, extend, version, cross-reference, and mark deprecated items instead of deleting them.

### Documentation Update Policy
When updating any documentation file:
*   Preserve all previous valid content unless it is factually incorrect.
*   Add new sections instead of rewriting existing ones.
*   Mark obsolete information as **Deprecated** rather than deleting it.
*   Preserve chronological ordering for journals and changelogs.
*   Never regenerate an entire document if only one section changed.
*   When conflicting information exists, add a correction entry referencing the previous version instead of silently replacing it.

### Documentation-Implementation Consistency Rule
A coding session is not complete until:
*   All affected documentation has been updated.
*   API examples match the current implementation.
*   Database schema reflects current collections.
*   Changelog records the change.
*   Development Journal records the session.
*   Memory reflects the current milestone.
*   Any new endpoints, environment variables, collections, or configuration files are documented.

### Documentation Refactoring Rule
If a document becomes excessively large:
*   Archive historical sections into `docs/history/` while preserving links from the current documentation. History must never be discarded.
