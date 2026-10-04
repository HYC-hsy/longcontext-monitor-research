
# Final compilation check
cd /app && go build ./... 2>&1 | head -20 || echo "Build completed"
