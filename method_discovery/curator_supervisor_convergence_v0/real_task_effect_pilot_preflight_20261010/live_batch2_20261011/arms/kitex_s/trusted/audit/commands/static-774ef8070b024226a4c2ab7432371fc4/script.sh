
# Wait for the pending build to complete
sleep 2
# Check build result
cd /app && go build ./pkg/protocol/... 2>&1 | head -30
