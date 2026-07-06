# Arch Productivity Hub

Aplicación de escritorio (customtkinter) para finanzas personales y hábitos, pensada para un solo usuario en México. Modela balances bajo NIF B-6, deducciones SAT/LISR, deudas a meses sin intereses (MSI), y ahora también un sistema de hábitos "gamificado" (Habit Game) integrado con la agenda. Todo se guarda en un archivo SQLite local (`data.db`); un bot de Telegram permite capturar gastos desde el celular.

## Módulos

- **Hábitos & Agenda — Habit Game** (ver detalle abajo)
- **Tesorería** — registro de ingresos/gastos, con flags de CFDI y deducibilidad, y edición de fecha por transacción
- **Planeación (MSI)** — control de deudas a meses sin intereses y simulador "what-if" de reducción de gasto por categoría
- **Impuestos e Inversión** — tasa marginal ISR (Art. 152 LISR), deducciones personales, runway de liquidez
- **Balance General** — activos/pasivos mensuales (NIF B-6), patrimonio neto, comparativa CETES vs. inflación
- **Dashboard Financiero** — flujos de efectivo, escudo fiscal, velocidad de patrimonio, pronóstico de gasto (regresión lineal)
- **Auditoría Patrimonial** — razón circulante y apalancamiento con dictamen automático

## Habit Game: Fuerza, Natación & Agenda

La pestaña "Hábitos & Agenda" combina entrenamiento, natación, hábitos personalizados, tareas y eventos en **una sola cuadrícula semanal** (Lunes–Domingo):

- **Split de fuerza a 5 días** (Push/Pull/Legs/Upper/Lower por defecto, reasignable por día) con checklist de ejercicios editable (crear, renombrar, eliminar).
- **Natación** semanal con registro de distancia por sesión.
- **Hábitos personalizados**: defines nombre, categoría y qué días de la semana aplican.
- **Tareas** (checkbox, sin hora) y **eventos** (con hora) por fecha.
- Cada tarjeta de día es colapsable (acordeón) — solo el día de hoy se expande por defecto, mostrando el resto como un resumen de una línea, para minimizar el scroll.
- Navegación ◀ / ▶ para ver o editar cualquier semana pasada o futura.
- **Sistema de XP, nivel y rango** (Novato → Aprendiz → Atleta → Competidor → Élite → Leyenda) derivado de tu historial de entrenamiento, natación y hábitos.
- **Holograma muscular animado**: diagrama anatómico (pectorales, deltoides, bíceps, abdomen, cuádriceps, pantorrillas) que brilla más en cada zona según qué tan constante has sido entrenándola — combina un componente histórico acumulado (nunca baja) con un boost de las últimas 4 semanas (si dejas de entrenar una zona, se atenúa). El color general del holograma evoluciona con tu rango.

## Bot de Telegram

`bot_listener.py` recibe mensajes con el formato `monto categoría descripción [+f] [+d]` (atajos de categoría en `/help`, `+f` = con factura CFDI, `+d` = deducible) y los guarda en la misma base de datos. Usa la fecha real de envío del mensaje (no la fecha de proceso), así que si el bot estuvo caído, los gastos acumulados se registran con su fecha correcta al reconectar.

Corre como servicio de usuario de **systemd** (`systemd/bot_listener.service`) con reinicio automático (`Restart=always`), para no depender de arrancarlo manualmente tras un corte de internet o un reinicio:

```bash
systemctl --user status bot_listener.service
journalctl --user -u bot_listener.service -f
systemctl --user restart bot_listener.service
```

## Instalación y ejecución

Requiere Python 3 y:

```bash
pip install customtkinter matplotlib numpy tkcalendar pyTelegramBotAPI
```

En Linux, además se necesita una fuente de emoji para que los íconos se rendericen correctamente (ej. en Arch: `sudo pacman -S noto-fonts-emoji && fc-cache -f`).

```bash
python main.py            # App de escritorio
python bot_listener.py     # Bot de Telegram (o instalar el servicio systemd de arriba)
```

`config.py` (no versionado) debe definir tus credenciales del bot:

```python
TELEGRAM_BOT_TOKEN = "..."
MI_CHAT_ID = 123456789
```

No hay suite de pruebas ni build — la app se verifica corriéndola directamente.
