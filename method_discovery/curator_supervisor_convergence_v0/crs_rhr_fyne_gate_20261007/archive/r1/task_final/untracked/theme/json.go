package theme

import (
	"encoding/json"
	"fmt"
	"image/color"
	"io"
	"strconv"
	"strings"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/storage"
)

// FromJSON parses a JSON string and returns a Theme.
// On parse error, returns the default theme along with the error.
//
// The JSON structure supports:
//   - "Colors": map of color name to hex string (applied regardless of variant)
//   - "Colors-dark": map of color name to hex string (applied only in dark variant)
//   - "Colors-light": map of color name to hex string (applied only in light variant)
//   - "Sizes": map of size name to float32 value
//   - "Fonts": map of font style name to URI string
//   - "Icons": map of icon name to URI string
//
// Since: 2.2
func FromJSON(data string) (fyne.Theme, error) {
	return FromJSONReader(strings.NewReader(data))
}

// FromJSONReader parses JSON from an io.Reader and returns a Theme.
// On parse error, returns the default theme along with the error.
//
// Since: 2.2
func FromJSONReader(r io.Reader) (fyne.Theme, error) {
	var raw map[string]interface{}
	if err := json.NewDecoder(r).Decode(&raw); err != nil {
		return DarkTheme(), err
	}

	jt := &jsonTheme{
		colors:      make(map[fyne.ThemeColorName]color.Color),
		colorsDark:  make(map[fyne.ThemeColorName]color.Color),
		colorsLight: make(map[fyne.ThemeColorName]color.Color),
		sizes:       make(map[fyne.ThemeSizeName]float32),
		fonts:       make(map[string]fyne.Resource),
		icons:       make(map[fyne.ThemeIconName]fyne.Resource),
	}

	// Parse generic colors
	if colors, ok := raw["Colors"].(map[string]interface{}); ok {
		for name, val := range colors {
			if hexStr, ok := val.(string); ok {
				if c, err := parseHexColor(hexStr); err == nil {
					jt.colors[fyne.ThemeColorName(name)] = c
				}
			}
		}
	}

	// Parse dark variant colors
	if colorsDark, ok := raw["Colors-dark"].(map[string]interface{}); ok {
		for name, val := range colorsDark {
			if hexStr, ok := val.(string); ok {
				if c, err := parseHexColor(hexStr); err == nil {
					jt.colorsDark[fyne.ThemeColorName(name)] = c
				}
			}
		}
	}

	// Parse light variant colors
	if colorsLight, ok := raw["Colors-light"].(map[string]interface{}); ok {
		for name, val := range colorsLight {
			if hexStr, ok := val.(string); ok {
				if c, err := parseHexColor(hexStr); err == nil {
					jt.colorsLight[fyne.ThemeColorName(name)] = c
				}
			}
		}
	}

	// Parse sizes
	if sizes, ok := raw["Sizes"].(map[string]interface{}); ok {
		for name, val := range sizes {
			// JSON numbers come as float64
			switch v := val.(type) {
			case float64:
				jt.sizes[fyne.ThemeSizeName(name)] = float32(v)
			case float32:
				jt.sizes[fyne.ThemeSizeName(name)] = v
			}
		}
	}

	// Parse fonts
	if fonts, ok := raw["Fonts"].(map[string]interface{}); ok {
		for style, val := range fonts {
			if uriStr, ok := val.(string); ok {
				if uri, err := storage.ParseURI(uriStr); err == nil {
					if res, err := storage.LoadResourceFromURI(uri); err == nil {
						jt.fonts[style] = res
					}
				}
			}
		}
	}

	// Parse icons
	if icons, ok := raw["Icons"].(map[string]interface{}); ok {
		for name, val := range icons {
			if uriStr, ok := val.(string); ok {
				if uri, err := storage.ParseURI(uriStr); err == nil {
					if res, err := storage.LoadResourceFromURI(uri); err == nil {
						jt.icons[fyne.ThemeIconName(name)] = res
					}
				}
			}
		}
	}

	return jt, nil
}

// parseHexColor parses a hex color string and returns a color.Color.
// Supports formats: 3-digit (#abc), 4-digit (#abcd), 6-digit (#a1b2c3), 8-digit (#a1b2c3f4)
// All formats work with or without the '#' prefix.
func parseHexColor(hex string) (color.Color, error) {
	hex = strings.TrimPrefix(hex, "#")

	var r, g, b, a uint8 = 0, 0, 0, 255

	switch len(hex) {
	case 3:
		// RGB shorthand: "abc" -> 0xaa, 0xbb, 0xcc, 0xff
		val, err := strconv.ParseUint(hex, 16, 16)
		if err != nil {
			return color.Transparent, fmt.Errorf("invalid hex color: %s", hex)
		}
		r = uint8((val >> 8) & 0xF)
		r = r<<4 | r
		g = uint8((val >> 4) & 0xF)
		g = g<<4 | g
		b = uint8(val & 0xF)
		b = b<<4 | b
		a = 255

	case 4:
		// RGBA shorthand: "abcd" -> 0xaa, 0xbb, 0xcc, 0xdd
		val, err := strconv.ParseUint(hex, 16, 16)
		if err != nil {
			return color.Transparent, fmt.Errorf("invalid hex color: %s", hex)
		}
		r = uint8((val >> 12) & 0xF)
		r = r<<4 | r
		g = uint8((val >> 8) & 0xF)
		g = g<<4 | g
		b = uint8((val >> 4) & 0xF)
		b = b<<4 | b
		a = uint8(val & 0xF)
		a = a<<4 | a

	case 6:
		// Full RGB: "a1b2c3" -> 0xa1, 0xb2, 0xc3, 0xff
		val, err := strconv.ParseUint(hex, 16, 32)
		if err != nil {
			return color.Transparent, fmt.Errorf("invalid hex color: %s", hex)
		}
		r = uint8((val >> 16) & 0xFF)
		g = uint8((val >> 8) & 0xFF)
		b = uint8(val & 0xFF)
		a = 255

	case 8:
		// Full RGBA: "a1b2c3f4" -> 0xa1, 0xb2, 0xc3, 0xf4
		val, err := strconv.ParseUint(hex, 16, 32)
		if err != nil {
			return color.Transparent, fmt.Errorf("invalid hex color: %s", hex)
		}
		r = uint8((val >> 24) & 0xFF)
		g = uint8((val >> 16) & 0xFF)
		b = uint8((val >> 8) & 0xFF)
		a = uint8(val & 0xFF)

	default:
		return color.Transparent, fmt.Errorf("invalid hex color length: %s", hex)
	}

	return color.NRGBA{R: r, G: g, B: b, A: a}, nil
}

type jsonTheme struct {
	colors      map[fyne.ThemeColorName]color.Color
	colorsDark  map[fyne.ThemeColorName]color.Color
	colorsLight map[fyne.ThemeColorName]color.Color
	sizes       map[fyne.ThemeSizeName]float32
	fonts       map[string]fyne.Resource
	icons       map[fyne.ThemeIconName]fyne.Resource
}

func (j *jsonTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color {
	// Check variant-specific colors first
	if variant == VariantDark {
		if c, ok := j.colorsDark[name]; ok {
			return c
		}
	} else if variant == VariantLight {
		if c, ok := j.colorsLight[name]; ok {
			return c
		}
	}

	// Check generic colors
	if c, ok := j.colors[name]; ok {
		return c
	}

	// Fallback to default theme
	return DarkTheme().Color(name, variant)
}

func (j *jsonTheme) Font(style fyne.TextStyle) fyne.Resource {
	var key string
	if style.Bold && style.Italic {
		key = "boldItalic"
	} else if style.Bold {
		key = "bold"
	} else if style.Italic {
		key = "italic"
	} else if style.Monospace {
		key = "monospace"
	} else {
		key = "regular"
	}

	if res, ok := j.fonts[key]; ok {
		return res
	}

	// Fallback to default theme
	return DarkTheme().Font(style)
}

func (j *jsonTheme) Icon(name fyne.ThemeIconName) fyne.Resource {
	if res, ok := j.icons[name]; ok {
		return res
	}

	// Fallback to default theme
	return DarkTheme().Icon(name)
}

func (j *jsonTheme) Size(name fyne.ThemeSizeName) float32 {
	if val, ok := j.sizes[name]; ok {
		return val
	}

	// Fallback to default theme
	return DarkTheme().Size(name)
}
