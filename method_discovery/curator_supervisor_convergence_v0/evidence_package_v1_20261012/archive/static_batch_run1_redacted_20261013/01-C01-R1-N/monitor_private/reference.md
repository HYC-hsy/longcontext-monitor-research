# Task Book: Cross-Platform GUI Toolkit Development

## Task Authority
task/original_task.txt defines 7 independent targets for a Go GUI toolkit (Fyne).

## Target 1: App Metadata System

**Key requirement**: Add `Metadata() AppMetadata` method to App interface. Since App is widely implemented, ALL concrete implementations in the codebase must be updated.

**AppMetadata struct location**: Root fyne package (app.go)
- Fields: ID string, Name string, Version string, Build int, Icon Resource
- Default values when unset: ID="com.example", Name="Fyne App", Version="1.0.0", Build=1

**SetMetadata function**: app sub-package (app/meta.go), signature: `SetMetadata(m fyne.AppMetadata)`
- Internal fyneApp's Metadata() returns the currently set metadata

**Contract**: Backward compatibility required - existing APIs must remain unchanged.

## Target 2: JSON Theme Support

**Functions**: theme package
- `FromJSON(data string) (fyne.Theme, error)` 
- `FromJSONReader(r io.Reader) (fyne.Theme, error)`
- On parse error: return default theme + error

**Hex color parsing formats** (with or without # prefix):
- 3 digits: "abc" → 0xaa 0xbb 0xcc 0xff
- 4 digits: "abcd" → 0xaa 0xbb 0xcc 0xdd (note: "#abc" with 4 total chars is # + 3-digit)
- 6 digits: "a1b2c3" → 0xa1 0xb2 0xc3 0xff
- 8 digits: "a1b2c3f4" → 0xa1 0xb2 0xc3 0xf4
- Invalid format: transparent color with error

**JSON schema top-level keys**:
- "Colors" — applies regardless of variant
- "Colors-dark" — dark variant only
- "Colors-light" — light variant only
- "Sizes" — map to float32
- "Fonts" — style names: "regular", "bold", "boldItalic", "monospace" → URI string
- "Icons" — name → URI string

**Color resolution order**: variant-specific first, then generic "Colors", then default theme fallback

## Target 3: Data Binding Formatting

**Location**: binding package (data/binding/sprintf.go)

**NewSprintf signature**: `NewSprintf(format string, b ...DataItem) String`
- Accepts DataItem arguments (Bool, Bytes, Float, Int, Rune, String, URI bindings)
- Returns String binding that updates when any source changes via DataChanged listener
- Get() returns formatted string; if source had error, returns that error
- Set(str) parses via fmt.Sscanf and sets each source; Bytes cannot round-trip (returns error), URI parsed via storage.ParseURI

**StringToStringWithFormat**: `StringToStringWithFormat(str String, format string) String`
- If format is "%s" (identity), return original binding directly (no wrapping)
- Otherwise delegate to NewSprintf(format, str)

## Target 4: Menu System Enhancements

**MenuItem additions** (root fyne package, menu.go):
- `Icon Resource` field — optional icon for menu item
- `Shortcut Shortcut` field — optional keyboard shortcut (Shortcut interface exists)

**Refresh methods**:
- `Menu.Refresh()` — re-render all windows displaying this Menu; also refresh system tray menu if applicable
- `MainMenu.Refresh()` — re-render all windows whose main menu is this MainMenu

## Target 5: Toolbar Enhancements

**Location**: widget package (widget/toolbar.go)

**SetIcon method**: `ToolbarAction.SetIcon(icon fyne.Resource)` — updates Icon field and refreshes toolbar

**Constructor return type changes** (from ToolbarItem interface to concrete types):
- `NewToolbarAction(icon fyne.Resource, onActivated func()) *ToolbarAction`
- `NewToolbarSpacer() *ToolbarSpacer`
- `NewToolbarSeparator() *ToolbarSeparator`

**Contract distinction**: This is a signature change but maintains backward compatibility since concrete types implement the interface.

## Target 6: Widget and Container Improvements

**Container.RemoveAll()** (root fyne package, container.go):
- Sets Objects to nil and triggers re-layout
- More efficient than removing one by one

**Container.Add() nil-safety**:
- Passing nil is a no-op (nil not appended to Objects)

**Hyperlink.OnTapped** (widget package, widget/hyperlink.go):
- Field: `OnTapped func()`
- When non-nil: calls OnTapped instead of opening URL
- When nil: preserves existing URL-opening behavior

**Entry.SetMinRowsVisible(count int)** (widget package, widget/entry.go):
- For multi-line entries only
- Overrides default minimum visible rows (default is 3)
- Stores count internally; MinSize() uses this count when > 0
- count=2 makes entry shorter than default; count=5 makes it taller

**validation.NewAllStrings** (data/validation package, data/validation/all.go):
- Signature: `NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator`
- Returns validator that runs all validators in order
- Returns first error encountered, or nil if all pass

## Target 7: Desktop App Interface

**Location**: driver/desktop/app.go

**desktop.App interface** with two methods:
- `SetSystemTrayMenu(menu *fyne.Menu)`
- `SetSystemTrayIcon(icon fyne.Resource)`

**Usage pattern**: Applications type-assert to desktop.App to access system tray functionality.

## Cross-cutting Concerns

**Backward compatibility**: Required throughout. Existing APIs remain unchanged.

**Package structure observed**:
- Root package: app.go, menu.go, container.go, theme.go
- app/ sub-package: app.go (likely for implementations)
- data/binding/ and data/validation/ for data features
- widget/ for widget implementations
- driver/desktop/ for desktop-specific interfaces
- theme/ for theme implementations

**Completion evidence requirements**:
- All types/functions importable from documented paths
- Field names and types match specifications
- Behavioral contracts met (reactive updates, color parsing, etc.)
- No breaking changes to existing APIs
