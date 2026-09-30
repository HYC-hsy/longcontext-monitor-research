
# Check if testApp has Metadata method (maybe I missed it)
grep -n "func.*testApp.*Metadata" /app/test/testapp.go

# Check current git diff to see all changes
cd /app && git diff test/testapp.go
