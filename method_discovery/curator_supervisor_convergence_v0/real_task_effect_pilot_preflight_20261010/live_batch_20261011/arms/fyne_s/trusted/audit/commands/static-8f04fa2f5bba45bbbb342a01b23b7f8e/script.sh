
cd /app
# Run the actual failing tests to see what's happening
go test ./dialog -v 2>&1 | grep -A 5 "TestColorDialog_Theme"
