# 🏔️ Ridge · Alpine UI Client

React 19 + TypeScript + Vite modern web application for the Ridge Corrective RAG (CRAG) platform.

---

## 🎨 Design & Visual Features

* **Alpine 2026 Design System**:
  * **Stone & Summit** (Light Sandstone Topography — `#F7F5F0`)
  * **Chalk & Void** (Dark Basalt Granite / Cyan — `#111418`)
  * **Rust & Ridge** (Desert Crag Terracotta Earth — `#14100E`)
* **Theme-Adaptive Mermaid.js Diagrams**:
  * Auto-sanitizes Unicode arrows (`──>`, `→`, `⇒`) and unquoted labels (`[Sentence-level (Local)]`).
  * In-memory SVG cache for instantaneous rendering with 0ms flickering.
  * 1-click **Visual / Source** toggle and **Copy** action.
* **KaTeX LaTeX Math Rendering**:
  * Inline `$ ... $` and block `$$ ... $$` math support.
  * Unicode whitespace normalizer (`\u202F`, `\u00A0`) and bracketed math converters.
* **Zero-Latency Isolated Chat Input Deck**:
  * Encapsulated input state tree running at native 120 FPS ($<0.1\text{ms}$ keystroke latency).
  * Auto-expanding textarea, slash-command shortcuts (`/web`, `/eval`, `/clear`), and source filter dropdown.
* **Real-Time Ascent Trace Drawer**:
  * Step-by-step telemetry for query decomposition, hybrid retrieval, relevance grading, and hallucination audits.
* **Knowledge Crag Source Scoper**:
  * Filter queries across all indexed files or scope strictly to specific documents.
* **Document Conflict Modal**:
  * Side-by-side split comparison viewer for contradictory source documents.

---

## 🚀 Development & Build

```bash
# Install dependencies
npm install

# Start Vite dev server (proxies /api and /ask to FastAPI on :8000)
npm run dev

# Run TypeScript compilation & production build
npm run build

# Preview production build
npm run preview
```

---

## 📁 Frontend Architecture

```
frontend/
├── src/
│   ├── App.tsx          # Root application, ChatInputDeck, MermaidDiagram, and state machines
│   ├── App.css          # Alpine design tokens, diagram styling, and animations
│   ├── index.css        # Core typography, color themes, and CSS custom properties
│   ├── main.tsx         # React root mounting point
│   └── components/
│       └── AuthModal.tsx# PBKDF2/JWT Login & Registration modal
├── public/              # Static assets and icons
├── package.json         # React 19, Lucide, KaTeX, Mermaid dependencies
└── vite.config.ts       # Vite proxy configuration to backend :8000
```
