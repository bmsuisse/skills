# Nuxt UI Reference

> Source: https://skills.sh/nuxt/ui/nuxt-ui
> Install: `npx skills add https://github.com/nuxt/ui --skill nuxt-ui`

Vue component library built on Reka UI + TailwindCSS + Tailwind Variants.

## Installation (Nuxt)

```bash
bun add @nuxt/ui tailwindcss
```

```ts
// nuxt.config.ts
export default defineNuxtConfig({
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css'],
})
```

```css
/* assets/css/main.css */
@import "tailwindcss";
@import "@nuxt/ui";
```

```vue
<!-- app.vue -->
<template>
  <UApp>
    <NuxtPage />
  </UApp>
</template>
```

`<UApp>` is required — provides global config for toasts, tooltips, and programmatic overlays.

## Icons

Uses Iconify (200,000+ icons). Format: `i-{collection}-{name}`

```vue
<UIcon name="i-lucide-sun" class="size-5" />
<UButton icon="i-lucide-plus" label="Add" />
<UAlert icon="i-lucide-info" title="Heads up" />
```

Install collections locally:
```bash
bun add @iconify-json/lucide @iconify-json/simple-icons
```

## Theming & Colors

7 semantic colors: `primary`, `secondary`, `success`, `info`, `warning`, `error`, `neutral`

```ts
// app.config.ts
export default defineAppConfig({
  ui: {
    colors: { primary: 'indigo', neutral: 'zinc' }
  }
})
```

Always use semantic utilities (`text-default`, `bg-elevated`, `border-muted`) — never raw Tailwind palette colors.

## Customizing components

The `ui` prop overrides a component's slots (highest priority):

```vue
<UButton :ui="{ base: 'rounded-none' }" />
<UCard :ui="{ header: 'bg-muted', body: 'p-8' }" />
```

Find slot names in `.nuxt/ui/<component>.ts`.

## Key composables

```ts
// Toast notifications
const toast = useToast()
toast.add({ title: 'Saved', color: 'success', icon: 'i-lucide-check' })

// Programmatic overlays
const overlay = useOverlay()
const modal = overlay.create(MyModal)
const { result } = modal.open({ title: 'Confirm' })
await result

// Keyboard shortcuts
defineShortcuts({
  meta_k: () => openSearch(),
  escape: () => close(),
})
```

## Form validation (Standard Schema — Zod/Valibot/Yup/Joi)

```vue
<script setup lang="ts">
import { z } from 'zod'
const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
})
const state = reactive({ email: '', password: '' })
</script>

<template>
  <UForm :schema="schema" :state="state" @submit="onSubmit">
    <UFormField name="email" label="Email" required>
      <UInput v-model="state.email" type="email" />
    </UFormField>
    <UButton type="submit">Sign in</UButton>
  </UForm>
</template>
```

## Common overlay components

```vue
<!-- Modal -->
<UModal v-model:open="isOpen" title="Edit">
  <template #body>Content</template>
  <template #footer>
    <UButton variant="ghost" @click="isOpen = false">Cancel</UButton>
    <UButton @click="save">Save</UButton>
  </template>
</UModal>

<!-- Slideover -->
<USlideover v-model:open="isOpen" title="Settings" side="right">
  <template #body>Content</template>
</USlideover>

<!-- Dropdown -->
<UDropdownMenu :items="[
  { label: 'Edit', icon: 'i-lucide-pencil' },
  { type: 'separator' },
  { label: 'Delete', icon: 'i-lucide-trash', color: 'error' },
]">
  <UButton icon="i-lucide-ellipsis-vertical" variant="ghost" />
</UDropdownMenu>
```

## Official templates

- [starter](https://github.com/nuxt-ui-templates/starter)
- [dashboard](https://github.com/nuxt-ui-templates/dashboard)
- [saas](https://github.com/nuxt-ui-templates/saas)
- [chat](https://github.com/nuxt-ui-templates/chat)
