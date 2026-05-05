# CodeYZ Web UI

## Overview

The Web UI is the main workspace for running tasks, reviewing results, and controlling agent behavior.  
It combines chat, workflow status, timeline, explorer, and layout controls in one interface.

## Workflow Area

- Shows the core run flow: `Task -> Plan -> Patch -> Tests -> Diff -> Approval`
- Includes a compact run summary:
  - Task
  - Patch
  - Tests
  - Risk
  - Decision
- Summary rows can be expanded for inline details.

## Focus Modes

Use focus modes to prioritize specific work contexts:

- `Workflow`: workflow card and run status emphasized
- `Code`: explorer and code context emphasized
- `Chat`: chat area emphasized, side panels reduced

Modes are persistent and restored across reloads.

## Command Palette

- Open with `Ctrl+K`
- Supports quick action execution for mode switching and panel toggles
- Includes filtering and recent-command behavior
- Keyboard navigation:
  - `ArrowUp` / `ArrowDown`
  - `Enter` to execute
  - `Escape` to close

## Keyboard Shortcuts

- `Ctrl+K` - Open Command Palette
- `Ctrl+1` - Workflow Mode
- `Ctrl+2` - Code Mode
- `Ctrl+3` - Chat Mode
- `Ctrl+B` - Toggle left sidebar
- `Ctrl+E` - Toggle explorer panel
- `Ctrl+Z` - Undo last UI action
- `Ctrl+Shift+Z` - Redo UI action

Shortcuts do not trigger while typing in form controls (`input`, `textarea`, `select`, contenteditable).

## Layout Preferences

- Panels are collapsible
- Left and right side areas are resizable
- Widths, mode, panel state, and related UI settings are persisted in `localStorage`
- Preferences are centralized under `codeyz_ui_preferences`
- Layout can be exported/imported from the UI
- Session restore reapplies the last known UI state on reload

## Timeline

- Run list uses virtual scrolling for large histories
- Replay events are grouped and compressed (for example multiple test or patch events)
- Grouped entries are expandable to inspect individual events

## Troubleshooting

- If UI layout feels broken, switch focus mode and re-expand panels
- If shortcuts do not work, check whether an input field has focus
- If layout state is unexpected, re-import a known layout export
- Extension-related browser console warnings (for example `runtime.lastError`) are often external to CodeYZ
