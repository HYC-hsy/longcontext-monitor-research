
# Check if StringToStringWithFormat has the %s optimization as required
cd /app && grep -B 5 "format == \"%s\"" data/binding/sprintf.go
