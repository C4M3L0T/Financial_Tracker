import customtkinter as ctk
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime
from database import CATEGORIA_AHORRO

# UMA diaria vigente — actualizar cada enero con el valor oficial del INEGI
UMA_DIARIA = 117.31
UMA_ANUAL = UMA_DIARIA * 365

# Topes anuales del decreto de colegiaturas (por nivel educativo).
# Las llaves deben coincidir con TIPOS_DEDUCCION de tabs/tesoreria.py.
TOPES_COLEGIATURA = {
    "Colegiatura Preescolar": 14200.0,
    "Colegiatura Primaria": 12900.0,
    "Colegiatura Secundaria": 19900.0,
    "Colegiatura Prof. Técnico": 17100.0,
    "Colegiatura Bachillerato": 24500.0,
}

# Conceptos con tope propio que NO computan dentro del tope general del Art. 151
# (último párrafo: excluye donativos y aportaciones de retiro; colegiaturas van por decreto aparte)
FUERA_TOPE_GENERAL = set(TOPES_COLEGIATURA) | {"Retiro (PPR/AFORE)", "Donativos"}

# Tarifa anual RESICO Personas Físicas (Art. 113-E LISR): tasa sobre ingreso BRUTO,
# sin deducción alguna. Solo aplica a actividad empresarial/profesional/arrendamiento
# (los ingresos por salario NO tributan en RESICO). Elegibilidad: ≤ $3.5M anuales.
TARIFA_RESICO = [
    (300000.0, 0.010),
    (600000.0, 0.011),
    (1000000.0, 0.015),
    (2500000.0, 0.020),
    (3500000.0, 0.025),
]
FUENTES_RESICO = ("Freelance", "Ventas")
LIMITE_RESICO = 3500000.0


class ImpuestosInversionTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        # Asegurar expansión vertical uniforme de ambas columnas
        self.grid_rowconfigure(0, weight=1)
        self.setup_ui()
        self.recalcular_metricas()

    def setup_ui(self):
        # =========================================================
        # PANEL IZQUIERDO: ARBITRAJE FISCAL (SAT - LISR)
        # =========================================================
        self.frame_sat = ctk.CTkFrame(self)
        self.frame_sat.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.frame_sat, text="Escudo Fiscal Anual (Art. 151 LISR)", font=("Urbanist", 18, "bold"), text_color="#10B981").pack(pady=15)
        
        # Input de Ingresos para cálculo de Tasa Marginal
        ctk.CTkLabel(self.frame_sat, text="Ingreso Anual Bruto Estimado ($ MXN):", font=("Urbanist", 12)).pack(pady=(5,0), padx=20, anchor="w")
        self.e_ingreso_anual = ctk.CTkEntry(self.frame_sat, placeholder_text="ej: 350000")
        self.e_ingreso_anual.insert(0, "300000")
        self.e_ingreso_anual.pack(pady=5, padx=20, fill="x")

        # ISR ya retenido por patrón/clientes: sin este dato no existe "saldo a favor", solo ahorro fiscal
        ctk.CTkLabel(self.frame_sat, text="ISR Retenido en el año ($ MXN, según tus CFDI de nómina/honorarios):", font=("Urbanist", 12)).pack(pady=(5,0), padx=20, anchor="w")
        self.e_isr_retenido = ctk.CTkEntry(self.frame_sat, placeholder_text="ej: 45000 (0 si nadie te retiene)")
        self.e_isr_retenido.pack(pady=5, padx=20, fill="x")

        ctk.CTkButton(self.frame_sat, text="Calcular Retorno SAT", fg_color="#10B981", hover_color="#059669", font=("Urbanist", 12, "bold"), command=self.recalcular_metricas).pack(pady=10, padx=20, fill="x")

        # Tarjetas de Métricas Fiscales
        self.box_deducible = self.crear_tarjeta_metrica(self.frame_sat, "Deducciones Aplicables del Año (tras topes SAT)", "$0.00", "#34D399")
        self.box_tasa = self.crear_tarjeta_metrica(self.frame_sat, "Tu Tasa Marginal de ISR", "0.00%", "#60A5FA")
        self.box_ahorro = self.crear_tarjeta_metrica(self.frame_sat, "Ahorro de ISR por Deducciones", "$0.00", "#FBBF24")
        self.box_saldo = self.crear_tarjeta_metrica(self.frame_sat, "Saldo Estimado en Declaración Anual (retenido − causado)", "$0.00", "#94A3B8")
        self.box_resico = self.crear_tarjeta_metrica(self.frame_sat, "Comparador RESICO (ingresos Freelance/Ventas del año)", "—", "#94A3B8")

        ctk.CTkButton(self.frame_sat, text="📄 Generar Borrador de Declaración Anual",
                      fg_color="#334155", hover_color="#475569", font=("Urbanist", 12, "bold"),
                      command=self.abrir_borrador_declaracion).pack(pady=(10, 5), padx=20, fill="x")

        # NUEVO: Guía de Deducciones Personales Autorizadas (SAT)
        ctk.CTkLabel(self.frame_sat, text="📋 Catálogo Normativo de Deducciones", font=("Urbanist", 13, "bold"), text_color="#34D399").pack(pady=(15, 2), padx=20, anchor="w")
        
        txt_guia_fiscal = (
            "• 🩺 SALUD:\n"
            "  - Honorarios médicos, dentales, psicología y nutrición.\n"
            "  - Gastos hospitalarios, análisis clínicos y prótesis.\n"
            "  - Lentes ópticos graduados (deducible hasta $2,500 MXN).\n"
            "  - Primas de seguros de gastos médicos mayores.\n"
            "  *Nota: Medicinas compradas en farmacias NO entran; solo si están dentro de la factura del hospital.*\n\n"
            "• 🎓 EDUCACIÓN (Límites Anuales de Colegiaturas):\n"
            "  - Preescolar: $14,200 MXN  |  - Primaria: $12,900 MXN\n"
            "  - Secundaria: $19,900 MXN |  - Profesional Técnico: $17,100 MXN\n"
            "  - Bachillerato o Equivalente: $24,500 MXN\n"
            "  - Transporte escolar (únicamente si es obligatorio por zona).\n\n"
            "• 🏠 VIVIENDA Y RETIRO:\n"
            "  - Intereses REALES devengados de créditos hipotecarios (Infonavit, Fovissste o instituciones bancarias).\n"
            "  - Aportaciones voluntarias a tu AFORE o a un Plan Personal de Retiro (PPR) (hasta el 10% de tus ingresos anuales).\n\n"
            "• ⚰️ OTROS:\n"
            "  - Gastos funerarios del cónyuge, padres, abuelos, hijos o nietos (tope de 1 UMA anual).\n\n"
            "⚠️ REGLA DE ORO DEL SAT (BANCARIZACIÓN):\n"
            "Todo gasto médico o educativo debe liquidarse estrictamente mediante tarjeta de crédito/débito, transferencia electrónica o cheque. ¡Los pagos en EFECTIVO invalidan la deducción de inmediato ante el SAT, aun si tienes el CFDI facturado! El uso de CFDI debe ser del bloque 'D01' al 'D10'."
        )
        
        self.txt_fiscal_box = ctk.CTkTextbox(self.frame_sat, font=("Urbanist", 11), fg_color="#1E293B", text_color="#94A3B8", wrap="word", height=150)
        self.txt_fiscal_box.pack(pady=(0, 10), padx=20, fill="both", expand=True)
        self.txt_fiscal_box.insert("1.0", txt_guia_fiscal)
        self.txt_fiscal_box.configure(state="disabled") # De solo lectura para el usuario

        # =========================================================
        # PANEL DERECHO: SOLVENCIA Y RUNWAY MICROECONÓMICO
        # =========================================================
        self.frame_solvencia = ctk.CTkFrame(self)
        self.frame_solvencia.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.frame_solvencia, text="Índice de Solvencia Dinámica", font=("Urbanist", 18, "bold"), text_color="#3B82F6").pack(pady=15)
        
        # Input de Capital Líquido Actual (Bancos, Efectivo, Cetes)
        ctk.CTkLabel(self.frame_solvencia, text="Liquidez Total Disponible (Efectivo/Cetes):", font=("Urbanist", 12)).pack(pady=(5,0), padx=20, anchor="w")
        self.e_liquidez = ctk.CTkEntry(self.frame_solvencia, placeholder_text="ej: 50000")
        self.e_liquidez.insert(0, "45000")
        self.e_liquidez.pack(pady=5, padx=20, fill="x")
        
        ctk.CTkButton(self.frame_solvencia, text="Calcular Runway de Supervivencia", fg_color="#3B82F6", hover_color="#2563EB", font=("Urbanist", 12, "bold"), command=self.recalcular_metricas).pack(pady=10, padx=20, fill="x")
        
        # Tarjetas de Solvencia
        self.box_gasto_medio = self.crear_tarjeta_metrica(self.frame_solvencia, "Gasto Medio Mensual Histórico", "$0.00", "#94A3B8")
        self.box_runway = self.crear_tarjeta_metrica(self.frame_solvencia, "Meses de Runway (Fondo de Emergencia)", "0.0 meses", "#F43F5E")
        self.box_runway_var = self.crear_tarjeta_metrica(self.frame_solvencia, "Runway Conservador (gasto adverso VaR 95%)", "0.0 meses", "#F59E0B")
        
        # Contenedor para gráfica de salud financiera
        self.canvas_frame = ctk.CTkFrame(self.frame_solvencia, fg_color="transparent")
        self.canvas_frame.pack(pady=10, padx=20, fill="both", expand=True)

    def crear_tarjeta_metrica(self, master, titulo, valor_defecto, color_valor):
        frame = ctk.CTkFrame(master, fg_color="#1E293B", height=70)
        frame.pack(pady=5, padx=20, fill="x")
        lbl_tit = ctk.CTkLabel(frame, text=titulo, font=("Urbanist", 11), text_color="#94A3B8")
        lbl_tit.pack(pady=(5, 2), padx=10, anchor="w")
        lbl_val = ctk.CTkLabel(frame, text=valor_defecto, font=("Urbanist", 18, "bold"), text_color=color_valor)
        lbl_val.pack(pady=(0, 5), padx=10, anchor="w")
        return lbl_val

    # =========================================================
    # MOTORES MATEMÁTICOS Y MATRICIALES
    # =========================================================
    def calcular_tasa_marginal_isr(self, ingreso_anual):
        """Aproximación matricial de la tarifa del Art. 152 LISR mexicano para 2026"""
        # El primer renglón de la tarifa arranca en $0.01: con ingreso 0 (o negativo)
        # el filtro no devolvería filas y el [-1] tronaría con IndexError
        ingreso_anual = max(ingreso_anual, 0.01)
        tablas_isr = np.array([
            [0.01, 0.00, 0.0192],
            [8952.50, 171.86, 0.0640],
            [75984.10, 4461.93, 0.1088],
            [133536.90, 10730.20, 0.1600],
            [155229.80, 14201.07, 0.1792],
            [185859.40, 19687.12, 0.2136],
            [374837.81, 60013.60, 0.2352],
            [589885.51, 110593.43, 0.3000],
            [1126569.71, 271618.39, 0.3200],
            [1502092.81, 391785.49, 0.3400],
            [3004185.51, 902497.02, 0.3500]
        ])
        
        fila = tablas_isr[tablas_isr[:, 0] <= ingreso_anual][-1]
        lim_inf, cuota_fija, porcentaje = fila[0], fila[1], fila[2]

        excedente = ingreso_anual - lim_inf
        isr_determinado = cuota_fija + (excedente * porcentaje)

        return porcentaje, isr_determinado, tablas_isr

    def calcular_isr_art152(self, base_gravable):
        """ISR anual del régimen general para una base gravable arbitraria."""
        _, isr, _ = self.calcular_tasa_marginal_isr(base_gravable)
        return isr

    def calcular_isr_resico(self, ingreso_bruto):
        """ISR anual RESICO PF: tasa por tramo sobre el ingreso bruto, sin deducciones.
        Devuelve (isr, tasa) o (None, None) si el ingreso excede el límite del régimen."""
        if ingreso_bruto > LIMITE_RESICO:
            return None, None
        for tope, tasa in TARIFA_RESICO:
            if ingreso_bruto <= tope:
                return ingreso_bruto * tasa, tasa
        return None, None

    def aplicar_topes_deducciones(self, por_tipo, ingreso):
        """Aplica los sub-topes por concepto del Art. 151 LISR y el decreto de
        colegiaturas, y después el tope general (15% de ingresos o 5 UMA anuales)
        solo a los conceptos que sí computan dentro de él."""
        tope_5uma = 5 * UMA_ANUAL
        aplicadas = {}
        for tipo, monto in por_tipo.items():
            if tipo == "Lentes ópticos":
                aplicadas[tipo] = min(monto, 2500.0)
            elif tipo in TOPES_COLEGIATURA:
                aplicadas[tipo] = min(monto, TOPES_COLEGIATURA[tipo])
            elif tipo == "Funerarios":
                aplicadas[tipo] = min(monto, UMA_ANUAL)
            elif tipo == "Retiro (PPR/AFORE)":
                aplicadas[tipo] = min(monto, ingreso * 0.10, tope_5uma)
            elif tipo == "Donativos":
                aplicadas[tipo] = min(monto, ingreso * 0.07)
            else:
                aplicadas[tipo] = monto

        suma_tope_general = sum(m for t, m in aplicadas.items() if t not in FUERA_TOPE_GENERAL)
        suma_tope_propio = sum(m for t, m in aplicadas.items() if t in FUERA_TOPE_GENERAL)
        tope_general = min(ingreso * 0.15, tope_5uma)
        total = min(suma_tope_general, tope_general) + suma_tope_propio
        return total, aplicadas

    def recalcular_metricas(self):
        # --- PARTE 1: MODELADO FISCAL ---
        try:
            ingreso = float(self.e_ingreso_anual.get())
        except ValueError:
            ingreso = 300000.0
        try:
            isr_retenido = float(self.e_isr_retenido.get())
        except ValueError:
            isr_retenido = 0.0

        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()

        # Solo el ejercicio fiscal en curso: la declaración anual es por año calendario
        anio_fiscal = str(datetime.now().year)
        cursor.execute("""
            SELECT COALESCE(tipo_deduccion, 'Otro (tope general)'), SUM(monto)
            FROM gastos
            WHERE es_deducible = 1 AND con_factura = 1 AND strftime('%Y', fecha) = ?
            GROUP BY COALESCE(tipo_deduccion, 'Otro (tope general)')
        """, (anio_fiscal,))
        por_tipo = dict(cursor.fetchall())
        deducciones_capturadas = sum(por_tipo.values())
        deducciones_aplicables, aplicadas_detalle = self.aplicar_topes_deducciones(por_tipo, ingreso)

        tasa_m, isr_sin_deducciones, tablas = self.calcular_tasa_marginal_isr(ingreso)

        base_gravable_optimizada = max(0.01, ingreso - deducciones_aplicables)
        fila_opt = tablas[tablas[:, 0] <= base_gravable_optimizada][-1]
        isr_causado = fila_opt[1] + ((base_gravable_optimizada - fila_opt[0]) * fila_opt[2])

        # Ahorro fiscal: cuánto ISR dejan de causarte las deducciones
        ahorro_fiscal = max(0.0, isr_sin_deducciones - isr_causado)
        # Saldo real de la declaración: lo que ya te retuvieron vs. lo que causaste
        saldo_declaracion = isr_retenido - isr_causado

        self.box_deducible.configure(
            text=f"${deducciones_aplicables:,.2f} de ${deducciones_capturadas:,.2f} capturadas ({anio_fiscal})")
        self.box_tasa.configure(text=f"{tasa_m * 100:.2f}%")
        self.box_ahorro.configure(text=f"${ahorro_fiscal:,.2f}")
        if saldo_declaracion >= 0:
            self.box_saldo.configure(text=f"A FAVOR: ${saldo_declaracion:,.2f} (devolución)", text_color="#10B981")
        else:
            self.box_saldo.configure(text=f"A CARGO: ${-saldo_declaracion:,.2f} (a pagar al SAT)", text_color="#EF4444")

        # --- COMPARADOR RESICO vs RÉGIMEN GENERAL ---
        # Solo el ingreso de actividad empresarial/profesional es elegible; el salario no
        marcadores = ",".join("?" * len(FUENTES_RESICO))
        cursor.execute(f"""
            SELECT COALESCE(SUM(monto), 0) FROM ingresos
            WHERE fuente IN ({marcadores}) AND strftime('%Y', fecha) = ?
        """, (*FUENTES_RESICO, anio_fiscal))
        ingreso_resico = cursor.fetchone()[0]

        cursor.execute("SELECT fuente, COALESCE(SUM(monto),0) FROM ingresos WHERE strftime('%Y', fecha)=? GROUP BY fuente", (anio_fiscal,))
        ingresos_por_fuente = dict(cursor.fetchall())

        if ingreso_resico <= 0:
            self.box_resico.configure(text="Sin ingresos Freelance/Ventas este año", text_color="#94A3B8")
            resico_info = None
        else:
            isr_resico, tasa_resico = self.calcular_isr_resico(ingreso_resico)
            if isr_resico is None:
                self.box_resico.configure(text=f"No elegible: ingresos > ${LIMITE_RESICO:,.0f}", text_color="#EF4444")
                resico_info = None
            else:
                isr_general_actividad = self.calcular_isr_art152(ingreso_resico)
                diferencia = isr_general_actividad - isr_resico
                resico_info = (ingreso_resico, isr_resico, tasa_resico, isr_general_actividad, diferencia)
                if diferencia > 0:
                    self.box_resico.configure(
                        text=f"RESICO ${isr_resico:,.0f} vs General ${isr_general_actividad:,.0f} → ahorras ${diferencia:,.0f}",
                        text_color="#10B981")
                else:
                    self.box_resico.configure(
                        text=f"General ${isr_general_actividad:,.0f} vs RESICO ${isr_resico:,.0f} → conviene General",
                        text_color="#F59E0B")

        # Insumos para el borrador de la declaración anual
        self.ultimo_calculo = {
            "anio": anio_fiscal,
            "ingreso": ingreso,
            "ingresos_por_fuente": ingresos_por_fuente,
            "por_tipo": por_tipo,
            "aplicadas": aplicadas_detalle,
            "capturadas": deducciones_capturadas,
            "aplicables": deducciones_aplicables,
            "base_gravable": base_gravable_optimizada,
            "tasa_marginal": tasa_m,
            "isr_causado": isr_causado,
            "isr_retenido": isr_retenido,
            "saldo": saldo_declaracion,
            "ahorro": ahorro_fiscal,
            "resico": resico_info,
        }

        # --- PARTE 2: ANÁLISIS DE RUNWAY MICROECONÓMICO ---
        try:
            liquidez = float(self.e_liquidez.get())
        except ValueError:
            liquidez = 0.0
            
        # Ordenar por el periodo agrupado: ORDER BY fecha en una query agrupada
        # toma una fecha arbitraria de cada grupo y puede traer meses equivocados
        cursor.execute("""
            SELECT strftime('%Y-%m', fecha) AS periodo, SUM(monto) FROM gastos
            WHERE categoria != ?
            GROUP BY periodo
            ORDER BY periodo DESC LIMIT 6
        """, (CATEGORIA_AHORRO,))
        gastos_mensuales = [row[1] for row in cursor.fetchall()]
        conn.close()
        
        gasto_medio = np.mean(gastos_mensuales) if gastos_mensuales else 1.0
        runway = liquidez / gasto_medio if gasto_medio > 0 else 0.0

        # Fondo de emergencia serio: dimensionar contra el gasto ADVERSO (VaR 95%), no el típico
        sigma = float(np.std(gastos_mensuales)) if len(gastos_mensuales) >= 2 else 0.0
        gasto_var95 = gasto_medio + 1.96 * sigma
        runway_conservador = liquidez / gasto_var95 if gasto_var95 > 0 else 0.0

        self.box_gasto_medio.configure(text=f"${gasto_medio:,.2f}/mes")
        self.box_runway.configure(text=f"{runway:.1f} meses")
        self.box_runway_var.configure(text=f"{runway_conservador:.1f} meses (gasto adverso: ${gasto_var95:,.0f}/mes)")
        
        if runway < 3.0: self.box_runway.configure(text_color="#EF4444")     
        elif runway < 6.0: self.box_runway.configure(text_color="#F59E0B")   
        else: self.box_runway.configure(text_color="#10B981")                

        self.renderizar_grafico_solvencia(runway)

    # =========================================================
    # BORRADOR DE DECLARACIÓN ANUAL (consolidado informativo)
    # =========================================================
    def construir_borrador_texto(self):
        c = self.ultimo_calculo
        L = []
        L.append(f"=== BORRADOR DECLARACIÓN ANUAL — EJERCICIO {c['anio']} ===")
        L.append("(Estimación informativa; valida contra el visor de nómina")
        L.append(" y los CFDI reales en el portal del SAT)")
        L.append("=" * 52)
        L.append("")
        L.append("[1] INGRESOS DEL EJERCICIO (capturados en Tesorería)")
        if c["ingresos_por_fuente"]:
            for fuente, monto in sorted(c["ingresos_por_fuente"].items()):
                L.append(f"    {fuente:<22} ${monto:>14,.2f}")
            L.append(f"    {'TOTAL CAPTURADO':<22} ${sum(c['ingresos_por_fuente'].values()):>14,.2f}")
        else:
            L.append("    (sin ingresos capturados este año)")
        L.append(f"    Ingreso bruto declarado (input): ${c['ingreso']:,.2f}")
        L.append("")
        L.append("[2] DEDUCCIONES PERSONALES (capturado → aplicable)")
        if c["por_tipo"]:
            for tipo, monto in sorted(c["por_tipo"].items()):
                aplicado = c["aplicadas"].get(tipo, 0.0)
                marca = "" if abs(aplicado - monto) < 0.01 else "  [topado]"
                L.append(f"    {tipo[:28]:<28} ${monto:>11,.2f} → ${aplicado:>11,.2f}{marca}")
        else:
            L.append("    (sin gastos deducibles con CFDI este año)")
        L.append(f"    {'TOTAL':<28} ${c['capturadas']:>11,.2f} → ${c['aplicables']:>11,.2f}")
        L.append("")
        L.append("[3] DETERMINACIÓN DEL ISR")
        L.append(f"    Base gravable:        ${c['base_gravable']:>14,.2f}")
        L.append(f"    Tasa marginal:        {c['tasa_marginal']*100:>13.2f}%")
        L.append(f"    ISR causado:          ${c['isr_causado']:>14,.2f}")
        L.append(f"    ISR retenido:         ${c['isr_retenido']:>14,.2f}")
        L.append(f"    Ahorro por deducciones: ${c['ahorro']:>12,.2f}")
        L.append("")
        if c["saldo"] >= 0:
            L.append(f">>> SALDO A FAVOR: ${c['saldo']:,.2f} (solicitable en devolución)")
        else:
            L.append(f">>> SALDO A CARGO: ${-c['saldo']:,.2f} (a pagar; puede diferirse en parcialidades)")
        L.append("")
        L.append("[4] NOTA RESICO")
        if c["resico"]:
            ing_r, isr_r, tasa_r, isr_g, dif = c["resico"]
            L.append(f"    Ingreso elegible ({'+'.join(FUENTES_RESICO)}): ${ing_r:,.2f}")
            L.append(f"    ISR en RESICO ({tasa_r*100:.1f}%): ${isr_r:,.2f}  vs  Régimen general: ${isr_g:,.2f}")
            if dif > 0:
                L.append(f"    RESICO te ahorraría ${dif:,.2f}, pero pierdes TODAS las deducciones")
                L.append("    personales sobre ese ingreso. El aviso de cambio de régimen se")
                L.append("    presenta al SAT en enero del siguiente ejercicio.")
            else:
                L.append("    El régimen general resulta igual o mejor con tus números actuales.")
        else:
            L.append("    Sin ingresos de actividad empresarial elegibles (o exceden el límite).")
        return "\n".join(L)

    def abrir_borrador_declaracion(self):
        self.recalcular_metricas()
        texto = self.construir_borrador_texto()

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Borrador Declaración Anual {self.ultimo_calculo['anio']}")
        dialog.geometry("640x560")
        dialog.transient(self)

        caja = ctk.CTkTextbox(dialog, font=("Courier New", 12), fg_color="#0F172A", text_color="#E2E8F0")
        caja.pack(fill="both", expand=True, padx=15, pady=15)
        caja.insert("1.0", texto)
        caja.configure(state="disabled")

    def renderizar_grafico_solvencia(self, runway_actual):
        for w in self.canvas_frame.winfo_children(): w.destroy()
        
        fig, ax = plt.subplots(figsize=(4, 2), dpi=90)
        fig.patch.set_facecolor('#0f172a')
        ax.set_facecolor('#0f172a')
        
        categorias = ['Tu Runway', 'Mínimo Corp.', 'Ideal Econ.']
        valores = [runway_actual, 3.0, 6.0]
        colores = ['#F43F5E' if runway_actual < 3 else '#3B82F6', '#64748B', '#10B981']
        
        bars = ax.barh(categorias, valores, color=colores, height=0.5)
        ax.tick_params(colors='white', labelsize=9)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#334155')
        ax.spines['left'].set_color('#334155')
        
        for bar in bars:
            width = bar.get_width()
            ax.text(width + 0.2, bar.get_y() + bar.get_height()/2, f'{width:.1f}m', 
                    va='center', ha='left', color='white', fontsize=8, fontweight='bold')
                    
        ax.set_xlim(0, max(runway_actual + 2, 8))
        ax.set_title("Meses de Cobertura de Efectivo", color="white", fontsize=10, fontweight="bold")
        ax.grid(True, axis='x', linestyle=":", alpha=0.1)
        
        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
