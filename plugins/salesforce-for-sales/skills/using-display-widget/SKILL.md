---
name: using-display-widget
description: "Render assembled Salesforce data as a styled widget using either a hydrated dynamic definition or a registered widget with props. Use when a skill needs a composed visual presentation or guidance on rendering mode, structure and supported tiles."
---
<!-- global-rules-bootstrap -->

# Global Rules

- **Execute silently between tool calls.** Do not output planning, progress, transition, waiting, or tool-result narration between calls. Execute tool calls silently and proceed directly to the next call. Parallelize independent tasks by batching tool calls into one turn whenever possible. Before the final output, speak only when the skill explicitly requires user input, approval, an exact notice, or material error/blocked reporting. Do not invent checkpoints.
- **Keep the final output concise.** Return only the requested result or deliverable. Omit process recaps, tool-call details, redundant preambles or conclusions, and data already shown in a widget.
- **Ground dynamic or custom relationship and field names before relying on them.** Fixed standard fields that this skill explicitly marks as requiring no grounding need no extra grounding call. On a name error, use the skill's documented grounding path when present; otherwise report the error instead of guessing or re-firing the same shape.
- **Cite every value exactly as queried**; never fabricate; distinguish a blank value from a value that was not queried. Link each Salesforce record inline: `https://[instanceUrl]/lightning/r/[SObjectType]/[Id]/view`.
- **Show human labels, never API/field literals.** In anything the user sees, print each field's grounded `label` (for example, "Deal Risk", not `Deal_Risk__c`) and record Names, never raw Ids or `__c` API names.
- **One idea per sentence.** In all generated content, if a sentence needs re-reading, it is carrying too much: split it.
- **Don't repeat the visual.** When a visualization or widget renders, the text around it tells the user what to conclude from the data. Do not restate numbers they can already see.
- **Use plain language.** Choose terms any reader understands on first read, with no domain knowledge or cultural context required. Avoid jargon and colloquialisms, and make labels signal what follows. Test: would a reader unfamiliar with the idiom understand the term and know what content to expect? Use "No engagement", not "went dark" or "ghosted".
- **Reproduce Salesforce terminology exactly.** Use the field labels, object names, and stage values the data returns; do not paraphrase them. Spell out acronyms on first use unless the term is an industry framework (for example, MEDDIC).
- **Empty `MINE` scope → fail fast, then ask which scope.** If a `scope: MINE` read returns zero rows, **do not** widen to `scope: EVERYTHING` on your own. Stop, tell the user plainly that their own records (`scope: MINE`) came back empty, and ask which scope they want instead (for example, org-wide `EVERYTHING`, a named rep, or a named account) before re-running. Never invent records, and never silently fall back to org-wide.
- **While following this skill, don't call `discover` or `describe`, and don't call any API or endpoint not written here. This file already has every query and widget reference you need. (Outside this skill, they're available as normal.)** Every Salesforce URL you need is in the skill. Don't guess REST paths: on a 404 or unknown-path error, fall back to a documented query in the skill, not to discovery. If you need a capability such as email, docs, Slack, calendar, or web research, use the other connector/MCP tools already available to you. Endpoint guessing and discovery add needless round-trips. Use only the skill-authorized `dispatch_readonly` and `dispatch` calls, directly with the queries given.
<!-- /global-rules-bootstrap -->

# Using `display_widget`

`display_widget` renders a widget from a **widget definition** using the native
Salesforce renderer. In
`dynamic` mode you author the widget definition yourself and the server echoes it straight to
the renderer — this is how an agent presents its own assembled UI. In
`salesforce_widget` mode you instead name a **pre-registered** widget and pass it data;
the server builds the widget definition. Most of this skill covers `dynamic` (authoring the definition);
`salesforce_widget` needs no widget-definition knowledge — just a `widget_resource_uri` and `props`.

Reach for `display_widget` whenever you want a **composed, styled layout** — a
summary card, a dashboard, a mixed text+table+badge view — instead of a wall of
text.

## When to call it

Gather first, render once. Do all your `dispatch` work, assemble the finished
picture, then call `display_widget` a single time to present it. The widget
reflects completed work, not one intermediate query.

- Use it in clients that mount MCP Apps widgets (a widget-capable client).
- In a terminal, the widget won't mount — the tool's text
  fallback is shown instead, so always keep the text content meaningful.

## Calling it

Two modes; `resourceType` is required (pick one):

```jsonc
// dynamic — you author the widget definition (this skill's focus)
display_widget({
  "resourceType": "dynamic",
  "widgetDefinition": { /* the renderer envelope you authored — see below */ }
})

// salesforce_widget — a pre-registered widget builds its own definition from your data
display_widget({
  "resourceType": "salesforce_widget",
  "widget_resource_uri": "ui://widget/lightningType/c__helloWorld",
  "props": { "text": "Hello, World" }
})
```

- `resourceType: "dynamic"` — you author the widget definition; the server echoes it back. Use
  this for a composed, styled layout the pre-registered widgets don't cover.
- `resourceType: "salesforce_widget"` — name a **pre-registered** widget by its
  `widget_resource_uri` (a lightning-type resource URI,
  `ui://widget/lightningType/c__<typeName>` — the identifier Core returns at
  runtime) and pass its `props` (the field values); the server builds the definition for
  you. Use this when a registered widget already matches what you want to show —
  you supply data, not layout. In production, Core builds this definition from the widget's
  Lightning Types resource. The standalone local server stands in with a fixed set of local
  builders (`c__helloWorld`, the minimal demo, and a few sales
  widgets) — author anything richer via `dynamic` mode.
  An unknown `widget_resource_uri` errors and names the registered set.
- There is no no-arg mode. For a quick demo, render the `c__helloWorld` widget:
  `display_widget({ "resourceType": "salesforce_widget", "widget_resource_uri":
  "ui://widget/lightningType/c__helloWorld" })`.

The result carries the widget definition in `_meta["salesforce/uiMetadata"]`, which the native
renderer reads via `accessToolMetadata` to paint the tree. The same definition is mirrored into
`structuredContent.widgetDefinition` (matching Core's `display_widget`, so the caller and the
renderer's structuredContent fallback can both read it); the text `content` is the
fallback for hosts that never mount the iframe.

## Widget-definition structure

The widget definition is a **declarative renderer envelope**. The renderer reads
`renderer.componentOverrides.$`, which is a `tile/mosaic` root whose `children`
are the tile blocks to render, in order:

```jsonc
{
  "renderer": {
    "componentOverrides": {
      "$": {
        "type": "mosaic",
        "definition": "tile/widget",
        "children": [
          /* tile blocks, rendered top to bottom */
        ]
      }
    }
  }
}
```

Every block is:

```jsonc
{
  "definition": "tile/<name>",   // e.g. "tile/text"
  "attributes": { /* block-specific props */ },
  "children": [ /* nested blocks, for layout/container blocks */ ]
}
```

The server also accepts a few shorthands and wraps them into this envelope for
you: a bare `tile/mosaic` root, a plain array of blocks, or a single block. Prefer
authoring the full envelope — it's unambiguous.

### Three rules that keep it from rendering blank

1. **Use only supported tiles.** The renderer paints only the blocks it
   registers. Any other `definition` renders as a red "No renderer config for
   block: tile/…" box instead of your content. The full, closed set is:

   `tile/accordion`, `tile/accordionItem`, `tile/avatar`, `tile/badge`, `tile/button`, `tile/buttonMenu`, `tile/callout`, `tile/chart`, `tile/checkbox`, `tile/code`, `tile/column`, `tile/container`, `tile/datagrid`, `tile/heatmap`, `tile/icon`, `tile/image`, `tile/link`, `tile/list`, `tile/listItem`, `tile/markdown`, `tile/menuItem`, `tile/meter`, `tile/numberField`, `tile/piechart`, `tile/progress`, `tile/radio`, `tile/rangeband`, `tile/richText`, `tile/row`, `tile/scatter`, `tile/select`, `tile/separator`, `tile/spacer`, `tile/sparkline`, `tile/spinner`, `tile/stepper`, `tile/switch`, `tile/tab`, `tile/tabSet`, `tile/table`, `tile/text`, `tile/textField`, `tile/textarea`, `tile/timeline`, `tile/waterfall`
   (plus the `tile/widget` / `tile/mosaic` root, used only at the top).

   Use only tiles from this list. Never create or guess a tile name, even when
   the request asks for a shape the list doesn't name — build it from the tiles
   above. Check every `definition` against this list before calling
   `display_widget`.
2. **Author fully-hydrated literals.** Put real values in `attributes`
   (`"text": "Acme Corp"`), not Mosaic expressions. This echo path does **no**
   compilation — `{!$record.Name}`-style bindings are not resolved and unhydrated
   `{!…}` attribute values are stripped before render. Resolve your data in the
   agent, then write the final strings/numbers into the widget definition.
3. **Use each block's real attribute name.** Notably `tile/text` takes `text`
   (not `content` or `value`), `tile/badge` takes `label`, `tile/markdown` takes
   `source`. See the vocabulary below.

## Tile-block vocabulary

Attributes are optional unless marked **required**. Enum values are the full set.

### Content

- **`tile/text`** — `text` (**required**), `variant` (`body`|`caption`|`code`|`h1`–`h6`),
  `weight` (`normal`|`medium`|`semibold`|`bold`), `color`
  (`default`|`error`|`muted`|`primary`|`success`|`warning`), `isItalic`,
  `isStrikethrough`.
- **`tile/markdown`** — `source` (**required**): a markdown string. Use for
  multi-paragraph or formatted prose.
- **`tile/badge`** — `label` (**required**), `variant`
  (`primary`|`secondary`|`outline`|`info`|`success`|`warning`|`error`). A small
  status pill.
- **`tile/link`** — `href` (**required**), `text`, `variant`
  (`default`|`muted`|`primary`), `underline` (`always`|`hover`|`none`).
- **`tile/callout`** — `title` (**required**), `description`, `variant`
  (`default`|`error`|`info`|`note`|`success`|`tip`|`warning`). A boxed notice.
- **`tile/separator`** — `orientation` (`horizontal`|`vertical`). A divider rule.

### Layout / containers (use `children`)

- **`tile/container`** — a panel with a rounded border. `borderless`
  (`true`|`false`, default `false`), `variant`
  (`default`|`emphasis`|`info`|`warning`|`error`|`success`). Put content blocks in
  `children`. To make a container fill/share a row's width, wrap it in a
  `tile/column` carrying `width` (container itself takes no width). Replaces the
  retired `tile/card`.
- **`tile/column`** — vertical stack. `gap` (`none`|`xs`|`sm`|`md`|`lg`|`xl`,
  default `md`), `align`, `width`. Children in `children`.
- **`tile/row`** — horizontal layout. `gap` (same tokens), `align`, `justify`
  (`start`|`center`|`end`|`between`|`around`|`evenly`), `isWrapped`.
- **`tile/list`** — `marker` (`none`|`bullet`|`number`); `children` are
  `tile/listItem` blocks.
- **`tile/listItem`** — no attributes; compose its `children` from `tile/text`,
  `tile/link`, `tile/badge`, etc.

### Table

- **`tile/table`** — `columns` (**required**), `rows` (**required**), `caption`
  (**required**), `appearance` (`default`|`bordered`|`striped`), `size`
  (`sm`|`md`), `isStickyHeader`.
  - `columns`: ordered array of `{ "key", "header", "align"? }`. `align` is
    `left` (default) | `center` | `right` (right-align numbers). `key` matches a
    property name in each row.
  - `rows`: array of objects; each object's keys match column `key`s. **All cell
    values are strings** — format numbers/dates into display-ready strings
    yourself (e.g. `"$4,200,000"`, `"2026-07-01"`). Missing keys render empty.

Other available blocks (same `{definition, attributes, children}` shape; see
`widget-definition.schema.json` for their attributes):
`tile/image`, `tile/icon`, `tile/avatar`, `tile/button`, `tile/buttonMenu` +
`tile/menuItem`, `tile/code`, `tile/richText`, `tile/timeline`, `tile/rangeband`,
`tile/scatter`, `tile/tabSet` + `tile/tab`,
`tile/progress`, `tile/spinner`, `tile/spacer`,
`tile/accordion` + `tile/accordionItem`, and the form inputs (`tile/textField`,
`tile/textarea`, `tile/numberField`, `tile/select`, `tile/checkbox`,
`tile/radio`, `tile/switch`). Form inputs only do something useful in a host that
wires their events; for a read-only presentation, stick to the content/layout
blocks above.

- **`tile/stepper`** — `caption` (**required**), `items` (**required**, ordered array of
  `{ name, state, detail? }`). `state` is `completed` | `current` | `target`; it is shown
  as visible text as well as a visual marker. Optional `completedLabel`, `currentLabel`, and
  `targetLabel` localize the status text. Use for discrete process stages, not date intervals.

### Data visualization

These tiles turn resolved numbers into charts. Two rules carry over: author
**hydrated literals** (numbers stay numbers here — unlike `tile/table`, whose
cells are all strings), and give every viz a `caption` — it is the accessible
description and the text-fallback line. `valueFormat` (where present) is
`number` | `percent` | `currency` | `compact`; `size` (where present) is
`sm` | `md` | `lg`. Values are labelled on the marks, so the read never rests on
color alone.

**Localized tile text.** A few tiles draw built-in English words of their own (an
"Other" slice, a "no data" readout, a past-due footnote). Each has an optional
`…Label` attribute, listed per tile below. When the user is not writing in English,
set every one that the widget can show, in the user's language; leave them out for
English (they default to it). `{0}`, `{1}` mark where the tile inserts a value, so
place them where the translation's grammar needs them, e.g. a timeline's
`"daysPastCloseLabel": "{0} jours après la clôture"`. Your own text (captions,
labels, headers) is already in the user's language and needs no extra attribute.
`tile/timeline` and `tile/rangeband` (described in the schema) carry them too:
timeline `todayLabel` ("today · {0}", `{0}` the date), `daysPastCloseLabel` ("{0} days
past close") and `dayPastCloseLabel` ("{0} day past close") in the bar tooltip,
`dateRangeLabel` ("{0} to {1}", the bar tooltip's dates), `daysPastShortLabel`
("{0}d past · {1}", `{1}` the close date), and the past-due footnote
`pastDueOneLabel` ("1 item is past its close date — {0}.", `{0}` the name) /
`pastDueManyLabel` ("{0} items are past their close date — {1}.", `{0}` the count,
`{1}` the names) when `pastDueNote` is unset; rangeband `noDataLabel` ("No data.").

- **`tile/chart`** — `chartType` (**required**, `bar`|`line`|`area`|`column`),
  `categories` (**required**, `string[]` — the x-axis), `series` (**required**,
  array of `{ name, data: (number|null)[], type? }`; `type` per-series overrides
  `chartType` for combos), `caption` (**required**). Optional: `stackMode`
  (`none`|`stacked`|`normalized`), `baseline` (`zero`|`center`), `valueFormat`,
  `showValues`, `showLegend`, `showGrid`, `title`, `xAxisLabel`, `yAxisLabel`,
  `size`. Use for multi-point/multi-series comparison.
- **`tile/sparkline`** — `data` (**required**, `(number|null)[]`), `label`
  (**required**). Optional: `variant` (`line`|`bar`|`area`), `baseline` (number),
  `showEndpoint`, `highlightExtremes`, `valueFormat`, `role`
  (`neutral`|`positive`|`negative`|`emphasis`), `size` (`sm`|`md`). A compact
  inline trend for a KPI. Localized text: `noDataLabel` ("no data", when `data` is empty).
- **`tile/meter`** — `value` (**required**, number), `valueLabel` (**required**,
  the formatted read). Optional: `min` (0), `max` (100), `target` (number),
  `bands` (array of `{ from, to, variant: error|success|info|warning, label }`),
  `label`, `targetLabel`, `status`, `overAttainment`, `orientation`
  (`horizontal`|`vertical`), `size`, `showValue`. A bullet graph for
  goal/attainment. Localized text: `overTargetLabel` ("over target", the tooltip on the
  over-attainment marker).
- **`tile/piechart`** — `slices` (**required**, array of `{ label, value,
  role?: normal|highlight }`), `caption` (**required**). Optional: `variant`
  (`pie`|`donut`), `valueFormat`, `showValues`, `showLegend`, `maxSlices`
  (buckets the rest into "Other"), `centerLabel` + `centerValue` (donut only),
  `size`. Part-to-whole composition. Localized text: `otherLabel` ("Other", the bucketed
  slice).
- **`tile/waterfall`** — `start` (**required**, `{ label, value }`), `steps`
  (**required**, array of `{ label, delta, role?: auto|increase|decrease }`),
  `end` (**required**, `{ label, value? }` — value computed when omitted).
  Optional: `valueFormat` (`number`|`percent`|`currency`), `showConnectors`,
  `showValues`, `caption`, `size`. A running-total bridge; each step is signed.
  Localized text: `residualLabel` ("Residual", the reconciling bar drawn when the steps
  don't add up to `end.value`).
- **`tile/heatmap`** — `caption` (**required**), `domain` (**required** except for the state
  layout, `[min, max]`). Matrix layout: `xLabels`, `yLabels` (`string[]`) and `cells`
  (array of `{ x, y, value, valueLabel? }`). Calendar layout (`layout:
  "calendar"`): `days` (array of `{ date: "YYYY-MM-DD", value }`). Optional:
  `layout` (`matrix`|`calendar`|`state`), `encode` (`color`|`size`), `scale`
  (`sequential`|`diverging`), `midpoint` (diverging), `valueFormat`, `size`.
  State layout (`layout: "state"`, no `domain`): categorical account x product
  grid; `cells` are `{ x, y, state, label? }` with `state` one of `purchased`,
  `inPlay`, `whitespace`, `lost`, `empty` (a missing cell is `empty`), plus
  `legend` (array of `{ state, label }`). Localized text: `openOpportunityLabel` (matrix,
  missing-cell tooltip, `{0}` row, `{1}` column: "{0} — {1}: open opportunity"); calendar
  `noActivityLabel` ("no activity") and `outsideRangeLabel` ("outside the range") day
  tooltips, and `noActivityRecordedLabel` ("No activity recorded.", when `days` is empty).
- **`tile/datagrid`** — a richer `tile/table`: typed, sortable columns and
  per-row status. `caption` (**required**), `columns` (**required**, array of
  `{ key, header, type?, align?, sortable?, width?, priority?, target? }`), `rows`
  (**required**). Column `type`: `text`|`number`|`currency`|`percent`|`date`|
  `datetime`|`boolean`|`link`|`badge`|`avatar`|`rating`|`databar`|`sparkline`.
  Cell values are the **raw typed value** (number for `currency`/`percent`,
  ISO string for `date`, `number[]` for `sparkline`) — the column `type`
  formats them — or an object `{ value, display?, href?, badgeVariant?, tone? }`.
  A row may carry `_status` (a label) + `_tone`
  (`error`|`success`|`info`|`warning`|`default`) to tint the whole row. Optional:
  `defaultSort` (`{ key, direction: asc|desc }`), `footer` (array of `{ key,
  label?, value }`), `appearance`, `size` (`sm`|`md`), `isStickyHeader`,
  `emptyText`, `totalRows`. Reach for it over `tile/table` when you want sorting,
  typed formatting, or risk tinting; use `tile/table` for a plain read-only grid.
  Localized text: `trendLabels` (`[rising, falling, flat]`, the trend word in a `sparkline`
  cell's tooltip) and `showingRowsLabel` ("showing {0} of {1}", `{0}` rows shown, `{1}`
  `totalRows`).
  `headerColor` (`muted`|`ink`) defaults to the existing muted headers; `ink`
  opts into the ink token for column/status headers and phone card labels,
  without changing cell values.

## Worked example — an opportunity summary

Data already fetched via `dispatch`, resolved into literals, then rendered once:

```jsonc
display_widget({
  "resourceType": "dynamic",
  "widgetDefinition": {
    "renderer": { "componentOverrides": { "$": {
      "type": "mosaic",
      "definition": "tile/widget",
      "children": [
        { "definition": "tile/container", "attributes": {},
          "children": [
            { "definition": "tile/row", "attributes": { "justify": "between", "align": "center" },
              "children": [
                { "definition": "tile/text", "attributes": { "text": "Acme Corp — Renewal", "variant": "h3" } },
                { "definition": "tile/badge", "attributes": { "label": "Proposal", "variant": "info" } }
              ] },
            { "definition": "tile/text", "attributes": { "text": "$4,200,000 · closes 2026-09-30", "variant": "body", "color": "muted" } },
            { "definition": "tile/separator" },
            { "definition": "tile/table",
              "attributes": {
                "caption": "Open opportunities",
                "appearance": "striped",
                "columns": [
                  { "key": "name",   "header": "Name" },
                  { "key": "stage",  "header": "Stage" },
                  { "key": "amount", "header": "Amount", "align": "right" }
                ],
                "rows": [
                  { "name": "Big Deal",    "stage": "Prospecting", "amount": "$100,000" },
                  { "name": "Bigger Deal", "stage": "Closed Won",  "amount": "$500,000" }
                ]
              } }
          ] }
      ]
    } } }
  }
})
```

## Text fallback

Always author the tool's text `content` to carry the same information as the
widget (the tool does this from your widget definition's block text automatically, but the
richer the blocks' `text`/`label`/`title`, the better the fallback). In a
terminal or a host that advertises MCP Apps but never mounts the iframe, the text
is all the user sees — it must stand on its own, not say "rendered a widget."

## Related

- `widget-definition.schema.json` (this skill's directory) — the full JSON Schema for the widget-definition
  renderer envelope and every tile block, with a description on each property and
  the complete enum sets. Validate a widget definition against it, or read it as the exhaustive
  attribute reference behind the vocabulary above.
