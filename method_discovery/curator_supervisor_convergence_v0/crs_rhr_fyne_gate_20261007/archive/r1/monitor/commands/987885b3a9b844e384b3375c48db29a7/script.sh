
# Test compilation properly - check the test package specifically
cd /app && go build ./test 2>&1
echo "---test package result: $?"
echo ""
# Try compiling the whole module
cd /app && go build ./... 2>&1 | head -30
