
# Check if there are any recent modifications suggesting work in progress
find /app -name "*.go" -type f -mmin -120 | wc -l

# Check the most recently modified files
find /app -name "*.go" -type f -mmin -120 | head -20

# Look for any work-in-progress or test files
ls -lt /app/*.go 2>&1 | head -10
