mod bar;
mod bar_group;

pub use bar::Bar;
pub use bar_group::BarGroup;

use crate::{
    buffer::Buffer,
    layout::Rect,
    style::Style,
    symbols,
    text::Line,
    widgets::{Block, Widget},
};
use std::cmp::min;
use unicode_width::UnicodeWidthStr;

/// Display multiple bars in a single widget
///
/// # Examples
///
/// ```
/// # use ratatui::widgets::{Block, Borders, BarChart, Bar, BarGroup};
/// # use ratatui::style::{Style, Color, Modifier};
/// # use ratatui::text::Line;
/// BarChart::default()
///     .block(Block::default().title("BarChart").borders(Borders::ALL))
///     .bar_width(3)
///     .bar_gap(1)
///     .group_gap(2)
///     .bar_style(Style::default().fg(Color::Yellow).bg(Color::Red))
///     .value_style(Style::default().fg(Color::Red).add_modifier(Modifier::BOLD))
///     .label_style(Style::default().fg(Color::White))
///     .data(BarGroup::default().bars(&[
///         Bar::default().label(Line::from("B1")).value(10),
///         Bar::default().label(Line::from("B2")).value(20),
///     ]))
///     .max(25);
/// ```
#[derive(Debug, Clone)]
pub struct BarChart<'a> {
    /// Block to wrap the widget in
    block: Option<Block<'a>>,
    /// The width of each bar
    bar_width: u16,
    /// The gap between each bar within a group
    bar_gap: u16,
    /// The gap between groups
    group_gap: u16,
    /// Set of symbols used to display the data
    bar_set: symbols::bar::Set,
    /// Style of the bars
    bar_style: Style,
    /// Style of the values printed at the bottom of each bar
    value_style: Style,
    /// Style of the labels printed under each bar
    label_style: Style,
    /// Style for the widget
    style: Style,
    /// Groups of bars to plot on the chart
    data: Vec<BarGroup<'a>>,
    /// Value necessary for a bar to reach the maximum height (if no value is specified,
    /// the maximum value in the data is taken as reference)
    max: Option<u64>,
}

impl<'a> Default for BarChart<'a> {
    fn default() -> BarChart<'a> {
        BarChart {
            block: None,
            max: None,
            data: Vec::new(),
            bar_style: Style::default(),
            bar_width: 1,
            bar_gap: 1,
            group_gap: 1,
            bar_set: symbols::bar::NINE_LEVELS,
            value_style: Style::default(),
            label_style: Style::default(),
            style: Style::default(),
        }
    }
}

impl<'a> BarChart<'a> {
    /// Add a group of bars to the chart
    pub fn data(mut self, group: impl Into<BarGroup<'a>>) -> BarChart<'a> {
        self.data.push(group.into());
        self
    }

    pub fn block(mut self, block: Block<'a>) -> BarChart<'a> {
        self.block = Some(block);
        self
    }

    pub fn max(mut self, max: u64) -> BarChart<'a> {
        self.max = Some(max);
        self
    }

    pub fn bar_style(mut self, style: Style) -> BarChart<'a> {
        self.bar_style = style;
        self
    }

    pub fn bar_width(mut self, width: u16) -> BarChart<'a> {
        self.bar_width = width;
        self
    }

    pub fn bar_gap(mut self, gap: u16) -> BarChart<'a> {
        self.bar_gap = gap;
        self
    }

    pub fn group_gap(mut self, gap: u16) -> BarChart<'a> {
        self.group_gap = gap;
        self
    }

    pub fn bar_set(mut self, bar_set: symbols::bar::Set) -> BarChart<'a> {
        self.bar_set = bar_set;
        self
    }

    pub fn value_style(mut self, style: Style) -> BarChart<'a> {
        self.value_style = style;
        self
    }

    pub fn label_style(mut self, style: Style) -> BarChart<'a> {
        self.label_style = style;
        self
    }

    pub fn style(mut self, style: Style) -> BarChart<'a> {
        self.style = style;
        self
    }
}

impl<'a> Widget for BarChart<'a> {
    fn render(mut self, area: Rect, buf: &mut Buffer) {
        buf.set_style(area, self.style);

        let chart_area = match self.block.take() {
            Some(b) => {
                let inner_area = b.inner(area);
                b.render(area, buf);
                inner_area
            }
            None => area,
        };

        if chart_area.height < 2 {
            return;
        }

        // Calculate maximum value across all bars
        let max = self.max.unwrap_or_else(|| {
            self.data
                .iter()
                .flat_map(|group| group.bars.iter())
                .map(|bar| bar.value)
                .max()
                .unwrap_or_default()
        });

        let mut current_x = chart_area.left();
        let label_height = 1;
        let group_label_height = 1;
        let value_height = 1;
        let bars_area_height = chart_area.height.saturating_sub(label_height + group_label_height + value_height);

        for group in &self.data {
            // Calculate group width
            let group_width = if group.bars.is_empty() {
                0
            } else {
                group.bars.len() as u16 * self.bar_width + (group.bars.len() as u16 - 1) * self.bar_gap
            };

            // Check if group fits
            if current_x + group_width > chart_area.right() {
                break;
            }

            let mut bar_x = current_x;

            // Render each bar in the group
            for bar in &group.bars {
                if bar_x + self.bar_width > chart_area.right() {
                    break;
                }

                // Calculate bar height (using 8-level sub-cell resolution)
                let mut bar_height = bar.value * u64::from(bars_area_height) * 8 / std::cmp::max(max, 1);

                // Render bar from bottom to top
                for j in (0..bars_area_height).rev() {
                    let symbol = match bar_height {
                        0 => self.bar_set.empty,
                        1 => self.bar_set.one_eighth,
                        2 => self.bar_set.one_quarter,
                        3 => self.bar_set.three_eighths,
                        4 => self.bar_set.half,
                        5 => self.bar_set.five_eighths,
                        6 => self.bar_set.three_quarters,
                        7 => self.bar_set.seven_eighths,
                        _ => self.bar_set.full,
                    };

                    let bar_style = bar.style.patch(self.bar_style);
                    for x in 0..self.bar_width {
                        buf.get_mut(bar_x + x, chart_area.top() + j)
                            .set_symbol(symbol)
                            .set_style(bar_style);
                    }

                    if bar_height > 8 {
                        bar_height -= 8;
                    } else {
                        bar_height = 0;
                    }
                }

                // Render value label (if not zero and fits)
                if bar.value != 0 {
                    let value_label = bar
                        .text_value
                        .as_ref()
                        .map(|s| s.as_str())
                        .unwrap_or_else(|| {
                            // This is a bit of a hack - we need to store the formatted value somewhere
                            // For now, we'll format it inline (note: this may be recalculated multiple times)
                            ""
                        });
                    
                    // If text_value is not set, format the numeric value
                    let formatted_value;
                    let display_value = if bar.text_value.is_some() {
                        value_label
                    } else {
                        formatted_value = format!("{}", bar.value);
                        formatted_value.as_str()
                    };

                    let width = display_value.width() as u16;
                    if width <= self.bar_width {
                        let value_style = bar.value_style.patch(self.value_style);
                        buf.set_string(
                            bar_x + (self.bar_width - width) / 2,
                            chart_area.bottom() - label_height - group_label_height - value_height,
                            display_value,
                            value_style,
                        );
                    }
                }

                // Render bar label
                let label_style = self.label_style;
                let label_y = chart_area.bottom() - label_height - group_label_height;
                for (i, span) in bar.label.spans.iter().enumerate() {
                    if i == 0 {
                        buf.set_stringn(
                            bar_x,
                            label_y,
                            &span.content,
                            self.bar_width as usize,
                            span.style.patch(label_style),
                        );
                    }
                }

                bar_x += self.bar_width + self.bar_gap;
            }

            // Render group label
            if let Some(ref group_label) = group.label {
                let label_y = chart_area.bottom() - group_label_height;
                let mut offset = 0;
                for span in &group_label.spans {
                    if current_x + offset < chart_area.right() {
                        let available = (chart_area.right() - current_x - offset) as usize;
                        buf.set_stringn(
                            current_x + offset,
                            label_y,
                            &span.content,
                            available.min(span.content.width()),
                            span.style.patch(self.label_style),
                        );
                        offset += span.content.width() as u16;
                    }
                }
            }

            current_x += group_width + self.group_gap;
        }
    }
}
