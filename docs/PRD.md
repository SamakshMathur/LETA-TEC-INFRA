# Product Requirements Document (PRD) - LETATEC AI Platform

## 1. Vision
LETATEC is designed as an enterprise-grade AI-powered GST legal research and document intelligence platform. It replaces static, rule-based legal lookup tables with a self-maintaining Retrieval-Augmented Generation (RAG) pipeline and templated litigation draft engine. It enables tax professionals and counselors to get precise, gold-standard, citation-verified legal opinions.

## 2. Target Users
*   **Tax Advocates & Lawyers**: Conducting complex statutory lookups and drafting responses to Show Cause Notices (SCNs) or ASMT-10 mismatch forms.
*   **Chartered Accountants (CAs) / CSs**: Reviewing statutory updates, notifications, circulars, and high court case filings.
*   **Corporate Finance Teams**: Verifying Input Tax Credit (ITC) eligibility rules and compliance frameworks.
*   **System Administrators**: Managing files, ingestion pipelines, API tokens, webhooks, and team memberships.

## 3. Core Features
1.  **LETATEC Chat (RAG)**: Intent-driven conversations retrieving from Acts, Rules, Notifications, Circulars, and Court filings.
2.  **Gold-Standard Citation Verification**: Highlights specific text snippets, page numbers, and PDF names.
3.  **Template Litigation Drafting**: Automated template generation for tax replies.
4.  **Admin Upload & Ingestion Center**: Drag-and-drop file ingestion, cryptographic SHA-256 duplicate validation, and live pipeline status updates.
5.  **Administrative Operations Console**: Centralized overview panel managing system health, analytics, API keys, webhooks, billing limits, and team permissions.
6.  **Admin AI Assistant**: Natural language console for admins to query system telemetry.

## 4. Key Performance Indicators (KPIs)
*   **Retrieval Latency**: Under 450ms for document lookup.
*   **Cache Hit Rate**: Above 45% for repetitive operational lookups.
*   **Citation Validation Accuracy**: 100% ground-truth citation matching (0% hallucination for circular/act citations).

## 5. Scope & Non-Goals
*   **In-Scope**: Complete document parsing, vector indexing (FAISS), stateful RBAC management, API token keys, webhooks, billing and quota tracking, operational AI monitoring.
*   **Non-Goals**: Autonomous write operations (e.g. LLM deleting data, restarting database containers, or modifying live system settings without explicit human authorization).
