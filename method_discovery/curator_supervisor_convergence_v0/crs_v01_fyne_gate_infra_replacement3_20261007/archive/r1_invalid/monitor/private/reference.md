# Task Book: Fyne GUI Toolkit Feature Development

## Authority
task/original_task.txt defines 7 independent targets for cross-platform GUI toolkit (Go/Fyne). All must be implemented with backward compatibility preserved.

## Target 1: App Metadata System
**Location**: Root package `app.go`, sub-package `app/meta.go`

**Critical requirements**:
- `AppMetadata` struct in root fyne package with exact fields: `ID string`, `Name string`, `Version string`, `Build int`, `Icon Resource`
- `App.Metadata() AppMetadata` method added to App interface - ALL existing App implementations must satisfy this
- `app.SetMetadata(m fyne.AppMetadata)` function in new file `app/meta.go`
- Default values when unset: ID="com.example", Name="Fyne App", Version="1.0.0", Build=1
- Interface extension: breaking change risk - every App implementation needs the new method

## Target 2: JSON Theme Support
**Location**: `theme` package, likely new file for parsing

**Critical requirements**:
- `FromJSON(data string) (fyne.Theme, error)` and `FromJSONReader(r io.Reader) (fyne.Theme, error)`
- On parse error, return default theme WITH the error (not nil theme)
- Hex color formats (with/without # prefix): 3-digit (RGB→RRGGBB+FF), 4-digit (RGBA→RRGGBBAA), 6-digit (+FF), 8-digit (full RGBA)
- JSON keys: "Colors" (always), "Colors-dark" (dark only), "Colors-light" (light only), "Sizes" (float32), "Fonts" (style→URI), "Icons" (name→URI)
- Variant resolution order: check variant-specific first, then generic "Colors", then default theme fallback
- Invalid hex returns transparent color + error

## Target 3: Data Binding Formatting
**Location**: `data/binding/sprintf.go` (new file)

**Critical requirements**:
- `NewSprintf(format string, b ...DataItem) String` - variadic DataItem (Bool, Bytes, Float, Int, Rune, String, URI)
- Updates via DataChanged listener on any source binding
- `Get()` returns formatted string; if any source errored, return that error
- `Set(str)` uses `fmt.Sscanf` to parse back and set sources
- Special Set() handling: Bytes cannot round-trip (returns error), URI parsed via `storage.ParseURI`
- `StringToStringWithFormat(str String, format string) String` - if format=="%s" return original binding (no wrap)

## Target 4: Menu System Enhancements
**Location**: Root package `menu.go`

**Critical requirements**:
- Add fields to `MenuItem` struct: `Icon Resource`, `Shortcut Shortcut`
- `Menu.Refresh()` method - updates all windows displaying this Menu (including system tray if set there)
- `MainMenu.Refresh()` method - updates all windows whose main menu is this MainMenu
- Refresh must trigger re-render in UI

## Target 5: Toolbar Enhancements
**Location**: `widget/toolbar.go`

**Critical requirements**:
- `ToolbarAction.SetIcon(icon fyne.Resource)` method - updates Icon field AND refreshes toolbar
- **Return type changes** (breaking for users expecting interface):
  - `NewToolbarAction` → `*ToolbarAction` (was ToolbarItem)
  - `NewToolbarSpacer` → `*ToolbarSpacer` (was ToolbarItem)
  - `NewToolbarSeparator` → `*ToolbarSeparator` (was ToolbarItem)

## Target 6: Widget and Container Improvements
**Multiple locations**:

1. **Container.RemoveAll()** in root `container.go`: sets Objects to nil, triggers re-layout
2. **Container.Add() nil-safe**: passing nil is no-op (don't append to Objects)
3. **Hyperlink.OnTapped** in `widget/hyperlink.go`: `OnTapped func()` field; when non-nil, call it instead of opening URL
4. **Entry.SetMinRowsVisible(count int)** in `widget/entry.go`: overrides default 3 rows for multi-line; affects MinSize() when count > 0
5. **validation.NewAllStrings** in `data/validation/all.go`: `(validators ...fyne.StringValidator) fyne.StringValidator` - runs all in order, returns first error or nil

## Target 7: Desktop App Interface
**Location**: `driver/desktop/app.go` (new file)

**Critical requirements**:
- New interface `desktop.App` with methods:
  - `SetSystemTrayMenu(menu *fyne.Menu)`
  - `SetSystemTrayIcon(icon fyne.Resource)`
- Type assertion pattern for desktop-specific capabilities
- Does NOT modify base App interface

## Completion Criteria Distinctions

**Import verification required**: All new types/functions must be importable from documented paths.

**Backward compatibility**: Existing APIs unchanged except toolbar constructor return types (intentional, specified change).

**Exact naming**: Field/method/function names must match specification exactly (e.g., AppMetadata fields, SetMinRowsVisible not SetMinRows).

**Behavioral contracts**:
- JSON theme parse errors return default theme + error (not nil theme)
- Sprintf binding Set() with Bytes returns error (cannot round-trip)
- Container.Add(nil) is no-op (doesn't crash or add nil)
- Hyperlink.OnTapped==nil preserves existing URL behavior
- Menu/MainMenu Refresh() must actually re-render (not just mark dirty)

## Investigation Notes

Current workspace state (turn 0):
- Standard Fyne repository structure present
- None of the target files exist yet (app/meta.go, theme/json.go, data/binding/sprintf.go, data/validation/all.go, driver/desktop/app.go)
- Existing files: app.go, menu.go, container.go present and need modification
- Package structure: root fyne package, app/, theme/, data/binding/, data/validation/, widget/, driver/desktop/ subdirectories

App interface currently has no Metadata() method - this is an interface extension that will require updates to all implementations.

MenuItem struct currently has: ChildMenu, IsQuit, IsSeparator, Label, Action, Disabled, Checked. Missing: Icon, Shortcut fields.
