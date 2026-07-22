---
name: knockoutjs
description: >
  KnockoutJS MVVM patterns as used in the BMS in-house web apps (DistributionPlan,
  OldMyPage/MyPageWeb) — TypeScript view models on top of vanilla Knockout 3.x, a shared
  "Kull" framework layer (BaseDataViewModel, PrefetchLoader component registration,
  DataAccessBase), and Kendo/jQuery widget integration via custom binding handlers. Use
  this skill whenever the user is writing or reviewing Knockout view models, `data-bind`
  markup, `ko.observable`/`ko.computed`/`ko.observableArray`, `ko.components.register` or
  `registerAsyncComponent`, custom `ko.bindingHandlers`, or working in a Kull-based
  TypeScript project (App/Components/**, Scripts/App/**, App/Kull/**). Also trigger on
  "knockout view model", "createViewModel", "BaseDataViewModel", "PrefetchLoader",
  "koBindings", or when adding a new admin/list/detail component to DistributionPlan or
  MyPageWeb.
---

# KnockoutJS (BMS house style)

Two things are true about Knockout in these codebases at once: it's plain, standard
KnockoutJS 3.x underneath, and there's a shared "Kull" framework layer (`App/Kull/**` in
DistributionPlan, `Scripts/Kull/**` in OldMyPage — copy-forked between the two repos, not
an npm package) that most feature code goes through instead of calling raw `ko.*` APIs
directly. Get the plain-Knockout part right first, then reach for the house layer where
it exists rather than re-inventing it.

## Observables — the vanilla part

- `ko.observable(x)` / `ko.observableArray([])` for state; read with `obs()`, write with
  `obs(newValue)`.
- `ko.computed(() => ...)` for a derived value that must always re-run its evaluator when
  a dependency changes — required whenever the evaluator has a **side effect** (updates
  the DOM directly, calls the server, mutates something outside itself).
- `ko.pureComputed(() => ...)` for a derived value that's a **pure function** of its
  dependencies with no side effects. It sleeps (unsubscribes from dependencies) when
  nothing is observing it, so prefer it by default for plain display-value derivations —
  it's cheaper and doesn't leak. Only fall back to `ko.computed` when the evaluator does
  something that must happen even while "unobserved".
- Dispose anything you create with `.subscribe(...)` or `ko.computed(...)` yourself when
  the owning view model/component goes away — Knockout does not do this for you outside
  of bindings it manages. See "Disposal" below.

## TypeScript setup: use the local type aliases, not raw `ko.*` types

Both codebases have a `maptypes.ts` (DistributionPlan: `App/Kull/Shared/knockout/maptypes.ts`;
same idea in OldMyPage) that re-exports the knockout type names as flat aliases:

```ts
import type * as ko from "knockout";
export type KnockoutObservable<T> = ko.Observable<T>;
export type KnockoutObservableArray<T> = ko.ObservableArray<T>;
export type KnockoutComputed<T> = ko.Computed<T>;
export type KnockoutBindingHandler<T = any> = ko.BindingHandler<T>;
// ...
```

Feature code imports from this module (`import { KnockoutObservable } from
".../Kull/Shared/knockout/maptypes"`), not from `ko.Observable<T>` directly — this is the
existing convention (a holdover from when `@types/knockout` used a global `Knockout*`
namespace instead of `ko.*`-scoped types) and keeps new code consistent with the bulk of
the existing codebase. Match it in these two repos even though it's not something vanilla
Knockout requires.

## View model construction

Two idioms coexist in both codebases — recognize both, and match whichever the
surrounding `components.ts`/registration file already uses for that feature area:

**1. Factory-object form** (the more common one — used for the large majority of
components):
```ts
class customerListViewModel {
    items = ko.observableArray<Customer>([]);

    constructor(private params: { customerId: KnockoutObservable<number> }) {
        this.load = this.load.bind(this);
    }

    load() { /* ... */ }
}

export const viewModel = {
    createViewModel(params: any, options: any) {
        return new customerListViewModel(params);
    },
};
export const template = _template; // see "Templates" below
```

**2. Direct class export**, registered with `viewModel: (p, i) => new mod.viewModel(p, i)`
at the registration call site instead of a `createViewModel` wrapper — used when the
constructor also needs the `ComponentInfo` (`info`) argument (e.g. to read the host
element). Don't introduce a third idiom; pick whichever of these two the feature area
already uses.

**Constructor conventions**: bind every method you'll pass around as a callback in the
constructor (`this.load = this.load.bind(this);`) rather than arrow-function class fields
or a `const self = this;` closure — that's the established pattern throughout both
codebases (grep confirms zero `self = this` occurrences). This matters because methods get
handed to `data-bind` expressions, Kendo widget event handlers, and `dataSource` callbacks
as bare references.

## `BaseDataViewModel<TParam, TData>` — extend this for anything that loads a list/grid from the server

Defined in `Components/Shared/BaseDataViewModel.ts` (DistributionPlan) /
`Scripts/App/Shared/baseDataViewModel.ts` (OldMyPage). It standardizes the "observable
gates a server load" pattern so you don't hand-roll it per component:

```ts
class customerListViewModel extends BaseDataViewModel<CustomerFilter, Customer> {
    protected async loadDataFromServer(parameters: CustomerFilter | null) {
        this.errorText(null);
        return await customerApi.list(parameters);
    }
    protected getParameters(): CustomerFilter | null {
        return { search: this.searchText() };
    }
    protected onDataReceived(dt: Customer[]) {
        // side effects once data arrives — set derived observables, etc.
    }
}
```

What this gets you for free:
- `visible` observable — set it (or pass it in via `componentParameters.visible`) and
  `load()` fires automatically when it flips to `true` (wired in `init()` via
  `this.visible.subscribe(...)`). Don't call `loadDataFromServer` yourself from outside;
  drive it through `visible`/`load()`.
- A Kendo `dataSource` built for you via `getDataSource()`/`GetCustomDataSource(...)` when
  `useKendo` is set, wired to the same `loadDataFromServer`/`getParameters` overrides.
- `errorText` observable for surfacing a load failure to the template.
- `registerDisposable(...disposables)` + `dispose()` — push anything you create
  (subscriptions, computeds, Kendo widget instances) here instead of tracking it yourself;
  `dispose()` iterates and disposes all of them and is called by the framework when the
  component is torn down.
- `initForId(id, componentParameters)` — the bootstrap entrypoint; only calls
  `ko.applyBindings` itself when there's no `componentParameters` (i.e. when this is a
  page-level root view model, not a nested `ko.components` child).

Don't extend this for view models that don't load a server-backed list/grid — it exists
specifically for the "gated load" case, not as a universal base class.

## Registering components — via `PrefetchLoader`, not raw `ko.components.register`

Both codebases register components through a shared custom `ko.components.Loader`
implementation (`Kull/koPrefetchLoader.ts` — `PrefetchLoader.getInstance()`), wired up
once via `registerLoader()`, then populated in one central file per app
(`Components/Shared/components.ts` in DistributionPlan, the equivalent in OldMyPage):

```ts
import { PrefetchLoader, registerLoader } from "../../Kull/koPrefetchLoader.js";
const loader = PrefetchLoader.getInstance();
registerLoader();

loader.registerAsyncComponent("customer-list", async () => {
    const mod = await import("../Customer/customer-list");
    return { template: mod.template, viewModel: mod.viewModel.createViewModel };
});
```

Register every new component here (dynamic `import()` — code-split, loaded on first
use), rather than calling `ko.components.register` yourself. `PrefetchLoader` also
supports prefix-based template transforms (`accordion-`, `modal-`, `detail-`, ...) that
wrap your template in Bootstrap accordion/modal chrome automatically — check
`prefixHandlers` in `koPrefetchLoader.ts` before hand-building an accordion/modal wrapper
around a component's template yourself.

### Templates

Templates are separate sibling `.html` files, imported as raw strings via the project's
webpack loader and re-exported as `template`:

```ts
import _template from "./customer-list.html";
export const template = _template;
```

Not inline template strings, not a `require: 'text!...'` AMD plugin (no AMD/RequireJS in
either codebase — everything is ES modules + webpack + dynamic `import()`).

## Talking to the server

There's no direct client-side use of `Kull.GenericBackend` — despite the shared "Kull"
naming, that's a server-side .NET package (see the [`kull-generic-backend` skill](../kull-generic-backend/SKILL.md)
if you're touching the API side). Client code goes through a generated data-access layer
instead:

- `DataAccessBase` (`Components/Shared/DataAccessBase.ts`) wraps `jQuery.ajax` and
  transparently unwraps a `{ Error, Result }` response envelope: a string `Error` rejects
  the promise, otherwise `Result` resolves it.
- Per-endpoint call wrappers are **code-generated** from the server's Swagger document
  (files marked `/* DO NOT CHANGE THIS CODE! It is generated! */`, e.g. `dataAccess.ts`) —
  don't hand-edit them; regenerate instead if the server contract changes.
- The repeated view-model pattern is: call the generated method, `.then(dt =>
  observable(dt))`, or (preferably, for list/grid data) let `BaseDataViewModel`'s
  `loadDataFromServer` override do it so the `visible`-gated load wiring applies.

## Custom binding handlers

Follow the shape already established in `Kull/koBindings.ts` / `Kull/koKendoBindings.ts`
/ `Kull/koVisibility.ts`:

```ts
ko.bindingHandlers.myWidget = {
    init(element, valueAccessor) {
        const options = ko.unwrap(valueAccessor());
        const $el = jQuery(element);
        $el.myWidget(options);

        ko.utils.domNodeDisposal.addDisposeCallback(element, () => {
            $el.myWidget("destroy"); // tear down the jQuery/Kendo widget when KO removes the node
        });
    },
};
```

- **Always pair a jQuery/Kendo widget init with `ko.utils.domNodeDisposal.addDisposeCallback`.**
  Knockout doesn't know how to tear down a third-party widget attached to an element it
  removes (via `if`/`foreach`/`component`/`template` bindings) — that's on the binding to
  wire up. This is the single most common source of leaks when mixing jQuery direct DOM
  manipulation with Knockout-managed elements.
- **Register a lowercase alias** for any binding with a capital letter in its name, e.g.:
  ```ts
  ko.bindingHandlers.enterAction = { init(...) { ... } };
  ko.bindingHandlers.enteraction = ko.bindingHandlers.enterAction; // data-bind attrs get lowercased
  ```
  Needed because `data-bind`/custom `data-ko-*` attribute names come through the DOM
  lowercased; skip this and the camelCase-named binding silently never fires when used
  from markup with mixed casing.
- Use `controlsDescendantBindings: true` (return it from `init`) when the binding fully
  owns rendering of its children and Knockout should not also apply bindings inside — see
  `allowBindings` in `koBindings.ts` for the pattern.
- For a value that should push edits back into the bound observable (a two-way binding
  like `datedata`/`numberData`), register the binding name in
  `ko.expressionRewriting.twoWayBindings` so `data-bind="datedata: someObs"` also allows
  writes, not just reads.

## Validation

Neither codebase uses `knockout-validation` or a similar library — validation is written
by hand per view model (e.g. `Contact/targetsAddValidation.ts`). Don't introduce
`knockout-validation` into new code without checking with the team first; match the
existing manual-validation style (plain observables + computed `isValid`/error-message
properties) instead.

## Gotchas checklist

- `visible` on a `BaseDataViewModel` subclass is the load trigger — if data never loads,
  check whether `visible` is actually being set to `true` (directly, or via
  `componentParameters.visible` when nested) before chasing the data-access code.
- A missing `ko.utils.domNodeDisposal.addDisposeCallback` next to any `jQuery(element).somePlugin(...)`
  call inside a binding handler is the most common leak source — the widget instance
  outlives the DOM node.
- Don't call `ko.components.register` directly for feature components — register through
  `PrefetchLoader.registerAsyncComponent` in the app's central `components.ts` so the
  component participates in code-splitting and the accordion/modal prefix-wrapping
  machinery.
- `koBindings.ts`/`koKendoBindings.ts`/`koVisibility.ts` are duplicated near-verbatim
  between DistributionPlan and OldMyPage — they're a copy-forked shared layer, not an
  installed package. A fix in one repo won't automatically show up in the other.
- `ko.pureComputed` silently stops re-evaluating once it has no subscribers ("sleeping") —
  if a computed's side effect (e.g. writing to another observable, calling the server)
  seems to stop firing under some conditions, check whether it was written as a
  `pureComputed` when it actually needs to run unconditionally; switch it to `ko.computed`.
