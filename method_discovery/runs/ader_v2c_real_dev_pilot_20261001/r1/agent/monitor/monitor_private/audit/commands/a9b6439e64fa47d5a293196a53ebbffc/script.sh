
# Verify compilation actually succeeds
cd /app && go build ./... 2>&1 | head -20
