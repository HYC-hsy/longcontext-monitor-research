
# Quick verification of build status
cd /app && timeout 20 go build ./client/... ./server/... 2>&1 | tail -5
