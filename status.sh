#!/bin/bash
# ==============================================================================
# 📊 Ridge · Background Health & Status Checker
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
echo -e "${CYAN}${BOLD}📊 RIDGE SERVICE STATUS${NC}"
echo -e "${CYAN}======================================================${NC}"

# Check Local Port 8000
BACKEND_PID=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "$BACKEND_PID" ]; then
    echo -e "  Backend API (Port 8000) : ${GREEN}● RUNNING${NC} (PID: $BACKEND_PID)"
else
    echo -e "  Backend API (Port 8000) : ${RED}○ STOPPED${NC}"
fi

# Check Cloudflare Tunnel
TUNNEL_PID=$(pgrep -f "cloudflared.*crag-tunnel" 2>/dev/null || true)
if [ -n "$TUNNEL_PID" ]; then
    echo -e "  Cloudflare Tunnel       : ${GREEN}● RUNNING${NC} (PID: $TUNNEL_PID)"
else
    echo -e "  Cloudflare Tunnel       : ${RED}○ STOPPED${NC}"
fi

# Test Local Endpoint
echo ""
echo -e "${BOLD}Health Probes:${NC}"
if curl -s http://localhost:8000/api/auth/me > /dev/null 2>&1 || curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo -e "  • Local Web (http://localhost:8000)            : ${GREEN}✓ 200 OK${NC}"
else
    echo -e "  • Local Web (http://localhost:8000)            : ${RED}✗ Unreachable${NC}"
fi

# Test Public Cloudflare Endpoint
HTTP_CODE=$(curl -o /dev/null -s -w "%{http_code}\n" https://ridge.karthikjayan.tech 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "304" ] || [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
    echo -e "  • Public Web (https://ridge.karthikjayan.tech) : ${GREEN}✓ $HTTP_CODE OK${NC}"
else
    echo -e "  • Public Web (https://ridge.karthikjayan.tech) : ${YELLOW}⚠ HTTP $HTTP_CODE${NC}"
fi

echo ""
