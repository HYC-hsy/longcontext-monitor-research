
cd /app && cat > /tmp/test_protocol.go << 'EOF'
package main

import (
    "fmt"
    "github.com/cloudwego/kitex/transport"
)

func main() {
    // Test individual flags
    fmt.Printf("PurePayload: %s\n", transport.PurePayload.String())
    fmt.Printf("TTHeader: %s\n", transport.TTHeader.String())
    fmt.Printf("Framed: %s\n", transport.Framed.String())
    fmt.Printf("GRPC: %s\n", transport.GRPC.String())
    fmt.Printf("HESSIAN2: %s\n", transport.HESSIAN2.String())
    fmt.Printf("TTHeaderStreaming: %s\n", transport.TTHeaderStreaming.String())
    fmt.Printf("GRPCStreaming: %s\n", transport.GRPCStreaming.String())
    
    // Test composite values
    fmt.Printf("TTHeaderFramed: %s\n", transport.TTHeaderFramed.String())
    fmt.Printf("GRPC|Framed: %s\n", (transport.GRPC | transport.Framed).String())
    
    // Verify values
    fmt.Printf("\nValues:\n")
    fmt.Printf("TTHeaderStreaming = %d\n", transport.TTHeaderStreaming)
    fmt.Printf("GRPCStreaming = %d\n", transport.GRPCStreaming)
}
EOF

go run /tmp/test_protocol.go
