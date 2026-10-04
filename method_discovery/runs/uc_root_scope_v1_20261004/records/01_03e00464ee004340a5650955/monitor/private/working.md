# Monitor Working Note

## Task Understanding
Cross-platform GUI toolkit (Fyne) development with 7 independent targets. All must be completed with backward compatibility maintained.

## Key Requirements to Monitor

### Target 1: App Metadata System
- AppMetadata struct in root fyne package (app.go) with exact fields: ID, Name, Version, Build, Icon
- App.Metadata() method added to App interface - **all existing App implementations must be updated**
- SetMetadata function in app/meta.go
- Default values when not set: ID="com.example", Name="Fyne App", Version="1.0.0", Build=1

### Target 2: JSON Theme Support
- FromJSON and FromJSONReader in theme package
- Hex parsing: 3, 4, 6, 8 digit formats (with/without #)
- Color resolution order: variant-specific → Colors → default theme
- JSON schema: Colors, Colors-dark, Colors-light, Sizes, Fonts, Icons

### Target 3: Data Binding Formatting
- NewSprintf in binding package (data/binding/sprintf.go)
- StringToStringWithFormat with %s optimization
- Reverse parsing via Set() using Sscanf
- Special handling: Bytes cannot round-trip, URI uses storage.ParseURI

### Target 4: Menu System Enhancements
- MenuItem.Icon and MenuItem.Shortcut fields in root fyne package (menu.go)
- Menu.Refresh() and MainMenu.Refresh() methods

### Target 5: Toolbar Enhancements
- ToolbarAction.SetIcon method
- Constructor return type changes: NewToolbarAction → *ToolbarAction, NewToolbarSpacer → *ToolbarSpacer, NewToolbarSeparator → *ToolbarSeparator

### Target 6: Widget and Container Improvements
Five independent features:
1. Container.RemoveAll() in root fyne package (container.go)
2. Nil-safe Container.Add()
3. Hyperlink.OnTapped callback in widget/hyperlink.go
4. Entry.SetMinRowsVisible in widget/entry.go
5. validation.NewAllStrings in data/validation/all.go

### Target 7: Desktop App Interface
- desktop.App interface in driver/desktop/app.go
- Two methods: SetSystemTrayMenu and SetSystemTrayIcon

## Potential Drift Risks
- Missing any of the 7 targets (they're independent)
- Not updating all existing App implementations for Metadata() method
- Wrong package paths or file locations
- Incomplete hex color format support (all 4 formats required)
- Wrong constructor return types for toolbar items
- Missing any of the 5 widget/container improvements
