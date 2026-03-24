# Sentinel.AI - GST & Legal Intelligence Engine

Sentinel.AI is a cutting-edge legal intelligence engine designed specifically for professionals handling Indirect Taxes (GST), Direct Taxes, Company Law, and FEMA in India. It leverages Advanced Retrieval-Augmented Generation (RAG) and an AI Template Engine to provide highly accurate legal advisory, case law extraction, and automated litigation drafting.

---

## 🚀 Core Features

### 1. **LETA (Legal Expert Tax Assistant)**

- **RAG-Powered Chatbot**: A highly intelligent conversational agent that understands complex legal queries, queries a massive library of statutory documents, case laws, and circulars, and provides **hallucination-free, gold-standard legal advice**.
- **Citation Verification**: Every claim made by LETA is cross-verified against actual PDF documents, providing the user with exact page numbers and document fragments for supreme confidence.
- **Agentic Routing**: Automatically understands whether a user is asking for legal advice (routes to RAG) or requesting a litigation draft (routes to the Template Engine).

### 2. **Litigation Support (Template Engine)**

- **Netflix-Style Interactive UI**: A premium, highly visual interface allowing users to browse through hundreds of pre-built litigation templates, notices, and appeals.
- **Semantic Template Matching**: Search for real-world scenarios (e.g., "ITC mismatch Notice") and the engine semantically ranks the best legal templates for the job.
- **AI Customization Workspace**: A split-pane editor where users input their specific facts (amounts, dates, notice numbers), and the LLM dynamically rewrites the standard template into a bespoke, ready-to-file legal draft.

### 3. **Complete Document Library**

- Access a continuously updated repository of Acts, Rules, Notifications, Circulars, Advance Rulings (AAR), and Forms directly from the application.
- One-click PDF Viewing directly in the browser for cross-referencing LETA's citations.

### 4. **Multi-Domain Support**

The application architecture supports dedicated dashboards for multiple domains, keeping knowledge bases isolated and highly relevant:

- GST Intelligence Hub
- Income Tax Advisory
- FEMA Expert System
- Company Law Compliance

---

## 🖥️ Application Pages

1. **Home (`/`)**: The immersive landing page introducing the Sentinel.AI suite.
2. **Login/Register (`/login`)**: JWT-secured authentication portal for professionals.
3. **Law Dashboards (`/gst`, `/income-tax`, `/fema`, `/company-law`)**: Domain-specific hubs featuring latest updates and the Document Library.
4. **Litigation Support (`/gst/templates`)**: The Netflix-style engine for exploring and discovering legal drafts and notices.
5. **Template Customization (`/gst/templates/:id/customize`)**: The workspace for injecting case facts into templates using AI.
6. **Documentation (`/docs`)**: Internal tool guides.
7. **About (`/about`)**: Information regarding the Sentinel mission.

---

## 🔌 API Endpoints Reference

The backend is powered by FastAPI, featuring modular routers for different domains.

### 1. Global Endpoints

- **`GET /`**: Health Check.
- **`POST /ask`**: The core LETA interaction endpoint (Streaming Response). Accepts natural language questions, maintains session history, routes intent, performs Vector Search, and streams the LLM-generated answer followed by verified citations.
- **`POST /generate-pdf`**: Converts LETA's markdown responses into polished PDF advisory reports for clients.

### 2. Authentication (`/api/auth`)

- **`POST /api/auth/register`**: Register a new user (`email`, `password`, `name`). Hashes passwords using bcrypt.
- **`POST /api/auth/login`**: OAuth2 login generating a JWT Access Token.
- **`GET /api/auth/me`**: Returns the currently authenticated user's profile information. Requires JWT.

### 3. Document Library (`/api/documents`)

- **`GET /api/documents/categories`**: Scans the `RAG_INFORMATION_DATABASE` and returns available legal categories with file counts.
- **`GET /api/documents/list/{category}`**: Returns a JSON list of all available PDF documents inside a specific category (e.g., Circulars, AARs).
- **`GET /api/documents/view`**: Streams a raw PDF file to the frontend for viewing within the browser. Accepts `category` and `filename` parameters.

### 4. Template Engine (`/api/templates`)

- **`GET /api/templates/search`**: The core Netflix UI endpoint.
  - _Without query_: Returns pre-grouped rows of templates (e.g., "Popular ITC Notices", "Refund Claims").
  - _With query_: Performs semantic searching to return a "Best Match" hero card and a row of "Similar Templates".
- **`GET /api/templates/{template_id}`**: Retrieves the full metadata and static content of a specific litigation template.
- **`POST /api/templates/{template_id}/customize`**: The AI generation endpoint. Accepts the `user_context` (case facts), fetches the base template, merges them via the LLM, and returns the tailored legal draft.

---

## 🛠️ Tech Stack & Architecture

- **Frontend**: React, Vite, TailwindCSS (with glassmorphism & film grain aesthetics), React Router, Lucide Icons.
- **Backend**: Python, FastAPI, Uvicorn, PyMongo.
- **Database**: MongoDB (User Auth, Template Library, Session History).
- **AI/ML**: Langchain, OpenAI/Anthropic APIs for generation and embeddings, custom Citation Verifier module for 100% accuracy enforcement.
