
# Search for where minRowsVisible is actually used in calculations
grep -B5 -A5 "minRowsVisible" /app/widget/entry.go | grep -v "^--$"
