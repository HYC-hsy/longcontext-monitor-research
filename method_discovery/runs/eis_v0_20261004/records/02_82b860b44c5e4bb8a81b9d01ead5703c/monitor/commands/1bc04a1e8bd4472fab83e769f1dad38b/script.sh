
# Check if MinSize method uses MinRowsVisible
grep -A 30 "func (e \*Entry) MinSize()" /app/widget/entry.go
