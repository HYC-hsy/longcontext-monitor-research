package theme

import (
	"encoding/json"
	"image/color"
	"io"

	"fyne.io/fyne/v2"
)

// jsonTheme represents a theme loaded from JSON with customizable colors, sizes, fonts, and icons.
type jsonTheme struct {
	colors map[fyne.ThemeColorName]color.Color
	sizes  map[fyne.ThemeSizeName]float32
	fonts  map[string]fyne.Resource
	icons  map[fyne.ThemeIconName]fyne.Resource
	
	variant fyne.ThemeVariant
}

// jsonThemeData represents the JSON structure for theme configuration.
type jsonThemeData struct {
	Colors map[string]string            `json:"colors"`
	Sizes  map[string]float32           `json:"sizes"`
	Fonts  map[string]string            `json:"fonts"`
	Icons  map[string]string            `json:"icons"`
}

// FromJSON parses a JSON byte slice and returns a Theme instance.
// The JSON should contain "colors", "sizes", "fonts", and "icons" objects.
// Colors are specified as hex strings (e.g., "#RRGGBBAA").
//
// Since: 2.2
func FromJSON(data []byte) (fyne.Theme, error) {
	var themeData jsonThemeData
	if err := json.Unmarshal(data, &themeData); err != nil {
		return nil, err
	}
	
	return buildThemeFromData(&themeData)
}

// FromJSONReader reads JSON from an io.Reader and returns a Theme instance.
// This is useful for loading themes from files or network streams.
//
// Since: 2.2
func FromJSONReader(r io.Reader) (fyne.Theme, error) {
	var themeData jsonThemeData
	decoder := json.NewDecoder(r)
	if err := decoder.Decode(&themeData); err != nil {
		return nil, err
	}
	
	return buildThemeFromData(&themeData)
}

func buildThemeFromData(data *jsonThemeData) (fyne.Theme, error) {
	theme := &jsonTheme{
		colors: make(map[fyne.ThemeColorName]color.Color),
		sizes:  make(map[fyne.ThemeSizeName]float32),
		fonts:  make(map[string]fyne.Resource),
		icons:  make(map[fyne.ThemeIconName]fyne.Resource),
		variant: VariantDark,
	}
	
	// Parse colors
	for name, hexColor := range data.Colors {
		if c, err := parseHexColor(hexColor); err == nil {
			theme.colors[fyne.ThemeColorName(name)] = c
		}
	}
	
	// Parse sizes
	for name, size := range data.Sizes {
		theme.sizes[fyne.ThemeSizeName(name)] = size
	}
	
	// Fonts and icons would need additional resource loading logic
	// For now, we'll store the paths/identifiers
	
	return theme, nil
}

// parseHexColor converts a hex color string (e.g., "#RRGGBBAA" or "#RRGGBB") to color.Color
func parseHexColor(hex string) (color.Color, error) {
	if len(hex) == 0 || hex[0] != '#' {
		return nil, &json.UnsupportedValueError{}
	}
	
	hex = hex[1:] // Remove '#'
	
	var r, g, b, a uint8
	a = 0xff // Default alpha
	
	switch len(hex) {
	case 6: // #RRGGBB
		if _, err := parseHexByte(hex[0:2], &r); err != nil {
			return nil, err
		}
		if _, err := parseHexByte(hex[2:4], &g); err != nil {
			return nil, err
		}
		if _, err := parseHexByte(hex[4:6], &b); err != nil {
			return nil, err
		}
	case 8: // #RRGGBBAA
		if _, err := parseHexByte(hex[0:2], &r); err != nil {
			return nil, err
		}
		if _, err := parseHexByte(hex[2:4], &g); err != nil {
			return nil, err
		}
		if _, err := parseHexByte(hex[4:6], &b); err != nil {
			return nil, err
		}
		if _, err := parseHexByte(hex[6:8], &a); err != nil {
			return nil, err
		}
	default:
		return nil, &json.UnsupportedValueError{}
	}
	
	return color.NRGBA{R: r, G: g, B: b, A: a}, nil
}

func parseHexByte(hex string, out *uint8) (bool, error) {
	var val uint8
	for i := 0; i < len(hex); i++ {
		c := hex[i]
		var digit uint8
		switch {
		case '0' <= c && c <= '9':
			digit = c - '0'
		case 'a' <= c && c <= 'f':
			digit = c - 'a' + 10
		case 'A' <= c && c <= 'F':
			digit = c - 'A' + 10
		default:
			return false, &json.UnsupportedValueError{}
		}
		val = val*16 + digit
	}
	*out = val
	return true, nil
}

// Color returns the color for the given name and variant from the JSON theme.
func (t *jsonTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color {
	if c, ok := t.colors[name]; ok {
		return c
	}
	// Fallback to default theme
	return DefaultTheme().Color(name, variant)
}

// Font returns the font resource for the given style from the JSON theme.
func (t *jsonTheme) Font(style fyne.TextStyle) fyne.Resource {
	// Font loading would require additional implementation
	// Fallback to default theme
	return DefaultTheme().Font(style)
}

// Icon returns the icon resource for the given name from the JSON theme.
func (t *jsonTheme) Icon(name fyne.ThemeIconName) fyne.Resource {
	if icon, ok := t.icons[name]; ok {
		return icon
	}
	// Fallback to default theme
	return DefaultTheme().Icon(name)
}

// Size returns the size for the given name from the JSON theme.
func (t *jsonTheme) Size(name fyne.ThemeSizeName) float32 {
	if size, ok := t.sizes[name]; ok {
		return size
	}
	// Fallback to default theme
	return DefaultTheme().Size(name)
}
