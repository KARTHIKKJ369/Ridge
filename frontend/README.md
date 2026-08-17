# 🏔️ Ridge · Alpine UI Client

React 19 + Vite + TypeScript frontend interface for the Ridge Corrective RAG (CRAG) system.

## 🎨 Features
- **Alpine 2026 Design System**: Custom climbing-inspired palettes (*Stone & Summit*, *Chalk & Void*, *Rust & Ridge*).
- **Real-Time Ascent Trace Drawer**: Side-by-side observability drawer displaying execution steps, grader rationales, and latency telemetry.
- **SSE Streaming Integration**: Low-latency Server-Sent Events stream for token-by-token answer generation and confidence scoring.
- **Knowledge Crag Manager**: Ingest documents (PDF, Word, PPTX, Excel, Code, Images via OCR) and web URLs.
- **Auth Modal**: Integrated JWT session management with PBKDF2 authentication.

## 🚀 Development Setup

```bash
# Install dependencies
npm install

# Start Vite dev server with proxy to backend
npm run dev

# Build production bundle
npm run build
```
