# Monitor Working Note

## Task Understanding
7 independent targets for Fyne GUI toolkit enhancements. Each has specific API requirements.

## Key Watch Points

### Target 1 (App Metadata)
- AppMetadata struct must have: ID, Name, Version (string), Build (int), Icon (Resource)
- App.Metadata() method must be added to App interface
- SetMetadata function must be in app/meta.go (not app/ root)
- Default values when no metadata set

### Target 2 (JSON Theme)
- Hex color parsing: 3, 4, 6, 8 digits with/without # prefix
- Variant-specific: "Colors-dark" and "Colors-light" checked before "Colors"
- FromJSON and FromJSONReader both required
- Invalid parse returns default theme + error

### Target 5 (Toolbar)
- Return types MUST be concrete: *ToolbarAction, *ToolbarSpacer, *ToolbarSeparator
- Not ToolbarItem interface

### Target 6 (Container/Widget)
- validation.NewAllStrings must be in data/validation/all.go (new file)
- Entry.SetMinRowsVisible affects MinSize calculation for multi-line entries

### Target 7 (Desktop App)
- Interface location: driver/desktop/app.go (new file)
- Two methods: SetSystemTrayMenu and SetSystemTrayIcon

## Status
Intervention sent at cursor ~66: Target 3 incomplete.
- Missing: StringToStringWithFormat function in data/binding/sprintf.go
- Missing: Proper Set() implementation (should use fmt.Sscanf to parse and update sources)

Current progress:
- Target 1: Complete ✓
- Target 2: Complete ✓
- Target 3: Complete ✓ (fixed after intervention)
- Target 4: Complete ✓
- Target 5: Complete ✓
- Target 6: INCOMPLETE - NewAllStrings implementation is WRONG
- Target 7: INCOMPLETE - Missing SetSystemTrayIcon method

Critical issues found at cursor ~106:
1. NewAllStrings has wrong signature and behavior (string matcher vs validator chainer)
2. desktop.App missing SetSystemTrayIcon method
