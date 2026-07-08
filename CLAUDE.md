# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Arch Productivity Hub" — a personal finance & habit-tracking desktop app for a single user in Mexico, built with `customtkinter`. It models NIF (Mexican financial reporting standards) balance sheets, SAT/LISR tax deductions, MSI (meses sin intereses) debt tracking, and habit/agenda logging, all backed by a **shared MariaDB server** (Docker container on an always-on machine — see `servidor/README.md`) so the app can run on several computers against the same data. A companion Telegram bot, which runs on the server machine, allows capturing expenses from a phone. The old per-machine SQLite `data.db` is legacy: it is only read by `migrar_a_mariadb.py` (one-time data migration) and kept as a historical backup.

## Running

```bash
python main.py             # Desktop app (needs the MariaDB server reachable + config.py)
python bot_listener.py     # Telegram capture bot (runs on the SERVER machine; needs config.py)
python migrar_a_mariadb.py # One-time: copy the legacy data.db into the MariaDB server (refuses if target has data; --forzar to override)
python generar_mock.py     # DESTRUCTIVE: TRUNCATEs ingresos/gastos/deudas_msi ON THE SHARED SERVER and repopulates with 12 months of fake data
```

**Server side** (`servidor/`): `docker-compose.yml` runs `mariadb:lts` (db `arch_tracker`, user `arch`, passwords in `servidor/.env` — gitignored, template in `.env.example`). Backups are logical dumps, hourly: `respaldo.sh` on the server (into `servidor/respaldos/`), `jalar_respaldo.sh` on each client over plain TCP (into `backups/`) — both installed as systemd user timers by `instalar_timers.sh servidor|cliente`. The full runbook (bring up a server from zero, connect a new client, restore a dump onto a replacement machine) is `servidor/README.md` — keep it in sync when changing anything under `servidor/`.

`bot_listener.py` runs as a systemd **user** service on the server machine, so it survives crashes/network drops without manual restart. It must run on exactly ONE machine (two pollers on the same token conflict):
```bash
systemctl --user status bot_listener.service       # check it's running
journalctl --user -u bot_listener.service -f       # tail logs
systemctl --user restart bot_listener.service       # after editing bot_listener.py
```
The unit template is `systemd/bot_listener.service` (uses `%h/arch_tracker`; adjust if the repo lives elsewhere); the installed copy is `~/.config/systemd/user/bot_listener.service` (`enable-linger` is on so it starts without an active login session).

There is no test suite, linter, or build step — verification is manual (run the app, exercise the tab).

### Local secrets

`config.py` (gitignored; copy from `config.example.py`) defines the DB connection for BOTH the app and the bot, plus the bot credentials:
```python
DB_HOST = "192.168.1.50"   # server IP ("127.0.0.1" on the server itself)
DB_PORT = 3306
DB_USER = "arch"
DB_PASSWORD = "..."         # = MARIADB_PASSWORD in servidor/.env
DB_NAME = "arch_tracker"
TELEGRAM_BOT_TOKEN = "..."  # only needed where the bot runs
MI_CHAT_ID = 123456789      # your numeric Telegram user ID; the bot ignores/blocks all other senders
```
`database.py` falls back to localhost defaults if `config.py` is missing. Client deps on Arch: `python-pymysql` (driver), `mariadb-clients` (for the backup pull), plus the existing GUI stack; the bot machine also needs `python-pytelegrambotapi`.

## Architecture

**Entry point (`main.py`)** builds a `CTkTabview` and instantiates one tab class per tab, all as siblings with no shared state or app-level context object — each tab is fully self-contained and opens its own short-lived DB connection per operation via `database.conectar()` (no shared connection pool or ORM).

**Tab switch → refresh dispatch**: `main.py`'s `orquestar_refrescos()` matches the active tab's display label to a hardcoded call into that tab's refresh method. **These method names are inconsistent by design of the original author** — when adding a new tab, add both the `CTkTabview.add(...)` label and a matching `elif` branch here:
- Dashboard Financiero → `.actualizar()`
- Tesorería → `.actualizar()`
- Planeación (MSI) → `.actualizar()`
- Hábitos & Agenda → `.actualizar()`
- Impuestos e Inversión → `.recalcular_metricas()`
- Balance General → `.recalcular_patrimonio()`
- Auditoría Patrimonial → `.ejecutar_auditoria()`


**Data layer (`database.py`)**: `conectar()` is the single door to the database — it returns a thin proxy over a PyMySQL connection. The project's SQL keeps sqlite3-style `?` placeholders: the `_Cursor` proxy rewrites them to PyMySQL's `%s` on every execute (so **no SQL string may contain a literal `?` or `%`** — LIKE wildcards go in the parameter values, never inline) and, like sqlite3, `execute()` returns the cursor itself (there are chained `.execute(...).fetchone()` calls). `database.IntegrityError` / `database.MySQLError` are re-exported for except clauses. `init_db()` is the single source of truth for schema — `CREATE TABLE IF NOT EXISTS` for every table, called at app startup against the shared server.

MariaDB dialect conventions (keep these when writing new SQL):
- The column `desc` (gastos/ingresos/deudas_msi) is a **reserved word in MariaDB** — always backtick bare references (`` `desc` ``); qualified `g.desc` also gets backticked for consistency.
- Dates are ISO text (`YYYY-MM-DD`); period grouping/filtering uses string prefixes — `LEFT(fecha, 7)` for month, `LEFT(fecha, 4)` for year, `LEFT(fecha, 10)` for day (this replaced SQLite's `strftime`).
- Upserts use `REPLACE INTO` (presupuestos, bot_estado, balance_general, entrenamiento_dias) and `INSERT IGNORE` (the two UNIQUE log tables) — not SQLite's `INSERT OR ...`/`ON CONFLICT`.
- Money/aggregatable columns are `DOUBLE` (not DECIMAL/INT) so `SUM()`/`AVG()` come back to Python as float — PyMySQL returns `Decimal` for aggregates over INT columns, which breaks float math; keep new numeric columns DOUBLE if they'll be summed.

Every tab module (`tabs/*.py`) and `bot_listener.py` independently calls `database.conectar()` per read/write (open → query/commit → close) rather than sharing a connection. Follow this existing per-call-connection pattern when adding features to a tab rather than introducing a shared connection/session layer.

**Tables** (see `database.py` for authoritative schema):
- `agenda` — dated events with a time (`hora`); `tareas` — dated to-dos with a `completada` checkbox flag (no time)
- `entrenamiento_dias` — editable weekday → gym day-type mapping (seeded Lun=Push, Mar=Pull, Mié=Legs, Jue=Upper, Vie=Lower, Sáb/Dom=Descanso); `entrenamiento_ejercicios` — exercise catalog per day-type (seeded with defaults); `entrenamiento_log` — which exercises were checked off in which ISO week (`UNIQUE(ejercicio_id, semana)`)
- `natacion_log` — logged swim sessions (`semana`, `fecha`, `distancia_m`); `natacion_config` — single-row weekly session target
- `habitos_custom` / `habitos_custom_log` — user-defined recurring habits (name + comma-joined weekday list) and their per-date completion log
- `ingresos` / `gastos` — income/expense ledger; `gastos` carries `con_factura` (has CFDI invoice), `es_deducible` (SAT-deductible), `tipo_deduccion` (SAT deduction concept, NULL for non-deductible; drives per-concept caps) and `cuenta_id` (nullable FK to `cuentas`; `ingresos` has it too) — the "deductible" rule everywhere is `es_deducible=1 AND con_factura=1` (no CFDI → no deduction); keep dashboard.py and impuestos_inversion.py queries in agreement
- `cuentas` — real accounts (nombre UNIQUE, tipo Efectivo/Débito/Crédito/Inversión, saldo_inicial, fecha_inicial); Crédito accounts hold debt as a **negative** balance. Current balance is always **derived**: `saldo_inicial + Σingresos − Σgastos + Σtransferencias_recibidas − Σtransferencias_enviadas` (see `TesoreriaTab.obtener_cuentas_con_saldo()`; the same formula is replicated in `auditoria.py` and `bot_listener.py` — keep the three in sync), never stored. Deleting an account nulls `cuenta_id` on its movements rather than deleting them
- `transferencias` — money moved between own accounts (credit-card payments above all): adjusts both balances but is **neither income nor expense** — the expense was recorded at purchase time. Auditoría's conciliación subtracts net transfers into Crédito accounts from the expected liquidity change for exactly this reason
- `presupuestos` — per-category monthly budget limits; written by `PlaneacionTab` (manual form or "Adoptar como presupuesto" from the what-if simulator), read by the traffic-light list in Planeación, `TesoreriaTab.verificar_presupuesto()` (capture-time warning) and the Telegram bot (reply feedback, `/resumen`, daily alert thread)
- `bot_estado` — key/value scratch table created/used only by `bot_listener.py` (e.g. `ultimo_aviso` date so the daily alert fires once per day across systemd restarts)
- `deudas_msi` — installment debts (`monto_total`, `mensualidad`, `meses_totales`, `meses_pagados`, `tasa_interes`); `tasa_interes=0` means true MSI, `>0` means the mensualidad was computed with French amortization at that annual rate

- `recurrentes` — templates (tipo ingreso/gasto, monto, categoría/fuente, `dia_mes`, cuenta) materialized by `database.generar_recurrentes()`: idempotent (tracks `ultima_generacion`), clamps day to short months, backfills the current month on creation. Called at app startup (`main.py`) and hourly by the bot's vigilante thread (which Telegram-notifies whatever it generated).
- `metas` — savings goals linked to a cuenta; progress is the linked account's derived balance. `database.obtener_metas_con_progreso()` also estimates the recent monthly net inflow (last 90 days ÷ 3) for the projected completion date; consumed by Planeación (full CRUD panel) and Inicio (compact list).

Account balances have a single source: `database.obtener_saldos_cuentas()` → `(id, nombre, tipo, tasa_anual, saldo)` — Tesorería, Inicio, Auditoría, Planeación's debt planner and the bot all consume it; never re-embed the balance SQL. All destructive 🗑 actions across tabs ask `messagebox.askyesno` first — keep that invariant for new delete buttons. Treasury history lists support live search (`actualizar_historiales()` re-renders on KeyRelease, separate from the full `actualizar()`) and CSV export to `exportes/` (gitignored, utf-8-sig for Excel). Budget rows show compliance streaks (consecutive *closed* months within the current limit — limits have no history, so past months are judged against today's limits).

`init_db()` also performs additive migrations (`_columnas()` reads `information_schema.COLUMNS`, then `ALTER TABLE ADD COLUMN`) for `gastos.tipo_deduccion`/`cuenta_id`, `ingresos.cuenta_id`, `deudas_msi.tasa_interes` and `cuentas.tasa_anual` — follow that pattern for future column additions since CREATE TABLE IF NOT EXISTS won't touch existing tables. Backups are NOT done in-app anymore: they are hourly `mariadb-dump` gzips — `servidor/respaldo.sh` on the server plus `servidor/jalar_respaldo.sh` on each client (into the gitignored `backups/`), both driven by systemd user timers (`servidor/instalar_timers.sh`).

**`CATEGORIA_AHORRO` convention** (defined in `database.py`): the "Ahorros" expense category is a wealth transfer, not consumption. All consumption analytics exclude it — dashboard flows/W(T)/VaR/PMC/forecast/Pareto/hormiga, the runway in impuestos, and the what-if simulator (both its totals and its category menu). Auditoría's conciliación deliberately does NOT exclude it (cash-basis: savings do move liquidity), and budgets keep it (pay-yourself-first commitment device). Preserve this split when adding new gasto-based queries.
- `balance_general` — one row per month (`fecha` as `YYYY-MM` primary key) capturing `activos_liquidos`, `activos_fijos`, `pasivos_corto`, `pasivos_largo`; this is the source for the Auditoría tab's ratios

The old `habitos_lista` / `habitos_log` tables (simple habit + daily checkbox) were superseded by the Habit Game tables above; `database.py` no longer creates them, but they're left in place (unused) on any `data.db` that already had them.

**Tab module conventions** (`tabs/*.py`): each is a `ctk.CTkFrame` subclass with a `setup_ui()` builder called from `__init__`, plus mutating methods (`guardar_*`, `eliminar_*`) that write to SQLite and then call the tab's own refresh method to redraw. List views are rebuilt from scratch on every refresh (`for w in frame.winfo_children(): w.destroy()` then re-populate) rather than diffed.

**Charting**: tabs with graphs (`dashboard.py`, `balance_general.py`, `planeacion.py`, `impuestos_inversion.py`) embed matplotlib via `FigureCanvasTkAgg` into a dedicated `canvas_frame`, destroying and recreating the figure on every refresh. The dark theme palette is hardcoded per-chart (`#0f172a`/`#1e293b` backgrounds, `#10B981` green / `#EF4444` red / `#F59E0B` amber / `#A855F7` purple / `#3B82F6` blue as consistent semantic colors for gain/loss/warning/debt/neutral across tabs) — match these when adding new charts rather than introducing new colors.

**`dashboard.py`** is the most complex tab: a 3×3 matplotlib grid inside a `CTkScrollableFrame` (the figure is taller than the window). Row 0: cash-flow bars, SAT-deductible pie, and all-history accumulated wealth W(T) (cumsum over every period, not just the 8-period window the other charts use). Row 1: 6-month MSI projection, Pareto by category, linear-regression (`np.polyfit`, degree 1) expense forecast. Row 2: monthly expense VaR 95% (`μ+1.96σ`, always monthly regardless of the granularity selector), PMC/PMA (`ΔG/ΔI` month-over-month, skipping periods where income barely changed), and the "gasto hormiga" detector (grouped by lowercased `desc`, `HORMIGA_*` constants control the ≤$300-avg / ≥3-times / 90-day window, projected to annual cost). The Diario/Mensual/Anual selector only drives rows 0–1 via an `strftime` format string.

**`impuestos_inversion.py`** hardcodes the 2026 Mexican ISR marginal tax bracket table (Art. 152 LISR) as a matrix in `calcular_tasa_marginal_isr()` — update this table if tax brackets change for a new fiscal year, along with the module-level `UMA_DIARIA` constant (published by INEGI each January), `TOPES_COLEGIATURA` and `TARIFA_RESICO`. Deductions are filtered to the current calendar year and run through `aplicar_topes_deducciones()` (returns `(total, per-concept dict)`): per-concept caps first (lentes $2,500, colegiaturas per level, funerarios 1 UMA, PPR 10%/5 UMA, donativos 7%), then the Art. 151 general cap (15% of income or 5 annual UMA) applied only to concepts *inside* it — colegiaturas/PPR/donativos are outside (`FUERA_TOPE_GENERAL`). The `tipo_deduccion` strings must match `TIPOS_DEDUCCION` in `tabs/tesoreria.py`. "Saldo Estimado en Declaración Anual" = user-entered ISR retenido − ISR causado (can be a cargo, shown red); it is distinct from "Ahorro de ISR por Deducciones" (ISR without deductions − ISR with them). The RESICO comparator taxes only `FUENTES_RESICO` income (Freelance/Ventas — salary is not RESICO-eligible) at the flat `TARIFA_RESICO` bracket vs the Art. 152 tariff on the same base. `recalcular_metricas()` stashes everything in `self.ultimo_calculo`, which `construir_borrador_texto()` formats into the annual-declaration draft (the button recalculates first, so the stash is never stale).

**`habitos_agenda.py`** ("Habit Game: Fuerza, Natación & Agenda") merges habit tracking and the calendar into one weekly, accordion-collapsible grid (only "today" is expanded by default; `self.dias_expandidos` tracks per-weekday-name expand state across re-renders). Each day card CRUDs five independent things against its own date: gym exercises (checked off per ISO week via `entrenamiento_log`), swim sessions, user-defined recurring habits (`habitos_custom`, assignable to any subset of weekdays), to-dos (`tareas`), and timed events (`agenda`). XP is a derived value recomputed from raw log tables on every refresh (never stored) — see `calcular_xp_total()`; level = `total_xp // XP_POR_NIVEL`, and level maps to one of 6 ranks in `RANGOS` (Novato → Leyenda). The muscle "holograma" (`dibujar_holograma()`) is a hand-built anatomical diagram (pecs/delts/biceps/abs/quads/calves as `matplotlib.patches.Polygon`/`FancyBboxPatch`, left-side shapes mirrored via `_mirror()` for the right side) redrawn on an independent `self.after(150, ...)` tick loop — decoupled from the data-driven `actualizar()` refresh so the glow/scan-line pulse animates continuously without re-querying the DB every frame. Per-muscle brightness in `calcular_brillo_musculos()` blends an all-time historical component (never decays) with a rolling-4-week recency component (decays if you stop training that muscle) — tune via `UMBRAL_HISTORICO`/`UMBRAL_RECIENTE`. Overall hologram color follows the current rank (`RANGOS[i][3]`), not the muscle data.

**`inicio.py`** is the first tab (default on launch): a 0-100 financial-health score banner (weighted composite — liquidity ratio, leverage from the latest balance, conservative runway, savings rate, budget compliance; weights renormalize over available components), four summary cards (net across accounts, month consumption vs total budget, monthly debt commitment, conservative runway = liquid balances / VaR95 of monthly consumption), a 50/30/20 section (needs per `database.CATEGORIAS_NECESIDAD`, wants = the rest minus Ahorros, savings = income residual; uses the most recent month WITH income), an "Atención" alert list, active metas, and today's agenda/tareas. Pure reads, rebuilt on every `actualizar()`.

Treasury capture accepts an optional past date (`resolver_fecha()`: empty = today, validates YYYY-MM-DD). Cuentas/metas/recurrentes rows have ✏ edit dialogs (UPDATE in place; account rename guards UNIQUE). The bot's `resolver_cuenta()` matches exact > prefix > substring — don't regress to plain substring, "nu" must resolve to "Nu" not "Cajitas Nu"; `/pago monto origen destino` inserts a transferencia from Telegram.

**`planeacion.py`** hosts four things: MSI/interest-bearing debt CRUD (rate 0 = MSI, rate > 0 → French amortization for the mensualidad), the what-if simulator, the budget panel, and the credit-card payoff planner (`simular_pago_deuda()` simulates month-by-month interest accrual + priority-ordered payments; avalanche = rate-desc vs snowball = balance-asc; returns None when the monthly payment can't beat accrued interest; card rates persist to `cuentas.tasa_anual`). The whole tab is one scrollable page (`self.pagina`). The simulator's `correr_simulacion()` stores its computed category cap in `self.ultima_simulacion` and arms `btn_adoptar`, which persists it to `presupuestos` — that simulation→commitment→tracking loop is the point of the feature; don't sever it when refactoring. It imports `CATEGORIAS_GASTOS` from `tabs.tesoreria` (one-way import; don't create a cycle).

**`bot_listener.py`** is a standalone script (not imported by `main.py`, run as the `bot_listener.service` systemd unit — see Running above) that runs its own polling loop and writes directly to the same `gastos` table using a shorthand category-code parser (`v`, `c`, `t`, ... in `CATEGORIAS` dict) and `+f`/`+d` trailing flags for CFDI/deductible status. Keep its `CATEGORIAS` short-code dict and the category strings used elsewhere (`tabs/tesoreria.py`, `generar_mock.py`) in sync if categories change. It stores `message.date` (the Telegram server's original receive timestamp), not `datetime.now()`, as the expense's `fecha` — this matters because `infinity_polling()` processes any backlog on reconnect, and using "now" would misdate everything sent while the bot/network was down. Expense confirmations append the category's budget status (`linea_presupuesto()`); `/resumen` replies with all budgets + active debts; `/cuenta [nombre]` lists accounts or sets the default one (stored as `cuenta_default` in `bot_estado`), and an `@nombre` token anywhere in an expense message overrides it for that expense (substring match against `cuentas.nombre`, falls back to the default with a warning if unmatched). All command handlers must stay registered *before* the catch-all `procesar_gasto` handler — telebot dispatches in registration order. A daemon thread (`vigilante_diario`) sends proactive alerts (budgets ≥90%, debts with ≤1 payment left) once per day after 9:00, deduped across restarts via `bot_estado`. **Restart the service after editing this file** (`systemctl --user restart bot_listener.service`).

## Gotchas

- `config.py` is gitignored; a fresh clone needs it (copy `config.example.py`). `main.py` requires the MariaDB server to be reachable — otherwise it shows a connection-error dialog and exits. `init_db()` bootstraps the schema on an empty server, but expect an empty app until you migrate the legacy `data.db` (`migrar_a_mariadb.py`), capture data, or run `generar_mock.py`.
- `generar_mock.py` **TRUNCATEs** `ingresos`, `gastos`, and `deudas_msi` unconditionally before repopulating — and now it does so on the SHARED server, so it nukes those tables for every machine. Never run it against real data you want to keep.
- The legacy `data.db` (gitignored) may still sit in the repo root; nothing writes to it anymore. Don't delete it — it's the last-resort historical backup and the source for `migrar_a_mariadb.py`.
- The `Auditorias/` directory is gitignored and appears to hold ad-hoc monthly exported reports; it is not read or written by any code in this repo.
- This system needed the `noto-fonts-emoji` package installed (`sudo pacman -S noto-fonts-emoji && fc-cache -f`) for Tk to render emoji glyphs at all — without it every emoji shows as a tofu box. Separately, emoji typed with a trailing U+FE0F variation selector (e.g. copy-pasted "🏋️"/"🗑️") render as the emoji **plus** a stray tofu box for the selector itself on this font stack; strip the trailing `️` (use the bare codepoint, e.g. `"🏋"`/`"🗑"`) when adding new emoji to any tab.
