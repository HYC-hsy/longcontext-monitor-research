
# Check if testApp has been updated with Metadata()
grep -n "Metadata" /app/test/testapp.go

# Check the exact lines with the error in theme/json.go
sed -n '85,90p' /app/theme/json.go
echo "---"
sed -n '111,116p' /app/theme/json.go
