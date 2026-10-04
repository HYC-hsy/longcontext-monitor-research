
# More direct: look for types implementing multiple App methods
cd /app
grep -l "func.*NewWindow" --include="*.go" -r . | while read f; do
  if grep -q "func.*Settings()" "$f" && grep -q "func.*Lifecycle()" "$f"; then
    echo "$f"
  fi
done
