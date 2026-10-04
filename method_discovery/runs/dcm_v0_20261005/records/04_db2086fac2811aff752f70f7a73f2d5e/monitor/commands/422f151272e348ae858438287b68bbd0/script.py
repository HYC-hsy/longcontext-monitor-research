
import os
import glob

# Check for new streaming files
streaming_files = sorted(glob.glob('/app/pkg/streaming/*.go'))
print("Streaming package files:")
for f in streaming_files:
    print(f"  {os.path.basename(f)}")

# Check if cep and sep packages were created
print("\nEndpoint packages:")
print(f"  cep exists: {os.path.isdir('/app/pkg/endpoint/cep')}")
print(f"  sep exists: {os.path.isdir('/app/pkg/endpoint/sep')}")

if os.path.isdir('/app/pkg/endpoint/cep'):
    cep_files = sorted(glob.glob('/app/pkg/endpoint/cep/*.go'))
    print("  cep files:")
    for f in cep_files:
        print(f"    {os.path.basename(f)}")

if os.path.isdir('/app/pkg/endpoint/sep'):
    sep_files = sorted(glob.glob('/app/pkg/endpoint/sep/*.go'))
    print("  sep files:")
    for f in sep_files:
        print(f"    {os.path.basename(f)}")

# Check endpoint package
endpoint_files = sorted(glob.glob('/app/pkg/endpoint/*.go'))
print("\nEndpoint package files:")
for f in endpoint_files:
    print(f"  {os.path.basename(f)}")
