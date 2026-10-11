# Task Book: Fyne GUI Toolkit Development

## Task Authority
task/original_task.txt — 7 independent targets for Go GUI toolkit

## Critical Constraints

### Backward Compatibility
Existing APIs remain unchanged. This is a library addition, not a breaking change.

### App Interface Extension Impact
Adding `Metadata() AppMetadata` to the `App` interface (Target 1) requires updating ALL concrete implementations in the codebase. The App interface is "widely-implemented" per task specification. Missing even one implementation will break compilation.

### Package Structure Requirements
- `AppMetadata` struct: root `fyne` package in `app.go`
- `SetMetadata` function: `app` sub-package in `app/meta.go`
- JSON theme functions: `theme` package
- `NewSprintf`: `binding` package in `data/binding/sprintf.go`
- Menu enhancements: root `fyne` package in `menu.go`
- Toolbar enhancements: `widget` package in `widget/toolbar.go`
- Container methods: root `fyne` package in `container.go`
- Hyperlink field: `widget` package in `widget/hyperlink.go`
- Entry method: `widget` package in `widget/entry.go`
- Validator: `data/validation` package in `data/validation/all.go`
- Desktop interface: `driver/desktop` package in `driver/desktop/app.go`

## Target-Specific Durable Facts

### Target 1: App Metadata
Default values when no metadata set: `ID: "com.example"`, `Name: "Fyne App"`, `Version: "1.0.0"`, `Build: 1`

### Target 2: JSON Theme
**Hex color format requirements** (all with or without `#` prefix):
- 3 digits: `"abc"` → `0xaa 0xbb 0xcc 0xff` (digit doubling)
- 4 digits: `"abcd"` → `0xaa 0xbb 0xcc 0xdd` (digit doubling with alpha)
- 6 digits: `"a1b2c3"` → `0xa1 0xb2 0xc3 0xff`
- 8 digits: `"a1b2c3f4"` → `0xa1 0xb2 0xc3 0xf4`
- Invalid format: transparent color with error

**Color resolution order**: variant-specific (`Colors-dark`/`Colors-light`) checked first, then generic `Colors`, then default theme fallback.

**On parse error**: return default theme along with the error (not nil theme).

### Target 3: Data Binding Formatting
`NewSprintf` combines multiple typed bindings (`Bool`, `Bytes`, `Float`, `Int`, `Rune`, `String`, `URI`) into formatted string.

**Reactivity**: When any source binding changes via `DataChanged` listener, the formatted result automatically updates.

**Reverse parsing via Set()**: Uses `fmt.Sscanf` semantics with special cases:
- `Bytes`: cannot round-trip, returns error
- `URI`: parsed via `storage.ParseURI`

**StringToStringWithFormat optimization**: If format is `"%s"` (identity), return original binding directly (no wrapping).

### Target 5: Toolbar Constructor Return Types
Change from interface to concrete types:
- `NewToolbarAction`: return `*ToolbarAction` (not `ToolbarItem`)
- `NewToolbarSpacer`: return `*ToolbarSpacer` (not `ToolbarItem`)
- `NewToolbarSeparator`: return `*ToolbarSeparator` (not `ToolbarItem`)

### Target 6: Widget Improvements
**Container.Add nil-safe**: Passing `nil` must be no-op (do not append to Objects).

**Hyperlink.OnTapped override semantics**: When `OnTapped` is non-nil, it replaces URL-opening behavior. When nil, preserve existing URL-opening behavior.

**Entry.SetMinRowsVisible**: For multi-line entries only. Setting count to 2 makes entry shorter than default (3); setting to 5 makes it taller. Count stored internally; MinSize() uses it when > 0.

### Target 7: Desktop App Interface
Define in `driver/desktop/app.go`, not root package. Applications type-assert to `desktop.App` for desktop-specific functionality.

## Completion Evidence Requirements
All targets are structural additions. Compilation success is primary evidence. Behavioral targets (binding reactivity, menu refresh, hyperlink callback override, entry min size) require observing actual runtime behavior or test assertions that distinguish the required behavior from absence.
