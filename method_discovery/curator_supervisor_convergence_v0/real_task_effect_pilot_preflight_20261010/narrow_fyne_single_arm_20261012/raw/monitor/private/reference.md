# Task Book: Cross-Platform GUI Toolkit Enhancements

## Task Interpretation

This task extends a Go cross-platform GUI toolkit (Fyne) with seven independent features. The work involves adding new APIs while maintaining backward compatibility. All targets must be importable from their documented packages, and existing APIs must remain unchanged.

## Target Overview

**Target 1: App Metadata System** — Runtime access to app identity (name, version, build, ID, icon)
**Target 2: JSON Theme Support** — Declarative theme definition via JSON parsing
**Target 3: Data Binding Formatting** — sprintf-style formatted bindings combining multiple data sources
**Target 4: Menu System Enhancements** — Icons, shortcuts, and runtime refresh for menus
**Target 5: Toolbar Enhancements** — Dynamic icon changes and concrete return types
**Target 6: Widget/Container Improvements** — Container clear, hyperlink callbacks, entry rows, validator chaining
**Target 7: Desktop App Interface** — System tray integration interface definition

## Target 1: App Metadata System

**Core Contract:**
- `AppMetadata` struct in root `fyne` package (`app.go`) with fields: `ID string`, `Name string`, `Version string`, `Build int`, `Icon Resource`
- `App.Metadata() AppMetadata` method added to `App` interface
- All existing `App` implementations must satisfy the new method
- `app.SetMetadata(m fyne.AppMetadata)` function in `app` sub-package (`app/meta.go`)
- Default metadata: `ID: "com.example"`, `Name: "Fyne App"`, `Version: "1.0.0"`, `Build: 1`

**Integration Point:** `App` is a widely-implemented interface; all concrete implementations require updates.

## Target 2: JSON Theme Support

**Core Contract:**
- `theme.FromJSON(data string) (fyne.Theme, error)` — parse JSON string
- `theme.FromJSONReader(r io.Reader) (fyne.Theme, error)` — parse from reader
- On parse error: return default theme + error
- JSON schema supports: `Colors`, `Colors-dark`, `Colors-light`, `Sizes`, `Fonts`, `Icons`
- Hex color parsing: 3-digit, 4-digit, 6-digit, 8-digit (with/without `#` prefix)
- Color resolution: variant-specific first, then generic `Colors`, then default theme
- Invalid hex format returns transparent color with error

**Hex Format Details:**
- 3-digit: `"abc"` → `0xaa 0xbb 0xcc 0xff`
- 4-digit: `"abcd"` → `0xaa 0xbb 0xcc 0xdd`
- 6-digit: `"a1b2c3"` → `0xa1 0xb2 0xc3 0xff`
- 8-digit: `"a1b2c3f4"` → `0xa1 0xb2 0xc3 0xf4`

## Target 3: Data Binding Formatting

**Core Contract:**
- `binding.NewSprintf(format string, b ...DataItem) String` in `data/binding/sprintf.go`
- Accepts format string + variadic `DataItem` (Bool, Bytes, Float, Int, Rune, String, URI)
- Returns `String` binding that updates when any source changes
- `Get()` returns formatted string; propagates source errors
- `Set(str string)` uses `fmt.Sscanf` to parse back and set source bindings
- Special handling: `Bytes` cannot round-trip (returns error), `URI` parsed via `storage.ParseURI`
- `binding.StringToStringWithFormat(str String, format string) String` — convenience wrapper; returns original binding if format is `"%s"`

## Target 4: Menu System Enhancements

**Core Contract:**
- `MenuItem.Icon Resource` field in root `fyne` package (`menu.go`)
- `MenuItem.Shortcut Shortcut` field in `MenuItem` struct
- `Menu.Refresh()` method — re-render all windows displaying this menu
- `MainMenu.Refresh()` method — re-render all windows with this main menu

**Integration Point:** Menu refresh must affect windows displaying the menu and system tray if applicable.

## Target 5: Toolbar Enhancements

**Core Contract:**
- `ToolbarAction.SetIcon(icon fyne.Resource)` in `widget` package (`widget/toolbar.go`) — updates icon and refreshes toolbar
- `NewToolbarAction(icon fyne.Resource, onActivated func()) *ToolbarAction` — return concrete type, not interface
- `NewToolbarSpacer() *ToolbarSpacer` — return concrete type
- `NewToolbarSeparator() *ToolbarSeparator` — return concrete type

**Breaking Change Note:** Constructor return type changes from interface to concrete type (backward compatible for assignment but may affect type assertions).

## Target 6: Widget and Container Improvements

**Core Contract:**
- `Container.RemoveAll()` in root `fyne` package (`container.go`) — sets `Objects` to nil, triggers re-layout
- `Container.Add(nil)` — no-op (nil not appended)
- `Hyperlink.OnTapped func()` field in `widget` package (`widget/hyperlink.go`) — overrides URL-opening when non-nil
- `Entry.SetMinRowsVisible(count int)` in `widget` package (`widget/entry.go`) — overrides default minimum rows (default 3) for multi-line entries
- `validation.NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator` in `data/validation` package (`data/validation/all.go`) — chains validators, returns first error

## Target 7: Desktop App Interface

**Core Contract:**
- `desktop.App` interface in `driver/desktop/app.go`
- Methods: `SetSystemTrayMenu(menu *fyne.Menu)` and `SetSystemTrayIcon(icon fyne.Resource)`
- Applications type-assert to `desktop.App` for desktop-specific functionality

## Completion Criteria

1. All new types/functions/methods importable from documented paths
2. Existing APIs unchanged (backward compatibility)
3. `AppMetadata` fields match specified names and types
4. JSON theme parsing handles all hex formats with default fallback
5. Data binding formatting updates reactively on source changes
6. Menu icon/shortcut fields accessible on `MenuItem`
7. Toolbar constructors return concrete types
8. Container operations behave as specified (RemoveAll clears, Add(nil) is no-op)
9. Hyperlink callback overrides URL-opening when set
10. Entry row visibility affects multi-line minimum size
11. Validator chaining returns first error
12. Desktop app interface defines system tray API

## Key Technical Constraints

- Go codebase following idiomatic patterns
- Package structure: root `fyne` package, `app`, `widget`, `theme`, `data/binding`, `data/validation`, `driver/desktop` sub-packages
- Interface additions require updating all implementations
- Reactive data binding system with listener pattern
- Theme system with variant support (light/dark)
- Resource system for icons/fonts using `Resource` and `fyne.Resource` types

## Exposure Requirements

All functionality must be accessible through public APIs in the specified packages. Internal implementation details are not part of the contract, but public behavior must match requirements.
