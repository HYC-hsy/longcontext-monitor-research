
# Verify final build status
cd /app && go build ./... 2>&1 | tail -10
