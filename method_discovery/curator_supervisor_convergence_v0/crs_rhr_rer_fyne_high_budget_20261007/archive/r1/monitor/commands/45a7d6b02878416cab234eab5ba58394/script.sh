
# Check if NewAllStrings is in data/validation or data/binding
cd /app && find . -name "all.go" -o -name "bindlists.go" | grep -E "(validation|binding)" | grep -v vendor
