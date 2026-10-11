# Task Book: Cross-Platform GUI Toolkit Development

## Mission Authority
task/original_task.txt - 7 targets for Fyne GUI toolkit expansion

## Critical Constraints

### Interface Compatibility (Target 1)
- `App.Metadata() AppMetadata` added to App interface in root fyne package
- **ALL existing App implementations must be updated** - this is not optional
- Breaking change internally; completion requires finding and updating all implementers

### API Breaking Changes (Explicit Requirements)
- Target 5: Toolbar constructors MUST return concrete types, not ToolbarItem interface
  - `NewToolbarAction` returns `*ToolbarAction`
  - `NewToolbarSpacer` returns `*ToolbarSpacer`
  - `NewToolbarSeparator` returns `*ToolbarSeparator`
- This is an intentional public API break per requirements

### Package Location Requirements
- `AppMetadata` struct: root fyne package (app.go)
- `SetMetadata` function: app sub-package (app/meta.go)
- JSON theme: `theme` package, functions `FromJSON` and `FromJSONReader`
- Data binding: `binding` package (data/binding/sprintf.go)
- Validator: `data/validation` package (data/validation/all.go)
- Desktop interface: `driver/desktop` package (driver/desktop/app.go)

## Precise Specifications

### AppMetadata Defaults (Target 1)
When no metadata set: `ID: "com.example"`, `Name: "Fyne App"`, `Version: "1.0.0"`, `Build: 1`

### JSON Color Parsing (Target 2)
All formats with or without `#` prefix:
- 3 digits: `"abc"` → `0xaa 0xbb 0xcc 0xff`
- 4 digits: `"abcd"` → `0xaa 0xbb 0xcc 0xdd`
- 6 digits: `"a1b2c3"` → `0xa1 0xb2 0xc3 0xff`
- 8 digits: `"a1b2c3f4"` → `0xa1 0xb2 0xc3 0xf4`
- Invalid → transparent color + error

Color resolution order: variant-specific (`Colors-dark`/`Colors-light`) → generic `Colors` → default theme

### Sprintf Binding Behavioral Requirements (Target 3) - CRITICAL
**Set() must implement bidirectional parsing:**
- Uses `fmt.Sscanf` to reverse parse the formatted string
- **Bytes binding**: cannot round-trip, Set() returns error
- **URI binding**: parsed via `storage.ParseURI`, not fmt.Sscanf
- All other DataItem types (Bool, Int, Float, Rune, String) use Sscanf
- ❌ NOT "read-only" - bidirectional binding is required

**Get() must support all DataItem types:**
- Must handle Bool, Bytes, Float, Int, Rune, String, URI bindings
- Requires type switches to extract values from different binding types
- ❌ NOT just String - all 7 DataItem types required

**StringToStringWithFormat identity optimization:**
- If format is `"%s"` (identity), return original binding directly (no wrapping)
- Only create wrapper for non-identity formats
- ❌ Must check format before creating wrapper

**Measurement distinction:** Method signatures alone don't prove behavioral compliance. The Set()/Get() implementation logic must match specified semantics.

### Entry MinRowsVisible (Target 6)
- Only affects multi-line entries
- Default is 3 rows
- Setting to 2 makes shorter, 5 makes taller
- Internal storage, affects MinSize() calculation when > 0

### Container.Add nil safety (Target 6)
Passing nil to Add() is a no-op (nil not appended to Objects)

### Hyperlink.OnTapped Override (Target 6)
When non-nil, OnTapped is called INSTEAD of opening URL (not in addition to)

## Completion Evidence Requirements

Must verify:
1. All App interface implementers satisfy new Metadata() method
2. JSON theme parsing handles all 4 hex formats correctly
3. Sprintf binding reacts to source changes (listener registration)
4. Toolbar constructors return concrete types (type signature check)
5. All 7 targets have importable APIs from documented paths

Backward compatibility preserved except where explicitly changed (Target 5 constructors).
