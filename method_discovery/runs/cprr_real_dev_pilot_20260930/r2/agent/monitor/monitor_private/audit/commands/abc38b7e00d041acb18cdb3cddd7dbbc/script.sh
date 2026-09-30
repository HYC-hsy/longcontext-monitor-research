
# Check if testApp explicitly declares conformance to fyne.App
grep -A2 -B2 "var _ fyne.App" /app/test/*.go

# Try to build specific packages to isolate errors
cd /app && go build ./app 2>&1
echo "---app build done---"
cd /app && go build . 2>&1 | head -10
echo "---root build done---"
