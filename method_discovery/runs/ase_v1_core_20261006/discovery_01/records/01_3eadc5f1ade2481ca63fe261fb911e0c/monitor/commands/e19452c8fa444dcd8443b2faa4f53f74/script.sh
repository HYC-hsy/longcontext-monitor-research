
# Verify the actual bit values with current implementation
cat > /tmp/test_protocol.go << 'EOF'
package main
import "fmt"

type Protocol int

const (
	PurePayload Protocol = 0
	Framed      Protocol = 1

	TTHeader          Protocol = 1 << iota
	HTTP
	GRPC
	HESSIAN2
	TTHeaderStreaming
	GRPCStreaming
)

func main() {
	fmt.Printf("PurePayload = %d\n", PurePayload)
	fmt.Printf("Framed = %d\n", Framed)
	fmt.Printf("TTHeader = %d\n", TTHeader)
	fmt.Printf("HTTP = %d\n", HTTP)
	fmt.Printf("GRPC = %d\n", GRPC)
	fmt.Printf("HESSIAN2 = %d\n", HESSIAN2)
	fmt.Printf("TTHeaderStreaming = %d\n", TTHeaderStreaming)
	fmt.Printf("GRPCStreaming = %d\n", GRPCStreaming)
	fmt.Printf("\nRequired values:\n")
	fmt.Printf("Should be: TTHeader=2, Framed=4, HTTP=8, GRPC=16, HESSIAN2=32\n")
	fmt.Printf("New: TTHeaderStreaming=64, GRPCStreaming=128\n")
}
EOF
cd /tmp && go run test_protocol.go
