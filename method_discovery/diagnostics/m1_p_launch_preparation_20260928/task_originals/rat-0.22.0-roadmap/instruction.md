# TUI Library Development Roadmap

## Overview

This version marks a significant step in making the terminal UI library more expressive and ergonomic. The headline feature is a brand-new **Scrollbar widget**, filling a long-standing gap for applications that display scrollable content — lists, text views, and data tables can now provide visual scroll position feedback. This is the first new interactive-feeling widget in several releases, and it comes with a flexible rendering model (vertical/horizontal, customizable symbols and styles, stateful position tracking).

In parallel, the two most visually prominent existing widgets receive major upgrades. **Block** evolves from supporting a single title string to a multi-title system where each title can be independently positioned (top/bottom) and aligned (left/center/right) — enabling rich framing for complex layouts. **BarChart** gains a hierarchical data model through new `Bar` and `BarGroup` types, allowing grouped bar comparisons with per-bar styling and custom text values.

Alongside these widget-level changes, the library's styling API undergoes a foundational rework. A new **Stylize** trait system introduces chainable shorthand methods (`.red()`, `.bold()`, `.on_blue()`) on strings, spans, and all widgets — replacing verbose `Style::default().fg(Color::Red)...` boilerplate. A complementary **prelude** module makes common imports a one-liner. Finally, lower-level ergonomic improvements round out the release: style and layout builder methods become `const`-compatible, and the color parser gains flexible name formats (hyphenated, "bright" prefix, "grey"/"gray" variants). These improvements collectively serve the goal of making TUI code more concise and readable without sacrificing expressiveness.

---

## Goals

Our overarching goal is to make the library more visually capable and ergonomically pleasant. The headline effort is a **Scrollbar widget** (Target 1) — the first new interactive-feeling primitive in several releases, filling a critical gap for any application with scrollable content. Building on this momentum, we plan to modernize the two most prominent existing widgets: **BarChart** gains grouped-bar support (Target 2) and **Block** evolves to multi-title rendering (Target 3). These widget improvements are the core of the release.

Supporting these widget-level changes, we will rework the styling ergonomics across the entire library. A **Stylize** trait system (Target 4) and a **prelude** module (Target 5) together eliminate most boilerplate from everyday TUI code. Finally, lower-level const-compatibility and color-parsing improvements (Target 6) round out the release.

- **Target 1: Scrollbar Widget** — new stateful widget for scroll position feedback
- **Target 2: BarChart Groups** — hierarchical data model for grouped bars
- **Target 3: Block Multi-Title Support** — multiple independently positioned titles
- **Target 4: Stylization System** — chainable style shorthands on all types
- **Target 5: Prelude Module** — single-line imports for common types
- **Target 6: Const Builders and Color Parsing** — const-compatible APIs and flexible color names

---

## Target 1: Scrollbar Widget

Users displaying scrollable content need a visual indicator of scroll position. The library currently has no scrollbar primitive, forcing application authors to build their own.

### Requirements

1. **`src/widgets/scrollbar.rs`** (new file):

A `Scrollbar` widget rendered via the `StatefulWidget` trait, paired with a `ScrollbarState` that tracks scroll position.

2. **Scrollbar symbols**: Define a `Set` struct in the scrollbar module with four public `&'static str` fields: `track`, `thumb`, `begin`, `end`. Provide four predefined constant sets:
- `DOUBLE_VERTICAL` — using `"▲"`, `"║"`, `"█"`, `"▼"` style characters
- `DOUBLE_HORIZONTAL` — horizontal equivalents (`"◄"`, `"═"`, `"█"`, `"►"`)
- `VERTICAL` — single-line (`"↑"`, `"│"`, `"█"`, `"↓"`)
- `HORIZONTAL` — single-line (`"←"`, `"─"`, `"█"`, `"→"`)

3. **ScrollDirection** enum: `Forward` (default) and `Backward`.

4. **ScrollbarOrientation** enum: `VerticalRight` (default), `VerticalLeft`, `HorizontalBottom`, `HorizontalTop`.

5. **ScrollbarState**: Tracks scroll position through three fields settable via consuming builder methods: `position()`, `content_length()`, and `viewport_content_length()`. Derive `Debug` and `Default`. Navigation methods (all `&mut self`): `prev()`, `next()`, `first()`, `last()`, and `scroll(direction: ScrollDirection)`. Position must be clamped to the valid range `[0, content_length - 1]` at all times — `first()` goes to the beginning, `last()` goes to the end, `prev()`/`next()` move by one step, and `scroll()` delegates based on direction.

6. **Scrollbar** struct (lifetime `'a`): constructed via `new(orientation)` or `Default::default()` (defaults to `VerticalRight` with `DOUBLE_VERTICAL` symbols). Builder methods: `orientation()` (also resets symbols to match vertical/horizontal), `orientation_and_symbol()`, `thumb_symbol()`, `thumb_style()`, `track_symbol()`, `track_style()`, `begin_symbol(Option<&'a str>)`, `begin_style()`, `end_symbol(Option<&'a str>)`, `end_style()`, `symbols(Set)`, `style(Style)` (sets all four style fields at once).

7. **Rendering behavior**: Implements `StatefulWidget` with `State = ScrollbarState`. The scrollbar occupies the selected edge of the area based on orientation (right column, left column, top row, or bottom row). When begin/end arrow symbols are enabled, they occupy the first/last cell of the track, reducing the available space for the track body. If the remaining track length after arrows is less than 1 cell, nothing renders. The thumb size should reflect the ratio of viewport to total content (minimum 1 cell); when `viewport_content_length` is 0, the thumb fills the entire track. The thumb position should reflect the current scroll position relative to total content. When content_length is 0 or the area is too small, nothing renders.

8. **`src/widgets/mod.rs`**: Declare the scrollbar module as `pub mod scrollbar` (not `mod scrollbar`) so that the symbol sets (`Set`, `DOUBLE_VERTICAL`, `DOUBLE_HORIZONTAL`, `VERTICAL`, `HORIZONTAL`) are accessible via the `ratatui::widgets::scrollbar` path. Additionally, re-export `Scrollbar`, `ScrollbarState`, `ScrollbarOrientation`, and `ScrollDirection` at the `widgets` level.

---

## Target 2: BarChart Groups

The current bar chart accepts only a flat slice of `(label, value)` pairs. Applications comparing data across groups (e.g., monthly revenue by product line) must render multiple charts. A hierarchical data model would allow grouped bars within a single chart.

### Requirements

1. **`src/widgets/barchart/bar.rs`** (new file):

A `Bar<'a>` struct representing a single bar. Fields (all settable via builder methods returning `Self`): `value(u64)`, `label(Line<'a>)`, `style(Style)`, `value_style(Style)`, `text_value(String)`. The `text_value` method allows setting a custom display string instead of the numeric value. Derive `Debug`, `Clone`, `Default`.

2. **`src/widgets/barchart/bar_group.rs`** (new file):

A `BarGroup<'a>` struct holding an optional `label: Option<Line<'a>>` and `bars: Vec<Bar<'a>>`. Builder methods: `label(Line<'a>)` and `bars(&[Bar<'a>])`. Implement `From<&[(&'a str, u64)]>` (and array/Vec variants) for backward compatibility — each tuple becomes a `Bar` with the string as label and the u64 as value. Derive `Debug`, `Clone`, `Default`.

3. **`src/widgets/barchart/mod.rs`** (replaces old `src/widgets/barchart.rs`):

Refactor `BarChart<'a>` to store `data: Vec<BarGroup<'a>>` instead of `data: &'a [(&'a str, u64)]`. The `data()` method now accepts `impl Into<BarGroup<'a>>` and **pushes** to the internal Vec (allowing multiple `.data()` calls to add groups). Add a `group_gap(u16)` method to control spacing between groups. Existing methods (`block`, `max`, `bar_style`, `bar_width`, `bar_gap`, `bar_set`, `value_style`, `label_style`, `style`) remain.

4. **Rendering rules** (extending the existing rendering logic to support groups):
- Bar heights use the existing sub-cell resolution system (8-level Unicode block characters). The bottom portion of the chart area is reserved for labels.
- Each bar displays its numeric value (or `text_value` if set) above the bar, and its label below. Values are not shown when `value == 0` or when the value string does not fit within `bar_width`.
- When a `BarGroup` has a label, it is displayed below the individual bar labels, aligned to the group's starting position.
- Groups are laid out left-to-right. Group width depends on the number of bars, `bar_width`, and `bar_gap`. Adjacent groups are separated by `group_gap` columns.
- Overflow handling: if a group would exceed the available width, it and all subsequent groups are not rendered.
- Backward compatibility: single-group rendering via the `From<&[(&str, u64)]>` conversion should produce visual output consistent with the previous implementation.

5. **`src/widgets/mod.rs`**: Export `Bar` and `BarGroup` alongside `BarChart`.

---

## Target 3: Block Multi-Title Support

Currently `Block` supports a single title string. Complex layouts need multiple title elements — for example, a title on the left and a status indicator on the right, or titles on both top and bottom borders.

### Requirements

1. **`src/title.rs`** (new file):

A `Title<'a>` struct with three public fields: `content: Line<'a>`, `alignment: Option<Alignment>`, `position: Option<Position>`. When `alignment` or `position` is `None`, the block's default values are used. Builder methods: `content()`, `alignment(Alignment)`, `position(Position)`. Implement `From<T> for Title<'a>` where `T: Into<Line<'a>>` — this allows strings to convert directly to titles. The `Position` enum: `Top` (default) and `Bottom`.

2. **`src/widgets/block.rs`** (modify):

Replace the single `title: Option<Line<'a>>` with `titles: Vec<Title<'a>>`. The `.title()` method now accepts `impl Into<Title<'a>>` and **pushes** to the Vec. Add fields/methods:
- `titles_style: Style` — patched onto all titles (set via `title_style()`)
- `titles_alignment: Alignment` — default alignment for titles without explicit alignment (set via `title_alignment()`)
- `titles_position: Position` — default position for titles without explicit position (set via `title_position()`)

3. **Rendering**: Titles sharing the same position render on the same border line. Within a position, left-aligned titles render left-to-right, right-aligned render right-to-left, and center-aligned titles are centered based on the full block width. Titles in the same alignment are separated by a single cell gap (when rendered on a border line, the gap cell retains the border's horizontal line symbol; when no border is present, it is a space). When titles overlap, rendering order determines which content is visible (right titles render first, then center, then left — left takes priority).

4. **Export paths**: `Title` and `Position` must be importable via `ratatui::widgets::block::title::{Title, Position}`.

---

## Target 4: Stylization System

Building styles via `Style::default().fg(Color::Red).bg(Color::Blue).add_modifier(Modifier::BOLD)` is verbose. A fluent chainable API on strings, spans, and widgets would dramatically reduce boilerplate.

### Requirements

1. **`src/style/stylize.rs`** (new file):

Define the `Styled` trait:
```
pub trait Styled {
    type Item;
    fn style(&self) -> Style;
    fn set_style(self, style: Style) -> Self::Item;
}
```

Define the `Stylize` trait, blanket-implemented for all `Styled` types, providing:
- `fg(color)` and `bg(color)` — set foreground/background
- `reset()` — reset to default style
- `add_modifier()` and `remove_modifier()`
- 16 foreground color shorthands: `black()`, `red()`, `green()`, `yellow()`, `blue()`, `magenta()`, `cyan()`, `gray()`, `dark_gray()`, `light_red()`, `light_green()`, `light_yellow()`, `light_blue()`, `light_magenta()`, `light_cyan()`, `white()`
- 16 background color shorthands: `on_black()`, `on_red()`, ..., `on_white()`
- 9 modifier shorthands: `bold()`, `dim()`, `italic()`, `underlined()`, `slow_blink()`, `rapid_blink()`, `reversed()`, `hidden()`, `crossed_out()`
- 9 modifier removal shorthands: `not_bold()`, `not_dim()`, ..., `not_crossed_out()`

2. **Implement `Styled` for**: `&str` (returns `Span`), `Span`, `Style`. Additionally implement `Styled` for all remaining widgets that have a `style` field: `BarChart`, `Chart`, `Axis`, `Dataset`, `Gauge`, `LineGauge`, `List`, `ListItem`, `Sparkline`, `Table`, `Row`, `Cell`, `Tabs`, `Block`, `Paragraph`.

3. **Re-export**: `Stylize` and `Styled` traits must be accessible from `ratatui::style::{Stylize, Styled}`.

This enables patterns like: `"hello".red().on_blue().bold()` yielding a `Span` with the equivalent style.

---

## Target 5: Prelude Module

Users currently need many import lines to use basic functionality. A prelude module should re-export the most commonly used types.

### Requirements

1. **`src/prelude.rs`** (new file):

Create a `prelude` module that re-exports:
- **Backend**: `Backend` trait, plus backend modules (`crossterm`, `termion`, `termwiz` behind their feature gates)
- **Buffer**: `Buffer`
- **Layout**: `Alignment`, `Constraint`, `Corner`, `Direction`, `Layout`, `Margin`, `Rect`
- **Style**: `Color`, `Modifier`, `Style`, `Styled`, `Stylize`
- **Symbols**: `Marker`
- **Terminal**: `Frame`, `Terminal`, `TerminalOptions`, `Viewport`
- **Text**: `Line`, `Masked`, `Span`, `Text`
- Each category's module should also be re-exported (e.g., `pub use crate::style;`) so users can qualify ambiguous names

2. **`src/lib.rs`**: Add `pub mod prelude;`

Users should be able to write `use ratatui::prelude::*;` and have access to all major types.

---

## Target 6: Const Builders and Color Parsing

Style and layout construction should work in `const` contexts for global constants. Additionally, color name parsing should be more flexible and forgiving.

### Requirements

1. **`src/style.rs`** (modify):

Make `Style::add_modifier()` and `Style::remove_modifier()` `const fn`.

Enhanced `Color::from_str`: Normalize input by stripping `" "`, `"-"`, `"_"` separators and lowercasing. Treat `"bright"` as equivalent to `"light"`. Support `"grey"` as alias for `"gray"`, and `"silver"` as alias for `Gray`. Handle edge cases in the light-color family: `"light black"` maps to `DarkGray`, `"light white"` maps to `White`, and `"light gray"` maps to `White` (since there is no `LightGray` variant). All existing color names must continue to work.

Implement a custom `Debug` format for `Modifier` such that: `Modifier::empty()` displays as `"NONE"`, individual flags display as their name (e.g., `"BOLD"`), and combinations display with ` | ` separator (e.g., `"BOLD | DIM"`).

2. **`src/layout.rs`** (modify):

Add a new `pub const fn new() -> Layout` method that returns a default Layout (direction: Vertical, zero margins, empty constraints). `Default::default()` should delegate to `Layout::new()`. Make the following existing methods `const fn`: `Layout::margin()`, `Layout::horizontal_margin()`, `Layout::vertical_margin()`, `Layout::direction()`, `Rect::area()`, `Rect::left()`, `Rect::right()`, `Rect::top()`, `Rect::bottom()`.

Fix `Constraint::apply` for `Percentage` and `Ratio`: the result must never exceed the input length. Additionally, `Ratio(n, 0)` must not panic — it should return a sensible value rather than dividing by zero.

---

## Completion Criteria

- All new types (`Scrollbar`, `ScrollbarState`, `ScrollbarOrientation`, `ScrollDirection`, `Bar`, `BarGroup`, `Title`, `Position`, `Stylize`, `Styled`) importable from their documented paths
- Existing APIs remain backward compatible (old `BarChart::data(&[(&str, u64)])` still works via `From` impls)
- All builder methods return `Self` for chaining
- Const builders compile in `const` contexts
- Prelude provides single-line access to all major types
