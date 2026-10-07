
# Check if there are any other App implementations we might have missed
grep -r "implements.*fyne.App\|var _ fyne.App" /app --include="*.go" 2>/dev/null | grep -v ".git"
