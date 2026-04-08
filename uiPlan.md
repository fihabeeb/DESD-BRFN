# UI Redesign Plan — DESD-BRFN Farm Marketplace

## Executive Summary

The app has a solid foundation (Bootstrap 5 + Tailwind + Alpine.js) but suffers from CSS fragmentation, mixed styling approaches, an underdeveloped homepage, and several missing features. This plan proposes a cohesive, modern redesign that feels like a premium farm-to-table marketplace — earthy, trustworthy, and clean.

---

## 1. Design System

### Color Palette

| Token | Value | Use |
|---|---|---|
| `--color-primary` | `#2d6a2d` | CTAs, active states, links |
| `--color-primary-hover` | `#1a5c1a` | Button hover |
| `--color-primary-light` | `#e8f5e8` | Backgrounds, hover tints |
| `--color-accent` | `#f59e0b` | Highlights, badges, seasonal |
| `--color-surface` | `#ffffff` | Cards, panels |
| `--color-bg` | `#f7f9f7` | Page background |
| `--color-text` | `#1a1a1a` | Body text |
| `--color-muted` | `#6b7280` | Secondary text |
| `--color-border` | `#e5e7eb` | Dividers, inputs |
| `--color-danger` | `#dc2626` | Errors, alerts |
| `--color-success` | `#16a34a` | Confirmations |
| `--color-warning` | `#d97706` | Warnings |
| Dark mode variants defined as `[data-theme="dark"]` overrides |

### Typography

- **Font:** Inter (Google Fonts) — clean, modern, readable
- **Scale:** 12 / 14 / 16 / 18 / 24 / 30 / 36 / 48px
- **Weights:** 400 (body), 500 (labels), 600 (subheadings), 700 (headings)

### Spacing & Shape

- **Base unit:** 4px
- **Border radius:** 8px (inputs, small cards), 12px (cards), 16px (large panels), 999px (pills)
- **Shadows:** Three levels — `sm` (2px), `md` (8px), `lg` (20px)

### Framework Direction

- **Keep:** Bootstrap 5 for grid + form scaffolding, Alpine.js for interactivity
- **Consolidate:** Move all utility styling to Tailwind. Remove inline CSS from templates into dedicated CSS files
- **Add:** CSS custom properties for theming (dark mode, brand tokens)

---

## 2. Global Layout & Navigation

### Navbar (Redesign)

**Current issues:** Sparse, text-only, no visual hierarchy.

**New design:**
- **Left:** Logo (leaf icon + brand name "FarmDirect") + primary nav links (Marketplace, About, How It Works)
- **Center (on wide screens):** Global search bar (persistent, with product + producer autocomplete)
- **Right:** Cart icon with item count badge, notifications bell, user avatar dropdown
- Sticky on scroll with subtle backdrop blur (`backdrop-filter: blur(8px)`)
- On mobile: Hamburger menu sliding from left as a drawer
- Active link indicator: green underline accent

### Footer (New)

Currently no footer. Add a structured footer with:
- Brand logo + tagline ("Fresh from farm to your door")
- Quick links: Marketplace, About, Become a Producer, Help
- Trust badges: Locally sourced, Carbon footprint tracking, Secure payments
- Social links
- Copyright + privacy/terms links
- Newsletter signup input

---

## 3. Homepage (Full Redesign — Currently Just a Title)

The homepage is completely underdeveloped. Redesign as a full landing page:

### Sections

1. **Hero Section**
   - Full-width banner with a high-quality farm/food image (CSS background or `<img>`)
   - Headline: "Fresh from local farms, delivered to you"
   - Subtext: Brief value proposition
   - Two CTAs: "Shop Now" (primary green button) + "Become a Producer" (outlined)
   - Overlaid search bar for quick product search

2. **Stats Bar**
   - Animated counters: X Producers | X Products | X Happy Customers | X Miles Saved
   - Subtle green background strip

3. **Category Showcase**
   - Horizontal scrollable row of category cards with icons/images
   - Categories: Vegetables, Fruits, Dairy, Meat, Bakery, etc.
   - Click to go to marketplace filtered by category

4. **Featured Products**
   - "What's Fresh This Week" — 4–6 product cards (same card design as marketplace)
   - "Seasonal Picks" — badge-highlighted in-season products

5. **How It Works**
   - 3-step explainer: Browse → Order → Delivered
   - Icon + title + 1-sentence description per step

6. **Producer Spotlight**
   - Carousel or 3-card grid of featured producer profiles
   - Producer name, farm name, location, product count

7. **Sustainability / Food Miles Section**
   - Visual showing food miles impact
   - "Our farmers are within X miles of you on average"

8. **Testimonials**
   - 3 customer quote cards with avatar, name, star rating

9. **CTA Banner**
   - "Join as a Producer" section — earthy dark green background, white text, sign up button

---

## 4. Marketplace / Product Listing (Enhancement)

### Current: Functional but basic grid with top filter bar.

**Improvements:**

- **Left sidebar filters** (on desktop): Category tree, Price range slider, Organic toggle, In-Season toggle, Food Miles range slider (0–100+ miles), Availability toggle, Producer multi-select
- **Sticky filter sidebar** on scroll
- **Mobile:** Filters in a slide-up drawer triggered by a "Filters" button with active filter count badge
- **Sort bar (top right):** Dropdown — Relevance / Price Low→High / Price High→Low / Newest / Distance
- **View toggle:** Grid view (default) / List view
- **Active filter chips** below search bar (dismissible tags showing applied filters)
- **Result count:** "Showing 24 of 87 products"
- **Infinite scroll** or **load more** button instead of pagination on this page

### Product Card (Redesign)

```
┌─────────────────────────┐
│  [Image]                │  ← Aspect ratio 4:3, object-fit cover
│  [Organic] [In Season]  │  ← Floating badges top-left
│                         │
├─────────────────────────┤
│  Category label (muted) │
│  Product Name (bold)    │
│  Producer name + icon   │
│  ★★★★☆  (4.2)          │  ← Rating (future feature)
│  🌿 Local · 12 miles    │  ← Food miles inline
│                         │
│  £2.40 / kg             │
│  [Low Stock warning]    │
│  [── Add to Cart ──]    │
└─────────────────────────┘
```

- Hover: Card lifts (shadow increase), image subtle zoom, button becomes solid green
- Quick-view button on hover (opens modal with product detail — avoids full page nav)

### Recommendation Section

- "Recommended for You" — horizontal scroll row with "Why recommended" tooltip
- Only shown when logged in and order history exists

---

## 5. Product Detail Page (Redesign)

### Current: Two-column card but has structural duplication.

**New layout:**

```
[← Back to Marketplace]

┌──────────────────┬──────────────────────────────┐
│                  │  Category > Product Name      │
│  Product Image   │  Product Name (h1, large)     │
│  (main, large)   │  ★★★★☆ 4.2  (12 reviews)     │
│                  │                               │
│  [Thumbnail row] │  [Organic] [In Season]        │
│  (if multiple    │  £2.40 / kg                   │
│   images later)  │  Stock: 48 available          │
│                  │  🌿 Local · Meadow Farm · 12mi │
│                  │                               │
│                  │  ─── Description ───          │
│                  │  (expandable if long)         │
│                  │                               │
│                  │  Qty: [─] [2] [+]             │
│                  │  [── Add to Cart ──]          │
│                  │  [♡ Save to Wishlist]         │
│                  │                               │
│                  │  ─── Details ───              │
│                  │  Harvest Date | Unit | ...     │
│                  │  Allergens (pill badges)       │
└──────────────────┴──────────────────────────────┘

─── About the Producer ───
Producer card: name, farm name, distance, link to producer page

─── You Might Also Like ───
4 related product cards (same category)
```

---

## 6. Cart Page (Enhancement)

### Current: Producer-grouped sections, basic table layout.

**Improvements:**

- **Two-column layout (desktop):** Cart items (left 2/3) + Order summary sidebar (right 1/3, sticky)
- Producer sections become collapsible accordions with producer name + item count header
- Each item row: image thumbnail, name, producer, unit price, qty stepper, subtotal, remove
- Qty stepper: `−` / input / `+` inline with instant debounce update (keep existing logic, improve UI)
- Food miles badge moved to producer section header, not per-item
- **Sticky order summary sidebar:**
  - Subtotal per producer
  - Total food miles / sustainability score
  - Promo/voucher code field
  - "Proceed to Checkout" button (fixed at bottom on mobile)
- **Empty cart state:** Illustrated empty plate SVG, "Your cart is empty", "Start Shopping" button
- **Save for later:** Move item to a saved list (future feature, add UI now)

---

## 7. Checkout Page (Enhancement)

### Current: Functional but dense, single-column-ish layout.

**New layout (3-step wizard):**

```
Step 1: Delivery          Step 2: Review            Step 3: Payment
[Address Selection]  →   [Order Summary]       →   [Stripe Payment]
[Delivery Notes]         [Delivery Dates]           [Confirm & Pay]
```

- Progress bar at top showing current step
- Each step on its own panel (slide animation between steps)
- **Step 1:** Address cards with radio selection (current approach but better styled), add new address inline, delivery notes per producer as expandable section
- **Step 2:** Clean order summary — grouped by producer, delivery date picker per producer, read-only product list with images
- **Step 3:** Stripe Elements embed (card input), order total breakdown (subtotal + delivery + commission), place order button with loading state

---

## 8. Order Success Page (Enhancement)

### Current: Functional but minimal.

**Improvements:**
- Animated checkmark (CSS/Lottie animation)
- Order number prominent (large, copyable)
- Timeline tracker: "Order Placed → Confirmed → Preparing → Ready → Delivered"
- Itemised receipt (product images, names, quantities, prices)
- Estimated delivery date highlighted
- "Track Your Order" button (links to order detail)
- "Continue Shopping" + "View All Orders" buttons

---

## 9. Customer Profile (Redesign)

### Current: Sparse overview card + placeholder for order history.

**New layout — tabbed dashboard:**

```
[My Account]
Tabs: Overview | Orders | Addresses | Recommendations | Settings
```

**Overview tab:**
- Welcome card (name, member since, avatar with upload)
- Quick stats: Total Orders | Total Spent | Favourite Category | Farms Supported
- Recent orders mini-list (last 3) with status badges
- "Recommended for you" section (from ML model)

**Orders tab:**
- Filter by status (All / Active / Delivered / Cancelled)
- Order cards: Order ID, date, producer(s), item thumbnails, total, status badge, "View Details" button
- Order detail modal/page: timeline, items, address, receipt

**Addresses tab:**
- Current manage_addresses.html content but redesigned as cards
- Add address button prominent at top
- Default badge more visible

**Recommendations tab:**
- "Based on your order history" section
- Powered by ML model — show top 10 recommended products
- "Why this?" tooltip explaining recommendation basis

**Settings tab:**
- Personal info form (editable inline fields)
- Password change section
- Notification preferences
- Delete account (behind confirmation modal — not just JS confirm())

---

## 10. Producer Dashboard (Redesign)

### Current: Stats grid + filter bar + sortable table (myproduct.html).

**New layout — sidebar navigation dashboard:**

```
┌──────────────┬──────────────────────────────────────┐
│              │                                      │
│  Dashboard   │  Main content area                   │
│  Products    │                                      │
│  Orders      │                                      │
│  Analytics   │                                      │
│  Profile     │                                      │
│  Quality AI  │                                      │
│              │                                      │
└──────────────┴──────────────────────────────────────┘
```

**Dashboard page:**
- Revenue chart (line chart — last 30 days, using Chart.js)
- Top selling products (ranked list with bar)
- Recent orders (last 5 with status)
- Stats cards (existing 7 metrics, redesigned)
- Low stock alerts (products below threshold)

**Products page (myproduct.html redesign):**
- Keep stats grid at top
- Filter bar: search input, status dropdown, organic/seasonal checkboxes
- Table with image thumbnails added to each row
- Inline availability toggle (switch input, AJAX)
- Quick edit (price/stock) inline without leaving page
- Bulk actions: Select multiple → Mark unavailable / Delete

**Orders page (myorders.html redesign):**
- Kanban board view (columns: Confirmed | Preparing | Ready | Delivered) as alternative to list view
- List view retained as toggle option
- Order cards: customer name, order date, item count, subtotal, status badge
- Click card to expand/open detail modal
- Status update via drag-and-drop in kanban OR dropdown in list view

**Analytics page (New):**
- Revenue over time (line chart)
- Top products by revenue (bar chart)
- Order volume by day of week (bar chart)
- Food miles distribution (pie chart)
- Customer repeat rate metric
- Export to CSV button

**Quality AI page (quality_scan.html — refinement):**
- Keep existing Alpine.js component
- Improve results card: larger score ring, cleaner breakdown bars
- Add scan history (last 5 scans with thumbnails and scores)
- "Product not suitable for sale" alert if score < 40

---

## 11. Authentication Pages (Redesign)

### Current: Centered card forms, functional but plain.

**New design — split-screen layout:**

```
┌──────────────────┬──────────────────┐
│                  │                  │
│  Farm imagery    │   Login / Register│
│  or brand        │   form           │
│  illustration    │                  │
│                  │                  │
│  "Fresh from     │                  │
│   farm to door"  │                  │
└──────────────────┴──────────────────┘
```

- Left panel: Full-height green gradient with farm illustration or photo, brand tagline
- Right panel: Clean form with social proof (e.g. "Join 2,000+ customers")
- Floating label inputs (label animates up on focus)
- Password strength meter (registration)
- Show/hide password toggle
- "Remember me" checkbox
- Smoother error states (shake animation on invalid submit)

---

## 12. Notifications System (Enhancement)

### Current: Toast notifications (auto-dismiss, 5 seconds).

**Improvements:**
- Keep toast system but add a **Notification Centre** (bell icon in navbar)
- Dropdown panel showing notification history: order status changes, new products from followed producers, low stock alerts (for producers)
- Unread count badge on bell icon
- Mark all as read button

---

## 13. Dark Mode (Complete Coverage)

### Current: Partially implemented, some components missing.

**Fixes needed:**
- Audit every template against the dark mode CSS in base.css
- Add dark mode overrides for: quality scan dropzone, checkout address cards, order success page, all form inputs across apps
- Use CSS custom properties (var(--color-*)) so dark mode is a single `[data-theme="dark"]` toggle rather than scattered overrides

---

## 14. Accessibility (WCAG 2.1 AA)

- Add `aria-label` to all icon-only buttons (cart icon, remove item, close modal)
- Ensure all form inputs have associated `<label>` elements
- Status indicators must have text alongside colour (not colour-only)
- Keyboard navigation: all dropdowns and modals must be keyboard accessible
- Focus rings visible (don't remove outline)
- Alt text on all product images
- Sufficient colour contrast on all text/background combinations

---

## 15. Performance

- Move all inline CSS from templates into dedicated CSS files
- Lazy-load product images (`loading="lazy"`)
- Debounce already implemented — keep it
- Consider preloading critical fonts (Inter)
- Remove unused Bootstrap components via custom build (future optimisation)

---

## 16. New Features to Add

| Feature | Page | Priority |
|---|---|---|
| Wishlist / Save for Later | Product list, Product detail, Cart | High |
| Producer public profile page | New page | High |
| Order tracking timeline | Order success, Customer orders tab | High |
| Analytics dashboard | Producer dashboard | High |
| Kanban order board | Producer orders | Medium |
| Quick-view product modal | Product list | Medium |
| Product image gallery | Product detail | Medium |
| Notifications centre | Global (navbar) | Medium |
| Promo/voucher code field | Cart, Checkout | Medium |
| Customer reviews/ratings | Product detail | Low |
| Follow a producer | Producer profile | Low |
| Scan history | Quality AI page | Low |

---

## 17. Implementation Order (Suggested)

1. **Design system** — CSS custom properties, typography, colour tokens, move inline CSS to files
2. **Base template** — Navbar redesign, footer, notification bell
3. **Homepage** — Full landing page build
4. **Product list + cards** — Sidebar filters, list/grid toggle, card redesign
5. **Product detail** — Layout fix, quick-view modal
6. **Cart** — Two-column layout, sticky summary
7. **Checkout** — Step wizard
8. **Customer dashboard** — Tabbed layout, orders tab, recommendations tab
9. **Producer dashboard** — Sidebar nav, analytics page, kanban orders
10. **Auth pages** — Split-screen layout
11. **Dark mode** — Full audit and completion
12. **Accessibility** — Aria labels, contrast, keyboard nav

# UI Redesign Plan — DESD-BRFN Farm Marketplace

## Executive Summary

The app has a solid foundation (Bootstrap 5 + Tailwind + Alpine.js) but suffers from CSS fragmentation, mixed styling approaches, an underdeveloped homepage, and several missing features. This plan proposes a cohesive, modern redesign that feels like a premium farm-to-table marketplace — earthy, trustworthy, and clean.

---

## 1. Design System

### Color Palette

| Token | Value | Use |
|---|---|---|
| `--color-primary` | `#2d6a2d` | CTAs, active states, links |
| `--color-primary-hover` | `#1a5c1a` | Button hover |
| `--color-primary-light` | `#e8f5e8` | Backgrounds, hover tints |
| `--color-accent` | `#f59e0b` | Highlights, badges, seasonal |
| `--color-surface` | `#ffffff` | Cards, panels |
| `--color-bg` | `#f7f9f7` | Page background |
| `--color-text` | `#1a1a1a` | Body text |
| `--color-muted` | `#6b7280` | Secondary text |
| `--color-border` | `#e5e7eb` | Dividers, inputs |
| `--color-danger` | `#dc2626` | Errors, alerts |
| `--color-success` | `#16a34a` | Confirmations |
| `--color-warning` | `#d97706` | Warnings |
| Dark mode variants defined as `[data-theme="dark"]` overrides |

### Typography

- **Font:** Inter (Google Fonts) — clean, modern, readable
- **Scale:** 12 / 14 / 16 / 18 / 24 / 30 / 36 / 48px
- **Weights:** 400 (body), 500 (labels), 600 (subheadings), 700 (headings)

### Spacing & Shape

- **Base unit:** 4px
- **Border radius:** 8px (inputs, small cards), 12px (cards), 16px (large panels), 999px (pills)
- **Shadows:** Three levels — `sm` (2px), `md` (8px), `lg` (20px)

### Framework Direction

- **Keep:** Bootstrap 5 for grid + form scaffolding, Alpine.js for interactivity
- **Consolidate:** Move all utility styling to Tailwind. Remove inline CSS from templates into dedicated CSS files
- **Add:** CSS custom properties for theming (dark mode, brand tokens)

---

## 2. Global Layout & Navigation

### Navbar (Redesign)

**Current issues:** Sparse, text-only, no visual hierarchy.

**New design:**
- **Left:** Logo (leaf icon + brand name "FarmDirect") + primary nav links (Marketplace, About, How It Works)
- **Center (on wide screens):** Global search bar (persistent, with product + producer autocomplete)
- **Right:** Cart icon with item count badge, notifications bell, user avatar dropdown
- Sticky on scroll with subtle backdrop blur (`backdrop-filter: blur(8px)`)
- On mobile: Hamburger menu sliding from left as a drawer
- Active link indicator: green underline accent

### Footer (New)

Currently no footer. Add a structured footer with:
- Brand logo + tagline ("Fresh from farm to your door")
- Quick links: Marketplace, About, Become a Producer, Help
- Trust badges: Locally sourced, Carbon footprint tracking, Secure payments
- Social links
- Copyright + privacy/terms links
- Newsletter signup input

---

## 3. Homepage (Full Redesign — Currently Just a Title)

The homepage is completely underdeveloped. Redesign as a full landing page:

### Sections

1. **Hero Section**
   - Full-width banner with a high-quality farm/food image (CSS background or `<img>`)
   - Headline: "Fresh from local farms, delivered to you"
   - Subtext: Brief value proposition
   - Two CTAs: "Shop Now" (primary green button) + "Become a Producer" (outlined)
   - Overlaid search bar for quick product search

2. **Stats Bar**
   - Animated counters: X Producers | X Products | X Happy Customers | X Miles Saved
   - Subtle green background strip

3. **Category Showcase**
   - Horizontal scrollable row of category cards with icons/images
   - Categories: Vegetables, Fruits, Dairy, Meat, Bakery, etc.
   - Click to go to marketplace filtered by category

4. **Featured Products**
   - "What's Fresh This Week" — 4–6 product cards (same card design as marketplace)
   - "Seasonal Picks" — badge-highlighted in-season products

5. **How It Works**
   - 3-step explainer: Browse → Order → Delivered
   - Icon + title + 1-sentence description per step

6. **Producer Spotlight**
   - Carousel or 3-card grid of featured producer profiles
   - Producer name, farm name, location, product count

7. **Sustainability / Food Miles Section**
   - Visual showing food miles impact
   - "Our farmers are within X miles of you on average"

8. **Testimonials**
   - 3 customer quote cards with avatar, name, star rating

9. **CTA Banner**
   - "Join as a Producer" section — earthy dark green background, white text, sign up button

---

## 4. Marketplace / Product Listing (Enhancement)

### Current: Functional but basic grid with top filter bar.

**Improvements:**

- **Left sidebar filters** (on desktop): Category tree, Price range slider, Organic toggle, In-Season toggle, Food Miles range slider (0–100+ miles), Availability toggle, Producer multi-select
- **Sticky filter sidebar** on scroll
- **Mobile:** Filters in a slide-up drawer triggered by a "Filters" button with active filter count badge
- **Sort bar (top right):** Dropdown — Relevance / Price Low→High / Price High→Low / Newest / Distance
- **View toggle:** Grid view (default) / List view
- **Active filter chips** below search bar (dismissible tags showing applied filters)
- **Result count:** "Showing 24 of 87 products"
- **Infinite scroll** or **load more** button instead of pagination on this page

### Product Card (Redesign)

```
┌─────────────────────────┐
│  [Image]                │  ← Aspect ratio 4:3, object-fit cover
│  [Organic] [In Season]  │  ← Floating badges top-left
│                         │
├─────────────────────────┤
│  Category label (muted) │
│  Product Name (bold)    │
│  Producer name + icon   │
│  ★★★★☆  (4.2)          │  ← Rating (future feature)
│  🌿 Local · 12 miles    │  ← Food miles inline
│                         │
│  £2.40 / kg             │
│  [Low Stock warning]    │
│  [── Add to Cart ──]    │
└─────────────────────────┘
```

- Hover: Card lifts (shadow increase), image subtle zoom, button becomes solid green
- Quick-view button on hover (opens modal with product detail — avoids full page nav)

### Recommendation Section

- "Recommended for You" — horizontal scroll row with "Why recommended" tooltip
- Only shown when logged in and order history exists

---

## 5. Product Detail Page (Redesign)

### Current: Two-column card but has structural duplication.

**New layout:**

```
[← Back to Marketplace]

┌──────────────────┬──────────────────────────────┐
│                  │  Category > Product Name      │
│  Product Image   │  Product Name (h1, large)     │
│  (main, large)   │  ★★★★☆ 4.2  (12 reviews)     │
│                  │                               │
│  [Thumbnail row] │  [Organic] [In Season]        │
│  (if multiple    │  £2.40 / kg                   │
│   images later)  │  Stock: 48 available          │
│                  │  🌿 Local · Meadow Farm · 12mi │
│                  │                               │
│                  │  ─── Description ───          │
│                  │  (expandable if long)         │
│                  │                               │
│                  │  Qty: [─] [2] [+]             │
│                  │  [── Add to Cart ──]          │
│                  │  [♡ Save to Wishlist]         │
│                  │                               │
│                  │  ─── Details ───              │
│                  │  Harvest Date | Unit | ...     │
│                  │  Allergens (pill badges)       │
└──────────────────┴──────────────────────────────┘

─── About the Producer ───
Producer card: name, farm name, distance, link to producer page

─── You Might Also Like ───
4 related product cards (same category)
```

---

## 6. Cart Page (Enhancement)

### Current: Producer-grouped sections, basic table layout.

**Improvements:**

- **Two-column layout (desktop):** Cart items (left 2/3) + Order summary sidebar (right 1/3, sticky)
- Producer sections become collapsible accordions with producer name + item count header
- Each item row: image thumbnail, name, producer, unit price, qty stepper, subtotal, remove
- Qty stepper: `−` / input / `+` inline with instant debounce update (keep existing logic, improve UI)
- Food miles badge moved to producer section header, not per-item
- **Sticky order summary sidebar:**
  - Subtotal per producer
  - Total food miles / sustainability score
  - Promo/voucher code field
  - "Proceed to Checkout" button (fixed at bottom on mobile)
- **Empty cart state:** Illustrated empty plate SVG, "Your cart is empty", "Start Shopping" button
- **Save for later:** Move item to a saved list (future feature, add UI now)

---

## 7. Checkout Page (Enhancement)

### Current: Functional but dense, single-column-ish layout.

**New layout (3-step wizard):**

```
Step 1: Delivery          Step 2: Review            Step 3: Payment
[Address Selection]  →   [Order Summary]       →   [Stripe Payment]
[Delivery Notes]         [Delivery Dates]           [Confirm & Pay]
```

- Progress bar at top showing current step
- Each step on its own panel (slide animation between steps)
- **Step 1:** Address cards with radio selection (current approach but better styled), add new address inline, delivery notes per producer as expandable section
- **Step 2:** Clean order summary — grouped by producer, delivery date picker per producer, read-only product list with images
- **Step 3:** Stripe Elements embed (card input), order total breakdown (subtotal + delivery + commission), place order button with loading state

---

## 8. Order Success Page (Enhancement)

### Current: Functional but minimal.

**Improvements:**
- Animated checkmark (CSS/Lottie animation)
- Order number prominent (large, copyable)
- Timeline tracker: "Order Placed → Confirmed → Preparing → Ready → Delivered"
- Itemised receipt (product images, names, quantities, prices)
- Estimated delivery date highlighted
- "Track Your Order" button (links to order detail)
- "Continue Shopping" + "View All Orders" buttons

---

## 9. Customer Profile (Redesign)

### Current: Sparse overview card + placeholder for order history.

**New layout — tabbed dashboard:**

```
[My Account]
Tabs: Overview | Orders | Addresses | Recommendations | Settings
```

**Overview tab:**
- Welcome card (name, member since, avatar with upload)
- Quick stats: Total Orders | Total Spent | Favourite Category | Farms Supported
- Recent orders mini-list (last 3) with status badges
- "Recommended for you" section (from ML model)

**Orders tab:**
- Filter by status (All / Active / Delivered / Cancelled)
- Order cards: Order ID, date, producer(s), item thumbnails, total, status badge, "View Details" button
- Order detail modal/page: timeline, items, address, receipt

**Addresses tab:**
- Current manage_addresses.html content but redesigned as cards
- Add address button prominent at top
- Default badge more visible

**Recommendations tab:**
- "Based on your order history" section
- Powered by ML model — show top 10 recommended products
- "Why this?" tooltip explaining recommendation basis

**Settings tab:**
- Personal info form (editable inline fields)
- Password change section
- Notification preferences
- Delete account (behind confirmation modal — not just JS confirm())

---

## 10. Producer Dashboard (Redesign)

### Current: Stats grid + filter bar + sortable table (myproduct.html).

**New layout — sidebar navigation dashboard:**

```
┌──────────────┬──────────────────────────────────────┐
│              │                                      │
│  Dashboard   │  Main content area                   │
│  Products    │                                      │
│  Orders      │                                      │
│  Analytics   │                                      │
│  Profile     │                                      │
│  Quality AI  │                                      │
│              │                                      │
└──────────────┴──────────────────────────────────────┘
```

**Dashboard page:**
- Revenue chart (line chart — last 30 days, using Chart.js)
- Top selling products (ranked list with bar)
- Recent orders (last 5 with status)
- Stats cards (existing 7 metrics, redesigned)
- Low stock alerts (products below threshold)

**Products page (myproduct.html redesign):**
- Keep stats grid at top
- Filter bar: search input, status dropdown, organic/seasonal checkboxes
- Table with image thumbnails added to each row
- Inline availability toggle (switch input, AJAX)
- Quick edit (price/stock) inline without leaving page
- Bulk actions: Select multiple → Mark unavailable / Delete

**Orders page (incoming_orders.html redesign):**
- Kanban board view (columns: Confirmed | Preparing | Ready | Delivered) as alternative to list view
- List view retained as toggle option
- Order cards: customer name, order date, item count, subtotal, status badge
- Click card to expand/open detail modal
- Status update via drag-and-drop in kanban OR dropdown in list view

**Analytics page (New):**
- Revenue over time (line chart)
- Top products by revenue (bar chart)
- Order volume by day of week (bar chart)
- Food miles distribution (pie chart)
- Customer repeat rate metric
- Export to CSV button

**Quality AI page (quality_scan.html — refinement):**
- Keep existing Alpine.js component
- Improve results card: larger score ring, cleaner breakdown bars
- Add scan history (last 5 scans with thumbnails and scores)
- "Product not suitable for sale" alert if score < 40

---

## 11. Authentication Pages (Redesign)

### Current: Centered card forms, functional but plain.

**New design — split-screen layout:**

```
┌──────────────────┬──────────────────┐
│                  │                  │
│  Farm imagery    │   Login / Register│
│  or brand        │   form           │
│  illustration    │                  │
│                  │                  │
│  "Fresh from     │                  │
│   farm to door"  │                  │
└──────────────────┴──────────────────┘
```

- Left panel: Full-height green gradient with farm illustration or photo, brand tagline
- Right panel: Clean form with social proof (e.g. "Join 2,000+ customers")
- Floating label inputs (label animates up on focus)
- Password strength meter (registration)
- Show/hide password toggle
- "Remember me" checkbox
- Smoother error states (shake animation on invalid submit)

---

## 12. Notifications System (Enhancement)

### Current: Toast notifications (auto-dismiss, 5 seconds).

**Improvements:**
- Keep toast system but add a **Notification Centre** (bell icon in navbar)
- Dropdown panel showing notification history: order status changes, new products from followed producers, low stock alerts (for producers)
- Unread count badge on bell icon
- Mark all as read button

---

## 13. Dark Mode (Complete Coverage)

### Current: Partially implemented, some components missing.

**Fixes needed:**
- Audit every template against the dark mode CSS in base.css
- Add dark mode overrides for: quality scan dropzone, checkout address cards, order success page, all form inputs across apps
- Use CSS custom properties (var(--color-*)) so dark mode is a single `[data-theme="dark"]` toggle rather than scattered overrides

---

## 14. Accessibility (WCAG 2.1 AA)

- Add `aria-label` to all icon-only buttons (cart icon, remove item, close modal)
- Ensure all form inputs have associated `<label>` elements
- Status indicators must have text alongside colour (not colour-only)
- Keyboard navigation: all dropdowns and modals must be keyboard accessible
- Focus rings visible (don't remove outline)
- Alt text on all product images
- Sufficient colour contrast on all text/background combinations

---

## 15. Performance

- Move all inline CSS from templates into dedicated CSS files
- Lazy-load product images (`loading="lazy"`)
- Debounce already implemented — keep it
- Consider preloading critical fonts (Inter)
- Remove unused Bootstrap components via custom build (future optimisation)

---

## 16. New Features to Add

| Feature | Page | Priority |
|---|---|---|
| Wishlist / Save for Later | Product list, Product detail, Cart | High |
| Producer public profile page | New page | High |
| Order tracking timeline | Order success, Customer orders tab | High |
| Analytics dashboard | Producer dashboard | High |
| Kanban order board | Producer orders | Medium |
| Quick-view product modal | Product list | Medium |
| Product image gallery | Product detail | Medium |
| Notifications centre | Global (navbar) | Medium |
| Promo/voucher code field | Cart, Checkout | Medium |
| Customer reviews/ratings | Product detail | Low |
| Follow a producer | Producer profile | Low |
| Scan history | Quality AI page | Low |

---

## 17. Implementation Order (Suggested)

1. **Design system** — CSS custom properties, typography, colour tokens, move inline CSS to files
2. **Base template** — Navbar redesign, footer, notification bell
3. **Homepage** — Full landing page build
4. **Product list + cards** — Sidebar filters, list/grid toggle, card redesign
5. **Product detail** — Layout fix, quick-view modal
6. **Cart** — Two-column layout, sticky summary
7. **Checkout** — Step wizard
8. **Customer dashboard** — Tabbed layout, orders tab, recommendations tab
9. **Producer dashboard** — Sidebar nav, analytics page, kanban orders
10. **Auth pages** — Split-screen layout
11. **Dark mode** — Full audit and completion
12. **Accessibility** — Aria labels, contrast, keyboard nav
