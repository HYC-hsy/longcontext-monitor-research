mod title;

pub use self::title::{Position, Title};

use crate::{
    buffer::Buffer,
    layout::{Alignment, Rect},
    style::Style,
    symbols::line,
    text::{Line, Span},
    widgets::{Borders, Widget},
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BorderType {
    Plain,
    Rounded,
    Double,
    Thick,
}

impl BorderType {
    pub fn line_symbols(border_type: BorderType) -> line::Set {
        match border_type {
            BorderType::Plain => line::NORMAL,
            BorderType::Rounded => line::ROUNDED,
            BorderType::Double => line::DOUBLE,
            BorderType::Thick => line::THICK,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct Padding {
    pub left: u16,
    pub right: u16,
    pub top: u16,
    pub bottom: u16,
}

impl Padding {
    pub fn new(left: u16, right: u16, top: u16, bottom: u16) -> Self {
        Padding {
            left,
            right,
            top,
            bottom,
        }
    }

    pub fn zero() -> Self {
        Padding {
            left: 0,
            right: 0,
            top: 0,
            bottom: 0,
        }
    }

    pub fn horizontal(value: u16) -> Self {
        Padding {
            left: value,
            right: value,
            top: 0,
            bottom: 0,
        }
    }

    pub fn vertical(value: u16) -> Self {
        Padding {
            left: 0,
            right: 0,
            top: value,
            bottom: value,
        }
    }

    pub fn uniform(value: u16) -> Self {
        Padding {
            left: value,
            right: value,
            top: value,
            bottom: value,
        }
    }
}

/// Base widget to be used with all upper level ones. It may be used to display a box border around
/// the widget and/or add a title.
///
/// # Examples
///
/// ```
/// # use ratatui::widgets::{Block, BorderType, Borders};
/// # use ratatui::widgets::block::{Title, Position};
/// # use ratatui::style::{Style, Color};
/// # use ratatui::layout::Alignment;
/// Block::default()
///     .title("Block")
///     .borders(Borders::LEFT | Borders::RIGHT)
///     .border_style(Style::default().fg(Color::White))
///     .border_type(BorderType::Rounded)
///     .style(Style::default().bg(Color::Black));
/// ```
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Block<'a> {
    /// Optional titles on the block
    titles: Vec<Title<'a>>,
    /// Visible borders
    borders: Borders,
    /// Border style
    border_style: Style,
    /// Type of the border. The default is plain lines but one can choose to have rounded corners
    /// or doubled lines instead.
    border_type: BorderType,
    /// Widget style
    style: Style,
    /// Block padding
    padding: Padding,
    /// Default style for all titles
    titles_style: Style,
    /// Default alignment for titles without explicit alignment
    titles_alignment: Alignment,
    /// Default position for titles without explicit position
    titles_position: Position,
}

impl<'a> Default for Block<'a> {
    fn default() -> Block<'a> {
        Block {
            titles: Vec::new(),
            borders: Borders::NONE,
            border_style: Style::default(),
            border_type: BorderType::Plain,
            style: Style::default(),
            padding: Padding::zero(),
            titles_style: Style::default(),
            titles_alignment: Alignment::Left,
            titles_position: Position::Top,
        }
    }
}

impl<'a> Block<'a> {
    /// Add a title to the block
    ///
    /// # Examples
    ///
    /// ```
    /// # use ratatui::widgets::{Block, block::Title};
    /// # use ratatui::text::Line;
    /// # use ratatui::layout::Alignment;
    /// Block::default()
    ///     .title("Title") // default title
    ///     .title(Title::from("Left").alignment(Alignment::Left))
    ///     .title(Title::from("Right").alignment(Alignment::Right));
    /// ```
    pub fn title<T>(mut self, title: T) -> Block<'a>
    where
        T: Into<Title<'a>>,
    {
        self.titles.push(title.into());
        self
    }

    /// Add multiple titles to the block
    ///
    /// # Examples
    ///
    /// ```
    /// # use ratatui::widgets::{Block, block::Title};
    /// Block::default()
    ///     .titles(vec![
    ///         Title::from("Title 1"),
    ///         Title::from("Title 2"),
    ///     ]);
    /// ```
    pub fn titles<I>(mut self, titles: I) -> Block<'a>
    where
        I: IntoIterator,
        I::Item: Into<Title<'a>>,
    {
        self.titles.extend(titles.into_iter().map(|t| t.into()));
        self
    }

    #[deprecated(
        since = "0.10.0",
        note = "You should use styling capabilities of `text::Line` given as argument of the `title` method to apply styling to the title."
    )]
    pub fn title_style(mut self, style: Style) -> Block<'a> {
        if let Some(title) = self.titles.last_mut() {
            title.content = Line::from(Span::styled(String::from(&title.content), style));
        }
        self
    }

    #[deprecated(
        since = "0.11.0",
        note = "Use `Title::alignment()` when creating a title"
    )]
    pub fn title_alignment(mut self, alignment: Alignment) -> Block<'a> {
        if let Some(title) = self.titles.last_mut() {
            title.alignment = Some(alignment);
        }
        self
    }

    #[deprecated(
        since = "0.11.0",
        note = "Use `Title::position(Position::Bottom)` when creating a title"
    )]
    pub fn title_on_bottom(mut self) -> Block<'a> {
        if let Some(title) = self.titles.last_mut() {
            title.position = Some(Position::Bottom);
        }
        self
    }

    /// Set the default style for all titles
    ///
    /// This style is patched on top of all title styles
    pub fn titles_style(mut self, style: Style) -> Block<'a> {
        self.titles_style = style;
        self
    }

    /// Set the default alignment for titles without explicit alignment
    pub fn titles_alignment(mut self, alignment: Alignment) -> Block<'a> {
        self.titles_alignment = alignment;
        self
    }

    /// Set the default position for titles without explicit position
    pub fn titles_position(mut self, position: Position) -> Block<'a> {
        self.titles_position = position;
        self
    }

    pub fn border_style(mut self, style: Style) -> Block<'a> {
        self.border_style = style;
        self
    }

    pub fn style(mut self, style: Style) -> Block<'a> {
        self.style = style;
        self
    }

    pub fn borders(mut self, flag: Borders) -> Block<'a> {
        self.borders = flag;
        self
    }

    pub fn border_type(mut self, border_type: BorderType) -> Block<'a> {
        self.border_type = border_type;
        self
    }

    /// Compute the inner area of a block based on its border visibility rules.
    ///
    /// # Examples
    ///
    /// ```
    /// // Draw a block nested within another block
    /// use ratatui::{backend::TestBackend, buffer::Buffer, terminal::Terminal, widgets::{Block, Borders}};
    /// let backend = TestBackend::new(15, 5);
    /// let mut terminal = Terminal::new(backend).unwrap();
    /// let outer_block = Block::default()
    ///     .title("Outer Block")
    ///     .borders(Borders::ALL);
    /// let inner_block = Block::default()
    ///     .title("Inner Block")
    ///     .borders(Borders::ALL);
    /// terminal.draw(|f| {
    ///     let inner_area = outer_block.inner(f.size());
    ///     f.render_widget(outer_block, f.size());
    ///     f.render_widget(inner_block, inner_area);
    /// });
    /// let expected = Buffer::with_lines(vec![
    ///     "┌Outer Block──┐",
    ///     "│┌Inner Block┐│",
    ///     "││           ││",
    ///     "│└───────────┘│",
    ///     "└─────────────┘",
    /// ]);
    /// terminal.backend().assert_buffer(&expected);
    /// ```
    pub fn inner(&self, area: Rect) -> Rect {
        let mut inner = area;
        if self.borders.intersects(Borders::LEFT) {
            inner.x = inner.x.saturating_add(1).min(inner.right());
            inner.width = inner.width.saturating_sub(1);
        }
        if self.borders.intersects(Borders::TOP) || self.title.is_some() {
            inner.y = inner.y.saturating_add(1).min(inner.bottom());
            inner.height = inner.height.saturating_sub(1);
        }
        if self.borders.intersects(Borders::RIGHT) {
            inner.width = inner.width.saturating_sub(1);
        }
        if self.borders.intersects(Borders::BOTTOM) {
            inner.height = inner.height.saturating_sub(1);
        }

        inner.x = inner.x.saturating_add(self.padding.left);
        inner.y = inner.y.saturating_add(self.padding.top);

        inner.width = inner
            .width
            .saturating_sub(self.padding.left + self.padding.right);
        inner.height = inner
            .height
            .saturating_sub(self.padding.top + self.padding.bottom);

        inner
    }

    pub fn padding(mut self, padding: Padding) -> Block<'a> {
        self.padding = padding;
        self
    }
}

impl<'a> Widget for Block<'a> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        if area.area() == 0 {
            return;
        }
        buf.set_style(area, self.style);
        let symbols = BorderType::line_symbols(self.border_type);

        // Sides
        if self.borders.intersects(Borders::LEFT) {
            for y in area.top()..area.bottom() {
                buf.get_mut(area.left(), y)
                    .set_symbol(symbols.vertical)
                    .set_style(self.border_style);
            }
        }
        if self.borders.intersects(Borders::TOP) {
            for x in area.left()..area.right() {
                buf.get_mut(x, area.top())
                    .set_symbol(symbols.horizontal)
                    .set_style(self.border_style);
            }
        }
        if self.borders.intersects(Borders::RIGHT) {
            let x = area.right() - 1;
            for y in area.top()..area.bottom() {
                buf.get_mut(x, y)
                    .set_symbol(symbols.vertical)
                    .set_style(self.border_style);
            }
        }
        if self.borders.intersects(Borders::BOTTOM) {
            let y = area.bottom() - 1;
            for x in area.left()..area.right() {
                buf.get_mut(x, y)
                    .set_symbol(symbols.horizontal)
                    .set_style(self.border_style);
            }
        }

        // Corners
        if self.borders.contains(Borders::RIGHT | Borders::BOTTOM) {
            buf.get_mut(area.right() - 1, area.bottom() - 1)
                .set_symbol(symbols.bottom_right)
                .set_style(self.border_style);
        }
        if self.borders.contains(Borders::RIGHT | Borders::TOP) {
            buf.get_mut(area.right() - 1, area.top())
                .set_symbol(symbols.top_right)
                .set_style(self.border_style);
        }
        if self.borders.contains(Borders::LEFT | Borders::BOTTOM) {
            buf.get_mut(area.left(), area.bottom() - 1)
                .set_symbol(symbols.bottom_left)
                .set_style(self.border_style);
        }
        if self.borders.contains(Borders::LEFT | Borders::TOP) {
            buf.get_mut(area.left(), area.top())
                .set_symbol(symbols.top_left)
                .set_style(self.border_style);
        }

        // Titles
        let left_border_dx = u16::from(self.borders.intersects(Borders::LEFT));
        let right_border_dx = u16::from(self.borders.intersects(Borders::RIGHT));
        let title_area_width = area
            .width
            .saturating_sub(left_border_dx)
            .saturating_sub(right_border_dx);

        for title in &self.titles {
            let position = title.position.unwrap_or(self.titles_position);
            let alignment = title.alignment.unwrap_or(self.titles_alignment);
            
            let title_dx = match alignment {
                Alignment::Left => left_border_dx,
                Alignment::Center => area.width.saturating_sub(title.content.width() as u16) / 2,
                Alignment::Right => area
                    .width
                    .saturating_sub(title.content.width() as u16)
                    .saturating_sub(right_border_dx),
            };

            let title_x = area.left() + title_dx;
            let title_y = match position {
                Position::Top => area.top(),
                Position::Bottom => area.bottom() - 1,
            };

            // Apply titles_style as default, then patch with title's style
            let title_content = title.content.clone().patch_style(self.titles_style);
            buf.set_line(title_x, title_y, &title_content, title_area_width);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::layout::Rect;

    #[test]
    fn inner_takes_into_account_the_borders() {
        // No borders
        assert_eq!(
            Block::default().inner(Rect::default()),
            Rect {
                x: 0,
                y: 0,
                width: 0,
                height: 0
            },
            "no borders, width=0, height=0"
        );
        assert_eq!(
            Block::default().inner(Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 1
            }),
            Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 1
            },
            "no borders, width=1, height=1"
        );

        // Left border
        assert_eq!(
            Block::default().borders(Borders::LEFT).inner(Rect {
                x: 0,
                y: 0,
                width: 0,
                height: 1
            }),
            Rect {
                x: 0,
                y: 0,
                width: 0,
                height: 1
            },
            "left, width=0"
        );
        assert_eq!(
            Block::default().borders(Borders::LEFT).inner(Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 1
            }),
            Rect {
                x: 1,
                y: 0,
                width: 0,
                height: 1
            },
            "left, width=1"
        );
        assert_eq!(
            Block::default().borders(Borders::LEFT).inner(Rect {
                x: 0,
                y: 0,
                width: 2,
                height: 1
            }),
            Rect {
                x: 1,
                y: 0,
                width: 1,
                height: 1
            },
            "left, width=2"
        );

        // Top border
        assert_eq!(
            Block::default().borders(Borders::TOP).inner(Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 0
            }),
            Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 0
            },
            "top, height=0"
        );
        assert_eq!(
            Block::default().borders(Borders::TOP).inner(Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 1
            }),
            Rect {
                x: 0,
                y: 1,
                width: 1,
                height: 0
            },
            "top, height=1"
        );
        assert_eq!(
            Block::default().borders(Borders::TOP).inner(Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 2
            }),
            Rect {
                x: 0,
                y: 1,
                width: 1,
                height: 1
            },
            "top, height=2"
        );

        // Right border
        assert_eq!(
            Block::default().borders(Borders::RIGHT).inner(Rect {
                x: 0,
                y: 0,
                width: 0,
                height: 1
            }),
            Rect {
                x: 0,
                y: 0,
                width: 0,
                height: 1
            },
            "right, width=0"
        );
        assert_eq!(
            Block::default().borders(Borders::RIGHT).inner(Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 1
            }),
            Rect {
                x: 0,
                y: 0,
                width: 0,
                height: 1
            },
            "right, width=1"
        );
        assert_eq!(
            Block::default().borders(Borders::RIGHT).inner(Rect {
                x: 0,
                y: 0,
                width: 2,
                height: 1
            }),
            Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 1
            },
            "right, width=2"
        );

        // Bottom border
        assert_eq!(
            Block::default().borders(Borders::BOTTOM).inner(Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 0
            }),
            Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 0
            },
            "bottom, height=0"
        );
        assert_eq!(
            Block::default().borders(Borders::BOTTOM).inner(Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 1
            }),
            Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 0
            },
            "bottom, height=1"
        );
        assert_eq!(
            Block::default().borders(Borders::BOTTOM).inner(Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 2
            }),
            Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 1
            },
            "bottom, height=2"
        );

        // All borders
        assert_eq!(
            Block::default()
                .borders(Borders::ALL)
                .inner(Rect::default()),
            Rect {
                x: 0,
                y: 0,
                width: 0,
                height: 0
            },
            "all borders, width=0, height=0"
        );
        assert_eq!(
            Block::default().borders(Borders::ALL).inner(Rect {
                x: 0,
                y: 0,
                width: 1,
                height: 1
            }),
            Rect {
                x: 1,
                y: 1,
                width: 0,
                height: 0,
            },
            "all borders, width=1, height=1"
        );
        assert_eq!(
            Block::default().borders(Borders::ALL).inner(Rect {
                x: 0,
                y: 0,
                width: 2,
                height: 2,
            }),
            Rect {
                x: 1,
                y: 1,
                width: 0,
                height: 0,
            },
            "all borders, width=2, height=2"
        );
        assert_eq!(
            Block::default().borders(Borders::ALL).inner(Rect {
                x: 0,
                y: 0,
                width: 3,
                height: 3,
            }),
            Rect {
                x: 1,
                y: 1,
                width: 1,
                height: 1,
            },
            "all borders, width=3, height=3"
        );
    }

    #[test]
    fn inner_takes_into_account_the_title() {
        assert_eq!(
            Block::default().title("Test").inner(Rect {
                x: 0,
                y: 0,
                width: 0,
                height: 1,
            }),
            Rect {
                x: 0,
                y: 1,
                width: 0,
                height: 0,
            },
        );
        assert_eq!(
            Block::default()
                .title("Test")
                .title_alignment(Alignment::Center)
                .inner(Rect {
                    x: 0,
                    y: 0,
                    width: 0,
                    height: 1,
                }),
            Rect {
                x: 0,
                y: 1,
                width: 0,
                height: 0,
            },
        );
        assert_eq!(
            Block::default()
                .title("Test")
                .title_alignment(Alignment::Right)
                .inner(Rect {
                    x: 0,
                    y: 0,
                    width: 0,
                    height: 1,
                }),
            Rect {
                x: 0,
                y: 1,
                width: 0,
                height: 0,
            },
        );
    }
}
