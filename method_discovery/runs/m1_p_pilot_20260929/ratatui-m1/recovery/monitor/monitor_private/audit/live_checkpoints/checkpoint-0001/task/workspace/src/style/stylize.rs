use crate::style::{Color, Modifier, Style};

/// A trait for objects that can be styled
///
/// This trait provides a fluent interface for styling any type that implements it.
///
/// # Examples
///
/// ```
/// use ratatui::prelude::*;
/// use ratatui::text::{Line, Span};
///
/// let span = Span::raw("Hello").blue().on_yellow().bold();
/// let line = Line::from("World").red().italic();
/// ```
pub trait Stylize: Sized {
    /// Returns the Style of the object
    fn style(&self) -> Style;

    /// Sets the style of the object
    fn set_style(self, style: Style) -> Self;

    /// Returns a styled object with the given style applied
    #[must_use]
    fn stylize(mut self, style: Style) -> Self {
        self = self.set_style(self.style().patch(style));
        self
    }

    // Foreground colors
    
    /// Sets the foreground color
    #[must_use]
    fn fg<C: Into<Color>>(self, color: C) -> Self {
        self.stylize(Style::new().fg(color))
    }

    /// Sets the foreground color to black
    #[must_use]
    fn black(self) -> Self {
        self.fg(Color::Black)
    }

    /// Sets the foreground color to dark gray
    #[must_use]
    fn dark_gray(self) -> Self {
        self.fg(Color::DarkGray)
    }

    /// Sets the foreground color to red
    #[must_use]
    fn red(self) -> Self {
        self.fg(Color::Red)
    }

    /// Sets the foreground color to dark red
    #[must_use]
    fn dark_red(self) -> Self {
        self.fg(Color::DarkRed)
    }

    /// Sets the foreground color to green
    #[must_use]
    fn green(self) -> Self {
        self.fg(Color::Green)
    }

    /// Sets the foreground color to dark green
    #[must_use]
    fn dark_green(self) -> Self {
        self.fg(Color::DarkGreen)
    }

    /// Sets the foreground color to yellow
    #[must_use]
    fn yellow(self) -> Self {
        self.fg(Color::Yellow)
    }

    /// Sets the foreground color to dark yellow
    #[must_use]
    fn dark_yellow(self) -> Self {
        self.fg(Color::DarkYellow)
    }

    /// Sets the foreground color to blue
    #[must_use]
    fn blue(self) -> Self {
        self.fg(Color::Blue)
    }

    /// Sets the foreground color to dark blue
    #[must_use]
    fn dark_blue(self) -> Self {
        self.fg(Color::DarkBlue)
    }

    /// Sets the foreground color to magenta
    #[must_use]
    fn magenta(self) -> Self {
        self.fg(Color::Magenta)
    }

    /// Sets the foreground color to dark magenta
    #[must_use]
    fn dark_magenta(self) -> Self {
        self.fg(Color::DarkMagenta)
    }

    /// Sets the foreground color to cyan
    #[must_use]
    fn cyan(self) -> Self {
        self.fg(Color::Cyan)
    }

    /// Sets the foreground color to dark cyan
    #[must_use]
    fn dark_cyan(self) -> Self {
        self.fg(Color::DarkCyan)
    }

    /// Sets the foreground color to white
    #[must_use]
    fn white(self) -> Self {
        self.fg(Color::White)
    }

    /// Sets the foreground color to gray
    #[must_use]
    fn gray(self) -> Self {
        self.fg(Color::Gray)
    }

    // Background colors

    /// Sets the background color
    #[must_use]
    fn bg<C: Into<Color>>(self, color: C) -> Self {
        self.stylize(Style::new().bg(color))
    }

    /// Sets the background color to black
    #[must_use]
    fn on_black(self) -> Self {
        self.bg(Color::Black)
    }

    /// Sets the background color to dark gray
    #[must_use]
    fn on_dark_gray(self) -> Self {
        self.bg(Color::DarkGray)
    }

    /// Sets the background color to red
    #[must_use]
    fn on_red(self) -> Self {
        self.bg(Color::Red)
    }

    /// Sets the background color to dark red
    #[must_use]
    fn on_dark_red(self) -> Self {
        self.bg(Color::DarkRed)
    }

    /// Sets the background color to green
    #[must_use]
    fn on_green(self) -> Self {
        self.bg(Color::Green)
    }

    /// Sets the background color to dark green
    #[must_use]
    fn on_dark_green(self) -> Self {
        self.bg(Color::DarkGreen)
    }

    /// Sets the background color to yellow
    #[must_use]
    fn on_yellow(self) -> Self {
        self.bg(Color::Yellow)
    }

    /// Sets the background color to dark yellow
    #[must_use]
    fn on_dark_yellow(self) -> Self {
        self.bg(Color::DarkYellow)
    }

    /// Sets the background color to blue
    #[must_use]
    fn on_blue(self) -> Self {
        self.bg(Color::Blue)
    }

    /// Sets the background color to dark blue
    #[must_use]
    fn on_dark_blue(self) -> Self {
        self.bg(Color::DarkBlue)
    }

    /// Sets the background color to magenta
    #[must_use]
    fn on_magenta(self) -> Self {
        self.bg(Color::Magenta)
    }

    /// Sets the background color to dark magenta
    #[must_use]
    fn on_dark_magenta(self) -> Self {
        self.bg(Color::DarkMagenta)
    }

    /// Sets the background color to cyan
    #[must_use]
    fn on_cyan(self) -> Self {
        self.bg(Color::Cyan)
    }

    /// Sets the background color to dark cyan
    #[must_use]
    fn on_dark_cyan(self) -> Self {
        self.bg(Color::DarkCyan)
    }

    /// Sets the background color to white
    #[must_use]
    fn on_white(self) -> Self {
        self.bg(Color::White)
    }

    /// Sets the background color to gray
    #[must_use]
    fn on_gray(self) -> Self {
        self.bg(Color::Gray)
    }

    // Modifiers

    /// Adds the given modifier
    #[must_use]
    fn add_modifier(self, modifier: Modifier) -> Self {
        self.stylize(Style::new().add_modifier(modifier))
    }

    /// Removes the given modifier
    #[must_use]
    fn remove_modifier(self, modifier: Modifier) -> Self {
        self.stylize(Style::new().remove_modifier(modifier))
    }

    /// Makes the text bold
    #[must_use]
    fn bold(self) -> Self {
        self.add_modifier(Modifier::BOLD)
    }

    /// Makes the text dim
    #[must_use]
    fn dim(self) -> Self {
        self.add_modifier(Modifier::DIM)
    }

    /// Makes the text italic
    #[must_use]
    fn italic(self) -> Self {
        self.add_modifier(Modifier::ITALIC)
    }

    /// Makes the text underlined
    #[must_use]
    fn underlined(self) -> Self {
        self.add_modifier(Modifier::UNDERLINED)
    }

    /// Makes the text slowly blinking
    #[must_use]
    fn slow_blink(self) -> Self {
        self.add_modifier(Modifier::SLOW_BLINK)
    }

    /// Makes the text rapidly blinking
    #[must_use]
    fn rapid_blink(self) -> Self {
        self.add_modifier(Modifier::RAPID_BLINK)
    }

    /// Reverses the foreground and background colors
    #[must_use]
    fn reversed(self) -> Self {
        self.add_modifier(Modifier::REVERSED)
    }

    /// Makes the text hidden
    #[must_use]
    fn hidden(self) -> Self {
        self.add_modifier(Modifier::HIDDEN)
    }

    /// Makes the text crossed out
    #[must_use]
    fn crossed_out(self) -> Self {
        self.add_modifier(Modifier::CROSSED_OUT)
    }
}

// Implement Stylize for Style itself
impl Stylize for Style {
    fn style(&self) -> Style {
        *self
    }

    fn set_style(self, style: Style) -> Self {
        style
    }
}
