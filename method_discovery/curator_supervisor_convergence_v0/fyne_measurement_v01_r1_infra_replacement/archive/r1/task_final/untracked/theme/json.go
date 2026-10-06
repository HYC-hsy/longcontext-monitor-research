package theme

import (
	"encoding/json"
	"errors"
	"image/color"
	"io"
	"os"
	"strings"

	"fyne.io/fyne/v2"
)

// jsonThemeData represents the structure of a JSON theme file
type jsonThemeData struct {
	Colors      map[string]string `json:"Colors,omitempty"`
	ColorsDark  map[string]string `json:"Colors-dark,omitempty"`
	ColorsLight map[string]string `json:"Colors-light,omitempty"`
	Sizes       map[string]float32 `json:"Sizes,omitempty"`
	Fonts       jsonFonts          `json:"Fonts,omitempty"`
	Icons       map[string]string  `json:"Icons,omitempty"`
}

// jsonFonts holds font file paths
type jsonFonts struct {
	Regular    string `json:"regular,omitempty"`
	Bold       string `json:"bold,omitempty"`
	Italic     string `json:"italic,omitempty"`
	BoldItalic string `json:"bolditalic,omitempty"`
	Monospace  string `json:"monospace,omitempty"`
}

// jsonTheme implements fyne.Theme using data loaded from JSON
type jsonTheme struct {
	data     jsonThemeData
	fonts    map[string]fyne.Resource
	icons    map[string]fyne.Resource
	fallback fyne.Theme
}

// FromJSON loads a theme from a JSON string.
// The JSON should contain color definitions (Colors, Colors-dark, Colors-light),
// size overrides (Sizes), font paths (Fonts), and icon paths (Icons).
// Any missing values will fall back to the default theme.
// Returns (default theme, error) on parse error.
//
// Since: 2.2
func FromJSON(data string) (fyne.Theme, error) {
	return FromJSONReader(strings.NewReader(data))
}

// FromJSONReader loads a theme from JSON data read from an io.Reader.
// The JSON should contain color definitions (Colors, Colors-dark, Colors-light),
// size overrides (Sizes), font paths (Fonts), and icon paths (Icons).
// Any missing values will fall back to the default theme.
// Returns (default theme, error) on parse error.
//
// Since: 2.2
func FromJSONReader(r io.Reader) (fyne.Theme, error) {
	data, err := io.ReadAll(r)
	if err != nil {
		return DefaultTheme(), err
	}

	var themeData jsonThemeData
	if err := json.Unmarshal(data, &themeData); err != nil {
		return DefaultTheme(), err
	}

	theme := &jsonTheme{
		data:     themeData,
		fonts:    make(map[string]fyne.Resource),
		icons:    make(map[string]fyne.Resource),
		fallback: DefaultTheme(),
	}

	// Load custom fonts if specified
	if themeData.Fonts.Regular != "" {
		if res := loadFontResource(themeData.Fonts.Regular); res != nil {
			theme.fonts["regular"] = res
		}
	}
	if themeData.Fonts.Bold != "" {
		if res := loadFontResource(themeData.Fonts.Bold); res != nil {
			theme.fonts["bold"] = res
		}
	}
	if themeData.Fonts.Italic != "" {
		if res := loadFontResource(themeData.Fonts.Italic); res != nil {
			theme.fonts["italic"] = res
		}
	}
	if themeData.Fonts.BoldItalic != "" {
		if res := loadFontResource(themeData.Fonts.BoldItalic); res != nil {
			theme.fonts["bolditalic"] = res
		}
	}
	if themeData.Fonts.Monospace != "" {
		if res := loadFontResource(themeData.Fonts.Monospace); res != nil {
			theme.fonts["monospace"] = res
		}
	}

	// Load custom icons if specified
	for name, path := range themeData.Icons {
		if res := loadIconResource(path); res != nil {
			theme.icons[name] = res
		}
	}

	return theme, nil
}

func (t *jsonTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color {
	nameStr := string(name)
	
	// Try variant-specific color first
	var hexColor string
	if variant == VariantDark {
		if c, ok := t.data.ColorsDark[nameStr]; ok {
			hexColor = c
		}
	} else {
		if c, ok := t.data.ColorsLight[nameStr]; ok {
			hexColor = c
		}
	}
	
	// Fall back to generic Colors if variant-specific not found
	if hexColor == "" {
		if c, ok := t.data.Colors[nameStr]; ok {
			hexColor = c
		}
	}

	if hexColor != "" {
		if c, err := parseHexColor(hexColor); err == nil {
			return c
		}
	}

	return t.fallback.Color(name, variant)
}

func (t *jsonTheme) Font(style fyne.TextStyle) fyne.Resource {
	var fontKey string
	if style.Monospace {
		fontKey = "monospace"
	} else if style.Bold && style.Italic {
		fontKey = "bolditalic"
	} else if style.Bold {
		fontKey = "bold"
	} else if style.Italic {
		fontKey = "italic"
	} else {
		fontKey = "regular"
	}

	if res, ok := t.fonts[fontKey]; ok {
		return res
	}

	return t.fallback.Font(style)
}

func (t *jsonTheme) Icon(name fyne.ThemeIconName) fyne.Resource {
	if res, ok := t.icons[string(name)]; ok {
		return res
	}
	return t.fallback.Icon(name)
}

func (t *jsonTheme) Size(name fyne.ThemeSizeName) float32 {
	if size, ok := t.data.Sizes[string(name)]; ok {
		return size
	}

	return t.fallback.Size(name)
}

// parseHexColor converts a hex color string to color.Color
// Supports: #RGB (3-digit), #RGBA (4-digit), #RRGGBB (6-digit), #RRGGBBAA (8-digit)
func parseHexColor(hex string) (color.Color, error) {
	var r, g, b, a uint8 = 0, 0, 0, 255

	if len(hex) > 0 && hex[0] == '#' {
		hex = hex[1:]
	}

	switch len(hex) {
	case 3:
		// #RGB -> #RRGGBB with full alpha
		if err := parseHexNibble(hex, 0, &r); err != nil {
			return nil, err
		}
		r = r | (r << 4)
		if err := parseHexNibble(hex, 1, &g); err != nil {
			return nil, err
		}
		g = g | (g << 4)
		if err := parseHexNibble(hex, 2, &b); err != nil {
			return nil, err
		}
		b = b | (b << 4)
	case 4:
		// #RGBA -> #RRGGBBAA
		if err := parseHexNibble(hex, 0, &r); err != nil {
			return nil, err
		}
		r = r | (r << 4)
		if err := parseHexNibble(hex, 1, &g); err != nil {
			return nil, err
		}
		g = g | (g << 4)
		if err := parseHexNibble(hex, 2, &b); err != nil {
			return nil, err
		}
		b = b | (b << 4)
		if err := parseHexNibble(hex, 3, &a); err != nil {
			return nil, err
		}
		a = a | (a << 4)
	case 6:
		// #RRGGBB with full alpha
		if err := parseHexByte(hex, 0, &r); err != nil {
			return nil, err
		}
		if err := parseHexByte(hex, 2, &g); err != nil {
			return nil, err
		}
		if err := parseHexByte(hex, 4, &b); err != nil {
			return nil, err
		}
	case 8:
		// #RRGGBBAA
		if err := parseHexByte(hex, 0, &r); err != nil {
			return nil, err
		}
		if err := parseHexByte(hex, 2, &g); err != nil {
			return nil, err
		}
		if err := parseHexByte(hex, 4, &b); err != nil {
			return nil, err
		}
		if err := parseHexByte(hex, 6, &a); err != nil {
			return nil, err
		}
	default:
		return nil, errors.New("invalid hex color format")
	}

	return color.NRGBA{R: r, G: g, B: b, A: a}, nil
}

// parseHexNibble parses a single hex digit (0-F) into the lower 4 bits of out
func parseHexNibble(hex string, offset int, out *uint8) error {
	c := hex[offset]
	if c >= '0' && c <= '9' {
		*out = c - '0'
	} else if c >= 'a' && c <= 'f' {
		*out = c - 'a' + 10
	} else if c >= 'A' && c <= 'F' {
		*out = c - 'A' + 10
	} else {
		return errors.New("invalid hex digit")
	}
	return nil
}

// parseHexByte parses two hex digits into a byte
func parseHexByte(hex string, offset int, out *uint8) error {
	val := uint8(0)
	for i := 0; i < 2; i++ {
		c := hex[offset+i]
		val <<= 4
		if c >= '0' && c <= '9' {
			val |= c - '0'
		} else if c >= 'a' && c <= 'f' {
			val |= c - 'a' + 10
		} else if c >= 'A' && c <= 'F' {
			val |= c - 'A' + 10
		} else {
			return errors.New("invalid hex digit")
		}
	}
	*out = val
	return nil
}

// loadFontResource loads a font file and returns it as a fyne.Resource
func loadFontResource(path string) fyne.Resource {
	data, err := os.ReadFile(path)
	if err != nil {
		fyne.LogError("Failed to load font", err)
		return nil
	}

	return fyne.NewStaticResource(path, data)
}

// loadIconResource loads an icon file and returns it as a fyne.Resource
func loadIconResource(path string) fyne.Resource {
	data, err := os.ReadFile(path)
	if err != nil {
		fyne.LogError("Failed to load icon", err)
		return nil
	}

	return fyne.NewStaticResource(path, data)
}
