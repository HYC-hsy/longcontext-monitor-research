package theme

import (
	"encoding/json"
	"fmt"
	"image/color"
	"io"
	"strings"

	"fyne.io/fyne/v2"
)

// jsonTheme represents a theme loaded from JSON with customizable colors, sizes, fonts, and icons.
type jsonTheme struct {
	colorsDark  map[fyne.ThemeColorName]color.Color
	colorsLight map[fyne.ThemeColorName]color.Color
	sizes       map[fyne.ThemeSizeName]float32
	fonts       map[string]fyne.Resource
	icons       map[fyne.ThemeIconName]fyne.Resource
}

// jsonThemeData represents the JSON structure for theme configuration.
type jsonThemeData struct {
	Colors      map[string]string            `json:"colors"`       // Generic colors (both variants)
	ColorsDark  map[string]string            `json:"colors-dark"`  // Dark variant specific
	ColorsLight map[string]string            `json:"colors-light"` // Light variant specific
	Sizes       map[string]float32           `json:"sizes"`
	Fonts       map[string]string            `json:"fonts"`
	Icons       map[string]string            `json:"icons"`
}

// FromJSON creates a new Theme from JSON data provided as a string.
// The JSON format supports defining colors (with variant-specific "colors-dark" and "colors-light" keys),
// sizes, fonts, and icons. Hex colors can be specified with or without '#' prefix in 3, 4, 6, or 8 digit formats.
// On parse error, returns the default theme and the error.
//
// Since: 2.2
func FromJSON(data string) (fyne.Theme, error) {
	theme, err := FromJSONReader(strings.NewReader(data))
	if err != nil {
		return DefaultTheme(), err
	}
	return theme, nil
}

// FromJSONReader reads JSON from an io.Reader and returns a Theme instance.
// This is useful for loading themes from files or network streams.
// On parse error, returns the default theme and the error.
//
// Since: 2.2
func FromJSONReader(r io.Reader) (fyne.Theme, error) {
	var themeData jsonThemeData
	decoder := json.NewDecoder(r)
	if err := decoder.Decode(&themeData); err != nil {
		return DefaultTheme(), err
	}
	
	return buildThemeFromData(&themeData)
}

func buildThemeFromData(data *jsonThemeData) (fyne.Theme, error) {
	theme := &jsonTheme{
		colorsDark:  make(map[fyne.ThemeColorName]color.Color),
		colorsLight: make(map[fyne.ThemeColorName]color.Color),
		sizes:       make(map[fyne.ThemeSizeName]float32),
		fonts:       make(map[string]fyne.Resource),
		icons:       make(map[fyne.ThemeIconName]fyne.Resource),
	}
	
	// Parse generic colors (apply to both variants)
	for name, hexColor := range data.Colors {
		if c, err := parseHexColor(hexColor); err == nil {
			colorName := fyne.ThemeColorName(name)
			theme.colorsDark[colorName] = c
			theme.colorsLight[colorName] = c
		}
	}
	
	// Parse dark-specific colors
	for name, hexColor := range data.ColorsDark {
		if c, err := parseHexColor(hexColor); err == nil {
			theme.colorsDark[fyne.ThemeColorName(name)] = c
		}
	}
	
	// Parse light-specific colors
	for name, hexColor := range data.ColorsLight {
		if c, err := parseHexColor(hexColor); err == nil {
			theme.colorsLight[fyne.ThemeColorName(name)] = c
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

// parseHexColor converts a hex color string to color.Color.
// Supports formats: #RGB, #RGBA, #RRGGBB, #RRGGBBAA (with or without # prefix)
// 3-digit: "abc" → 0xaa 0xbb 0xcc 0xff
// 4-digit: "abcd" → 0xaa 0xbb 0xcc 0xdd
// 6-digit: "aabbcc" → 0xaa 0xbb 0xcc 0xff
// 8-digit: "aabbccdd" → 0xaa 0xbb 0xcc 0xdd
func parseHexColor(hex string) (color.Color, error) {
	// Remove '#' prefix if present
	hex = strings.TrimPrefix(hex, "#")
	
	if len(hex) == 0 {
		return nil, fmt.Errorf("empty color string")
	}
	
	var r, g, b, a uint8
	a = 0xff // Default alpha
	
	switch len(hex) {
	case 3: // RGB - each digit doubled
		if err := parseHexDigit(hex[0], &r); err != nil {
			return nil, err
		}
		r = r*16 + r
		if err := parseHexDigit(hex[1], &g); err != nil {
			return nil, err
		}
		g = g*16 + g
		if err := parseHexDigit(hex[2], &b); err != nil {
			return nil, err
		}
		b = b*16 + b
		
	case 4: // RGBA - each digit doubled
		if err := parseHexDigit(hex[0], &r); err != nil {
			return nil, err
		}
		r = r*16 + r
		if err := parseHexDigit(hex[1], &g); err != nil {
			return nil, err
		}
		g = g*16 + g
		if err := parseHexDigit(hex[2], &b); err != nil {
			return nil, err
		}
		b = b*16 + b
		if err := parseHexDigit(hex[3], &a); err != nil {
			return nil, err
		}
		a = a*16 + a
		
	case 6: // RRGGBB
		if err := parseHexByte(hex[0:2], &r); err != nil {
			return nil, err
		}
		if err := parseHexByte(hex[2:4], &g); err != nil {
			return nil, err
		}
		if err := parseHexByte(hex[4:6], &b); err != nil {
			return nil, err
		}
		
	case 8: // RRGGBBAA
		if err := parseHexByte(hex[0:2], &r); err != nil {
			return nil, err
		}
		if err := parseHexByte(hex[2:4], &g); err != nil {
			return nil, err
		}
		if err := parseHexByte(hex[4:6], &b); err != nil {
			return nil, err
		}
		if err := parseHexByte(hex[6:8], &a); err != nil {
			return nil, err
		}
		
	default:
		return nil, fmt.Errorf("invalid hex color length: %d", len(hex))
	}
	
	return color.NRGBA{R: r, G: g, B: b, A: a}, nil
}

func parseHexDigit(c byte, out *uint8) error {
	switch {
	case '0' <= c && c <= '9':
		*out = c - '0'
	case 'a' <= c && c <= 'f':
		*out = c - 'a' + 10
	case 'A' <= c && c <= 'F':
		*out = c - 'A' + 10
	default:
		return fmt.Errorf("invalid hex digit: %c", c)
	}
	return nil
}

func parseHexByte(hex string, out *uint8) error {
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
			return fmt.Errorf("invalid hex character: %c", c)
		}
		val = val*16 + digit
	}
	*out = val
	return nil
}

// Color returns the color for the given name and variant from the JSON theme.
func (t *jsonTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color {
	var colorMap map[fyne.ThemeColorName]color.Color
	if variant == VariantLight {
		colorMap = t.colorsLight
	} else {
		colorMap = t.colorsDark
	}
	
	if c, ok := colorMap[name]; ok {
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
