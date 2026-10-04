
# Quick verification of all 6 targets
import os

targets = {
    "Target 1 - Streaming Types": [
        "/app/pkg/streaming/types.go",
        "/app/pkg/streaming/generic_client.go",
        "/app/pkg/streaming/generic_server.go"
    ],
    "Target 2 - Endpoints": [
        "/app/pkg/endpoint/cep/endpoint.go",
        "/app/pkg/endpoint/sep/endpoint.go",
        "/app/pkg/endpoint/deprecated.go"
    ],
    "Target 3 - Transport": [
        "/app/transport/keys.go"
    ],
    "Target 5 - Client Options": [
        "/app/client/option_unary.go",
        "/app/client/option_stream.go",
        "/app/client/option_ttstream.go",
        "/app/client/callopt/streamcall/streamcall.go"
    ],
    "Target 6 - Diagnostics": [
        "/app/pkg/remote/trans/nphttp2/conn_pool.go",
        "/app/pkg/remote/trans/nphttp2/grpc/grpcframe/frame_reader.go"
    ]
}

print("Target Implementation Status:\n")
for target, files in targets.items():
    all_exist = all(os.path.exists(f) for f in files)
    status = "✓" if all_exist else "✗"
    print(f"{status} {target}")
    for f in files:
        exists = os.path.exists(f)
        if not exists:
            print(f"    MISSING: {f}")

print("\n\nTarget 4 (Thrift Codec): Task claims no changes needed.")
print("Checking if thrift codec files were modified...")
thrift_dir = "/app/pkg/remote/codec/thrift"
if os.path.exists(thrift_dir):
    files = [f for f in os.listdir(thrift_dir) if f.endswith('.go')]
    print(f"Thrift codec has {len(files)} .go files")
