# LETATEC System Documentation Overview

Welcome to the **LETATEC AI Platform** documentation suite. This document serves as the entry point and index for all developers and AI coding agents.

> [!IMPORTANT]
> **Living Documentation Policy**: Documentation is part of the implementation, not a post-development task. No task is considered complete until both the codebase and the documentation are synchronized. Every session must follow the documentation update matrix inside **[RULES.md](./RULES.md)**.

---

## 1. Documentation Index

| Filename | Purpose |
|---|---|
| **[00_OVERVIEW.md](./00_OVERVIEW.md)** | Index of the documentation framework, agent instructions, and directory map. |
| **[PRD.md](./PRD.md)** | Product Requirements Document: Vision, KPIs, target user profiles, scope, and non-goals. |
| **[ARCHITECTURE.md](./ARCHITECTURE.md)** | Core system topology, layout mapping React frontend to FastAPI, Redis, and FAISS. |
| **[AI_SYSTEM.md](./AI_SYSTEM.md)** | AI design: Hybrid RAG pipelines, local embeddings, and Intent-based Planner. |
| **[DESIGN.md](./DESIGN.md)** | UI/UX specifications, glassmorphic layout rules, animations, and loading states. |
| **[RULES.md](./RULES.md)** | Coding constitution, Always/Never rules, and AI implementation lifecycle. |
| **[PHASES.md](./PHASES.md)** | High-level roadmap tracking completed milestones and next steps. |
| **[MEMORY.md](./MEMORY.md)** | AI Working Memory: Active branch, current milestone, known risks, and pending tasks. |
| **[CHANGELOG.md](./CHANGELOG.md)** | Chronological history of completed features, enhancements, and refactoring fixes. |
| **[DECISIONS.md](./DECISIONS.md)** | Architecture Decision Records (ADRs) explaining caching, roles, and boundaries. |
| **[DEVELOPMENT_JOURNAL.md](./DEVELOPMENT_JOURNAL.md)** | Session-by-session engineering log tracking debugging lessons and changes. |
| **[TESTING.md](./TESTING.md)** | Testing protocols (Unit, Integration, E2E, Load, Security, and Regression). |
| **[DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)** | Collection layouts, indexes, validation rules, updates, lifecycles, and examples. |
| **[API_REFERENCE.md](./API_REFERENCE.md)** | Inbound request contracts, parameters, HTTP status codes, and JSON payloads. |
| **[SECURITY.md](./SECURITY.md)** | Security boundaries, authorization layers, duplicate checks, and audits. |
| **[DEPLOYMENT.md](./DEPLOYMENT.md)** | Local start guides, Render YAML templates, Dockerfiles, and S3 mounts. |
| **[OPERATIONS.md](./OPERATIONS.md)** | Production maintenance: Backups, monitoring systems, logs, and recovery loops. |
| **[ROADMAP.md](./ROADMAP.md)** | Prioritized backlog: Completed, Current, Next, Future, Research, Rejected. |
| **[KNOWN_ISSUES.md](./KNOWN_ISSUES.md)** | Technical debt tracker and active bugs registry. |

---

## 2. Directory Layout Map
```
LETATEC/
├── docs/                      # Unified Documentation Framework
│   ├── diagrams/              # Diagrams Assets Folder
│   └── *.md                   # System Markdown Docs
├── frontend/                  # React 19 Client UI Web App
│   ├── src/                   # Client source
│   │   ├── components/        # UI widgets (Auth, Layout, Documents)
│   │   ├── pages/             # Portal pages (AdminUploadPortal)
│   │   └── lib/               # Permissions helper module
│   └── package.json           # Dependencies and build commands
└── rag-backend/               # Python FastAPI Microservice App
    ├── app/                   # App source code
    │   ├── api/               # Routers (auth, admin, control_center)
    │   ├── retrieval/         # RAG hybrid search retriever
    │   └── pipeline/          # Document extraction & indexing
    └── main.py                # Server entry point
```

---

## 3. Mandatory AI Coding Agent Workflow
Every session executing on this repository must complete these steps:
1.  **Read** `docs/MEMORY.md`, `docs/PHASES.md`, `docs/RULES.md`, and `docs/ROADMAP.md`.
2.  **Determine** the current active milestone and any open technical debt.
3.  **Plan** the implementation.
4.  **Execute** requested refactoring or code additions.
5.  **Verify** and test changes.
6.  **Update** affected markdown files under `/docs/` according to the Update Matrix.
7.  **Record** decisions in `docs/DECISIONS.md`.
8.  **Record** code changes in `docs/CHANGELOG.md`.
9.  **Record** the session in `docs/DEVELOPMENT_JOURNAL.md`.
10. **Update** project progress details inside `docs/MEMORY.md`.
11. **Produce** a concise engineering session implementation report.
