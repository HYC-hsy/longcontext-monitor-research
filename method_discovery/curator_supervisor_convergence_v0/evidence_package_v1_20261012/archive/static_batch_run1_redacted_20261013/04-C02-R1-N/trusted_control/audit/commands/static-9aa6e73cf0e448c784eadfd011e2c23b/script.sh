
# Check if StringToStringWithFormat has the "%s" identity optimization
cd /app && sed -n '/^func StringToStringWithFormat/,/^}/p' data/binding/sprintf.go
