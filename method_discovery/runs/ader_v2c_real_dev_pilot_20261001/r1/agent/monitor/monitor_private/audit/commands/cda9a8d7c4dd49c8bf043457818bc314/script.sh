
# Check if testApp has Metadata method
grep -n "func.*testApp.*Metadata" /app/test/testapp.go 2>/dev/null || echo "No Metadata method found in testApp"
