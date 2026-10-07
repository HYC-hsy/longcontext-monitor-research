# Task Book: GUI Toolkit Development Roadmap

## Mission
Add 7 independent capabilities to a cross-platform GUI toolkit for Go, maintaining backward compatibility.

## Seven Targets (All Required)

### Target 1: App Metadata System
- `AppMetadata` struct in root fyne package (app.go): ID, Name, Version (string), Build (int), Icon (Resource)
- `App.Metadata() AppMetadata` method added to App interface - **affects all App implementations in codebase**
- `SetMetadata(m fyne.AppMetadata)` in app/meta.go for runtime override
- Default metadata when not set: ID="com.example", Name="Fyne App", Version="1.0.0", Build=1

### Target 2: JSON Theme Support
- `theme.FromJSON(data string) (fyne.Theme, error)` and `theme.FromJSONReader(r io.Reader)`
- JSON keys: Colors, Colors-dark, Colors-light, Sizes, Fonts, Icons
- Color resolution: variant-specific → generic Colors → default theme fallback
- Hex formats (with/without #): 3-digit (→ RGB+FF), 4-digit (→ RGBA), 6-digit (→ RGB+FF), 8-digit (→ RGBA)
- 3-digit expansion: "abc" → 0xaa 0xbb 0xcc 0xff

### Target 3: Data Binding Formatting
- `binding.NewSprintf(format string, b ...DataItem) String` in data/binding/sprintf.go
- Auto-updates when any source binding changes via DataChanged listener
- Set() uses fmt.Sscanf for reverse parsing; **Bytes cannot round-trip** (error), URI uses storage.ParseURI
- `binding.StringToStringWithFormat(str String, format string) String` - if format="%s", return original unwrapped

### Target 4: Menu System Enhancements
- `MenuItem.Icon Resource` and `MenuItem.Shortcut Shortcut` fields in fyne/menu.go
- `Menu.Refresh()` - updates all windows displaying this menu + system tray if applicable
- `MainMenu.Refresh()` - updates all windows with this main menu

### Target 5: Toolbar Enhancements
- `ToolbarAction.SetIcon(icon fyne.Resource)` in widget/toolbar.go - updates Icon and refreshes toolbar
- **Return type changes** (interface → concrete):
  - `NewToolbarAction` → `*ToolbarAction`
  - `NewToolbarSpacer` → `*ToolbarSpacer`
  - `NewToolbarSeparator` → `*ToolbarSeparator`

### Target 6: Widget and Container Improvements
- `Container.RemoveAll()` in fyne/container.go - sets Objects=nil, triggers re-layout
- `Container.Add(nil)` **must be no-op** (nil-safe, don't append nil)
- `Hyperlink.OnTapped func()` in widget/hyperlink.go - **when non-nil, overrides URL opening**; when nil, preserve existing behavior
- `Entry.SetMinRowsVisible(count int)` in widget/entry.go - for multi-line entries, overrides default 3 rows when count>0
- `validation.NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator` in data/validation/all.go - chains validators, returns first error

### Target 7: Desktop App Interface
- `desktop.App` interface in driver/desktop/app.go
- Methods: `SetSystemTrayMenu(menu *fyne.Menu)`, `SetSystemTrayIcon(icon fyne.Resource)`

## Critical Constraints

1. **Backward compatibility** - existing APIs unchanged
2. **Interface extension impact** - App.Metadata() requires updating all App implementations in codebase
3. **Package paths are authoritative** - theme, binding, data/validation, driver/desktop, widget, fyne root
4. **Behavioral contracts**:
   - Container.Add(nil) is no-op, not append
   - Hyperlink.OnTapped=nil preserves URL-opening; non-nil calls callback instead
   - Entry.SetMinRowsVisible affects MinSize when count>0
   - Bytes binding cannot round-trip in NewSprintf.Set()

## Completion Evidence Required

- All new types/functions importable from documented paths
- AppMetadata fields match spec (ID, Name, Version string; Build int; Icon Resource)
- JSON theme handles all hex formats, falls back to default for missing values
- Data bindings update reactively on source changes
- MenuItem has Icon and Shortcut fields accessible
- Toolbar constructors return concrete types (not ToolbarItem interface)
- Container.RemoveAll() clears; Add(nil) is no-op
- Hyperlink.OnTapped overrides URL opening when set
- Entry.SetMinRowsVisible affects MinSize
- NewAllStrings chains validators
- desktop.App interface defines system tray API
