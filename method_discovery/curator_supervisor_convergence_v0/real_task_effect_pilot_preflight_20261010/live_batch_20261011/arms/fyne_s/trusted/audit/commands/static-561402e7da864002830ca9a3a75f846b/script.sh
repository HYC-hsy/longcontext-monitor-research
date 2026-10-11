
# Verify the actual MinSize impact of minRowsVisible
grep -A 20 "func (e \*Entry) MinSize" /app/widget/entry.go | grep -B 5 -A 5 "minRowsVisible"
