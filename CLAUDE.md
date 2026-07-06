# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Arch Productivity Hub" — a personal finance & habit-tracking desktop app for a single user in Mexico, built with `customtkinter`. It models NIF (Mexican financial reporting standards) balance sheets, SAT/LISR tax deductions, MSI (meses sin intereses) debt tracking, and habit/agenda logging, all backed by a local SQLite file (`data.db`). A companion Telegram bot allows capturing expenses from a phone.

## Running

```bash
python main.py           # Launch the desktop app (creates/opens data.db in cwd)
python bot_listener.py    # Run the Telegram capture bot directly (needs config.py, see below)
python generar_mock.py    # DESTRUCTIVE: drops and repopulates ingresos/gastos/deudas_msi with 12 months of fake data
```

`bot_listener.py` is normally run as a systemd **user** service instead of directly, so it survives crashes/network drops without manual restart:
```bash
systemctl --user status bot_listener.service       # check it's running
journalctl --user -u bot_listener.service -f       # tail logs
systemctl --user restart bot_listener.service       # after editing bot_listener.py
```
The unit file lives at `systemd/bot_listener.service` in this repo; the installed copy is `~/.config/systemd/user/bot_listener.service` (`enable-linger` is on for this user so it starts without an active login session).

There is no test suite, linter, or build step — verification is manual (run the app, exercise the tab).

### Local secrets

`config.py` (gitignored, must be created manually) defines:
```python
TELEGRAM_BOT_TOKEN = "..."
MI_CHAT_ID = 123456789   # your numeric Telegram user ID; the bot ignores/blocks all other senders
```

## Architecture

**Entry point (`main.py`)** builds a `CTkTabview` and instantiates one tab class per tab, all as siblings with no shared state or app-level context object — each tab is fully self-contained and opens its own SQLite connection per operation (no shared connection pool or ORM).

**Tab switch → refresh dispatch**: `main.py`'s `orquestar_refrescos()` matches the active tab's display label to a hardcoded call into that tab's refresh method. **These method names are inconsistent by design of the original author** — when adding a new tab, add both the `CTkTabview.add(...)` label and a matching `elif` branch here:
- Dashboard Financiero → `.actualizar()`
- Tesorería → `.actualizar()`
- Planeación (MSI) → `.actualizar()`
- Hábitos & Agenda → `.actualizar()`
- Impuestos e Inversión → `.recalcular_metricas()`
- Balance General → `.recalcular_patrimonio()`
- Auditoría Patrimonial → `.ejecutar_auditoria()`

Note: `PlaneacionTab` doesn't actually define `.actualizar()` (only `.actualizar_msi()` / `.actualizar_categorias()`), so switching to "Planeación (MSI)" raises an `AttributeError` today — a pre-existing bug, not yet fixed.

**Data layer (`database.py`)**: `init_db()` is the single source of truth for schema — `CREATE TABLE IF NOT EXISTS` for every table, called once at app startup. There are no migrations; schema changes mean editing this file directly (existing `data.db` files won't retroactively pick up new columns on tables that already exist — you'd need to drop/recreate or manually `ALTER TABLE`).

Every tab module (`tabs/*.py`) and `bot_listener.py` independently does `sqlite3.connect("data.db")` per read/write rather than importing shared connection logic from `database.py` — `database.py` is only used for initial schema creation. Follow this existing per-call-connection pattern when adding features to a tab rather than introducing a shared connection/session layer.

**Tables** (see `database.py` for authoritative schema):
- `agenda` — dated events with a time (`hora`); `tareas` — dated to-dos with a `completada` checkbox flag (no time)
- `entrenamiento_dias` — editable weekday → gym day-type mapping (seeded Lun=Push, Mar=Pull, Mié=Legs, Jue=Upper, Vie=Lower, Sáb/Dom=Descanso); `entrenamiento_ejercicios` — exercise catalog per day-type (seeded with defaults); `entrenamiento_log` — which exercises were checked off in which ISO week (`UNIQUE(ejercicio_id, semana)`)
- `natacion_log` — logged swim sessions (`semana`, `fecha`, `distancia_m`); `natacion_config` — single-row weekly session target
- `habitos_custom` / `habitos_custom_log` — user-defined recurring habits (name + comma-joined weekday list) and their per-date completion log
- `ingresos` / `gastos` — income/expense ledger; `gastos` carries `con_factura` (has CFDI invoice) and `es_deducible` (SAT-deductible) flags used throughout the tax and dashboard calculations
- `presupuestos` — per-category budget limits (currently unused by any tab UI — defined in schema only)
- `deudas_msi` — "meses sin intereses" installment debts (`monto_total`, `mensualidad`, `meses_totales`, `meses_pagados`)
- `balance_general` — one row per month (`fecha` as `YYYY-MM` primary key) capturing `activos_liquidos`, `activos_fijos`, `pasivos_corto`, `pasivos_largo`; this is the source for the Auditoría tab's ratios

The old `habitos_lista` / `habitos_log` tables (simple habit + daily checkbox) were superseded by the Habit Game tables above; `database.py` no longer creates them, but they're left in place (unused) on any `data.db` that already had them.

**Tab module conventions** (`tabs/*.py`): each is a `ctk.CTkFrame` subclass with a `setup_ui()` builder called from `__init__`, plus mutating methods (`guardar_*`, `eliminar_*`) that write to SQLite and then call the tab's own refresh method to redraw. List views are rebuilt from scratch on every refresh (`for w in frame.winfo_children(): w.destroy()` then re-populate) rather than diffed.

**Charting**: tabs with graphs (`dashboard.py`, `balance_general.py`, `planeacion.py`, `impuestos_inversion.py`) embed matplotlib via `FigureCanvasTkAgg` into a dedicated `canvas_frame`, destroying and recreating the figure on every refresh. The dark theme palette is hardcoded per-chart (`#0f172a`/`#1e293b` backgrounds, `#10B981` green / `#EF4444` red / `#F59E0B` amber / `#A855F7` purple / `#3B82F6` blue as consistent semantic colors for gain/loss/warning/debt/neutral across tabs) — match these when adding new charts rather than introducing new colors.

**`dashboard.py`** is the most complex tab: a 3×2 matplotlib grid computing cash flow bars, SAT-deductible pie split, period-over-period wealth velocity (`dW/dt` via `np.diff` on cumulative flow), 6-month MSI debt projection, Pareto cost breakdown by category, and a linear-regression (`np.polyfit`, degree 1) expense forecast. Its period granularity (Diario/Mensual/Anual) is driven by an `strftime` format string swapped per selection.

**`impuestos_inversion.py`** hardcodes the 2026 Mexican ISR marginal tax bracket table (Art. 152 LISR) as a matrix in `calcular_tasa_marginal_isr()` — update this table if tax brackets change for a new fiscal year. LISR personal-deduction cap logic (`min(ingreso * 0.15, 198000.0)`) is likewise a hardcoded current-law constant.

**`habitos_agenda.py`** ("Habit Game: Fuerza, Natación & Agenda") merges habit tracking and the calendar into one weekly, accordion-collapsible grid (only "today" is expanded by default; `self.dias_expandidos` tracks per-weekday-name expand state across re-renders). Each day card CRUDs five independent things against its own date: gym exercises (checked off per ISO week via `entrenamiento_log`), swim sessions, user-defined recurring habits (`habitos_custom`, assignable to any subset of weekdays), to-dos (`tareas`), and timed events (`agenda`). XP is a derived value recomputed from raw log tables on every refresh (never stored) — see `calcular_xp_total()`; level = `total_xp // XP_POR_NIVEL`, and level maps to one of 6 ranks in `RANGOS` (Novato → Leyenda). The muscle "holograma" (`dibujar_holograma()`) is a hand-built anatomical diagram (pecs/delts/biceps/abs/quads/calves as `matplotlib.patches.Polygon`/`FancyBboxPatch`, left-side shapes mirrored via `_mirror()` for the right side) redrawn on an independent `self.after(150, ...)` tick loop — decoupled from the data-driven `actualizar()` refresh so the glow/scan-line pulse animates continuously without re-querying the DB every frame. Per-muscle brightness in `calcular_brillo_musculos()` blends an all-time historical component (never decays) with a rolling-4-week recency component (decays if you stop training that muscle) — tune via `UMBRAL_HISTORICO`/`UMBRAL_RECIENTE`. Overall hologram color follows the current rank (`RANGOS[i][3]`), not the muscle data.

**`bot_listener.py`** is a standalone script (not imported by `main.py`, run as the `bot_listener.service` systemd unit — see Running above) that runs its own polling loop and writes directly to the same `gastos` table using a shorthand category-code parser (`v`, `c`, `t`, ... in `CATEGORIAS` dict) and `+f`/`+d` trailing flags for CFDI/deductible status. Keep its `CATEGORIAS` short-code dict and the category strings used elsewhere (`tabs/tesoreria.py`, `generar_mock.py`) in sync if categories change. It stores `message.date` (the Telegram server's original receive timestamp), not `datetime.now()`, as the expense's `fecha` — this matters because `infinity_polling()` processes any backlog on reconnect, and using "now" would misdate everything sent while the bot/network was down.

## Gotchas

- `data.db` and `config.py` are gitignored; a fresh clone has neither. `main.py` will create an empty `data.db` on first run via `database.init_db()`, but expect an empty app until you either use the UI or run `generar_mock.py` for fake historical data.
- `generar_mock.py` **drops** `ingresos`, `gastos`, and `deudas_msi` unconditionally before repopulating — never run it against real data you want to keep.
- The `Auditorias/` directory is gitignored and appears to hold ad-hoc monthly exported reports; it is not read or written by any code in this repo.
- This system needed the `noto-fonts-emoji` package installed (`sudo pacman -S noto-fonts-emoji && fc-cache -f`) for Tk to render emoji glyphs at all — without it every emoji shows as a tofu box. Separately, emoji typed with a trailing U+FE0F variation selector (e.g. copy-pasted "🏋️"/"🗑️") render as the emoji **plus** a stray tofu box for the selector itself on this font stack; strip the trailing `️` (use the bare codepoint, e.g. `"🏋"`/`"🗑"`) when adding new emoji to any tab.
