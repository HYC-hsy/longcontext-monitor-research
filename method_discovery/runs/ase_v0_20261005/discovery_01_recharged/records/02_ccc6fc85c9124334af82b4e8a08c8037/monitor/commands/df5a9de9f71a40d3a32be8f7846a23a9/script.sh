
# Check if the files were actually modified after intervention
stat -c "%y %n" /app/theme/json.go /app/data/binding/sprintf.go 2>/dev/null
