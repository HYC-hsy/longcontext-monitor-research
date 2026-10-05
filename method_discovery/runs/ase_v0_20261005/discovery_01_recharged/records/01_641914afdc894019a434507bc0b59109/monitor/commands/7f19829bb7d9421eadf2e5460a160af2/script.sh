
# Test the String() method behavior for composites
cd /app && cat > /tmp/test_protocol.go << 'EOF'
package main

import (
	"fmt"
	"github.com/cloudwego/kitex/transport"
)

func main() {
	// Test single flags
	fmt.Printf("TTHeader: %s\n", transport.TTHeader.String())
	fmt.Printf("Framed: %s\n", transport.Framed.String())
	fmt.Printf("GRPC: %s\n", transport.GRPC.String())
	
	// Test composites
	fmt.Printf("TTHeaderFramed: %s\n", transport.TTHeaderFramed.String())
	fmt.Printf("TTHeaderStreaming: %s\n", transport.TTHeaderStreaming.String())
	
	// Test arbitrary composite
	composite := transport.GRPC | transport.Framed
	fmt.Printf("GRPC | Framed: %s\n", composite.String())
}
EOF
go run /tmp/test_protocol.go 2>&1 || echo "Build or run failed"
