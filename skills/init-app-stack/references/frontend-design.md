# Frontend Design Aesthetics

> Source: https://skills.sh/anthropics/skills/frontend-design
> Install: `bunx skills add https://github.com/anthropics/skills --skill frontend-design` (recommended) / `npx skills add ...`

Guide for creating distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics.

## Design Thinking (before coding)

Pick a **bold aesthetic direction** and commit to it. Ask:

- **Purpose** — What problem does this solve? Who uses it?
- **Tone** — Choose an extreme: brutally minimal, maximalist, retro-futuristic, luxury/refined, playful, editorial, brutalist, art deco, organic, industrial…
- **Differentiation** — What makes this _unforgettable_?

CRITICAL: Bold maximalism and refined minimalism both work — the key is _intentionality_.

## Aesthetic guidelines

**Typography**

- Choose beautiful, characterful fonts — avoid Inter, Roboto, Arial, system fonts
- Pair a distinctive display font with a refined body font

**Color & Theme**

- Use CSS variables for consistency
- Dominant colors with sharp accents > evenly-distributed timid palettes
- Commit to a cohesive look — avoid purple gradients on white

**Motion**

- CSS animations for effects and micro-interactions
- One well-orchestrated page load (staggered reveals) > scattered micro-interactions
- Scroll triggers and hover states that surprise

**Spatial Composition**

- Unexpected layouts: asymmetry, overlap, diagonal flow, grid-breaking elements
- Generous negative space OR controlled density (not in-between)

**Backgrounds & Visual Details**

- Gradient meshes, noise textures, geometric patterns, layered transparencies
- Dramatic shadows, decorative borders, grain overlays
- Atmosphere > solid colors

## What to NEVER do

- Overused font families (Inter, Roboto, Space Grotesk, system fonts)
- Clichéd color schemes (purple gradients on white)
- Predictable, cookie-cutter layouts
- Converge on the same aesthetic across generations

Match implementation complexity to vision: maximalist needs elaborate animations, minimalist needs precision and restraint.
