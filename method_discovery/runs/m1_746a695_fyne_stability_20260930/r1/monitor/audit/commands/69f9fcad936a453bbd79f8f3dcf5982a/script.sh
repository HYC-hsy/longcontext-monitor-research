
# Check test package for App implementations
grep -rn "type.*struct" /app/test/testapp.go | head -5
grep -n "func.*Metadata" /app/test/testapp.go
