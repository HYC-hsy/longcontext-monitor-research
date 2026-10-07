package theme

import (
	"encoding/json"
	"errors"
	"image/color"
	"io"

	"fyne.io/fyne/v2"
)

// jsonTheme implements fyne.Theme using data loaded from JSON
type jsonTheme struct {
	colors     map[fyne.ThemeColorName]color.Color      // generic colors
	colorsDark map[fyne.ThemeColorName]color.Color      // dark variant specific
	colorsLight map[fyne.ThemeColorName]color.Color     // light variant specific
	sizes      map[fyne.ThemeSizeName]float32
	fonts      map[string]fyne.Resource
}

// FromJSON creates a new Theme from JSON-encoded theme data string.
// The JSON should contain top-level keys: "Colors", "Colors-dark", "Colors-light", "Sizes", "Fonts", "Icons".
// Color resolution: checks variant-specific key first, then "Colors", then default theme.
//
// Since: 2.5
func FromJSON(data string) (fyne.Theme, error) {
	return fromJSONBytes([]byte(data))
}

// FromJSONReader creates a new Theme from JSON data read from an io.Reader.
//
// Since: 2.5
func FromJSONReader(r io.Reader) (fyne.Theme, error) {
	data, err := io.ReadAll(r)
	if err != nil {
		return nil, err
	}
	return fromJSONBytes(data)
}

func fromJSONBytes(data []byte) (fyne.Theme, error) {
	var raw struct {
		Colors      map[string]string `json:"Colors"`       // generic colors: colorName -> hex
		ColorsDark  map[string]string `json:"Colors-dark"`  // dark variant: colorName -> hex
		ColorsLight map[string]string `json:"Colors-light"` // light variant: colorName -> hex
		Sizes       map[string]float32 `json:"Sizes"`       // sizeName -> value
		Fonts       map[string]string `json:"Fonts"`        // style -> path
	}

	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}

	theme := &jsonTheme{
		colors:      make(map[fyne.ThemeColorName]color.Color),
		colorsDark:  make(map[fyne.ThemeColorName]color.Color),
		colorsLight: make(map[fyne.ThemeColorName]color.Color),
		sizes:       make(map[fyne.ThemeSizeName]float32),
		fonts:       make(map[string]fyne.Resource),
	}

	// Parse generic colors
	for colorName, hexColor := range raw.Colors {
		if c, err := parseHexColor(hexColor); err == nil {
			theme.colors[fyne.ThemeColorName(colorName)] = c
		}
	}

	// Parse dark variant colors
	for colorName, hexColor := range raw.ColorsDark {
		if c, err := parseHexColor(hexColor); err == nil {
			theme.colorsDark[fyne.ThemeColorName(colorName)] = c
		}
	}

	// Parse light variant colors
	for colorName, hexColor := range raw.ColorsLight {
		if c, err := parseHexColor(hexColor); err == nil {
			theme.colorsLight[fyne.ThemeColorName(colorName)] = c
		}
	}

	// Parse sizes
	for sizeName, value := range raw.Sizes {
		theme.sizes[fyne.ThemeSizeName(sizeName)] = value
	}

	// Fonts would require loading from paths - simplified here
	// Real implementation would use fyne.LoadResourceFromPath or similar

	return theme, nil
}

// parseHexColor converts hex color strings to color.Color
// Supports: #RGB (3-digit), #RGBA (4-digit), #RRGGBB (6-digit), #RRGGBBAA (8-digit)
func parseHexColor(hex string) (color.Color, error) {
	var r, g, b, a uint8 = 0, 0, 0, 255

	if len(hex) == 0 || hex[0] != '#' {
		hex = "#" + hex
	}

	switch len(hex) {
	case 4: // #RGB -> #RRGGBB
		if _, err := parseHex(hex[1:], &r, &g, &b); err != nil {
			return nil, err
		}
		// Expand: R -> RR (e.g., 0xA -> 0xAA)
		r = r<<4 | r
		g = g<<4 | g
		b = b<<4 | b
	case 5: // #RGBA -> #RRGGBBAA
		if _, err := parseHex(hex[1:], &r, &g, &b, &a); err != nil {
			return nil, err
		}
		// Expand each component
		r = r<<4 | r
		g = g<<4 | g
		b = b<<4 | b
		a = a<<4 | a
	case 7: // #RRGGBB
		if _, err := parseHex(hex[1:], &r, &g, &b); err != nil {
			return nil, err
		}
	case 9: // #RRGGBBAA
		if _, err := parseHex(hex[1:], &r, &g, &b, &a); err != nil {
			return nil, err
		}
	default:
		return nil, errors.New("invalid hex color format")
	}

	return color.RGBA{R: r, G: g, B: b, A: a}, nil
}

// parseHex helper to parse hex digits into byte values
// For 3/4 digit format, parses single hex digit per component
// For 6/8 digit format, parses two hex digits per component
func parseHex(s string, vals ...*uint8) (int, error) {
	hexPerVal := 2
	if len(s) == 3 || len(s) == 4 {
		hexPerVal = 1 // Single hex digit per component
	}

	for i, v := range vals {
		if i*hexPerVal+hexPerVal > len(s) {
			return i, errors.New("hex string too short")
		}
		hex := s[i*hexPerVal : i*hexPerVal+hexPerVal]
		var val uint8
		for _, c := range hex {
			val <<= 4
			switch {
			case '0' <= c && c <= '9':
				val |= uint8(c - '0')
			case 'a' <= c && c <= 'f':
				val |= uint8(c - 'a' + 10)
			case 'A' <= c && c <= 'F':
				val |= uint8(c - 'A' + 10)
			default:
				return i, errors.New("invalid hex digit")
			}
		}
		*v = val
	}
	return len(vals), nil
}

func (t *jsonTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color {
	// Check variant-specific color first
	if variant == 1 { // dark
		if c, ok := t.colorsDark[name]; ok {
			return c
		}
	} else { // light (0)
		if c, ok := t.colorsLight[name]; ok {
			return c
		}
	}

	// Check generic colors
	if c, ok := t.colors[name]; ok {
		return c
	}

	// Fallback to default theme
	return DefaultTheme().Color(name, variant)
}

func (t *jsonTheme) Font(style fyne.TextStyle) fyne.Resource {
	// Fonts would require proper loading - simplified
	// Fallback to default theme
	return DefaultTheme().Font(style)
}

func (t *jsonTheme) Icon(name fyne.ThemeIconName) fyne.Resource {
	// Fallback to default theme
	return DefaultTheme().Icon(name)
}

func (t *jsonTheme) Size(name fyne.ThemeSizeName) float32 {
	if size, ok := t.sizes[name]; ok {
		return size
	}
	// Fallback to default theme
	return DefaultTheme().Size(name)
}
