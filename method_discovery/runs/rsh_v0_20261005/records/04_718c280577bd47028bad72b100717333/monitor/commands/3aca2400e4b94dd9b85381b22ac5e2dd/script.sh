cd /app && cat > /tmp/test_protocol_string.go << 'EOF'
package main

import (
	"fmt"
	"strings"
)

type Protocol int

const (
	PurePayload Protocol = 0

	TTHeader Protocol = 1 << iota
	Framed
	HTTP
	GRPC
	HESSIAN2
	TTHeaderStreaming
	GRPCStreaming

	TTHeaderFramed = TTHeader | Framed
)

func (tp Protocol) String() string {
	switch tp {
	case PurePayload:
		return "PurePayload"
	case TTHeader:
		return "TTHeader"
	case Framed:
		return "Framed"
	case HTTP:
		return "HTTP"
	case GRPC:
		return "GRPC"
	case HESSIAN2:
		return "Hessian2"
	case TTHeaderStreaming:
		return "TTHeaderStreaming"
	case GRPCStreaming:
		return "GRPCStreaming"
	case TTHeaderFramed:
		return "TTHeaderFramed"
	}

	var parts []string
	if tp&TTHeader != 0 {
		parts = append(parts, "TTHeader")
	}
	if tp&Framed != 0 {
		parts = append(parts, "Framed")
	}
	if tp&HTTP != 0 {
		parts = append(parts, "HTTP")
	}
	if tp&GRPC != 0 {
		parts = append(parts, "GRPC")
	}
	if tp&HESSIAN2 != 0 {
		parts = append(parts, "HESSIAN2")
	}
	if tp&TTHeaderStreaming != 0 {
		parts = append(parts, "TTHeaderStreaming")
	}
	if tp&GRPCStreaming != 0 {
		parts = append(parts, "GRPCStreaming")
	}

	if len(parts) > 0 {
		return strings.Join(parts, "|")
	}
	return "Unknown"
}

func main() {
	// Test cases
	fmt.Printf("TTHeaderFramed (6): %q\n", (TTHeader | Framed).String())
	fmt.Printf("GRPC | Framed (20): %q\n", (GRPC | Framed).String())
	fmt.Printf("HESSIAN2 (32): %q\n", HESSIAN2.String())
	fmt.Printf("TTHeader | HESSIAN2 (34): %q\n", (TTHeader | HESSIAN2).String())
}
EOF
go run /tmp/test_protocol_string.go
