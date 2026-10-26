# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Notas
**Generated:** 2026-10-25 22:07:59
**Category:** Productivity Tool
**Design Dials:** Variance 3/10 (Centered / Minimal) | Motion 2/10 (Subtle) | Density 6/10 (Standard)

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#0F766E` | `--color-primary` |
| On Primary | `#FFFFFF` | `--color-on-primary` |
| Secondary | `#14B8A6` | `--color-secondary` |
| On Secondary | `#0F172A` | `--color-on-secondary` |
| Accent/CTA | `#EA580C` | `--color-accent` |
| On Accent/CTA | `#000000` | `--color-on-accent` |
| Background | `#F0FDFA` | `--color-background` |
| Foreground | `#134E4A` | `--color-foreground` |
| Card | `#FFFFFF` | `--color-card` |
| Card Foreground | `#134E4A` | `--color-card-foreground` |
| Muted | `#E8F1F4` | `--color-muted` |
| Muted Foreground | `#475569` | `--color-muted-foreground` |
| Border | `#D5E8E3` | `--color-border` |
| Destructive | `#DC2626` | `--color-destructive` |
| On Destructive | `#FFFFFF` | `--color-on-destructive` |
| Ring | `#0F766E` | `--color-ring` |

**Color Notes:** Teal focus + action orange. Primary darkened to `#0F766E` so white text
passes 4.5:1 (5.5:1). Orange `#EA580C` uses near-black text (5.9:1) and is reserved
for reminders/urgency, not for every primary action.

### Dark Mode

| Role | Hex |
|------|-----|
| Background | `#0B1514` |
| Surface | `#10201E` |
| Surface 2 | `#16302C` |
| Foreground | `#E6F4F1` |
| Muted Foreground | `#9DB8B3` |
| Border | `#24413C` |
| Primary | `#2DD4BF` (text on it: `#042F2E`) |
| Accent | `#FB923C` (text on it: `#1A0D04`) |
| Destructive | `#F87171` |

### Typography

- **Heading Font:** Plus Jakarta Sans
- **Body Font:** Plus Jakarta Sans
- **Mood:** friendly, modern, saas, clean, approachable, professional
- **Google Fonts:** [Plus Jakarta Sans + Plus Jakarta Sans](https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
```

### Spacing Variables

*Density: 6/10 — Standard*

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #0F766E;
  color: #FFFFFF;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: background-color 200ms ease, box-shadow 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  background: #115E59;
}

/* Accent Button: solo recordatorios/urgencia */
.btn-accent {
  background: #EA580C;
  color: #1A0D04;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
}

.btn-accent:hover {
  background: #C2410C;
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #134E4A;
  border: 2px solid #0D9488;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #F0FDFA;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #0D9488;
  outline: none;
  box-shadow: 0 0 0 3px #0D948820;
}
```

### Format Bar (Markdown)

```css
.format-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: var(--color-card);
}

.format-btn {
  min-width: 44px;
  min-height: 44px;
  border-radius: 8px;
  background: transparent;
  color: var(--color-foreground);
}

.format-btn:hover {
  background: var(--color-muted);
}
```

- Acciones: H1/H2, negrita, cursiva, tachado, listas, cita, código, bloque de
  código y enlace.
- El texto visible (`H1`, `B`, `I`, `S`) debe estar incluido en el nombre
  accesible, sin paréntesis. Axe elimina los paréntesis al comparar, así que
  `aria-label="Título 1 (H1)"` **falla**; usar `aria-label="H1 Título 1"`.
- En móvil la barra envuelve a dos filas; no usa scroll horizontal oculto.

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Minimalism & Swiss Style

**Keywords:** Clean, simple, spacious, functional, white space, high contrast, geometric, sans-serif, grid-based, essential

**Best For:** Enterprise apps, dashboards, documentation sites, SaaS platforms, professional tools

**Key Effects:** Subtle hover (200-250ms), smooth transitions, sharp shadows if any, clear type hierarchy, fast loading

### Page Pattern

**Pattern Name:** App Shell — sidebar + editor (not a landing page)

- **Desktop:** sidebar fija de 340px con marca, búsqueda, árbol de carpetas y lista de
  notas; el resto es el editor Markdown. Barra superior solo dentro del editor.
- **Tablet:** sidebar de 300px; mismas dos zonas.
- **Móvil:** una sola zona. Sin nota seleccionada se ve la lista; con nota abierta se ve
  el editor y un botón de volver. Navegación inferior fija con Notas, Recordatorios y
  Buscar (3 destinos, ≤5).
- **Login:** tarjeta centrada de 420px, sin shell.
- **Recordatorios:** página propia con barra superior, formulario y lista. Naranja solo
  para fechas vencidas o urgencia.
- **Deep links:** `?folder=`, `?note=`, `?q=` y `?focus=search` deben funcionar y el
  botón atrás del navegador debe respetarlos.

---

## Motion

**Micro-interacciones sutiles** — 150-250ms, `ease-out`. Sin scroll reveal, sin
parallax y sin animaciones de entrada en una app de uso diario.

- ✅ Hover y focus en botones, filas y enlaces (150-250ms)
- ✅ Cambio de tema sin transición de color global (evita parpadeos)
- ✅ `prefers-reduced-motion: reduce` desactiva transiciones no esenciales
- ❌ No animar `width`/`height`; usar `opacity` y `transform`
- ❌ No usar GSAP ni scroll triggers en esta app

---

## Anti-Patterns (Do NOT Use)

- ❌ Complex onboarding
- ❌ Slow performance

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile