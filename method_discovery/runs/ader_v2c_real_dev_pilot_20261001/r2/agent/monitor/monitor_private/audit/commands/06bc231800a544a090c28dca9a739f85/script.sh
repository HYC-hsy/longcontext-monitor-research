
# Check for default protocol setting - should be Framed not PurePayload
grep -r "default.*protocol\|Protocol.*=.*Framed\|NewClient.*transport" /app/client --include="*.go" -A 2 -B 2 | grep -i "default\|framed\|purepayload" | head -15
