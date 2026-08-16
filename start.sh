#!/bin/bash
# ==============================================================================
# 🏔️ Ridge · Unified Background Launcher & Cloudflare Tunnel
# ==============================================================================
# Hosts the full stack (FastAPI Backend + React Frontend + Cloudflare Tunnel)
# at https://ridge.karthikjayan.tech in the background.
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

LOGS_DIR="$PROJECT_ROOT/logs"
PID_FILE="$PROJECT_ROOT/.ridge.pids"
mkdir -p "$LOGS_DIR"

# Color Codes
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo ""
echo -e "${CYAN}${BOLD}🏔️  RIDGE · CORRECTIVE RAG PRODUCTION LAUNCHER${NC}"
echo -e "${CYAN}======================================================${NC}"

# 1. Stop any previously running instance
if [ -f "$PID_FILE" ]; then
    echo -e "${YELLOW}ℹ️  Cleaning up previous background sessions...${NC}"
    "$PROJECT_ROOT/stop.sh" > /dev/null 2>&1 || true
fi

# Double check port 8000
PORT_PID=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$PORT_PID" ]; then
    echo -e "${YELLOW}ℹ️  Stopping process on port 8000 (PID: $PORT_PID)...${NC}"
    kill -9 $PORT_PID 2>/dev/null || true
fi

# 2. Build Frontend
echo -e "\n${BOLD}[1/3] 📦 Compiling React Frontend...${NC}"
cd "$PROJECT_ROOT/frontend"
if npm run build > "$LOGS_DIR/frontend_build.log" 2>&1; then
    echo -e "      ${GREEN}✓ Frontend compiled successfully to dist/${NC}"
else
    echo -e "      ${RED}✗ Frontend build failed. See logs/frontend_build.log${NC}"
    exit 1
fi
cd "$PROJECT_ROOT"

# 3. Launch Backend API & Static Host
echo -e "\n${BOLD}[2/3] 🚀 Starting FastAPI Backend (Port 8000)...${NC}"
nohup uv run uvicorn api:app --host 0.0.0.0 --port 8000 > "$LOGS_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > "$PID_FILE"

# Wait for backend to be healthy
echo -n "      Waiting for backend to initialize..."
MAX_WAIT=20
WAITED=0
BACKEND_UP=false

while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8000/api/auth/me > /dev/null 2>&1 || curl -s http://localhost:8000/ > /dev/null 2>&1; then
        BACKEND_UP=true
        break
    fi
    sleep 1
    WAITED=$((WAITED + 1))
    echo -n "."
done
echo ""

if [ "$BACKEND_UP" = true ]; then
    echo -e "      ${GREEN}✓ Backend healthy on http://localhost:8000 (PID: $BACKEND_PID)${NC}"
else
    echo -e "      ${RED}✗ Backend failed to start. Check logs/backend.log:${NC}"
    tail -n 15 "$LOGS_DIR/backend.log"
    exit 1
fi

# 4. Launch Cloudflare Tunnel
echo -e "\n${BOLD}[3/3] 🌐 Connecting Cloudflare Tunnel (ridge.karthikjayan.tech)...${NC}"
nohup /opt/homebrew/bin/cloudflared tunnel --config "$PROJECT_ROOT/cloudflared.yml" run crag-tunnel > "$LOGS_DIR/tunnel.log" 2>&1 &
TUNNEL_PID=$!
echo $TUNNEL_PID >> "$PID_FILE"

# Give tunnel a couple seconds to connect
sleep 3

if ps -p $TUNNEL_PID > /dev/null 2>&1; then
    echo -e "      ${GREEN}✓ Cloudflare Tunnel connected (PID: $TUNNEL_PID)${NC}"
else
    echo -e "      ${RED}✗ Cloudflare Tunnel failed to start. Check logs/tunnel.log${NC}"
    tail -n 15 "$LOGS_DIR/tunnel.log"
    exit 1
fi

# Success Banner
echo ""
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}${BOLD}🎉 RIDGE IS LIVE AND RUNNING IN THE BACKGROUND!${NC}"
echo -e "${GREEN}${BOLD}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  🌍 ${BOLD}Public HTTPS URL :${NC} ${CYAN}https://ridge.karthikjayan.tech${NC}"
echo -e "  💻 ${BOLD}Local Web URL    :${NC} ${CYAN}http://localhost:8000${NC}"
echo -e "  ⚡ ${BOLD}Embedding Engine :${NC} BAAI/bge-large-en-v1.5 (Apple Silicon GPU)"
echo ""
echo -e "  📜 ${BOLD}View Live Logs   :${NC}"
echo -e "     • Backend API : ${YELLOW}tail -f logs/backend.log${NC}"
echo -e "     • CF Tunnel   : ${YELLOW}tail -f logs/tunnel.log${NC}"
echo ""
echo -e "  🛑 ${BOLD}Stop Server      :${NC} ${YELLOW}./stop.sh${NC}"
echo -e "  📊 ${BOLD}Check Status     :${NC} ${YELLOW}./status.sh${NC}"
echo ""
