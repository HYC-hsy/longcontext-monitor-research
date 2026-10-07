# Task Book: Cross-Platform GUI Toolkit Development

## Task Authority
Full requirements: task/original_task.txt (178 lines)
Environment: Offline, no external references available

## Core Constraints

**Backward Compatibility**: Existing APIs must remain unchanged. This is a library used by external code.

**App Interface is Widely Implemented**: The `App` interface already has multiple concrete implementations throughout the codebase. Adding `Metadata() AppMetadata` requires updating ALL implementations.

## Seven Independent Targets

1. **App Metadata System**: `AppMetadata` struct in root fyne package (app.go), `App.Metadata()` method, `app.SetMetadata()` in app sub-package (meta.go)
2. **JSON Theme Support**: `theme.FromJSON()` and `FromJSONReader()` with color/size/font/icon overrides
3. **Data Binding Formatting**: `binding.NewSprintf()` and `StringToStringWithFormat()` for reactive formatted bindings
4. **Menu Enhancements**: Add `Icon` and `Shortcut` fields to `MenuItem`, add `Refresh()` to `Menu` and `MainMenu`
5. **Toolbar Enhancements**: `ToolbarAction.SetIcon()`, change constructors to return concrete types
6. **Widget/Container Improvements**: `Container.RemoveAll()`, nil-safe `Add()`, `Hyperlink.OnTapped`, `Entry.SetMinRowsVisible()`, `validation.NewAllStrings()`
7. **Desktop App Interface**: New `driver/desktop/app.go` with `desktop.App` interface for system tray

## Critical Specifications

### AppMetadata (Target 1)
- Fields: `ID string`, `Name string`, `Version string`, `Build int`, `Icon Resource`
- Defaults when not set: `ID: "com.example"`, `Name: "Fyne App"`, `Version: "1.0.0"`, `Build: 1`
- Location: root fyne package (app.go)
- SetMetadata function: in app sub-package (meta.go)

### JSON Theme Hex Color Parsing (Target 2)
Support with or without `#` prefix:
- 3 digits: `"abc"` → `0xaa 0xbb 0xcc 0xff`
- 4 digits: `"abcd"` → `0xaa 0xbb 0xcc 0xdd` (note: `#rgb` with 4 chars = `#` + 3-digit)
- 6 digits: `"a1b2c3"` → `0xa1 0xb2 0xc3 0xff`
- 8 digits: `"a1b2c3f4"` → `0xa1 0xb2 0xc3 0xf4`
- Invalid format returns transparent with error

Color resolution: variant-specific (`Colors-dark`/`Colors-light`) checked first, then generic `Colors`, then default theme

### Data Binding Formatting (Target 3)
- `NewSprintf(format string, b ...DataItem) String` in binding package (data/binding/sprintf.go)
- Reactive: when any source binding changes, reformats via `fmt.Sprintf`
- `Set()` parses back via `fmt.Sscanf`
- Special handling: `Bytes` cannot round-trip (error), `URI` parsed via `storage.ParseURI`
- `StringToStringWithFormat`: if format is `"%s"`, return original binding directly (no wrapping)

### Entry Min Rows (Target 6)
- Default minimum visible rows: 3
- `SetMinRowsVisible(count int)`: overrides default when count > 0
- Setting to 2 makes shorter, setting to 5 makes taller

### Toolbar Constructors (Target 5)
Must return concrete types, not `ToolbarItem` interface:
- `NewToolbarAction` → `*ToolbarAction`
- `NewToolbarSpacer` → `*ToolbarSpacer`
- `NewToolbarSeparator` → `*ToolbarSeparator`

### Container.Add Nil Safety (Target 6)
`Add(nil)` must be a no-op (nil not appended to Objects)

### Validation Chaining (Target 6)
`NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator` in data/validation (all.go)
- Returns first error encountered, or nil if all pass

## Package Structure Understanding
- Root fyne package: app.go, container.go, menu.go
- app sub-package: contains app implementations
- theme package: theme-related functions
- binding package: data/binding/
- validation package: data/validation/
- widget package: widget/
- driver/desktop package: desktop-specific interfaces

## Completion Evidence Requirements
Per task: "All new types, functions, and methods are importable from their documented paths"
- Importability requires actual implementation in the specified files/packages
- Behavioral requirements like reactive updates, parsing correctness, nil-safety must be verifiable
- Backward compatibility must be preserved
