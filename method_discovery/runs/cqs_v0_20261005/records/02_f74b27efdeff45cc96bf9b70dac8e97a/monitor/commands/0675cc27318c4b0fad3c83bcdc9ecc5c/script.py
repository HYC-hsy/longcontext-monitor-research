
# Quick verification of Targets 4, 5, 6
import os

print("=== Target 4: Thrift Codec Fallback ===")
thrift_path = '/app/pkg/remote/codec/thrift/thrift.go'
if os.path.exists(thrift_path):
    with open(thrift_path, 'r') as f:
        content = f.read()
        has_ttheader_streaming = 'TTHeaderStreaming' in content
        print(f"Contains TTHeaderStreaming references: {has_ttheader_streaming}")
        if 'transport.TTHeaderStreaming' in content:
            print("✓ TTHeaderStreaming protocol handling added")
else:
    print("❌ File not found")

print("\n=== Target 5: Client Option Categories ===")
option_path = '/app/client/option.go'
if os.path.exists(option_path):
    with open(option_path, 'r') as f:
        content = f.read()
        has_unary = 'UnaryOption' in content
        has_stream = 'StreamOption' in content  
        has_ttheader = 'TTHeaderStreamingOption' in content
        print(f"Has UnaryOption: {has_unary}")
        print(f"Has StreamOption: {has_stream}")
        print(f"Has TTHeaderStreamingOption: {has_ttheader}")
        if has_unary and has_stream and has_ttheader:
            print("✓ Option type aliases present")
else:
    print("❌ File not found")

print("\n=== Target 6: gRPC Diagnostics ===")
transport_path = '/app/pkg/remote/trans/nphttp2/grpc/transport.go'
if os.path.exists(transport_path):
    with open(transport_path, 'r') as f:
        content = f.read()
        has_dump = 'func (s *Stream) Dump()' in content or 'func (s *stream) Dump()' in content
        has_connection_error = 'streamID' in content and 'ConnectionError' in content
        print(f"Has Dump() method: {has_dump}")
        print(f"Has ConnectionError enhancements: {has_connection_error}")
        if has_dump:
            print("✓ Dump() method added")
else:
    print("❌ File not found")
