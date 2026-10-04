
cd /app
# Check if the code compiles - testApp should fail since it doesn't implement Metadata()
go build ./test 2>&1 | head -20
