use crate::style::{Color, Modifier, Style};
use crate::text::Span;
use crate::widgets::{
    Block, Paragraph,
    chart::{Axis, Dataset, Chart},
};
use crate::widgets::barchart::BarChart;
use crate::widgets::gauge::{Gauge, LineGauge};
use crate::widgets::list::{List, ListItem};
use crate::widgets::sparkline::Sparkline;
use crate::widgets::table::{Row, Cell};
use crate::widgets::tabs::Tabs;

/// A trait for objects that have an associated style
///
/// This trait provides the foundation for the fluent styling API by defining
/// how to get and set the style of an object.
///
/// # Associated Type
///
/// `Item` - The type returned when setting the style. Usually `Self`, but can differ
/// (e.g., `&str` returns `Span`).
pub trait Styled {
    type Item;

    /// Returns the current style of the object
    fn style(&self) -> Style;

    /// Sets the style of the object, returning the styled result
    fn set_style(self, style: Style) -> Self::Item;
}

/// A trait for fluently styling objects
///
/// This trait provides chainable methods for setting colors, modifiers, and other
/// style attributes on objects that implement [`Styled`].
///
/// # Examples
///
/// ```
/// use ratatui::prelude::*;
/// use ratatui::text::Span;
///
/// let span = Span::raw("Hello").blue().on_yellow().bold();
/// ```
///
/// This trait is automatically implemented for all types that implement [`Styled`]
/// where `Styled::Item = Self`.
pub trait Stylize: Sized {
    /// Returns a styled object with the given style applied
    #[must_use]
    fn stylize(self, style: Style) -> Self
    where
        Self: Styled<Item = Self>,
    {
        let current = self.style();
        self.set_style(current.patch(style))
    }

    // Foreground colors
    
    /// Sets the foreground color
    #[must_use]
    fn fg<C: Into<Color>>(self, color: C) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.stylize(Style::new().fg(color))
    }

    /// Sets the foreground color to black
    #[must_use]
    fn black(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::Black)
    }

    /// Sets the foreground color to dark gray
    #[must_use]
    fn dark_gray(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::DarkGray)
    }

    /// Sets the foreground color to red
    #[must_use]
    fn red(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::Red)
    }

    /// Sets the foreground color to dark red
    #[must_use]
    fn dark_red(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::DarkRed)
    }

    /// Sets the foreground color to green
    #[must_use]
    fn green(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::Green)
    }

    /// Sets the foreground color to dark green
    #[must_use]
    fn dark_green(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::DarkGreen)
    }

    /// Sets the foreground color to yellow
    #[must_use]
    fn yellow(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::Yellow)
    }

    /// Sets the foreground color to dark yellow
    #[must_use]
    fn dark_yellow(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::DarkYellow)
    }

    /// Sets the foreground color to blue
    #[must_use]
    fn blue(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::Blue)
    }

    /// Sets the foreground color to dark blue
    #[must_use]
    fn dark_blue(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::DarkBlue)
    }

    /// Sets the foreground color to magenta
    #[must_use]
    fn magenta(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::Magenta)
    }

    /// Sets the foreground color to dark magenta
    #[must_use]
    fn dark_magenta(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::DarkMagenta)
    }

    /// Sets the foreground color to cyan
    #[must_use]
    fn cyan(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::Cyan)
    }

    /// Sets the foreground color to dark cyan
    #[must_use]
    fn dark_cyan(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::DarkCyan)
    }

    /// Sets the foreground color to white
    #[must_use]
    fn white(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::White)
    }

    /// Sets the foreground color to gray
    #[must_use]
    fn gray(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.fg(Color::Gray)
    }

    // Background colors

    /// Sets the background color
    #[must_use]
    fn bg<C: Into<Color>>(self, color: C) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.stylize(Style::new().bg(color))
    }

    /// Sets the background color to black
    #[must_use]
    fn on_black(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::Black)
    }

    /// Sets the background color to dark gray
    #[must_use]
    fn on_dark_gray(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::DarkGray)
    }

    /// Sets the background color to red
    #[must_use]
    fn on_red(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::Red)
    }

    /// Sets the background color to dark red
    #[must_use]
    fn on_dark_red(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::DarkRed)
    }

    /// Sets the background color to green
    #[must_use]
    fn on_green(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::Green)
    }

    /// Sets the background color to dark green
    #[must_use]
    fn on_dark_green(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::DarkGreen)
    }

    /// Sets the background color to yellow
    #[must_use]
    fn on_yellow(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::Yellow)
    }

    /// Sets the background color to dark yellow
    #[must_use]
    fn on_dark_yellow(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::DarkYellow)
    }

    /// Sets the background color to blue
    #[must_use]
    fn on_blue(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::Blue)
    }

    /// Sets the background color to dark blue
    #[must_use]
    fn on_dark_blue(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::DarkBlue)
    }

    /// Sets the background color to magenta
    #[must_use]
    fn on_magenta(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::Magenta)
    }

    /// Sets the background color to dark magenta
    #[must_use]
    fn on_dark_magenta(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::DarkMagenta)
    }

    /// Sets the background color to cyan
    #[must_use]
    fn on_cyan(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::Cyan)
    }

    /// Sets the background color to dark cyan
    #[must_use]
    fn on_dark_cyan(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::DarkCyan)
    }

    /// Sets the background color to white
    #[must_use]
    fn on_white(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::White)
    }

    /// Sets the background color to gray
    #[must_use]
    fn on_gray(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.bg(Color::Gray)
    }

    // Modifiers

    /// Adds the given modifier
    #[must_use]
    fn add_modifier(self, modifier: Modifier) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.stylize(Style::new().add_modifier(modifier))
    }

    /// Removes the given modifier
    #[must_use]
    fn remove_modifier(self, modifier: Modifier) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.stylize(Style::new().remove_modifier(modifier))
    }

    /// Makes the text bold
    #[must_use]
    fn bold(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.add_modifier(Modifier::BOLD)
    }

    /// Makes the text dim
    #[must_use]
    fn dim(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.add_modifier(Modifier::DIM)
    }

    /// Makes the text italic
    #[must_use]
    fn italic(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.add_modifier(Modifier::ITALIC)
    }

    /// Makes the text underlined
    #[must_use]
    fn underlined(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.add_modifier(Modifier::UNDERLINED)
    }

    /// Makes the text slowly blinking
    #[must_use]
    fn slow_blink(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.add_modifier(Modifier::SLOW_BLINK)
    }

    /// Makes the text rapidly blinking
    #[must_use]
    fn rapid_blink(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.add_modifier(Modifier::RAPID_BLINK)
    }

    /// Reverses the foreground and background colors
    #[must_use]
    fn reversed(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.add_modifier(Modifier::REVERSED)
    }

    /// Makes the text hidden
    #[must_use]
    fn hidden(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.add_modifier(Modifier::HIDDEN)
    }

    /// Makes the text crossed out
    #[must_use]
    fn crossed_out(self) -> Self
    where
        Self: Styled<Item = Self>,
    {
        self.add_modifier(Modifier::CROSSED_OUT)
    }
}

// Blanket implementation of Stylize for all types that implement Styled<Item = Self>
impl<T: Styled<Item = T>> Stylize for T {}

// Implement Styled for Style itself
impl Styled for Style {
    type Item = Style;

    fn style(&self) -> Style {
        *self
    }

    fn set_style(self, style: Style) -> Self::Item {
        style
    }
}

// Implement Styled for &str - returns Span
impl<'a> Styled for &'a str {
    type Item = Span<'a>;

    fn style(&self) -> Style {
        Style::default()
    }

    fn set_style(self, style: Style) -> Self::Item {
        Span::styled(self, style)
    }
}

// Implement Styled for Span
impl<'a> Styled for Span<'a> {
    type Item = Span<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for Block
impl<'a> Styled for Block<'a> {
    type Item = Block<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for Paragraph
impl<'a> Styled for Paragraph<'a> {
    type Item = Paragraph<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for BarChart
impl<'a> Styled for BarChart<'a> {
    type Item = BarChart<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for Axis
impl<'a> Styled for Axis<'a> {
    type Item = Axis<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for Dataset
impl<'a> Styled for Dataset<'a> {
    type Item = Dataset<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for Gauge
impl<'a> Styled for Gauge<'a> {
    type Item = Gauge<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for ListItem
impl<'a> Styled for ListItem<'a> {
    type Item = ListItem<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for List
impl<'a> Styled for List<'a> {
    type Item = List<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for Sparkline
impl<'a> Styled for Sparkline<'a> {
    type Item = Sparkline<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for Row
impl<'a> Styled for Row<'a> {
    type Item = Row<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for Cell
impl<'a> Styled for Cell<'a> {
    type Item = Cell<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for Tabs
impl<'a> Styled for Tabs<'a> {
    type Item = Tabs<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for Chart
impl<'a> Styled for Chart<'a> {
    type Item = Chart<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}

// Implement Styled for LineGauge
impl<'a> Styled for LineGauge<'a> {
    type Item = LineGauge<'a>;

    fn style(&self) -> Style {
        self.style
    }

    fn set_style(mut self, style: Style) -> Self::Item {
        self.style = self.style.patch(style);
        self
    }
}
