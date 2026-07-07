import customtkinter as ctk
import sqlite3
import datetime

class AuditoriaTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        # Distribución de la cuadrícula: 2 columnas simétricas
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.setup_ui()

    def setup_ui(self):
        # =========================================================
        # PANEL IZQUIERDO: MARCO TEÓRICO (EXPLICACIÓN DE RATIOS)
        # =========================================================
        self.frame_teoria = ctk.CTkFrame(self)
        self.frame_teoria.grid(row=0, column=0, padx=15, pady=15, sticky="nsew")
        
        ctk.CTkLabel(self.frame_teoria, text="Fundamentos de Auditoría (NIF B-6)", 
                     font=("Urbanist", 16, "bold"), text_color="#60A5FA").pack(pady=15, padx=20, anchor="w")
        
        # Texto educativo estructurado con las explicaciones financieras
        txt_educativo = (
            "▶ PATRIMONIO NETO REAL\n"
            "Fórmula: Activos Totales - Pasivos Totales\n"
            "Representa tu verdadera riqueza neta. Los ingresos mensuales son solo el clima "
            "del día, pero tu patrimonio neto mide la solidez de los cimientos de tu edificio "
            "financiero.\n\n"
            "▶ RAZÓN CIRCULANTE (Prueba de Liquidez Inmediata)\n"
            "Fórmula: Activos Líquidos / Pasivos a Corto Plazo\n"
            "Responde a cuántos pesos tienes en efectivo, débito o renta fija (CETES) por cada "
            "peso que debes en tus tarjetas de crédito al corte.\n"
            "• Regla de Oro: Mantenerlo por arriba de 1.5. Si es menor, estás en insolvencia "
            "técnica y bajo alto riesgo de pagar intereses moratorios o el temido CAT.\n\n"
            "▶ APALANCAMIENTO PATRIMONIAL (Leverage)\n"
            "Fórmula: Pasivos Totales / Activos Totales\n"
            "Determina qué porcentaje de todo lo que posees (bienes, auto, inversiones) realmente "
            "le pertenece a los bancos y acreedores.\n"
            "• Regla de Oro: Mantenerlo por debajo del 30% (0.30). Si sube de ahí, estás "
            "comprometiendo severamente tu flujo de efectivo futuro.\n\n"
            "▶ ARBITRAJE MONETARIO E INFLACIÓN\n"
            "El dinero ocioso en cuentas tradicionales al 0% pierde un ~4.5% anual debido al INPC. "
            "La optimización exige migrar la liquidez ociosa a instrumentos regulados con "
            "rendimientos del ~11% anual para asegurar ganancias reales."
        )
        
        # Caja de texto informativa de solo lectura
        self.txt_teoria_box = ctk.CTkTextbox(self.frame_teoria, font=("Urbanist", 12), 
                                             fg_color="transparent", text_color="#94A3B8", wrap="word")
        self.txt_teoria_box.pack(pady=5, padx=20, fill="both", expand=True)
        self.txt_teoria_box.insert("1.0", txt_educativo)
        self.txt_teoria_box.configure(state="disabled") # Bloquea edición del usuario

        # =========================================================
        # PANEL DERECHO: CONSOLA DE DIAGNÓSTICO Y RESULTADOS
        # =========================================================
        self.frame_dictamen = ctk.CTkFrame(self)
        self.frame_dictamen.grid(row=0, column=1, padx=15, pady=15, sticky="nsew")
        
        ctk.CTkLabel(self.frame_dictamen, text="Ejecución de Diagnóstico", 
                     font=("Urbanist", 16, "bold"), text_color="#F59E0B").pack(pady=15, padx=20, anchor="w")
        
        self.btn_auditar = ctk.CTkButton(self.frame_dictamen, text="Generar Dictamen del Mes", 
                                         font=("Urbanist", 12, "bold"), fg_color="#F59E0B", 
                                         hover_color="#D97706", command=self.ejecutar_auditoria)
        self.btn_auditar.pack(pady=5, padx=20, fill="x")
        
        # Consola estilo terminal para el reporte crudo
        self.txt_reporte = ctk.CTkTextbox(self.frame_dictamen, font=("Courier New", 12), 
                                           fg_color="#0F172A", text_color="#E2E8F0")
        self.txt_reporte.pack(pady=15, padx=20, fill="both", expand=True)

    def ejecutar_auditoria(self):
        mes_actual = datetime.datetime.now().strftime("%Y-%m")
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()

        # Usar el balance más reciente disponible: exigir exactamente el mes en
        # curso dejaba la auditoría inservible los primeros días de cada mes
        cursor.execute("""
            SELECT fecha, activos_liquidos, activos_fijos, pasivos_corto, pasivos_largo
            FROM balance_general ORDER BY fecha DESC LIMIT 2
        """)
        filas = cursor.fetchall()

        self.txt_reporte.delete("1.0", "end")

        if not filas:
            conn.close()
            self.txt_reporte.insert("end", "[!] ERROR DE AUDITORÍA: No hay ningún balance capturado.\n\nPor favor, dirígete a la pestaña 'Balance General' para capturar tus Activos y Pasivos antes de correr el dictamen.")
            return

        fecha_mes, act_l, act_f, pas_c, pas_l = filas[0]

        # Conciliación contable: el cambio de liquidez entre los dos últimos
        # balances debería explicarse por el flujo neto registrado en Tesorería
        conciliacion = None
        if len(filas) == 2:
            fecha_prev, act_l_prev = filas[1][0], filas[1][1]
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0) FROM ingresos
                WHERE strftime('%Y-%m', fecha) > ? AND strftime('%Y-%m', fecha) <= ?
            """, (fecha_prev, fecha_mes))
            ingresos_periodo = cursor.fetchone()[0]
            cursor.execute("""
                SELECT COALESCE(SUM(monto), 0) FROM gastos
                WHERE strftime('%Y-%m', fecha) > ? AND strftime('%Y-%m', fecha) <= ?
            """, (fecha_prev, fecha_mes))
            gastos_periodo = cursor.fetchone()[0]
            conciliacion = {
                "fecha_prev": fecha_prev,
                "delta_liquidez": act_l - act_l_prev,
                "flujo_neto": ingresos_periodo - gastos_periodo,
                "gastos_periodo": gastos_periodo,
            }

        # Liquidez según cuentas reales (excluye crédito: eso es pasivo, no activo)
        cursor.execute("""
            SELECT COALESCE(SUM(c.saldo_inicial
                 + COALESCE((SELECT SUM(i.monto) FROM ingresos i WHERE i.cuenta_id = c.id), 0)
                 - COALESCE((SELECT SUM(g.monto) FROM gastos g WHERE g.cuenta_id = c.id), 0)), 0),
                   COUNT(*)
            FROM cuentas c WHERE c.tipo != 'Crédito'
        """)
        liquidez_cuentas, num_cuentas = cursor.fetchone()
        conn.close()

        tot_activos = act_l + act_f
        tot_pasivos = pas_c + pas_l
        
        # Razones Financieras
        razon_circulante = act_l / pas_c if pas_c > 0 else float('inf')
        apalancamiento = tot_pasivos / tot_activos if tot_activos > 0 else 0.0
        patrimonio_neto = tot_activos - tot_pasivos
        
        # Renderizado de la Terminal de Auditoría
        reporte = f"=== AUDITORÍA FINANCIERA INTERNA ({fecha_mes}) ===\n"
        reporte += "="*45 + "\n\n"
        if fecha_mes != mes_actual:
            reporte += f"[AVISO] No has cerrado el balance de {mes_actual}.\n"
            reporte += f"        Este dictamen usa el más reciente: {fecha_mes}.\n\n"
        reporte += f"PATRIMONIO NETO: ${patrimonio_neto:,.2f} MXN\n"
        if patrimonio_neto < 0:
            reporte += " [STATUS] QUIEBRA TÉCNICA DETECTADA\n"
        else:
            reporte += " [STATUS] ESTRUCTURA PATRIMONIAL POSITIVA\n"
        reporte += "-"*45 + "\n"
        
        reporte += "\n[1] RAZÓN CIRCULANTE (LIQUIDEZ DE CORTO PLAZO)\n"
        if razon_circulante == float('inf'):
            reporte += " -> RATIO: Infinito (Óptimo)\n"
            reporte += " -> No registras pasivos corrientes. Liquidez total.\n"
        elif razon_circulante >= 1.5:
            reporte += f" -> RATIO: {razon_circulante:.2f} (Saludable)\n"
            reporte += " -> Cubres tus tarjetas de crédito con comodidad.\n"
        else:
            reporte += f" -> RATIO: {razon_circulante:.2f} (Insolvencia Crítica)\n"
            reporte += " -> ¡ALERTA! Tus deudas de corto plazo superan\n    tu efectivo disponible. Paga a capital ya.\n"
            
        reporte += "\n[2] APALANCAMIENTO (ESTRUCTURA DE CAPITAL)\n"
        if apalancamiento <= 0.30:
            reporte += f" -> GRADO: {apalancamiento*100:.1f}% (Sólido)\n"
            reporte += " -> Eres el dueño legítimo de tus activos.\n"
        elif apalancamiento <= 0.50:
            reporte += f" -> GRADO: {apalancamiento*100:.1f}% (Precaución)\n"
            reporte += " -> Nivel de deuda manejable, pero detén créditos.\n"
        else:
            reporte += f" -> GRADO: {apalancamiento*100:.1f}% (Alto Riesgo)\n"
            reporte += " -> El banco posee la mayor parte de tus bienes.\n"
            
        reporte += "\n[3] CONCILIACIÓN TESORERÍA vs BALANCE\n"
        if conciliacion is None:
            reporte += " -> Se necesitan al menos dos balances mensuales\n    para conciliar. Sigue cerrando tus meses.\n"
        else:
            delta = conciliacion["delta_liquidez"]
            flujo = conciliacion["flujo_neto"]
            divergencia = delta - flujo
            tolerancia = max(conciliacion["gastos_periodo"] * 0.05, 500.0)
            reporte += f" -> Cambio en activos líquidos ({conciliacion['fecha_prev']} → {fecha_mes}): ${delta:,.2f}\n"
            reporte += f" -> Flujo neto registrado en Tesorería:    ${flujo:,.2f}\n"
            reporte += f" -> Divergencia: ${divergencia:,.2f}\n"
            if abs(divergencia) <= tolerancia:
                reporte += " -> [OK] CONCILIADO. Tu contabilidad de flujo\n    explica el cambio en tu liquidez.\n"
            else:
                reporte += " -> [ALERTA] DESCUADRE RELEVANTE. Hay dinero que\n    entró o salió sin registrarse en Tesorería\n"
                reporte += "    (o el balance está mal capturado). Compras de\n    activos y rendimientos también explican parte.\n"

        if num_cuentas > 0:
            reporte += "\n[4] CUENTAS REALES vs BALANCE DECLARADO\n"
            dif_cuentas = liquidez_cuentas - act_l
            reporte += f" -> Liquidez según tus {num_cuentas} cuenta(s): ${liquidez_cuentas:,.2f}\n"
            reporte += f" -> Activos líquidos del balance:  ${act_l:,.2f}\n"
            reporte += f" -> Diferencia: ${dif_cuentas:,.2f}\n"
            if abs(dif_cuentas) <= max(act_l * 0.03, 300.0):
                reporte += " -> [OK] Tus cuentas respaldan el balance declarado.\n"
            else:
                reporte += " -> [REVISAR] El balance no coincide con tus cuentas.\n    Actualiza el Balance General o revisa movimientos\n    sin cuenta asignada.\n"

        reporte += "\n" + "="*45 + "\n"
        reporte += ">>> DIAGNÓSTICO FINALIZADO CON ÉXITO"

        self.txt_reporte.insert("end", reporte)
