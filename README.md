# Financial_Tracker

Una plataforma avanzada de ingeniería financiera personal que cierra la brecha entre el simple registro de datos y el modelado económico riguroso. Diseñada para operar en la intersección de las finanzas cuantitativas, el cálculo, la microeconomía y los principios de la contabilidad de partida doble.

Este proyecto utiliza `customtkinter` para una interfaz gráfica de alto rendimiento, `sqlite3` para la persistencia analítica local, y el motor de `matplotlib` combinado con `numpy` para la renderización de modelos numéricos.

---

## Arquitectura Teórica y Componentes del Dashboard

A diferencia de los rastreadores de gastos tradicionales, **Financial_Tracker** modela al usuario como un agente microeconómico que busca optimizar su utilidad intertemporal mientras gestiona su liquidez y riesgo sistémico.

A continuación se detalla la fundamentación matemática, contable y microeconómica de cada uno de los módulos visuales implementados.

### 1. Flujos de Efectivo (Liquidez Histórica)
* **Descripción:** Gráfica de barras de doble eje que monitorea periódicamente los ingresos frente a las salidas de capital. Sirve como interfaz visual primaria para evaluar los umbrales de liquidez absoluta.
* **Modelo Matemático:** Siendo $I_t$ la suma de ingresos y $E_t$ la suma de gastos (egresos) en el periodo $t$, el flujo neto $F_t$ se define como:
  $$F_t = I_t - E_t = \sum_{i=1}^{n} I_i - \sum_{j=1}^{m} E_j$$
* **Marco Contable:** Refleja el *Estado de Flujos de Efectivo* bajo la base de caja. Aísla la liquidez operativa del agente antes de impactos de financiamiento.
* **Contexto Microeconómico:** Representa la frontera de restricción presupuestaria periódica. Monitorea si el agente opera en un régimen de superávit ($F_t > 0$) o si requiere acumulación de deuda ($F_t < 0$).

### 2. Escudo Fiscal LISR (Eficiencia Fiscal)
* **Descripción:** Desglose estructural que clasifica las salidas operativas basándose en sus atributos de deducibilidad fiscal.
* **Modelo Matemático:** Dada una base de gastos $E_{\text{total}}$, el coeficiente de escudo fiscal $\eta$ se expresa como:
  $$\eta = \frac{\sum E_{\text{deducible}}}{E_{\text{total}}}$$
  El ahorro real generado (Escudo Fiscal) bajo una tasa marginal de impuesto $\tau$ es:
  $$\text{Ahorro} = \tau \cdot \sum E_{\text{deducible}}$$
* **Marco Contable:** Optimización contable fiscal. Mapea conceptos permitidos bajo la Ley del Impuesto sobre la Renta (LISR) para disminuir la base gravable neta.
* **Contexto Microeconómico:** Minimiza las distorsiones del mercado. Los impuestos actúan como un costo exógeno; maximizar $\eta$ desplaza efectivamente la línea de presupuesto hacia afuera sin requerir mayor esfuerzo laboral.

### 3. Aceleración del Patrimonio ($dW/dt$)
* **Descripción:** Gráfica de líneas que representa la primera y segunda derivada de la riqueza respecto al tiempo, indicando la velocidad a la que cambia la acumulación de capital.
* **Modelo Matemático:** Si $W(t)$ es la riqueza neta en el tiempo $t$, su aproximación discreta de velocidad (primera derivada) es el flujo neto:
  $$\frac{dW}{dt} \approx \frac{\Delta W}{\Delta t} = W_t - W_{t-1} = F_t$$
  La gráfica muestra la *aceleración* o desaceleración de esta velocidad:
  $$\frac{d^2W}{dt^2} \approx \frac{F_t - F_{t-1}}{\Delta t}$$
* **Marco Contable:** Conecta el Estado de Resultados con el Balance General. Una velocidad positiva expande las Utilidades Retenidas dentro del Capital Contable.
* **Contexto Microeconómico:** Monitorea la trayectoria de la tasa de ahorro. Si la segunda derivada es negativa, el agente sufre de "inflación de estilo de vida", mostrando una compresión de márgenes sistémica.

### 4. Proyección de Pasivos y MSI (Deuda a 6 Meses)
* **Descripción:** Calendario de amortización que proyecta compromisos de efectivo obligatorios sobre un horizonte futuro, aislando la deuda sin intereses (MSI).
* **Modelo Matemático:** Sea $L_k$ el pago mensual del pasivo $k$, con meses totales $M_k$ y meses pagados $P_k$. El compromiso de caja $C(m)$ para un mes futuro $m$ utiliza una función indicadora:
  $$C(m) = \sum_{k=1}^{K} L_k \cdot \mathbb{I}_{\{M_k - P_k \ge m\}}$$
* **Marco Contable:** Gestión de capital de trabajo y calendario de Pasivos Circulantes para prevenir crisis de liquidez a corto plazo.
* **Contexto Microeconómico:** Teoría de elección intertemporal. Mapea cómo las decisiones de consumo pasadas restringen el ingreso discrecional futuro.

### 5. Pareto de Costos (Estructura de Consumo)
* **Descripción:** Análisis categórico ordenado diseñado para separar visualmente los pocos centros de costos vitales de los muchos triviales.
* **Modelo Matemático:** Los gastos se ordenan tal que $E_{(1)} \ge E_{(2)} \ge \dots \ge E_{(c)}$. La función de distribución acumulada es:
  $$Y_k = \frac{\sum_{i=1}^{k} E_{(i)}}{\sum_{j=1}^{c} E_{(j)}}$$
* **Marco Contable:** Contabilidad administrativa. Permite dirigir las estrategias de reducción de costos hacia las cuentas que ofrecen el mayor impacto en la utilidad neta.
* **Contexto Microeconómico:** Revela mapas de preferencias. Distingue los costos estructurales inelásticos (renta, educación) de las opciones discrecionales altamente elásticas.

### 6. Pronóstico de Gasto (Machine Learning - Regresión Lineal OLS)
* **Descripción:** Motor de inferencia predictiva que utiliza mínimos cuadrados ordinarios (OLS) para proyectar el comportamiento del gasto en el periodo $t+1$.
* **Modelo Matemático:** Dados los periodos $x$ y gastos $y$, se estiman los parámetros $(\beta_0, \beta_1)$ minimizando los residuos:
  $$\hat{y} = \beta_1 x + \beta_0$$
  $$\beta_1 = \frac{\sum (x_i - \bar{x})(y_i - \bar{y})}{\sum (x_i - \bar{x})^2}$$
* **Marco Contable:** Pronóstico financiero Pro-Forma. Establece la línea base necesaria para construir el presupuesto operativo del siguiente mes.
* **Contexto Microeconómico:** Modelos de expectativas racionales y suavización del consumo estacional.

---

### 7. Integral del Flujo de Efectivo (Patrimonio Acumulado)
* **Descripción:** Modelo de acumulación continua que mapea la riqueza total neta generada a partir del área bajo la curva del flujo de efectivo.
* **Modelo Matemático:** La función de riqueza acumulada $W(T)$, dado un capital inicial $W_0$, se define como la integral del flujo neto:
  $$W(T) = W_0 + \int_{0}^{T} (I(t) - G(t)) dt$$
  En el sistema discreto, esto se resuelve mediante integración numérica (suma acumulativa de Riemann):
  $$W_t = W_0 + \sum_{i=1}^{t} F_i$$
* **Marco Contable:** Representa la evolución real de los Activos Netos en el Balance General a través del tiempo.
* **Contexto Microeconómico:** Indica la trayectoria de acumulación a largo plazo. La pendiente general revela la salud estructural del motor económico del usuario.

### 8. Intervalos de Confianza y Value at Risk (VaR)
* **Descripción:** Módulo de modelado de riesgo que establece límites estadísticos y cuantifica la exposición a sobregiros estocásticos de gastos.
* **Modelo Matemático:** Asumiendo una distribución normal del gasto con media $\mu_G$ y desviación estándar $\sigma_G$, el Límite de Gasto Máximo (Value at Risk) a un 95% de confianza ($Z = 1.96$) es:
  $$\text{VaR}_{95\%} = \mu_G + 1.96 \cdot \sigma_G$$
* **Marco Contable:** Provisionamiento de contingencias. Determina matemáticamente el tamaño del fondo de emergencia requerido para evitar la insolvencia técnica.
* **Contexto Microeconómico:** Cuantifica la vulnerabilidad frente a choques macroeconómicos inesperados o fluctuaciones de consumo atípicas.

### 9. Propensión Marginal al Consumo (PMC) y al Ahorro (PMA)
* **Descripción:** Métrica de economía conductual que evalúa cómo los cambios incrementales en los ingresos afectan el consumo frente al ahorro.
* **Modelo Matemático:** Calculado como derivadas discretas del consumo ($G$) y el ingreso ($I$):
  $$\text{PMC} = \frac{\Delta G}{\Delta I} = \frac{G_t - G_{t-1}}{I_t - I_{t-1}}$$
  Por identidad macroeconómica:
  $$\text{PMA} = 1 - \text{PMC}$$
* **Marco Contable:** Análisis de apalancamiento operativo personal. Evalúa la eficiencia de conversión entre ingresos brutos y capital retenido.
* **Contexto Microeconómico:** Basado en la Función de Consumo Keynesiana. Una PMA alta asegura que los aumentos de sueldo se destinen a la creación de riqueza y no sean absorbidos por la inflación de estilo de vida.

---
*Diseñado bajo paradigmas de ingeniería transdisciplinaria para la máxima optimización de capital.*

---

## Novedades: Presupuestos, Análisis de Riesgo, Fiscal Avanzado y Cuentas

### Presupuestos por categoría (ciclo conductual completo)

- **CRUD de límites mensuales** en la pestaña Planeación, con semáforo de consumo (verde <80%, ámbar 80–100%, rojo >100%) calculado contra el gasto real del mes.
- **"Adoptar como presupuesto"**: el simulador What-If ya no solo grafica el escenario — su límite calculado se convierte en presupuesto persistido con un clic (simulación → compromiso → seguimiento).
- **Aviso en el momento de captura**: al registrar un gasto en Tesorería (o por Telegram), si la categoría llega al 80% o rebasa su límite, recibes la alerta ahí mismo.

### Dashboard ampliado a 3×3 (secciones 7–9 del marco teórico, ya implementadas)

- **Patrimonio Acumulado W(T)** — la integral del flujo sobre toda la historia (reemplaza la gráfica dW/dt, que duplicaba la información de los flujos).
- **VaR 95% del gasto mensual** (μ + 1.96σ) con líneas de referencia — la base estadística para dimensionar el fondo de emergencia contra el gasto *adverso*, no el promedio.
- **PMC/PMA** — propensión marginal al consumo/ahorro mes a mes (ΔG/ΔI), detector de inflación de estilo de vida.
- **Detector de gasto hormiga** — compras pequeñas (≤$300) y recurrentes (≥3 veces en 90 días) proyectadas a costo anual.

### Fiscal avanzado

- **Comparador RESICO vs Régimen General**: aplica la tarifa RESICO PF (1%–2.5%, Art. 113-E) a tus ingresos de Freelance/Ventas del año y la compara contra el Art. 152, con validación de elegibilidad (≤$3.5M; el salario no tributa en RESICO).
- **Borrador de Declaración Anual**: reporte consolidado con ingresos por fuente, deducciones capturadas → aplicables (con topes por concepto marcados), base gravable, ISR causado vs retenido y saldo a favor/cargo.
- **Runway conservador**: meses de supervivencia calculados contra el gasto VaR 95%, además del promedio.

### Cuentas con saldo real

- Alta de cuentas (Efectivo/Débito/Crédito/Inversión) con saldo inicial; cada ingreso/gasto puede asignarse a una cuenta y el saldo actual se **deriva** de los movimientos (saldo inicial + entradas − salidas).
- La Auditoría Patrimonial gana la sección [4]: contrasta la liquidez según tus cuentas contra los activos líquidos declarados en el Balance General.

### Bot de Telegram con alertas

- Cada gasto capturado responde con el estado del presupuesto de su categoría (✅/⚠️/🚨).
- Comando `/resumen`: semáforo de todos los presupuestos + deudas activas.
- **Vigilante diario**: una vez al día (después de las 9:00) el bot te avisa proactivamente de presupuestos al ≥90% y deudas por liquidar, sin duplicados aunque el servicio se reinicie.

---

## Novedades anteriores: Habit Game, Tesorería y Bot de Telegram

Más allá del dashboard financiero original, el proyecto incorpora un sistema de hábitos gamificado y mejoras operativas al bot de captura:

### Habit Game: Fuerza, Natación & Agenda

La pestaña "Hábitos & Agenda" fusiona entrenamiento, natación, hábitos personalizados, tareas y eventos en **una sola cuadrícula semanal** (Lunes–Domingo):

- **Split de fuerza a 5 días** (Push/Pull/Legs/Upper/Lower por defecto, reasignable por día) con checklist de ejercicios editable (crear, renombrar, eliminar).
- **Natación** semanal con registro de distancia por sesión.
- **Hábitos personalizados**: nombre, categoría y qué días de la semana aplican.
- **Tareas** (checkbox, sin hora) y **eventos** (con hora) por fecha.
- Tarjetas de día colapsables (acordeón) — solo hoy se expande por defecto, el resto se resume en una línea, para minimizar el scroll.
- Navegación ◀ / ▶ para ver o editar cualquier semana pasada o futura.
- **Sistema de XP, nivel y rango** (Novato → Aprendiz → Atleta → Competidor → Élite → Leyenda) derivado del historial de entrenamiento, natación y hábitos.
- **Holograma muscular animado**: diagrama anatómico (pectorales, deltoides, bíceps, abdomen, cuádriceps, pantorrillas) que brilla más en cada zona según qué tan constante ha sido el entrenamiento — combina un componente histórico acumulado (nunca baja) con un boost de las últimas 4 semanas (decae si se deja de entrenar esa zona). El color general del holograma evoluciona con el rango.

### Tesorería

Ahora permite editar la fecha de ingresos y gastos ya capturados (útil para corregir capturas retrasadas), además del registro y borrado existentes.

### Bot de Telegram

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
