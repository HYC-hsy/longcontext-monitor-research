package theme

import (
	"encoding/json"
	"errors"
	"image/color"
	"io"
	"strconv"
	"strings"

	"fyne.io/fyne/v2"
)

// jsonTheme is an internal structure for deserializing JSON theme data
type jsonTheme struct {
	Colors map[string]string `json:"colors"`
	Sizes  map[string]int    `json:"sizes"`
}

// FromJSON creates a Theme from JSON-encoded theme data.
// The JSON format should contain "colors" and "sizes" objects.
//
// Example JSON:
//   {
//     "colors": {
//       "background": "#ffffff",
//       "foreground": "#000000",
//       "primary": "#0066cc"
//     },
//     "sizes": {
//       "text": 14,
//       "padding": 4
//     }
//   }
//
// Since: 2.2
func FromJSON(data []byte) (fyne.Theme, error) {
	return FromJSONReader(strings.NewReader(string(data)))
}

// FromJSONReader creates a Theme from a JSON reader.
// See FromJSON for the expected JSON format.
//
// Since: 2.2
func FromJSONReader(reader io.Reader) (fyne.Theme, error) {
	var jt jsonTheme
	decoder := json.NewDecoder(reader)
	if err := decoder.Decode(&jt); err != nil {
		return nil, err
	}

	// Parse colors
	colors := make(map[fyne.ThemeColorName]color.Color)
	for name, hexStr := range jt.Colors {
		c, err := parseHexColor(hexStr)
		if err != nil {
			return nil, err
		}
		colors[fyne.ThemeColorName(name)] = c
	}

	return &dynamicTheme{
		colors: colors,
		sizes:  jt.Sizes,
	}, nil
}

// parseHexColor converts a hex color string to a color.Color.
// Supports formats: #RGB, #RRGGBB, #RRGGBBAA
func parseHexColor(s string) (color.Color, error) {
	s = strings.TrimPrefix(s, "#")
	
	var r, g, b, a uint8
	a = 0xff // default alpha
	
	switch len(s) {
	case 3: // #RGB
		vals := make([]uint8, 3)
		for i := 0; i < 3; i++ {
			v, err := strconv.ParseUint(s[i:i+1], 16, 8)
			if err != nil {
				return nil, errors.New("invalid hex color format")
			}
			vals[i] = uint8(v * 17) // expand 0-F to 0-FF
		}
		r, g, b = vals[0], vals[1], vals[2]
		
	case 6: // #RRGGBB
		vals := make([]uint8, 3)
		for i := 0; i < 3; i++ {
			v, err := strconv.ParseUint(s[i*2:i*2+2], 16, 8)
			if err != nil {
				return nil, errors.New("invalid hex color format")
			}
			vals[i] = uint8(v)
		}
		r, g, b = vals[0], vals[1], vals[2]
		
	case 8: // #RRGGBBAA
		vals := make([]uint8, 4)
		for i := 0; i < 4; i++ {
			v, err := strconv.ParseUint(s[i*2:i*2+2], 16, 8)
			if err != nil {
				return nil, errors.New("invalid hex color format")
			}
			vals[i] = uint8(v)
		}
		r, g, b, a = vals[0], vals[1], vals[2], vals[3]
		
	default:
		return nil, errors.New("invalid hex color format")
	}
	
	return color.NRGBA{R: r, G: g, B: b, A: a}, nil
}

// dynamicTheme is a theme implementation that uses maps for colors and sizes
type dynamicTheme struct {
	colors map[fyne.ThemeColorName]color.Color
	sizes  map[string]int
}

func (t *dynamicTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color {
	if c, ok := t.colors[name]; ok {
		return c
	}
	// Fallback to default theme
	return DefaultTheme().Color(name, variant)
}

func (t *dynamicTheme) Icon(name fyne.ThemeIconName) fyne.Resource {
	// Fallback to default theme
	return DefaultTheme().Icon(name)
}

func (t *dynamicTheme) Font(style fyne.TextStyle) fyne.Resource {
	// Fallback to default theme
	return DefaultTheme().Font(style)
}

func (t *dynamicTheme) Size(name fyne.ThemeSizeName) float32 {
	// Try to find the size by name
	if size, ok := t.sizes[string(name)]; ok {
		return float32(size)
	}
	// Fallback to default theme
	return DefaultTheme().Size(name)
}
