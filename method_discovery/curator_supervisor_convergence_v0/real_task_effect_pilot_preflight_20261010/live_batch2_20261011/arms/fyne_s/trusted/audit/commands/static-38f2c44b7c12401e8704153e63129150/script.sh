
# Verify build still succeeds after Target 7 fix
cd /app
go build ./... 2>&1 | tail -5
echo "---"
echo "Build exit code: $?"
