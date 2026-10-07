
cd /app && grep -n "func.*Metadata" test/testapp.go app_test.go theme/themedtestapp.go 2>/dev/null || echo "No Metadata methods found in these files"
