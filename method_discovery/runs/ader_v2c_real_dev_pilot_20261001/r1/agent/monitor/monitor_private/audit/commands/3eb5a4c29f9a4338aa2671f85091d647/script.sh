
# Check if both implementations now have Metadata()
grep -n "func.*Metadata" /app/test/testapp.go /app/app_test.go 2>/dev/null
