
# Verify all App implementations now have Metadata() method
cd /app
grep -A 8 "func.*Metadata()" --include="*.go" -r . | grep -E "(func|AppMetadata)" | head -20
