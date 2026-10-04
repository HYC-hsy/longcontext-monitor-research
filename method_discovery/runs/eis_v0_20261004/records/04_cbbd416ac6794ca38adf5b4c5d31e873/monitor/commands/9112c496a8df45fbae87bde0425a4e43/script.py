
# Check Target 4 thrift codec files more thoroughly
import os
import subprocess

print("=== TARGET 4: Thrift Codec Fallback Verification ===\n")

# Find the thrift package files
thrift_dir = '/app/pkg/remote/codec/thrift'
if os.path.exists(thrift_dir):
    files = os.listdir(thrift_dir)
    print(f"Files in {thrift_dir}:")
    for f in sorted(files):
        if f.endswith('.go'):
            print(f"  {f}")
    
    # Check for MarshalThriftData and UnmarshalThriftData
    print("\n--- Checking for Marshal/Unmarshal functions ---")
    result = subprocess.run(
        ['grep', '-n', 'func.*MarshalThriftData\\|func.*UnmarshalThriftData', 
         f'{thrift_dir}/thrift_data.go'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("Functions found in thrift_data.go:")
        print(result.stdout[:500])
    else:
        # Try thrift.go
        result = subprocess.run(
            ['grep', '-n', 'func.*MarshalThriftData\\|func.*UnmarshalThriftData',
             f'{thrift_dir}/thrift.go'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("Functions found in thrift.go:")
            print(result.stdout[:500])
    
    # Check if Basic codec has fallback logic
    print("\n--- Checking for Basic codec fallback ---")
    for fname in ['thrift_data.go', 'thrift.go']:
        fpath = f'{thrift_dir}/{fname}'
        if os.path.exists(fpath):
            result = subprocess.run(
                ['grep', '-A10', 'Basic', fpath],
                capture_output=True, text=True
            )
            if 'FastCodec' in result.stdout or 'Frugal' in result.stdout:
                print(f"✓ Fallback logic found in {fname}")
                print(result.stdout[:800])
                break
else:
    print(f"Directory {thrift_dir} does not exist!")
