
# Check if fyneApp has Metadata() method
grep -A5 "func.*fyneApp.*Metadata" /app/app/app.go || echo "No Metadata method found in fyneApp"

echo "---"
# Check if testApp has Metadata() method  
grep -A5 "func.*testApp.*Metadata" /app/test/testapp.go || echo "No Metadata method found in testApp"
