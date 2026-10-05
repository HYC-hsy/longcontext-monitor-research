
# Search for the unmarshalThriftData method definition in thrift-related files
find /app/pkg/remote/codec/thrift -name "*.go" -exec grep -l "func.*unmarshalThriftData" {} \;
