use crate::{
    layout::Alignment,
    text::Line,
};

/// Position of a title on a [`Block`](super::Block)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Position {
    /// Position title on the top border
    #[default]
    Top,
    /// Position title on the bottom border
    Bottom,
}

/// A title on a [`Block`](super::Block)
///
/// # Examples
///
/// ```
/// # use ratatui::widgets::block::{Title, Position};
/// # use ratatui::layout::Alignment;
/// # use ratatui::text::Line;
/// Title::from("Title")
///     .position(Position::Top)
///     .alignment(Alignment::Center);
/// ```
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Title<'a> {
    /// Title content
    pub content: Line<'a>,
    /// Alignment of the title
    pub alignment: Option<Alignment>,
    /// Position of the title
    pub position: Option<Position>,
}

impl<'a> Title<'a> {
    /// Set the content of the title
    pub fn content<T>(mut self, content: T) -> Title<'a>
    where
        T: Into<Line<'a>>,
    {
        self.content = content.into();
        self
    }

    /// Set the alignment of the title
    pub fn alignment(mut self, alignment: Alignment) -> Title<'a> {
        self.alignment = Some(alignment);
        self
    }

    /// Set the position of the title
    pub fn position(mut self, position: Position) -> Title<'a> {
        self.position = Some(position);
        self
    }
}

impl<'a> Default for Title<'a> {
    fn default() -> Title<'a> {
        Title {
            content: Line::from(""),
            alignment: None,
            position: None,
        }
    }
}

impl<'a, T> From<T> for Title<'a>
where
    T: Into<Line<'a>>,
{
    fn from(value: T) -> Self {
        Title {
            content: value.into(),
            alignment: None,
            position: None,
        }
    }
}
