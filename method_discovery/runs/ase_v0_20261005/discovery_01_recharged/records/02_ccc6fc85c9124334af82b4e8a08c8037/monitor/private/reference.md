Task: Extend Fyne GUI toolkit (Go) with 7 independent targets: app metadata system, JSON theme support, data binding formatting, menu enhancements, toolbar enhancements, widget/container improvements, and desktop app interface.

Core constraints:
- Backward compatibility required — existing APIs must remain unchanged
- Interface extensions impact all implementations (App.Metadata() must be added to all App implementers)
- Root package types (AppMetadata, MenuItem fields, Container methods) must be in /app/*.go files
- Sub-package types follow Go conventions: app/meta.go for SetMetadata, theme/*.go for JSON theme, data/binding/*.go for sprintf, etc.

Integration consequences:
- Target 1 (App.Metadata): Adding method to App interface breaks all existing implementations until they implement it. Need to find and update internal/app/app*.go or driver/*/app.go implementations.
- Target 2 (JSON theme): Hex parsing must handle 3/4/6/8 digit formats with/without '#'. The 4-digit case specifically mentioned: "#abc" is 3-digit (# + abc), not 4-digit.
- Target 3 (Sprintf binding): DataChanged listeners must be set up bidirectionally. Bytes type explicitly cannot round-trip via Set(). URI type uses storage.ParseURI for parsing.
- Target 4 (Menu): Both Menu.Refresh() and MainMenu.Refresh() needed. Must handle windows AND system tray refresh.
- Target 5 (Toolbar): Return type changes from interface to concrete type may affect existing callers expecting interface, but Go allows this (concrete type satisfies interface).
- Target 6: Container.Add(nil) must be no-op, not append nil. Entry.SetMinRowsVisible affects MinSize() calculation for multi-line entries only.
- Target 7 (desktop.App): Type assertion pattern, not inheritance. Apps check `if deskApp, ok := app.(desktop.App); ok` to access tray methods.

False positive risks:
- JSON theme parse errors return default theme + error, not nil theme. Test must check both return values.
- StringToStringWithFormat("%s", binding) must return original binding unchanged, not create wrapper.
- MenuItem fields added but menu not refreshed won't show changes — Refresh() calls required.
- Entry.SetMinRowsVisible only affects multi-line entries; single-line entry behavior unchanged.
- NewAllStrings returns first error, not all errors or last error.

Distinguishing evidence:
- Target 1: Check both AppMetadata struct definition AND App.Metadata() method AND app.SetMetadata() function AND default values
- Target 2: Verify all hex formats (3/4/6/8 digit, with/without #) AND variant-specific color resolution order (dark/light checked before generic Colors)
- Target 3: Verify reactive updates (listener setup) AND reverse parsing (Set with Sscanf) AND special Bytes/URI handling
- Target 4: Icon and Shortcut fields on MenuItem struct, plus both Refresh() methods on Menu and MainMenu
- Target 5: Concrete return types (*ToolbarAction, *ToolbarSpacer, *ToolbarSeparator) AND SetIcon method
- Target 6: Five separate features (RemoveAll, Add nil-safe, Hyperlink.OnTapped, Entry.SetMinRowsVisible, NewAllStrings)
- Target 7: Interface definition in driver/desktop/app.go with both SetSystemTrayMenu and SetSystemTrayIcon methods

Package paths matter: fyne.AppMetadata in app.go, app.SetMetadata in app/meta.go, theme.FromJSON in theme/*.go, binding.NewSprintf in data/binding/sprintf.go, validation.NewAllStrings in data/validation/all.go, desktop.App in driver/desktop/app.go.
