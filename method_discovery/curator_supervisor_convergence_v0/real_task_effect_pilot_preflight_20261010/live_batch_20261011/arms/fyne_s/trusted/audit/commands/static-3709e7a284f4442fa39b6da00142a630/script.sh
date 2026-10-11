
# Verify build still passes after structural change
cd /app && go build ./theme 2>&1
echo ""
echo "Build exit code: $?"
