
# Try to compile to confirm the interface break
cd /app && go build ./... 2>&1 | head -20
