
cd /app
# Check if Entry.SetMinRowsVisible method exists
grep -n "func.*SetMinRowsVisible" widget/entry.go
echo "---"
# Verify build still succeeds
go build ./... 2>&1
if [ $? -eq 0 ]; then
  echo "✅ Build successful"
else
  echo "❌ Build failed"
fi
