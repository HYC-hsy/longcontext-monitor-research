
cd /app
# Search for Metadata() implementations in test and theme files
grep -n "func.*Metadata()" test/testapp.go theme/themedtestapp.go
