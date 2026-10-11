
cd /app
# Check all App implementations have Metadata method
echo "=== Checking fyneApp in app/app.go ==="
grep -A 5 "func.*fyneApp.*Metadata" app/app.go || echo "NOT FOUND in app/app.go"
echo ""
echo "=== Checking testApp in app/app_test.go ==="
grep -A 5 "func.*testApp.*Metadata" app/app_test.go || echo "NOT FOUND in app_test.go"
