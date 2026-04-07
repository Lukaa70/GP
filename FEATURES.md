# ActressDB — Feature Tracker

## Legend
✅ Done  🔧 In progress  📋 Planned  ⚠️ Known bug

---

## Core Scraping & Import

| Status | Feature | Notes |
|--------|---------|-------|
| ✅ | IAFD single actress scrape | `/test-scraper/?name=` |
| ✅ | IAFD bulk import with AJAX progress | One name at a time, live log |
| ✅ | IAFD search — pick different result | "⇄ Pick different match" in review queue |
| ✅ | IAFD rescrape single actress | "↻ Refresh from IAFD" in bio edit mode |
| ✅ | IAFD bulk rescrape all actresses | `/bulk-refresh-iafd/` endpoint (console-driven) |
| 🔧 | IAFD bulk rescrape — UI | Select actresses + fields to update — **this session** |
| ✅ | Nationality detection from IAFD | Parsed from biodata, list of 50+ nationalities |
| ✅ | Timeout increased to 60s | Handles slow pages like Nina Hartley |
| ✅ | Browser runs offscreen | `--window-position=-2560,0` |
| ✅ | Duplicate actress detection on import | ⚠ warning in progress log |
| 🔧 | Background scraping | Currently freezes the page — **this session** |
| 📋 | Celery + Redis for true async tasks | Proper task queue, notifications when done |

## Photo Scraping

| Status | Feature | Notes |
|--------|---------|-------|
| ✅ | PornPics search + scrape | Up to 30 galleries × 20 photos |
| ✅ | Two-stage AJAX progress bar | Gallery-by-gallery with ETA |
| ✅ | Configurable galleries + photos | Spinners in scrape form |
| ✅ | Full album mode | Checkbox to download all photos from each gallery |
| ✅ | Get all from specific album | "↓ Full album" button per gallery in review |
| ✅ | Custom search name (alias support) | Editable name field in scrape form |
| ✅ | Duplicate photo detection | MD5 hash check, badge in review, skip on approve |
| ✅ | Photo staging + approval | Review queue with keep/skip per photo |
| ✅ | Bulk approve/skip with selection | Checkboxes, sticky bulk bar |
| ✅ | Skip all in gallery | "✕ Skip all" per gallery header |
| ✅ | Scroll position preserved | AJAX — no page reload on approve/skip |

## Photo Management

| Status | Feature | Notes |
|--------|---------|-------|
| ✅ | Manual photo upload | Drag & drop, multi-file |
| ✅ | Set profile photo | Gold ring indicator |
| ✅ | Delete photo | With confirmation |
| ✅ | HD upgrade (single) | AJAX, no page scroll jump |
| ✅ | HD upgrade (bulk) | Progress bar, one at a time |
| ✅ | HD badge on upgraded photos | Blue "HD" tag bottom-right |
| ✅ | Photo resolution stored | width × height from Pillow |
| ✅ | Resolution shown on photo | Badge on hover/display |
| ✅ | Masonry layout | CSS columns, natural aspect ratio |
| ✅ | Icon overlay buttons | Circular: ☑ ★ 🗑 ↑HD |
| ✅ | Bulk select | Checkboxes, select all, clear |
| 📋 | Thumbnail generation at upload | Generate 300px thumbs, serve those in grid |
| 📋 | Photo ordering / drag to reorder | Custom display order |

## Image Viewer

| Status | Feature | Notes |
|--------|---------|-------|
| ✅ | Fullscreen viewer | Fixed overlay, prev/next arrows |
| ✅ | Keyboard navigation | ← → ESC |
| ✅ | Thumbnail strip at bottom | Click to jump, scrolls to active |
| ✅ | Slideshow mode | Auto-advances every 3s, ESC stops |
| 📋 | Zoom + pan | Was attempted but caused bugs; defer |
| 📋 | Touch/swipe support | Mobile gesture navigation |

## Actress Detail Page

| Status | Feature | Notes |
|--------|---------|-------|
| ✅ | Bio stats display | Country, nationality, DOB, height, weight, active years |
| ✅ | Inline edit | Toggle edit mode, AJAX save |
| ✅ | Star rating (1–5) | Hover preview, AJAX save, clear button |
| ✅ | Social links | OnlyFans, Twitter/X, Instagram — shown as icon buttons |
| ✅ | Scenes tracker | Add/delete scenes with title, link, notes, rating |
| ✅ | Recently viewed tracking | localStorage, shown on collection page |
| 📋 | Scenes — edit existing | Currently add/delete only |
| 📋 | Scenes — link to Movie model | Associate scene with a movie entry |

## Collection Page

| Status | Feature | Notes |
|--------|---------|-------|
| ✅ | Actress grid | 4-column responsive |
| ✅ | Filters | Name, country, decade, height min/max |
| ✅ | Sort | A–Z, Top rated, Recently added, Tallest |
| ✅ | Rating filter | Min stars filter |
| ✅ | Pagination | 24 per page |
| ✅ | Charts | Nationality bar, Decade bar, Height doughnut |
| ✅ | Click chart to filter | Clicking segment navigates to filtered list |
| ✅ | Recently viewed strip | Last 5 visited, circular thumbnails |
| ✅ | Hover photo preview | Shows featured photo on card hover |
| 📋 | Nationality filter | Add nationality to filter panel |
| 📋 | Rating shown on card | Stars below name (done) — also filter by it |
| 📋 | Comparison view | Side-by-side stats for 2 selected actresses |
| 📋 | Infinite scroll | Alternative to pagination |

## Review Queue (IAFD)

| Status | Feature | Notes |
|--------|---------|-------|
| ✅ | Pending / approved / rejected tables | |
| ✅ | Approve / reject with CSRF | |
| ✅ | Pick different IAFD match | Radio buttons, re-scrape selected |
| ✅ | Scrape photos from review page | Per-actress scrape button with alias + spinners |
| ✅ | Clear all errors | "✕ Clear all" button |
| ✅ | IAFD profile link on pending rows | "IAFD ↗" next to name |
| ✅ | Review count (pending only) | Doesn't count already-processed photos |

## Data & Models

| Status | Feature | Notes |
|--------|---------|-------|
| ✅ | Actress model | name, DOB, country, nationality, height, weight, active years, rating, social links, notes |
| ✅ | Photo model | image, caption, is_featured, source_url_1280, image_hash, is_hd, width, height |
| ✅ | StagedActress | full IAFD staging pipeline |
| ✅ | StagedPhoto | pornpics staging with duplicate detection |
| ✅ | FavoriteScene | title, description, link, rating, added_at |
| ✅ | Movie model | Exists but no UI beyond admin |
| 📋 | Tags model | Freeform or predefined, filterable |
| 📋 | Movie UI | Scene/movie logging interface |

## System & Infrastructure

| Status | Feature | Notes |
|--------|---------|-------|
| ✅ | Export / backup | ZIP with CSV data + all photos |
| ✅ | Django admin | All models registered with proper fieldsets |
| 🔧 | Background scraping | Thread-based with DB task tracking — **this session** |
| 📋 | Celery + Redis | True async; upgrade path from thread-based |
| 📋 | Photo thumbnail generation | Pillow resize at upload time |
| 📋 | Batch IAFD rescrape UI | **This session** |

## Bugs / Known Issues

| Status | Issue | Fix |
|--------|-------|-----|
| ⚠️ | Image viewer may not open | Fixed: `|tojson` → `|escapejs`, duplicate viewerClose removed |
| ⚠️ | HD upgrade needs page refresh for new URL | Fixed: returns `new_url` in JSON, updates `img.src` in place |
| ⚠️ | Masonry gaps with lazy loading | Fixed: `loading="eager"` on gallery images |
| ⚠️ | Blank masonry spaces on some actresses | Mitigated: `column-fill: balance`, max-height cap |
