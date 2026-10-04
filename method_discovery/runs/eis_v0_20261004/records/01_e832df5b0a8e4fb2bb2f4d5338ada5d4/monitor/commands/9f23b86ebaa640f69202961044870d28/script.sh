
# Check dummyApp implementation - my earlier check showed 0 results
echo "=== Checking dummyApp in app_test.go ==="
grep -B2 -A5 "func (d \*dummyApp) Metadata" /app/app_test.go

echo -e "\n=== If not found, check if dummyApp exists and needs Metadata() ==="
grep -n "type dummyApp struct" /app/app_test.go

echo -e "\n=== Check if dummyApp implements App interface ==="
grep -B5 "dummyApp" /app/app_test.go | head -20
