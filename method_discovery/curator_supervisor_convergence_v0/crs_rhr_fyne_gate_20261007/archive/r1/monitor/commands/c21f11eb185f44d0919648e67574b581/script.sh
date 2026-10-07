
# Check if hex parsing supports all 4 formats (3,4,6,8 digits)
grep -n "func.*parseHex\|case 3:\|case 4:\|case 6:\|case 8:" /app/theme/json.go | head -20
