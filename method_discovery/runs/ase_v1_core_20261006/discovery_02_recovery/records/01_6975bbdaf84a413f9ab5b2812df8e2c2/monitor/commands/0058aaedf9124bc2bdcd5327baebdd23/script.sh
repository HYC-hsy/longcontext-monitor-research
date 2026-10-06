
# Look for remote/trans/nphttp2 mentioned in Target 6
find /app -type d -name "nphttp2" 2>/dev/null

# Look for codec/thrift mentioned in Target 4
find /app -type d -name "codec" 2>/dev/null | head -10
