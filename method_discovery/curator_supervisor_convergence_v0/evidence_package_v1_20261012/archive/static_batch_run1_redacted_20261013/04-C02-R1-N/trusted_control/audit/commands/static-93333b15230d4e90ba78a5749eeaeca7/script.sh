
# Check if StringToStringWithFormat has identity optimization for "%s"
cd /app && grep -B5 -A20 "func StringToStringWithFormat" data/binding/sprintf.go | head -30
