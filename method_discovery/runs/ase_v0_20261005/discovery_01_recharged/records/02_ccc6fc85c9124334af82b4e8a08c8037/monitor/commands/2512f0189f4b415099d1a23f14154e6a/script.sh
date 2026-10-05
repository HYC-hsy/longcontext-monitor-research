
# Check specific compilation errors
cd /app && go build ./data/binding 2>&1
echo "---"
cd /app && go build ./theme 2>&1
echo "---"  
cd /app && go build ./test 2>&1
