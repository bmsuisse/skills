---
name: remove-ai-writing
description: "Detect and surgically fix AI writing patterns in English, German, French, or Italian text. Use this skill whenever the user asks to 'remove AI writing', 'fix AI tells', 'make this sound less like ChatGPT/Claude', 'avoid AI patterns', 'make this more human', 'de-slop my text', 'nettoyer le texte IA', 'KI-Schreibstil entfernen', 'rimuovere la scrittura IA', or pastes text that sounds stiff, puffed-up, or formulaic. Also trigger proactively after writing or editing long prose sections — even if the user doesn't explicitly ask for AI pattern removal. The skill applies targeted word-level and sentence-level fixes without rewriting content or changing meaning."
---

# Remove AI Writing

Finds and fixes the specific patterns that mark text as AI-generated, based on documented linguistic research. Applies surgical fixes — one phrase at a time — without rewriting paragraphs or changing the author's meaning.

Works for **English, German, French, and Italian** text. Auto-detect the language from the input — no need for the user to specify it.

## Reference vocabulary

For the full era-sorted word lists and language-specific equivalents, read:

```
references/ai-vocabulary.md
```

Load this reference when scanning long documents or when unsure about a specific word.

---

## The two rules that matter most

**Rule 1 — Replace, don't add.** Every fix must make the sentence shorter or simpler. If a replacement adds words, reconsider it.

**Rule 2 — Don't change meaning.** Fix the *phrasing*, not the *claim*. If you're unsure whether a fix changes the meaning, leave it.

---

## Patterns to fix

### 1. AI vocabulary overuse

These words appear far more in LLM output than in human writing. One or two is fine; a cluster is a signal.

| Pattern | EN | DE | FR | IT |
|:---|:---|:---|:---|:---|
| Importance filler | crucial, pivotal, key | entscheidend, massgeblich, zentral | crucial, essentiel, fondamental | cruciale, fondamentale, essenziale |
| Emphasis verbs | underscore, highlight | unterstreicht, hebt hervor | souligne, met en lumière/évidence | sottolinea, mette in luce/evidenza |
| Enabler verbs | enhance, foster, enable | fördert, ermöglicht, befähigt | favorise, permet, renforce | favorisce, consente, potenzia |
| Empty adjectives | comprehensive, robust | umfassend, robust | exhaustif, robuste | esaustivo, robusto |
| Adverb filler | seamlessly, meticulously | nahtlos, sorgfältig | de manière transparente, méticuleusement | in modo trasparente, meticolosamente |
| Hype adjectives | vibrant, groundbreaking | wegweisend, innovativ | novateur, révolutionnaire | innovativo, rivoluzionario |
| Display verbs | showcase, demonstrate | zeigt, veranschaulicht | illustre, démontre | illustra, dimostra |
| Abstract metaphor | landscape, tapestry | Landschaft (abstract) | paysage (abstract), tissu | panorama (abstract), tessuto |
| Filler attribution | valuable insights | wertvolle Erkenntnisse | précieuses perspectives | preziose intuizioni |
| Sentence opener | Additionally, | Darüber hinaus, / Zudem, | De plus, / En outre, / Par ailleurs, | Inoltre, / In aggiunta, |

**Fix**: delete, replace with a specific claim, or use a plain verb.

### 2. Copula avoidance

AI avoids "is" and replaces it with fancier constructions.

| Language | AI pattern | Fix |
|:---|:---|:---|
| EN | serves as, stands as, functions as | → "is" |
| DE | dient als, fungiert als, steht für | → "ist" |
| FR | fait office de, tient lieu de, constitue | → "est" |
| IT | funge da, costituisce, si configura come | → "è" |

Also watch for:
- DE: "ermöglicht es" (long construct) → direct verb; "bietet einen Überblick über" → "zeigt" / "beschreibt"
- FR: "offre la possibilité de" → direct verb; "permet de mettre en œuvre" → direct verb
- IT: "offre la possibilità di" → direct verb; "consente di implementare" → direct verb

### 3. Superficial analysis clause endings

Clauses tacked onto sentences to explain *why something matters* — when the text already shows it.

| Language | Examples (delete the clause) |
|:---|:---|
| EN | "… highlighting its importance", "… underscoring the need for" |
| DE | "… was X ermöglicht", "… und trägt damit zu X bei", "… was die Notwendigkeit von Y unterstreicht" |
| FR | "… ce qui souligne l'importance de", "… contribuant ainsi à", "… mettant en évidence" |
| IT | "… il che sottolinea l'importanza di", "… contribuendo così a", "… mettendo in evidenza" |

These endings add nothing. The preceding sentence already made the point.

### 4. Negative parallelisms

| Language | AI pattern | Fix |
|:---|:---|:---|
| EN | not only X but also Y | "X and Y" (unless contrast is genuinely surprising) |
| DE | nicht nur X, sondern auch Y | "X und Y" |
| FR | non seulement X mais aussi/également Y | "X et Y" |
| IT | non solo X ma anche Y | "X e Y" |

Use the parallel form only when the contrast is genuinely surprising. Otherwise simplify.

### 5. Inline bold-header lists (the "listicle" tell)

```
(1) **Bold Label**: description; (2) **Bold Label**: description
```

Replace with prose ("Firstly … Secondly …" / "Erstens … Zweitens …" / "Premièrement … Deuxièmement …" / "In primo luogo … In secondo luogo …") or a plain unordered list without bold labels.

### 6. Puffery / undue importance

| Language | AI pattern | Fix |
|:---|:---|:---|
| EN | leading, premier, renowned, plays a crucial role in | specific fact, or delete; "affects" / "shapes" |
| DE | führend, wegweisend, renommiert, spielt eine entscheidende Rolle | specific fact, or direct verb |
| FR | leader, de premier plan, renommé, joue un rôle crucial/clé | specific fact, or direct verb |
| IT | leader, di primo piano, rinomato, gioca un ruolo cruciale/chiave | specific fact, or direct verb |

### 7. Rule-of-three filler

"The system is fast, reliable, and scalable" — if all three adjectives are expected/obvious, delete them. Keep only the surprising or specific one. Applies to all languages.

### 8. Vague attributions

- "Experts argue / Researchers show" without citation → add citation or delete
- DE: "Experten sind sich einig" → same
- FR: "Les experts s'accordent à dire" / "Les chercheurs montrent" → same
- IT: "Gli esperti concordano" / "I ricercatori dimostrano" → same

### 9. Formulaic parallel structures

- DE: "Der Schlüssel zu X liegt in Y, der Schlüssel zu Z in …" → restructure
- EN: "The key to X is Y; the key to Z is …" → restructure
- FR: "La clé de X réside dans Y, la clé de Z dans …" → restructure
- IT: "La chiave di X risiede in Y, la chiave di Z in …" → restructure

### 10. Promotional sentence openers

| Language | AI pattern | Fix |
|:---|:---|:---|
| EN | "This represents a significant shift toward …" | state what actually changed |
| DE | "Dies stellt einen wichtigen Fortschritt dar" | state what changed concretely |
| FR | "Cela représente un tournant significatif vers …" | state what changed concretely |
| IT | "Questo rappresenta un significativo passo avanti verso …" | state what changed concretely |

---

## How to apply this skill

### Step 1 — Scan
Read the target text. Auto-detect the language. Use Grep if it's a long file. Look for the patterns above. Make a mental list of hits, starting with clusters (multiple patterns in one sentence = highest priority).

### Step 2 — Fix, one change at a time
For each hit:
- Make the minimal change (word swap or deletion)
- Verify the sentence still reads naturally and means the same thing
- Move to the next hit

Do not batch changes into paragraph rewrites. Each fix is independent.

### Step 3 — Check what you changed
After all fixes, read the changed sentences aloud (mentally). If any sounds worse than the original, revert that one.

### Step 4 — Report
Tell the user:
- How many instances were fixed
- Which pattern types were most common
- Any remaining instances you left on purpose (e.g., a word that is used correctly in context)

---

## What NOT to change

- Technical terms, model names, metric names — these are not AI tells
- Quoted material or citations
- Sentences that are already direct and plain
- Structural words that are genuinely needed (e.g., "Erstens / Zweitens", "Premièrement", "In primo luogo" as enumeration)
- "Ermöglicht" / "permet" / "consente" when it describes a real technical capability (e.g., "Spark ermöglicht verteiltes Processing") — only flag it when used as a filler ending clause

---

## Language-specific notes

### German (Swiss convention)
Use "ss" not "ß" throughout. If you see "ß", replace with "ss". German academic writing tends toward long subordinate clauses — these are not AI tells by themselves. Only flag constructions that match the patterns above.

### French
French academic style uses longer sentences and more formal register than English. This is normal — don't simplify legitimate French rhetorical structures. Focus on the AI-specific fillers (e.g., "de manière transparente", "il convient de souligner") rather than natural French formality. Use straight quotes « » where the original uses them.

### Italian
Italian academic prose is naturally elaborate. Long periods with subordinate clauses are part of the tradition, not AI tells. Focus on the stock phrases ("è importante sottolineare", "gioca un ruolo fondamentale") and empty emphasis. Respect the original register.
