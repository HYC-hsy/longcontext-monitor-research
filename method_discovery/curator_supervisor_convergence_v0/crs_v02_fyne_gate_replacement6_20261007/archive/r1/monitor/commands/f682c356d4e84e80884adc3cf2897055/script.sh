
# Check if there are other App implementations that need updating
cd /app && grep -l "func.*Lifecycle()" test/testapp.go app_test.go theme/themedtestapp.go 2>/dev/null | xargs -I {} grep -L "func.*Metadata()" {}
