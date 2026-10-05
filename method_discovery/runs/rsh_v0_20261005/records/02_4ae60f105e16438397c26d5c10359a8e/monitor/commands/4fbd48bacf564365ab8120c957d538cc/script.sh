
# Check if testApp has Metadata method
grep -n "Metadata" /app/test/testapp.go || echo "No Metadata method found in testapp.go"
