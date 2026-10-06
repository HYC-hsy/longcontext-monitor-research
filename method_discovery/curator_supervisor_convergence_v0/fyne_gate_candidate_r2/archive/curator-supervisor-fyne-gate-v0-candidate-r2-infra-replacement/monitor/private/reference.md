# Task Book — Durable Cognition for Cross-Platform GUI Toolkit Development

**Authority**: task/original_task.txt (178 lines, sha256: cae5f11a...)

## Mission
Develop 7 targets for a cross-platform GUI toolkit (Fyne for Go): app metadata system, JSON theme support, data binding formatting, menu enhancements, toolbar enhancements, widget/container improvements, and desktop app interface.

## Critical Constraints
- **Backward compatibility**: Existing APIs remain unchanged
- **Offline**: No internet, no reference solutions, no prior-run artifacts
- **Package structure**: Fyne uses root `fyne` package and sub-packages (`app`, `widget`, `data/binding`, `data/validation`, `theme`, `driver/desktop`, etc.)

---

## Target 1: App Metadata System

### Exact Requirements
- **Location**: `app.go` in root fyne package, `app/meta.go` in app sub-package
- **Struct**: `AppMetadata` in root fyne package with fields:
  - `ID string` (e.g., "com.example")
  - `Name string` (e.g., "Fyne App")
  - `Version string` (e.g., "1.0.0")
  - `Build int` (e.g., 1)
  - `Icon Resource` (Resource type already exists)
- **Interface change**: Add `Metadata() AppMetadata` to `App` interface
- **Implementation impact**: ALL existing App implementations must satisfy new method
- **Function**: `SetMetadata(m fyne.AppMetadata)` in `app/meta.go`
- **Default values**: ID="com.example", Name="Fyne App", Version="1.0.0", Build=1

---

## Target 2: JSON Theme Support

### Exact Requirements
- **Location**: `theme` package
- **Functions**:
  - `FromJSON(data string) (fyne.Theme, error)`
  - `FromJSONReader(r io.Reader) (fyne.Theme, error)`
  - On parse error: return default theme + error
  
### JSON Schema
- `"Colors"` — generic colors (all variants)
- `"Colors-dark"` — dark variant only
- `"Colors-light"` — light variant only
- `"Sizes"` — map to float32
- `"Fonts"` — map of "regular", "bold", "boldItalic", "monospace" to URI
- `"Icons"` — map to URI
- **Resolution**: variant-specific → generic Colors → default theme

### Hex Color Parsing (Critical Distinction)
- 3 digits: "abc" → 0xaa 0xbb 0xcc 0xff
- 4 digits: "abcd" → 0xaa 0xbb 0xcc 0xdd (Note: "#rgb" with 4 chars = "#" + 3-digit)
- 6 digits: "a1b2c3" → 0xa1 0xb2 0xc3 0xff
- 8 digits: "a1b2c3f4" → 0xa1 0xb2 0xc3 0xf4
- All formats support optional "#" prefix
- Invalid → transparent color + error

---

## Target 3: Data Binding Formatting

### Exact Requirements
- **Location**: `data/binding/sprintf.go`
- **Function**: `NewSprintf(format string, b ...DataItem) String`
  - Returns String binding
  - Updates on any source DataChanged
  - `Get()` returns formatted string; propagates source errors
  - `Set(str string)` uses `fmt.Sscanf` to parse back
  - **Special handling**: Bytes cannot round-trip (error), URI uses `storage.ParseURI`
- **Function**: `StringToStringWithFormat(str String, format string) String`
  - If format == "%s": return original binding (no wrapping)
  - Else: delegate to NewSprintf

---

## Target 4: Menu System Enhancements

### Exact Requirements
- **Location**: `menu.go` in root fyne package
- **MenuItem struct additions**:
  - `Icon Resource` field
  - `Shortcut Shortcut` field (Shortcut interface exists)
- **Methods**:
  - `Menu.Refresh()` — re-render in all windows + system tray if applicable
  - `MainMenu.Refresh()` — re-render in all windows with this MainMenu

---

## Target 5: Toolbar Enhancements

### Exact Requirements
- **Location**: `widget/toolbar.go`
- **Method**: `ToolbarAction.SetIcon(icon fyne.Resource)` — updates Icon field + refreshes
- **Constructor return types** (breaking change from interface to concrete):
  - `NewToolbarAction` → `*ToolbarAction`
  - `NewToolbarSpacer` → `*ToolbarSpacer`
  - `NewToolbarSeparator` → `*ToolbarSeparator`

---

## Target 6: Widget and Container Improvements

### Exact Requirements
1. **Container.RemoveAll()** (`container.go` in root)
   - Sets Objects to nil
   - Triggers re-layout
   
2. **Container.Add() nil-safe** (`container.go` in root)
   - Passing nil is no-op (don't append)
   
3. **Hyperlink.OnTapped** (`widget/hyperlink.go`)
   - Field: `OnTapped func()`
   - When non-nil: call instead of opening URL
   - When nil: preserve existing URL-opening behavior
   
4. **Entry.SetMinRowsVisible(count int)** (`widget/entry.go`)
   - For multi-line entries only
   - Overrides default 3 rows
   - count=2 → shorter; count=5 → taller
   - Stored internally, affects MinSize() when > 0
   
5. **validation.NewAllStrings** (`data/validation/all.go`)
   - Signature: `NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator`
   - Runs validators in order
   - Returns first error or nil if all pass

---

## Target 7: Desktop App Interface

### Exact Requirements
- **Location**: `driver/desktop/app.go`
- **Interface**: `desktop.App` with methods:
  - `SetSystemTrayMenu(menu *fyne.Menu)`
  - `SetSystemTrayIcon(icon fyne.Resource)`
- Desktop apps can type-assert to this interface

---

## Completion Criteria (Non-negotiable)
- All new types/functions/methods importable from documented paths
- Backward compatibility maintained
- AppMetadata struct fields match exact names/types
- JSON theme parsing handles all hex formats correctly
- Data binding formatting updates reactively
- MenuItem has icon and shortcut fields accessible
- Toolbar constructors return concrete types
- Container.RemoveAll() clears all; Add(nil) is no-op
- Hyperlink.OnTapped overrides URL opening when set
- Entry.SetMinRowsVisible affects multi-line entry MinSize
- NewAllStrings chains validators, returns first error
- desktop.App interface defines system tray API

---

## Learned Facts
(To be populated as task progresses with durable discoveries about codebase structure, implementation patterns, test requirements, or distinctions that prevent recurring mistakes)
