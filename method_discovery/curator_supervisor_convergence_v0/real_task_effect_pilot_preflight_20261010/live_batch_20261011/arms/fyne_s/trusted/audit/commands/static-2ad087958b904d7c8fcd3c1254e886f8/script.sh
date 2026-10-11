
cd /app
# Check if testapp.go and themedtestapp.go have App implementations with Metadata() method
grep -A 3 "type.*App.*struct" test/testapp.go theme/themedtestapp.go
