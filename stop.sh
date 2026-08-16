#!/bin/bash
# ==============================================================================
# 🛑 Ridge · Background Process Shutdown Script
# ==============================================================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$PROJECT_ROOT/.ridge.pids"

# Color Codes
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${YELLOW}${BOLD}🛑 Stopping Ridge Background Services...${NC}"

# Kill from PID file if exists
if [ -f "$PID_FILE" ]; then
    while IFS= read -r pid; do
        if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
            echo -e "   Killing process ${BOLD}$pid${NC}..."
            kill "$pid" 2>/dev/null || true
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi

# Kill any leftover cloudflared instances running crag-tunnel
pkill -f "cloudflared.*crag-tunnel" 2>/dev/null || true

# Kill any leftover uvicorn processes on port 8000
PORT_PIDS=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$PORT_PIDS" ]; then
    for pid in $PORT_PIDS; do
        echo -e "   Cleaning up port 8000 process ${BOLD}$pid${NC}..."
        kill -9 "$pid" 2>/dev/null || true
    done
fi

echo -e "${GREEN}✓ All Ridge services and tunnels have been stopped.${NC}"
echo ""
