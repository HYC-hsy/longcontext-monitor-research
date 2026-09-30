
# Find where fyneApp is defined and check if it has Metadata() method
grep -n "type fyneApp struct" /app/app/app.go
grep -n "func.*Metadata.*AppMetadata" /app/app/app.go
