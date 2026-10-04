
import os

# Check if all required Target 5 files exist
files_to_check = [
    '/app/client/option_unary.go',
    '/app/client/option_stream.go',
    '/app/client/option_ttstream.go',
    '/app/pkg/endpoint/deprecated.go'
]

print("Required files:")
for f in files_to_check:
    exists = os.path.exists(f)
    print(f"  {os.path.basename(f)}: {'✓' if exists else '✗'}")

# Check if streamcall package has WithRecvTimeout
streamcall_files = []
if os.path.isdir('/app/client/callopt/streamcall'):
    import glob
    streamcall_files = glob.glob('/app/client/callopt/streamcall/*.go')
    
print(f"\nstreamcall package files: {len(streamcall_files)}")
for f in sorted(streamcall_files):
    print(f"  {os.path.basename(f)}")
