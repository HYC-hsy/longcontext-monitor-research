# Task Book: Cross-Platform GUI Toolkit Development

## Mission
Implement 7 independent feature targets for a Go-based cross-platform GUI toolkit (Fyne). All features must maintain backward compatibility.

## Global Constraints

**Backward Compatibility**: Existing APIs cannot change. New methods on interfaces require updating ALL concrete implementations in the codebase.

**Package Structure**: This is the root `fyne` package at `/app`. Subpackages include:
- `app/` - application implementation
- `data/binding/` - data binding system
- `data/validation/` - validation utilities  
- `driver/desktop/` - desktop-specific interfaces
- `theme/` - theming system
- `widget/` - UI widgets

**App Interface Warning**: The `App` interface is widely-implemented. Adding `Metadata()` method requires finding and updating every concrete `App` implementation.

## Target 1: App Metadata System

**Purpose**: Runtime access to app identity (name, version, build, ID, icon).

**Key Requirements**:
- `AppMetadata` struct in root package (`app.go`) with fields: `ID string`, `Name string`, `Version string`, `Build int`, `Icon Resource`
- `App.Metadata() AppMetadata` method added to App interface
- `app.SetMetadata(m fyne.AppMetadata)` function in `app/meta.go`
- Defaults: `ID: "com.example"`, `Name: "Fyne App"`, `Version: "1.0.0"`, `Build: 1`

**Critical**: Must update ALL concrete App implementations in codebase.

## Target 2: JSON Theme Support

**Purpose**: Declarative theme definition via JSON instead of Go code.

**Key Requirements**:
- `theme.FromJSON(data string) (fyne.Theme, error)` 
- `theme.FromJSONReader(r io.Reader) (fyne.Theme, error)`
- JSON keys: `Colors`, `Colors-dark`, `Colors-light`, `Sizes`, `Fonts`, `Icons`
- Color resolution order: variant-specific → generic Colors → default theme

**Hex Color Parsing Rules** (with or without `#`):
- 3 digits: `"abc"` → `0xaa 0xbb 0xcc 0xff`
- 4 digits: `"abcd"` → `0xaa 0xbb 0xcc 0xdd`
- 6 digits: `"a1b2c3"` → `0xa1 0xb2 0xc3 0xff`  
- 8 digits: `"a1b2c3f4"` → `0xa1 0xb2 0xc3 0xf4`
- Invalid → transparent + error

**Font names**: `"regular"`, `"bold"`, `"boldItalic"`, `"monospace"`

## Target 3: Data Binding Formatting

**Purpose**: Sprintf-style formatted bindings that combine multiple typed sources.

**Key Requirements**:
- `binding.NewSprintf(format string, b ...DataItem) String` in `data/binding/sprintf.go`
- Returns String binding that updates when any source changes
- `Get()` returns formatted string; propagates source errors
- `Set(str)` uses `fmt.Sscanf` to reverse-parse into sources
- Special handling: `Bytes` cannot round-trip (error), `URI` uses `storage.ParseURI`
- `binding.StringToStringWithFormat(str String, format string) String` - if format is `"%s"`, return original binding unwrapped

## Target 4: Menu System Enhancements

**Key Requirements**:
- Add `Icon Resource` field to `MenuItem` struct in `menu.go`
- Add `Shortcut Shortcut` field to `MenuItem` struct  
- `Menu.Refresh()` method - updates all windows displaying this menu
- `MainMenu.Refresh()` method - updates all windows with this main menu

## Target 5: Toolbar Enhancements

**Key Requirements**:
- `ToolbarAction.SetIcon(icon fyne.Resource)` method in `widget/toolbar.go`
- Change `NewToolbarAction` return type from `ToolbarItem` to `*ToolbarAction`
- Change `NewToolbarSpacer` return type from `ToolbarItem` to `*ToolbarSpacer`
- Change `NewToolbarSeparator` return type from `ToolbarItem` to `*ToolbarSeparator`

## Target 6: Widget and Container Improvements

**Five independent improvements**:

1. **Container.RemoveAll()** - sets `Objects` to `nil`, triggers re-layout (in `container.go`)
2. **Nil-safe Container.Add()** - passing `nil` is a no-op
3. **Hyperlink.OnTapped callback** - `OnTapped func()` field in `widget/hyperlink.go`. When non-nil, calls this instead of opening URL.
4. **Entry.SetMinRowsVisible(count int)** - method in `widget/entry.go` for multi-line entries. Overrides default (3 rows). Used in MinSize() calculation.
5. **validation.NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator** - in `data/validation/all.go`. Chains validators, returns first error.

## Target 7: Desktop App Interface

**Purpose**: Define desktop-specific application interface for system tray support.

**Key Requirements**:
- New interface `desktop.App` in `driver/desktop/app.go`
- Two methods:
  - `SetSystemTrayMenu(menu *fyne.Menu)`
  - `SetSystemTrayIcon(icon fyne.Resource)`

## Completion Evidence Requirements

Each target verified by:
- Types/functions importable from documented paths
- Correct struct field names and types
- Behavioral correctness (JSON parsing, binding updates, etc.)
- All concrete implementations updated where interfaces change
- No breaking changes to existing APIs

## Known Risk Areas

1. **App.Metadata()** - Must find ALL App implementations, including test mocks
2. **Toolbar return types** - Breaking API change, but explicitly required
3. **Hex color parsing edge cases** - 4-digit format with `#` prefix needs careful handling
4. **Binding lifecycle** - NewSprintf must properly attach/detach listeners
5. **Menu refresh** - Must update both window menus and system tray menus
