
# Check the full NewSprintf Set() implementation - need to see Bytes and URI handling
cd /app && sed -n '/^func (b \*sprintfBinding) Set/,/^func /p' data/binding/sprintf.go | head -80
