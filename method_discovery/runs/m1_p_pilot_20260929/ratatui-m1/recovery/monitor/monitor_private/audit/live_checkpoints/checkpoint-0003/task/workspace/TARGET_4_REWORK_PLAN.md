# Target 4: Styled/Stylize Traits - Rework Plan

## Problem
Current `/app/src/style/stylize.rs` has wrong structure:
- Stylize trait contains both style()/set_style() AND all chainable methods
- Only one impl exists: `impl Stylize for Style`
- Missing all required Styled implementations

## Required Architecture (from lines 118-135)

### 1. Styled Trait (Foundation)
```rust
pub trait Styled {
    type Item;
    fn style(&self) -> Style;
    fn set_style(self, style: Style) -> Self::Item;
}
```

### 2. Stylize Trait (Blanket Implementation)
```rust
pub trait Stylize: Sized {
    // ~40 chainable methods: fg(), bg(), bold(), italic(), etc.
    // Uses self.style() and self.set_style() from Styled
}

// Blanket impl for all Styled types
impl<T: Styled<Item = T>> Stylize for T {
    // All methods implemented using Styled trait
}
```

### 3. Styled Implementations Required

**Text Types:**
- `&str` → returns `Span<'_>`
- `Span<'a>` → returns `Span<'a>`  
- `Style` → returns `Style`

**Widgets with style fields:**
- BarChart, Chart, Axis, Dataset
- Gauge, LineGauge
- List, ListItem
- Sparkline
- Table, Row, Cell
- Tabs
- Block
- Paragraph

## Implementation Steps

1. Rewrite stylize.rs with correct two-trait structure
2. Implement Styled for &str, Span, Style
3. Find all widgets with .style field
4. Implement Styled for each widget
5. Verify compilation

## Current File Status
- File: `/app/src/style/stylize.rs` (316 lines)
- Lines 1-305: Single Stylize trait with all methods
- Lines 308-316: Only `impl Stylize for Style`
- Needs complete rewrite to match requirements
