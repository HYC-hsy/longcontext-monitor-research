
# Check all functions in Target 5 files
echo "=== option_unary.go functions ==="
grep "^func With" /app/client/option_unary.go

echo -e "\n=== option_stream.go functions ==="
grep "^func With" /app/client/option_stream.go

echo -e "\n=== option_ttstream.go functions ==="
grep "^func With" /app/client/option_ttstream.go

echo -e "\n=== option.go TailOption ==="
grep "^func TailOption" /app/client/option.go

echo -e "\n=== callopt/streamcall/streamcall.go ==="
grep "^func With" /app/client/callopt/streamcall/streamcall.go
