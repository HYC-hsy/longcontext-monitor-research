# Task Book: Cross-Platform GUI Toolkit Development

## Mission Authority
task/original_task.txt — Complete 7 targets for Fyne GUI toolkit release

## Critical Constraints

### Backward Compatibility
All existing APIs must remain unchanged. This is a library used by external developers.

### Interface Extension Impact
`App` interface is widely implemented. Adding `Metadata() AppMetadata` requires updating ALL concrete implementations in the codebase, not just the primary fyneApp.

## Target 1: App Metadata System

**Package locations (mandated):**
- `AppMetadata` struct: root `fyne` package in `app.go`
- `SetMetadata` function: `app` sub-package in `app/meta.go` (new file)

**Struct field names (exact):**
- `ID string` — unique identifier (e.g., "com.example")
- `Name string` — human-friendly name (e.g., "Fyne App")
- `Version string` — semantic version (e.g., "1.0.0")
- `Build int` — build number (e.g., 1)
- `Icon Resource` — optional icon (Resource type already exists)

**Default values when not set:**
- ID: "com.example"
- Name: "Fyne App"
- Version: "1.0.0"
- Build: 1

**Method signature:** `Metadata() AppMetadata` on App interface

## Target 2: JSON Theme Support

**Package location:** `theme` package
**Functions:** `FromJSON(data string)` and `FromJSONReader(r io.Reader)` both return `(fyne.Theme, error)`

**Hex color parsing (exact formats):**
- 3 digits: `"abc"` → `0xaa 0xbb 0xcc 0xff` (expand each digit, full alpha)
- 4 digits: `"abcd"` → `0xaa 0xbb 0xcc 0xdd` (expand each digit including alpha)
- 6 digits: `"a1b2c3"` → `0xa1 0xb2 0xc3 0xff` (direct hex, full alpha)
- 8 digits: `"a1b2c3f4"` → `0xa1 0xb2 0xc3 0xf4` (direct hex with alpha)
- All formats work with or without `#` prefix
- Invalid format returns transparent color with error

**JSON schema keys:**
- `"Colors"` — generic colors for both variants
- `"Colors-dark"` — dark variant only
- `"Colors-light"` — light variant only
- `"Sizes"` — map to float32
- `"Fonts"` — map font style ("regular", "bold", "boldItalic", "monospace") to URI string
- `"Icons"` — map icon name to URI string

**Color resolution order:** variant-specific first, then generic "Colors", then default theme fallback

**Error handling:** On parse error, return default theme + error (not nil theme)

## Target 3: Data Binding Formatting

**Package location:** `binding` package in `data/binding/sprintf.go` (new file)

**Function signature:** `NewSprintf(format string, b ...DataItem) String`

**Behavior:**
- Takes format string and variadic DataItem bindings
- Returns String binding that auto-updates when any source changes
- Uses `fmt.Sprintf` for formatting
- `Get()` returns formatted string or first error from sources
- `Set(str string)` uses `fmt.Sscanf` to parse back to sources
- `Bytes` type cannot round-trip (returns error on Set)
- `URI` type parsed via `storage.ParseURI` (not fmt.Sscanf)

**Function:** `StringToStringWithFormat(str String, format string) String`
- If format is `"%s"` (identity), return original binding directly (optimization)
- Otherwise delegate to `NewSprintf(format, str)`

## Target 4: Menu System Enhancements

**Location:** root `fyne` package in `menu.go`

**New MenuItem fields:**
- `Icon Resource` — optional icon alongside label
- `Shortcut Shortcut` — optional keyboard shortcut (Shortcut interface already exists)

**New methods:**
- `Menu.Refresh()` — re-render all windows displaying this menu (including system tray if set)
- `MainMenu.Refresh()` — re-render all windows whose main menu is this MainMenu

## Target 5: Toolbar Enhancements

**Location:** `widget` package in `widget/toolbar.go`

**Breaking change rationale:** Returning concrete types instead of interface enables access to type-specific fields

**New method:** `ToolbarAction.SetIcon(icon fyne.Resource)` — updates Icon field and refreshes toolbar

**Changed return types (from ToolbarItem interface to concrete):**
- `NewToolbarAction(icon fyne.Resource, onActivated func()) *ToolbarAction`
- `NewToolbarSpacer() *ToolbarSpacer`
- `NewToolbarSeparator() *ToolbarSeparator`

## Target 6: Widget and Container Improvements

**Container.RemoveAll()** — root `fyne` package in `container.go`
- Sets Objects to nil
- Triggers re-layout
- More efficient than removing one by one

**Container.Add(nil) defensive behavior:**
- Must be no-op (do not append nil to Objects)
- Existing Add() must be updated

**Hyperlink.OnTapped callback** — `widget` package in `widget/hyperlink.go`
- Field: `OnTapped func()`
- When non-nil: call OnTapped instead of opening URL
- When nil: preserve existing URL-opening behavior (not additive, it's override)

**Entry.SetMinRowsVisible(count int)** — `widget` package in `widget/entry.go`
- Only affects multi-line entries
- Overrides default minimum (3 rows)
- Used in MinSize() calculation when count > 0
- count=2 makes shorter; count=5 makes taller

**NewAllStrings validator** — `data/validation` package in `data/validation/all.go` (new file)
- Signature: `NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator`
- Runs all validators in order
- Returns first error encountered (short-circuit)
- Returns nil if all pass

## Target 7: Desktop App Interface

**Package location:** `driver/desktop` package in `driver/desktop/app.go` (new file)

**Interface name:** `desktop.App`

**Methods:**
- `SetSystemTrayMenu(menu *fyne.Menu)` — sets system tray menu
- `SetSystemTrayIcon(icon fyne.Resource)` — sets system tray icon

**Usage pattern:** Type-assert App to desktop.App for desktop-specific features

## Acceptance Evidence Requirements

**Not sufficient for behavioral claims:**
- File existence
- Symbol presence
- Compilation success
- Local helper calls

**Behavioral contracts require:**
- Tests that exercise the actual behavior
- Tests that distinguish correct from incorrect states
- Observation of runtime behavior matching specification

## Structural Facts

**Existing types confirmed:**
- `Resource` interface exists in root fyne package
- `Shortcut` interface exists in root fyne package
- `DataItem` interface exists in binding package
- `Storage` with `ParseURI` exists
- Menu and MenuItem structs exist
- Container struct exists in root package

**No work started:** All 7 targets are unimplemented (confirmed via file checks)
