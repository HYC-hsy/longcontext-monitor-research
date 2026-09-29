use super::Bar;
use crate::text::Line;

/// A group of bars to be displayed in a [`BarChart`](super::BarChart).
///
/// # Examples
///
/// ```
/// # use ratatui::widgets::{Bar, BarGroup};
/// # use ratatui::text::Line;
/// let group = BarGroup::default()
///     .label(Line::from("Group 1"))
///     .bars(&[Bar::default().value(10), Bar::default().value(20)]);
/// ```
#[derive(Debug, Clone, Default)]
pub struct BarGroup<'a> {
    pub(super) label: Option<Line<'a>>,
    pub(super) bars: Vec<Bar<'a>>,
}

impl<'a> BarGroup<'a> {
    /// Set the group label
    pub fn label(mut self, label: Line<'a>) -> Self {
        self.label = Some(label);
        self
    }

    /// Set the bars in this group
    pub fn bars(mut self, bars: &[Bar<'a>]) -> Self {
        self.bars = bars.to_vec();
        self
    }
}

// Backward compatibility: convert from old-style data format
impl<'a> From<&'a [(&'a str, u64)]> for BarGroup<'a> {
    fn from(data: &'a [(&'a str, u64)]) -> Self {
        let bars = data
            .iter()
            .map(|&(label, value)| Bar::default().label(Line::from(label)).value(value))
            .collect();
        BarGroup {
            label: None,
            bars,
        }
    }
}

impl<'a, const N: usize> From<&'a [(&'a str, u64); N]> for BarGroup<'a> {
    fn from(data: &'a [(&'a str, u64); N]) -> Self {
        BarGroup::from(&data[..])
    }
}

impl<'a> From<Vec<(&'a str, u64)>> for BarGroup<'a> {
    fn from(data: Vec<(&'a str, u64)>) -> Self {
        let bars = data
            .into_iter()
            .map(|(label, value)| Bar::default().label(Line::from(label)).value(value))
            .collect();
        BarGroup {
            label: None,
            bars,
        }
    }
}
