# Task Book: Cross-Platform GUI Toolkit Development

## Mission
Deliver 7 targets for a Go GUI toolkit: app metadata, JSON themes, formatted data bindings, menu enhancements, toolbar improvements, widget/container improvements, and desktop app interface.

## Critical Constraints

**Backward Compatibility**: Existing APIs must remain unchanged. Adding methods to interfaces requires updating all implementations in the codebase.

**Package Structure**:
- Root `fyne` package: app.go, container.go, menu.go
- `app` sub-package: meta.go for SetMetadata
- `theme` package: JSON parsing functions
- `binding` package: sprintf.go for formatted bindings
- `widget` package: toolbar.go, hyperlink.go, entry.go
- `data/validation` package: all.go for validator chaining
- `driver/desktop` package: app.go for desktop interface

## Target 1: App Metadata System

**Contract**: Runtime identity/version query via `app.Metadata()`

**Types** (root fyne package, app.go):
- `AppMetadata` struct: `ID string`, `Name string`, `Version string`, `Build int`, `Icon Resource`

**Interface Change** (requires updating ALL App implementations):
- Add `Metadata() AppMetadata` to `App` interface
- Default values: ID="com.example", Name="Fyne App", Version="1.0.0", Build=1

**Runtime Override** (app/meta.go):
- `SetMetadata(m fyne.AppMetadata)` function
- Internal fyneApp type returns currently set metadata

## Target 2: JSON Theme Support

**Contract**: Declarative theme definition with fallback to defaults

**API** (theme package):
- `FromJSON(data string) (fyne.Theme, error)` - on parse error, return default theme + error
- `FromJSONReader(r io.Reader) (fyne.Theme, error)`

**JSON Schema**:
- `Colors` - generic color map
- `Colors-dark` - dark variant overrides
- `Colors-light` - light variant overrides
- `Sizes` - map to float32
- `Fonts` - map style name (regular/bold/boldItalic/monospace) to URI
- `Icons` - map icon name to URI
- Resolution order: variant-specific → Colors → default theme

**Hex Color Parsing** (must support all formats with/without #):
- 3 digits: "abc" → 0xaa 0xbb 0xcc 0xff
- 4 digits: "abcd" → 0xaa 0xbb 0xcc 0xdd
- 6 digits: "a1b2c3" → 0xa1 0xb2 0xc3 0xff
- 8 digits: "a1b2c3f4" → 0xa1 0xb2 0xc3 0xf4
- Invalid → transparent + error

## Target 3: Data Binding Formatting

**Contract**: Reactive formatted strings from multiple typed bindings

**API** (binding package, sprintf.go):
- `NewSprintf(format string, b ...DataItem) String`
  - Returns String binding that updates when any source changes
  - Get() returns formatted string or source error
  - Set() uses fmt.Sscanf to parse back and update sources
  - Bytes cannot round-trip (error)
  - URI parsed via storage.ParseURI
- `StringToStringWithFormat(str String, format string) String`
  - If format is "%s", return original binding directly (no wrap)
  - Otherwise delegate to NewSprintf

## Target 4: Menu System Enhancements

**Contract**: Icons, shortcuts, and runtime refresh

**MenuItem Fields** (fyne package, menu.go):
- `Icon Resource` - optional icon
- `Shortcut Shortcut` - optional keyboard shortcut (Shortcut interface exists)

**Refresh Methods**:
- `Menu.Refresh()` - updates all windows displaying this menu (including system tray)
- `MainMenu.Refresh()` - updates all windows with this MainMenu

## Target 5: Toolbar Enhancements

**Contract**: Dynamic icon changes and concrete return types

**API Changes** (widget package, toolbar.go):
- `ToolbarAction.SetIcon(icon fyne.Resource)` - updates Icon field and refreshes toolbar
- `NewToolbarAction` returns `*ToolbarAction` (not ToolbarItem interface)
- `NewToolbarSpacer` returns `*ToolbarSpacer` (not ToolbarItem interface)
- `NewToolbarSeparator` returns `*ToolbarSeparator` (not ToolbarItem interface)

## Target 6: Widget and Container Improvements

**Container** (fyne package, container.go):
- `RemoveAll()` - sets Objects to nil, triggers re-layout (more efficient than Remove loop)
- `Add(nil)` - must be no-op (nil not appended)

**Hyperlink** (widget package, hyperlink.go):
- `OnTapped func()` field
- When non-nil: calls OnTapped instead of opening URL
- When nil: preserves existing URL-opening behavior

**Entry** (widget package, entry.go):
- `SetMinRowsVisible(count int)` method
- For multi-line entries, overrides default minimum rows (default is 3)
- MinSize() uses this count when > 0
- count=2 makes shorter, count=5 makes taller

**Validation** (data/validation package, all.go):
- `NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator`
- Runs all validators in order
- Returns first error or nil if all pass

## Target 7: Desktop App Interface

**Contract**: Type-assertion API for desktop-specific capabilities

**API** (driver/desktop/app.go):
- `desktop.App` interface with methods:
  - `SetSystemTrayMenu(menu *fyne.Menu)`
  - `SetSystemTrayIcon(icon fyne.Resource)`

## Acceptance Criteria

- All APIs importable from documented paths
- Backward compatibility preserved
- Field/type names match specification exactly
- JSON parsing handles all hex formats correctly
- Formatted bindings update reactively
- MenuItem icon/shortcut accessible
- Toolbar constructors return concrete types
- Container.RemoveAll() clears; Add(nil) is no-op
- Hyperlink.OnTapped overrides URL opening when set
- Entry.SetMinRowsVisible affects MinSize
- NewAllStrings returns first error
- desktop.App defines system tray surface

## Key Distinctions

**Interface Extension Impact**: Adding Metadata() to App interface requires updating every concrete App implementation in the codebase, not just the primary one.

**JSON Theme Error Handling**: Parse errors return (default theme, error), not (nil, error). This allows graceful degradation.

**Hex Color Special Case**: 4-digit hex with # prefix is "#" + 3-digit format (not 4-digit RGBA).

**Format Identity Optimization**: StringToStringWithFormat must return original binding when format is "%s" to avoid unnecessary wrapping.

**Toolbar Return Type Change**: This is a breaking change that exposes concrete types. Existing code using ToolbarItem interface variables will continue to work.
