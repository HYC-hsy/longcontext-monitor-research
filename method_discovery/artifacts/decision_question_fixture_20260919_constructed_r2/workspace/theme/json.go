package theme

import (
	"encoding/json"
	"image/color"
	"io"
	"strconv"
	"strings"

	"fyne.io/fyne/v2"
)

// jsonTheme is a theme that loads colors, sizes, fonts, and icons from JSON.
// It falls back to the default theme for any unspecified values.
type jsonTheme struct {
	colors      map[fyne.ThemeColorName]color.Color
	colorsDark  map[fyne.ThemeColorName]color.Color
	colorsLight map[fyne.ThemeColorName]color.Color
	sizes       map[fyne.ThemeSizeName]float32
	fonts       map[string]fyne.Resource
	icons       map[fyne.ThemeIconName]fyne.Resource
	fallback    fyne.Theme
}

// jsonThemeData represents the structure of a theme JSON file.
type jsonThemeData struct {
	Colors      map[string]string            `json:"Colors"`
	ColorsDark  map[string]string            `json:"Colors-dark"`
	ColorsLight map[string]string            `json:"Colors-light"`
	Sizes       map[string]float32           `json:"Sizes"`
	Fonts       map[string]string            `json:"Fonts"`
	Icons       map[string]string            `json:"Icons"`
}

// FromJSON creates a theme from JSON data.
// The JSON format supports:
// - "Colors": variant-independent colors (map of color name to hex string)
// - "Colors-dark": dark variant colors (map of color name to hex string)
// - "Colors-light": light variant colors (map of color name to hex string)
// - "Sizes": size values (map of size name to float)
// - "Fonts": font resources (map of font style to path)
// - "Icons": icon resources (map of icon name to path)
//
// Hex color formats supported: #RGB, #RGBA, #RRGGBB, #RRGGBBAA
//
// Since: 2.5
func FromJSON(data []byte) (fyne.Theme, error) {
	return FromJSONReader(strings.NewReader(string(data)))
}

// FromJSONReader creates a theme from a JSON reader.
// See FromJSON for the JSON format specification.
//
// Since: 2.5
func FromJSONReader(r io.Reader) (fyne.Theme, error) {
	var data jsonThemeData
	decoder := json.NewDecoder(r)
	if err := decoder.Decode(&data); err != nil {
		return nil, err
	}

	theme := &jsonTheme{
		colors:      make(map[fyne.ThemeColorName]color.Color),
		colorsDark:  make(map[fyne.ThemeColorName]color.Color),
		colorsLight: make(map[fyne.ThemeColorName]color.Color),
		sizes:       make(map[fyne.ThemeSizeName]float32),
		fonts:       make(map[string]fyne.Resource),
		icons:       make(map[fyne.ThemeIconName]fyne.Resource),
		fallback:    DefaultTheme(),
	}

	// Parse variant-independent colors
	for name, hexColor := range data.Colors {
		if col, err := parseHexColor(hexColor); err == nil {
			theme.colors[fyne.ThemeColorName(name)] = col
		}
	}

	// Parse dark variant colors
	for name, hexColor := range data.ColorsDark {
		if col, err := parseHexColor(hexColor); err == nil {
			theme.colorsDark[fyne.ThemeColorName(name)] = col
		}
	}

	// Parse light variant colors
	for name, hexColor := range data.ColorsLight {
		if col, err := parseHexColor(hexColor); err == nil {
			theme.colorsLight[fyne.ThemeColorName(name)] = col
		}
	}

	// Parse sizes
	for name, size := range data.Sizes {
		theme.sizes[fyne.ThemeSizeName(name)] = size
	}

	// Parse fonts
	for style, path := range data.Fonts {
		if res, err := fyne.LoadResourceFromPath(path); err == nil {
			theme.fonts[style] = res
		}
	}

	// Parse icons
	for name, path := range data.Icons {
		if res, err := fyne.LoadResourceFromPath(path); err == nil {
			theme.icons[fyne.ThemeIconName(name)] = res
		}
	}

	return theme, nil
}

// Color returns the theme's color for the specified color name and variant.
func (t *jsonTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color {
	// Check variant-specific colors first
	if variant == VariantDark {
		if col, ok := t.colorsDark[name]; ok {
			return col
		}
	} else if variant == VariantLight {
		if col, ok := t.colorsLight[name]; ok {
			return col
		}
	}

	// Check variant-independent colors
	if col, ok := t.colors[name]; ok {
		return col
	}

	// Fall back to default theme
	return t.fallback.Color(name, variant)
}

// Font returns the theme's font for the specified text style.
func (t *jsonTheme) Font(style fyne.TextStyle) fyne.Resource {
	// Map text style to font key
	var key string
	if style.Monospace {
		key = "monospace"
	} else if style.Bold && style.Italic {
		key = "bolditalic"
	} else if style.Bold {
		key = "bold"
	} else if style.Italic {
		key = "italic"
	} else {
		key = "regular"
	}

	if font, ok := t.fonts[key]; ok {
		return font
	}

	// Fall back to default theme
	return t.fallback.Font(style)
}

// Icon returns the theme's icon for the specified icon name.
func (t *jsonTheme) Icon(name fyne.ThemeIconName) fyne.Resource {
	if icon, ok := t.icons[name]; ok {
		return icon
	}

	// Fall back to default theme
	return t.fallback.Icon(name)
}

// Size returns the theme's size for the specified size name.
func (t *jsonTheme) Size(name fyne.ThemeSizeName) float32 {
	if size, ok := t.sizes[name]; ok {
		return size
	}

	// Fall back to default theme
	return t.fallback.Size(name)
}

// parseHexColor parses a hex color string in various formats:
// #RGB (12-bit)
// #RGBA (16-bit)
// #RRGGBB (24-bit)
// #RRGGBBAA (32-bit)
func parseHexColor(s string) (color.Color, error) {
	s = strings.TrimPrefix(s, "#")
	
	var r, g, b, a uint8
	a = 0xff // default alpha

	switch len(s) {
	case 3: // RGB
		val, err := strconv.ParseUint(s, 16, 16)
		if err != nil {
			return nil, err
		}
		r = uint8((val >> 8) & 0xf)
		g = uint8((val >> 4) & 0xf)
		b = uint8(val & 0xf)
		// Expand 4-bit to 8-bit
		r = r<<4 | r
		g = g<<4 | g
		b = b<<4 | b

	case 4: // RGBA
		val, err := strconv.ParseUint(s, 16, 16)
		if err != nil {
			return nil, err
		}
		r = uint8((val >> 12) & 0xf)
		g = uint8((val >> 8) & 0xf)
		b = uint8((val >> 4) & 0xf)
		a = uint8(val & 0xf)
		// Expand 4-bit to 8-bit
		r = r<<4 | r
		g = g<<4 | g
		b = b<<4 | b
		a = a<<4 | a

	case 6: // RRGGBB
		val, err := strconv.ParseUint(s, 16, 32)
		if err != nil {
			return nil, err
		}
		r = uint8((val >> 16) & 0xff)
		g = uint8((val >> 8) & 0xff)
		b = uint8(val & 0xff)

	case 8: // RRGGBBAA
		val, err := strconv.ParseUint(s, 16, 64)
		if err != nil {
			return nil, err
		}
		r = uint8((val >> 24) & 0xff)
		g = uint8((val >> 16) & 0xff)
		b = uint8((val >> 8) & 0xff)
		a = uint8(val & 0xff)

	default:
		return nil, strconv.ErrSyntax
	}

	return color.NRGBA{R: r, G: g, B: b, A: a}, nil
}
