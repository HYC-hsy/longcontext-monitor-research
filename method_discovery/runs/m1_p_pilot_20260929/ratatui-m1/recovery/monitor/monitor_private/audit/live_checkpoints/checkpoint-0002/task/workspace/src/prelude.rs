//! # Prelude
//!
//! The prelude is a collection of the most commonly used types and traits in ratatui.
//! It's designed to be glob imported to bring these items into scope with a single line.
//!
//! # Examples
//!
//! ```
//! use ratatui::prelude::*;
//! ```

// Re-export commonly used types
pub use crate::{
    backend::Backend,
    buffer::Buffer,
    layout::{Alignment, Constraint, Direction, Layout, Margin, Rect},
    style::{Color, Modifier, Style, Stylize},
    symbols,
    terminal::{CompletedFrame, Frame, Terminal, TerminalOptions, Viewport},
    text::{Line, Span, Text},
    widgets::{
        block::{Position, Title},
        Block, BorderType, Borders, Clear, Padding, Widget,
    },
};
