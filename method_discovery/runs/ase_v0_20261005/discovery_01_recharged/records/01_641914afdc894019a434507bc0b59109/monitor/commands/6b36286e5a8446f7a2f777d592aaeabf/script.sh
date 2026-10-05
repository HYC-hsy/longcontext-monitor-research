
# Check for key directories related to the targets
for dir in "pkg/streaming" "pkg/endpoint/cep" "pkg/endpoint/sep" "pkg/endpoint" "pkg/remote/codec/thrift" "pkg/remote/trans/nphttp2" "transport"; do
  echo "=== $dir ==="
  if [ -d "/app/$dir" ]; then
    ls -la "/app/$dir" | head -20
  else
    echo "Directory does not exist"
  fi
  echo
done
