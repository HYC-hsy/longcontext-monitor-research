use crate::{style::Style, text::Line};

/// A bar to be shown in a [`BarChart`](super::BarChart).
///
/// # Examples
///
/// ```
/// # use ratatui::widgets::Bar;
/// # use ratatui::style::{Style, Color};
/// # use ratatui::text::Line;
/// let bar = Bar::default()
///     .value(64)
///     .label(Line::from("Label"))
///     .style(Style::default().fg(Color::Red))
///     .value_style(Style::default().fg(Color::Green))
///     .text_value(String::from("64 units"));
/// ```
#[derive(Debug, Clone, Default)]
pub struct Bar<'a> {
    pub(super) value: u64,
    pub(super) label: Line<'a>,
    pub(super) style: Style,
    pub(super) value_style: Style,
    pub(super) text_value: Option<String>,
}

impl<'a> Bar<'a> {
    /// Set the value of the bar
    pub fn value(mut self, value: u64) -> Self {
        self.value = value;
        self
    }

    /// Set the label of the bar
    pub fn label(mut self, label: Line<'a>) -> Self {
        self.label = label;
        self
    }

    /// Set the style of the bar
    pub fn style(mut self, style: Style) -> Self {
        self.style = style;
        self
    }

    /// Set the value style of the bar
    pub fn value_style(mut self, style: Style) -> Self {
        self.value_style = style;
        self
    }

    /// Set a custom text value instead of the numeric value
    pub fn text_value(mut self, text_value: String) -> Self {
        self.text_value = Some(text_value);
        self
    }
}
