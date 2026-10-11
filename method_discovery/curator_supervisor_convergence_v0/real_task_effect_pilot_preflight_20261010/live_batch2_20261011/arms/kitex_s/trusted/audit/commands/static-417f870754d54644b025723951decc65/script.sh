
# Check if transport package needs to be created or if it's in a vendor/module
cat /app/go.mod | grep -A 5 "module "
