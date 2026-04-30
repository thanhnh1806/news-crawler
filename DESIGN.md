---
name: news-crawler-dashboard
version: "1.0"
description: Elegant design system for news-crawler economic news dashboard
platform: web
density: 4
variance: 3
motion: 3
---

# Design System: News Crawler Dashboard

## 1. Visual Theme & Atmosphere

A refined, editorial interface for economic news consumption. The atmosphere evokes a premium financial publication — think The Economist meets a modern fintech dashboard. Warm limestone backgrounds create a paper-like reading experience, while confident typography and restrained accent colors signal credibility and authority.

- **Density**: 4/10 — spacious, article-focused
- **Variance**: 3/10 — mostly symmetric, editorial grid
- **Motion**: 3/10 — subtle fades, hover transitions

## 2. Color Palette & Roles

- **Warm Limestone** (#F7F5F2) — Primary page background, paper-like warmth
- **Pure Surface** (#FFFFFF) — Card backgrounds, elevated content layers
- **Deep Ink** (#1A1C1E) — Headlines, primary text, article titles
- **Slate Sophisticate** (#6C7278) — Secondary text, timestamps, source labels
- **Boston Clay** (#B8422E) — Single accent for crypto positive indicators, active states, focus rings
- **Forest Green** (#2D6A4F) — Crypto positive change indicator
- **Muted Rose** (#C4A7A1) — Crypto negative change indicator
- **Whisper Border** (rgba(226,232,240,0.5)) — 1px card borders, dividers
- **Ghost Hover** (#F0EEEB) — Subtle hover state backgrounds

## 3. Typography Rules

- **H1 (Page Title)**: Public Sans, 2.5rem (40px), weight 700, letter-spacing -0.02em
- **H2 (Section Title)**: Public Sans, 1.5rem (24px), weight 600
- **H3 (Article Title)**: Public Sans, 1.125rem (18px), weight 600, line-height 1.4
- **Body**: Public Sans, 1rem (16px), weight 400, line-height 1.6
- **Caption / Meta**: Space Grotesk, 0.75rem (12px), weight 500, uppercase, letter-spacing 0.05em
- **Data / Prices**: JetBrains Mono, 0.875rem (14px), weight 500, tabular nums

## 4. Component Stylings

- **Article Cards**: Background Pure Surface, border-radius 16px, 1px Whisper Border, padding 0 (image flush) + 20px (content area). Hover: subtle lift (translateY -2px) + shadow increase.
- **Crypto Sidebar**: Background Pure Surface, border-radius 20px, padding 24px. Sticky positioning on desktop.
- **Crypto Row**: Minimal separators (1px Whisper Border). Coin icon 28px circular. Price in JetBrains Mono.
- **Source Badge**: Space Grotesk uppercase, 0.7rem, Boston Clay color, no background.
- **Timestamp**: Slate Sophisticate, 0.75rem.

## 5. Layout Principles

- **Max-width**: 1280px centered
- **Grid**: Main content 2-column (md+), sidebar 320px sticky on right
- **Spacing**: Section gaps 3rem, card gaps 1.5rem
- **Responsive**: Single column below 768px, sidebar moves to top

## 6. Motion & Interaction

- **Card hover**: translateY(-2px), shadow increase, 200ms ease
- **Image hover**: Scale 1.03, 300ms ease, overflow hidden
- **Crypto refresh**: Fade transition 150ms

## 7. Anti-Patterns

- No Inter font
- No pure black (#000000)
- No neon/outer glow
- No emojis
- No generic placeholder text
- No fake statistics
