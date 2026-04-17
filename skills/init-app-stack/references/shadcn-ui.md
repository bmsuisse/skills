# shadcn/ui Reference

Not a library — a CLI that **copies component source into your repo**. You own the code, edit freely.

Load this when adding UI components, theming, dark mode, or debugging class merge issues.

---

## Mental model

- `components.json` at repo root tells the shadcn CLI: where to drop components (`@/components/ui/*`), what style (`new-york`), base color (`neutral`), icon library (`lucide`).
- Run `bunx --bun shadcn@latest add <component>` to copy a component's source into `src/components/ui/`. The file is now **your code** — modify it, delete it, whatever.
- All components are styled via Tailwind v4 using semantic tokens (`bg-background`, `text-foreground`) that map to CSS custom properties in `src/index.css`. Swap themes by changing those vars, not by editing every component.

---

## Adding a component

```bash
cd frontend
bunx --bun shadcn@latest add button
bunx --bun shadcn@latest add card input label dialog dropdown-menu
```

Files land under `src/components/ui/`. Import with the `@/` alias:

```tsx
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function Save({ className }: { className?: string }) {
  return <Button className={cn('min-w-24', className)}>Save</Button>
}
```

---

## Theme tokens (always prefer these)

| Token                        | Use for                              |
| ---------------------------- | ------------------------------------ |
| `bg-background`              | App/page background                  |
| `text-foreground`            | Primary text                         |
| `text-muted-foreground`      | Secondary text, captions, hints      |
| `bg-card text-card-foreground` | Card surfaces                      |
| `bg-primary text-primary-foreground` | Primary actions (buttons, links) |
| `bg-secondary text-secondary-foreground` | Secondary actions           |
| `bg-muted`                   | Subtle surfaces (input bg, inactive tabs) |
| `bg-accent text-accent-foreground` | Hover states                   |
| `bg-destructive`             | Destructive buttons, error banners   |
| `border-border`              | Borders, dividers                    |
| `ring-ring`                  | Focus rings                          |

**Do not use** raw palette classes like `bg-neutral-800`, `text-gray-500`, `bg-zinc-50` — they break theming and dark mode.

---

## Dark mode

Scaffold already defines `.dark` variants in `src/index.css` and registers `@custom-variant dark (&:is(.dark *))`. Activate by toggling `className="dark"` on `<html>`.

Minimal theme toggle:

```tsx
// src/components/theme-toggle.tsx
import { Moon, Sun } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ThemeToggle() {
  const toggle = () => document.documentElement.classList.toggle('dark')
  return (
    <Button variant="ghost" size="icon" onClick={toggle}>
      <Sun className="h-4 w-4 dark:hidden" />
      <Moon className="hidden h-4 w-4 dark:block" />
    </Button>
  )
}
```

Persist across reloads by reading/writing `localStorage` in a `useEffect` on the root route.

---

## The `cn()` helper

`@/lib/utils` exports:

```ts
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- `clsx` handles arrays, objects, conditionals.
- `twMerge` resolves Tailwind conflicts — `cn('p-2', 'p-4')` → `'p-4'` (not both).

Use it **anywhere** you're composing Tailwind classes:

```tsx
<div className={cn(
  'rounded-lg border p-4',
  isActive && 'border-primary bg-primary/5',
  className,   // prop override — goes last so it wins
)} />
```

---

## Icons (lucide-react)

Already installed. Import by name:

```tsx
import { Check, ChevronRight, Loader2 } from 'lucide-react'

<Check className="h-4 w-4" />
<Loader2 className="h-4 w-4 animate-spin" />
```

Browse: https://lucide.dev/icons

---

## Building your own components

Follow the shadcn pattern (same one used in `components/ui/`):

```tsx
// src/components/empty-state.tsx
import { cn } from '@/lib/utils'
import type { ReactNode } from 'react'

interface EmptyStateProps {
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed p-12 text-center', className)}>
      <h3 className="text-lg font-medium">{title}</h3>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  )
}
```

Rules:
- Accept `className`, pass through `cn(base, className)` with the prop **last** so overrides win.
- Use semantic tokens, never raw palette colors.
- Don't install a competing component library (MUI, Chakra, Mantine, Ant, HeroUI). If shadcn is missing something, build it with the primitives (`@radix-ui/react-*` — shadcn components use these under the hood; you can add more).

---

## When it breaks

- **`Cannot find module '@/components/ui/...'`**: path alias not wired. Check `vite.config.ts` has `resolve.alias['@']`, `tsconfig.json` and `tsconfig.app.json` both have `"paths": { "@/*": ["./src/*"] }` and `"baseUrl": "."`.
- **Dark mode classes not applying**: missing `@custom-variant dark (&:is(.dark *));` in `index.css`, or `.dark` class not on `<html>`.
- **`twMerge` not resolving correctly**: you're using arbitrary values that conflict (e.g. `p-[13px] p-4`). Use standard scale classes when possible.
- **Component imported but unstyled**: `@import "tailwindcss"` missing from `index.css`, or the file isn't imported in `main.tsx`.
- **`tw-animate-css` errors on install**: confirm you're on Tailwind v4 — `tw-animate-css` is the v4 replacement for the old `tailwindcss-animate` PostCSS plugin and requires v4.
