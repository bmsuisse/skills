# Icons

**Icon library: [`@heroicons/react`](https://heroicons.com/), `24/outline`
set.** This is OneSales's actual icon library (`navigation.ts` imports
`Squares2X2Icon`, `UsersIcon`, `CalendarDaysIcon`, `MapIcon`, etc. from
`@heroicons/react/24/outline`) — use it for anything you place yourself: nav
items, page/business icons, empty states. Never hand-draw or invent an
icon's SVG path data — it reads as generic and drifts from what the rest of
the app uses. If you need an icon outside a React component (a static HTML
page, an email template), pull the exact SVG from
`https://raw.githubusercontent.com/tailwindlabs/heroicons/master/optimized/24/outline/<name>.svg`
rather than approximating it by hand.

Don't confuse this with `lucide-react`, which `init-app-stack` also
installs — that one is internal to shadcn's generated components (`select.tsx`,
`calendar.tsx`, etc. import it directly as a byproduct of the shadcn CLI) and
isn't the library you reach for in your own UI. See
`init-app-stack/references/shadcn-ui.md`'s icon section for that split.

## Usage

```tsx
import { Squares2X2Icon, UsersIcon } from "@heroicons/react/24/outline"

// nav row — matches the sizing/weight spec in SKILL.md
<Squares2X2Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />

// active nav row
<Squares2X2Icon className="h-[18px] w-[18px] text-nav-primary" strokeWidth={2} />
```

Sizing follows the nav spec in the main `SKILL.md`: 18×18px, stroke-width
1.75 inactive / 2 active. For icons outside the nav (buttons, empty states,
table cells), `h-4 w-4` (16px) is a common default.

## Curated set for common concepts

A starting map from "thing the nav item represents" to the Heroicons
`24/outline` component to import — so the same concept gets the same icon
across apps instead of each one picking a different lookalike. Not
exhaustive; browse https://heroicons.com for anything not listed and add it
here once it's established as the app's choice for that concept.

| Concept | Component | Notes |
|---|---|---|
| Dashboard / overview | `Squares2X2Icon` | Landing/home nav item |
| Customers / users / accounts | `UsersIcon` | |
| Organization / company | `BuildingOfficeIcon` | |
| Calendar / schedule | `CalendarDaysIcon` | |
| Contracts / documents | `DocumentTextIcon` | |
| Approvals / confirmed status | `CheckCircleIcon` | Also usable as a status pill icon |
| Reports / analytics | `ChartBarIcon` | |
| Export / download | `ArrowDownTrayIcon` | |
| Settings | `Cog6ToothIcon` | |
| Search | `MagnifyingGlassIcon` | |
| Notifications | `BellIcon` | |
| Help / support | `QuestionMarkCircleIcon` | |
| Territory / map view | `MapIcon` | |
| Create / add new | `PlusIcon` | |
| Edit | `PencilIcon` | |
| Delete | `TrashIcon` | |
| View / preview | `EyeIcon` | |
| Close / dismiss | `XMarkIcon` | |
| Filter | `FunnelIcon` | |
| Refresh / sync | `ArrowPathIcon` | |
| Tasks / rule lists | `ClipboardDocumentListIcon` | e.g. bonus rules, checklists |
| Finance / amounts | `BanknotesIcon` | |
| Warning | `ExclamationTriangleIcon` | Pair with the `--warning` token, not a raw color |
| Nav group collapse chevron | `ChevronDownIcon` | Rotate `-90deg` when the group is collapsed |
