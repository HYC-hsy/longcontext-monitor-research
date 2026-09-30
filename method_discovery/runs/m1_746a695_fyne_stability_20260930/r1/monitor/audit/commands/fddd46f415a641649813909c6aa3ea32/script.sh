
# Definitively check if testApp has Metadata method
grep -n "func (a \*testApp) Metadata" /app/test/testapp.go
echo "Exit code: $?"
