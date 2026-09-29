use crate::{
    buffer::Buffer,
    layout::Rect,
    style::Style,
    widgets::{StatefulWidget, Widget},
};

/// Scrollbar symbols for different orientations and styles
#[derive(Debug, Clone, Copy)]
pub struct Set {
    pub track: &'static str,
    pub thumb: &'static str,
    pub begin: &'static str,
    pub end: &'static str,
}

/// Double-line vertical scrollbar symbols
pub const DOUBLE_VERTICAL: Set = Set {
    track: "║",
    thumb: "█",
    begin: "▲",
    end: "▼",
};

/// Double-line horizontal scrollbar symbols
pub const DOUBLE_HORIZONTAL: Set = Set {
    track: "═",
    thumb: "█",
    begin: "◄",
    end: "►",
};

/// Single-line vertical scrollbar symbols
pub const VERTICAL: Set = Set {
    track: "│",
    thumb: "█",
    begin: "↑",
    end: "↓",
};

/// Single-line horizontal scrollbar symbols
pub const HORIZONTAL: Set = Set {
    track: "─",
    thumb: "█",
    begin: "←",
    end: "→",
};

/// Direction for scrolling
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ScrollDirection {
    /// Scroll forward (down/right)
    #[default]
    Forward,
    /// Scroll backward (up/left)
    Backward,
}

/// Orientation and position of the scrollbar
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum ScrollbarOrientation {
    /// Vertical scrollbar on the right side
    #[default]
    VerticalRight,
    /// Vertical scrollbar on the left side
    VerticalLeft,
    /// Horizontal scrollbar on the bottom
    HorizontalBottom,
    /// Horizontal scrollbar on the top
    HorizontalTop,
}

/// State for the scrollbar widget
#[derive(Debug, Clone, Default)]
pub struct ScrollbarState {
    position: usize,
    content_length: usize,
    viewport_content_length: usize,
}

impl ScrollbarState {
    /// Create a new scrollbar state
    pub fn new(content_length: usize) -> Self {
        Self {
            position: 0,
            content_length,
            viewport_content_length: 0,
        }
    }

    /// Set the scroll position
    pub fn position(mut self, position: usize) -> Self {
        self.position = position;
        self.clamp_position();
        self
    }

    /// Set the total content length
    pub fn content_length(mut self, content_length: usize) -> Self {
        self.content_length = content_length;
        self.clamp_position();
        self
    }

    /// Set the viewport content length
    pub fn viewport_content_length(mut self, viewport_content_length: usize) -> Self {
        self.viewport_content_length = viewport_content_length;
        self
    }

    fn clamp_position(&mut self) {
        if self.content_length > 0 {
            self.position = self.position.min(self.content_length - 1);
        } else {
            self.position = 0;
        }
    }

    /// Move to the first position
    pub fn first(&mut self) {
        self.position = 0;
    }

    /// Move to the last position
    pub fn last(&mut self) {
        if self.content_length > 0 {
            self.position = self.content_length - 1;
        } else {
            self.position = 0;
        }
    }

    /// Move to the previous position
    pub fn prev(&mut self) {
        self.position = self.position.saturating_sub(1);
    }

    /// Move to the next position
    pub fn next(&mut self) {
        if self.content_length > 0 {
            self.position = (self.position + 1).min(self.content_length - 1);
        }
    }

    /// Scroll in the given direction
    pub fn scroll(&mut self, direction: ScrollDirection) {
        match direction {
            ScrollDirection::Forward => self.next(),
            ScrollDirection::Backward => self.prev(),
        }
    }
}

/// A scrollbar widget
#[derive(Debug, Clone)]
pub struct Scrollbar<'a> {
    orientation: ScrollbarOrientation,
    thumb_symbol: &'a str,
    thumb_style: Style,
    track_symbol: &'a str,
    track_style: Style,
    begin_symbol: Option<&'a str>,
    begin_style: Style,
    end_symbol: Option<&'a str>,
    end_style: Style,
    style: Style,
}

impl<'a> Default for Scrollbar<'a> {
    fn default() -> Self {
        Self {
            orientation: ScrollbarOrientation::VerticalRight,
            thumb_symbol: DOUBLE_VERTICAL.thumb,
            thumb_style: Style::default(),
            track_symbol: DOUBLE_VERTICAL.track,
            track_style: Style::default(),
            begin_symbol: Some(DOUBLE_VERTICAL.begin),
            begin_style: Style::default(),
            end_symbol: Some(DOUBLE_VERTICAL.end),
            end_style: Style::default(),
            style: Style::default(),
        }
    }
}

impl<'a> Scrollbar<'a> {
    /// Create a new scrollbar with the given orientation
    pub fn new(orientation: ScrollbarOrientation) -> Self {
        let symbols = match orientation {
            ScrollbarOrientation::VerticalRight | ScrollbarOrientation::VerticalLeft => {
                DOUBLE_VERTICAL
            }
            ScrollbarOrientation::HorizontalBottom | ScrollbarOrientation::HorizontalTop => {
                DOUBLE_HORIZONTAL
            }
        };

        Self {
            orientation,
            thumb_symbol: symbols.thumb,
            track_symbol: symbols.track,
            begin_symbol: Some(symbols.begin),
            end_symbol: Some(symbols.end),
            ..Default::default()
        }
    }

    /// Set the orientation (also resets symbols to match)
    pub fn orientation(mut self, orientation: ScrollbarOrientation) -> Self {
        self.orientation = orientation;
        let symbols = match orientation {
            ScrollbarOrientation::VerticalRight | ScrollbarOrientation::VerticalLeft => {
                DOUBLE_VERTICAL
            }
            ScrollbarOrientation::HorizontalBottom | ScrollbarOrientation::HorizontalTop => {
                DOUBLE_HORIZONTAL
            }
        };
        self.thumb_symbol = symbols.thumb;
        self.track_symbol = symbols.track;
        self.begin_symbol = Some(symbols.begin);
        self.end_symbol = Some(symbols.end);
        self
    }

    /// Set the orientation and symbols
    pub fn orientation_and_symbol(
        mut self,
        orientation: ScrollbarOrientation,
        symbols: Set,
    ) -> Self {
        self.orientation = orientation;
        self.thumb_symbol = symbols.thumb;
        self.track_symbol = symbols.track;
        self.begin_symbol = Some(symbols.begin);
        self.end_symbol = Some(symbols.end);
        self
    }

    /// Set all symbols at once
    pub fn symbols(mut self, symbols: Set) -> Self {
        self.thumb_symbol = symbols.thumb;
        self.track_symbol = symbols.track;
        self.begin_symbol = Some(symbols.begin);
        self.end_symbol = Some(symbols.end);
        self
    }

    /// Set the thumb symbol
    pub fn thumb_symbol(mut self, symbol: &'a str) -> Self {
        self.thumb_symbol = symbol;
        self
    }

    /// Set the thumb style
    pub fn thumb_style(mut self, style: Style) -> Self {
        self.thumb_style = style;
        self
    }

    /// Set the track symbol
    pub fn track_symbol(mut self, symbol: &'a str) -> Self {
        self.track_symbol = symbol;
        self
    }

    /// Set the track style
    pub fn track_style(mut self, style: Style) -> Self {
        self.track_style = style;
        self
    }

    /// Set the begin symbol
    pub fn begin_symbol(mut self, symbol: Option<&'a str>) -> Self {
        self.begin_symbol = symbol;
        self
    }

    /// Set the begin style
    pub fn begin_style(mut self, style: Style) -> Self {
        self.begin_style = style;
        self
    }

    /// Set the end symbol
    pub fn end_symbol(mut self, symbol: Option<&'a str>) -> Self {
        self.end_symbol = symbol;
        self
    }

    /// Set the end style
    pub fn end_style(mut self, style: Style) -> Self {
        self.end_style = style;
        self
    }

    /// Set the style for all components
    pub fn style(mut self, style: Style) -> Self {
        self.style = style;
        self.thumb_style = style;
        self.track_style = style;
        self.begin_style = style;
        self.end_style = style;
        self
    }
}

impl<'a> StatefulWidget for Scrollbar<'a> {
    type State = ScrollbarState;

    fn render(self, area: Rect, buf: &mut Buffer, state: &mut Self::State) {
        if state.content_length == 0 {
            return;
        }

        let (track_start, track_axis, is_vertical) = match self.orientation {
            ScrollbarOrientation::VerticalRight => (area.top(), area.right().saturating_sub(1), true),
            ScrollbarOrientation::VerticalLeft => (area.top(), area.left(), true),
            ScrollbarOrientation::HorizontalBottom => (area.left(), area.bottom().saturating_sub(1), false),
            ScrollbarOrientation::HorizontalTop => (area.left(), area.top(), false),
        };

        let track_length = if is_vertical {
            area.height as usize
        } else {
            area.width as usize
        };

        if track_length == 0 {
            return;
        }

        // Calculate available track length after arrows
        let mut available_start = 0;
        let mut available_length = track_length;

        if self.begin_symbol.is_some() {
            available_start += 1;
            available_length = available_length.saturating_sub(1);
        }

        if self.end_symbol.is_some() {
            available_length = available_length.saturating_sub(1);
        }

        if available_length < 1 {
            return;
        }

        // Calculate thumb size and position
        let thumb_size = if state.viewport_content_length == 0 {
            available_length
        } else {
            let ratio = state.viewport_content_length as f64 / state.content_length as f64;
            ((available_length as f64 * ratio).round() as usize).max(1).min(available_length)
        };

        let scrollable_length = state.content_length.saturating_sub(state.viewport_content_length).max(1);
        let thumb_position = if scrollable_length <= 1 {
            0
        } else {
            let ratio = state.position as f64 / scrollable_length as f64;
            let max_pos = available_length.saturating_sub(thumb_size);
            ((max_pos as f64 * ratio).round() as usize).min(max_pos)
        };

        // Render begin arrow
        if let Some(symbol) = self.begin_symbol {
            let (x, y) = if is_vertical {
                (track_axis, track_start)
            } else {
                (track_start, track_axis)
            };
            buf.get_mut(x, y)
                .set_symbol(symbol)
                .set_style(self.style.patch(self.begin_style));
        }

        // Render track and thumb
        for i in 0..available_length {
            let (x, y) = if is_vertical {
                (track_axis, track_start + (available_start + i) as u16)
            } else {
                (track_start + (available_start + i) as u16, track_axis)
            };

            if i >= thumb_position && i < thumb_position + thumb_size {
                buf.get_mut(x, y)
                    .set_symbol(self.thumb_symbol)
                    .set_style(self.style.patch(self.thumb_style));
            } else {
                buf.get_mut(x, y)
                    .set_symbol(self.track_symbol)
                    .set_style(self.style.patch(self.track_style));
            }
        }

        // Render end arrow
        if let Some(symbol) = self.end_symbol {
            let (x, y) = if is_vertical {
                (track_axis, track_start + (track_length - 1) as u16)
            } else {
                (track_start + (track_length - 1) as u16, track_axis)
            };
            buf.get_mut(x, y)
                .set_symbol(symbol)
                .set_style(self.style.patch(self.end_style));
        }
    }
}
