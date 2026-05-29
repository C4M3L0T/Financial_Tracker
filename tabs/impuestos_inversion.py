import customtkinter as ctk
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

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
        
        ctk.CTkButton(self.frame_sat, text="Calcular Retorno SAT", fg_color="#10B981", hover_color="#059669", font=("Urbanist", 12, "bold"), command=self.recalcular_metricas).pack(pady=10, padx=20, fill="x")
        
        # Tarjetas de Métricas Fiscales
        self.box_deducible = self.crear_tarjeta_metrica(self.frame_sat, "Deducciones Acumuladas (Con CFDI)", "$0.00", "#34D399")
        self.box_tasa = self.crear_tarjeta_metrica(self.frame_sat, "Tu Tasa Marginal de ISR", "0.00%", "#60A5FA")
        self.box_devolucion = self.crear_tarjeta_metrica(self.frame_sat, "Devolución Estimada (Saldo a Favor)", "$0.00", "#FBBF24")

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

    def recalcular_metricas(self):
        # --- PARTE 1: MODELADO FISCAL ---
        try:
            ingreso = float(self.e_ingreso_anual.get())
        except ValueError:
            ingreso = 300000.0
            
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT SUM(monto) FROM gastos WHERE es_deducible = 1 AND con_factura = 1")
        deducciones_totales = cursor.fetchone()[0] or 0.0
        
        tope_ley = min(ingreso * 0.15, 198000.0)
        deducciones_mitigadas = min(deducciones_totales, tope_ley)
        
        tasa_m, isr_original, tablas = self.calcular_tasa_marginal_isr(ingreso)
        
        base_gravable_optimizada = max(0.0, ingreso - deducciones_mitigadas)
        fila_opt = tablas[tablas[:, 0] <= base_gravable_optimizada][-1]
        isr_optimizado = fila_opt[1] + ((base_gravable_optimizada - fila_opt[0]) * fila_opt[2])
        
        saldo_a_favor = max(0.0, isr_original - isr_optimizado)
        
        self.box_deducible.configure(text=f"${deducciones_totales:,.2f} (Tope: ${tope_ley:,.2f})")
        self.box_tasa.configure(text=f"{tasa_m * 100:.2f}%")
        self.box_devolucion.configure(text=f"${saldo_a_favor:,.2f}")

        # --- PARTE 2: ANÁLISIS DE RUNWAY MICROECONÓMICO ---
        try:
            liquidez = float(self.e_liquidez.get())
        except ValueError:
            liquidez = 0.0
            
        cursor.execute("""
            SELECT SUM(monto) FROM gastos 
            GROUP BY strftime('%Y-%m', fecha) 
            ORDER BY fecha DESC LIMIT 6
        """)
        gastos_mensuales = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        gasto_medio = np.mean(gastos_mensuales) if gastos_mensuales else 1.0
        runway = liquidez / gasto_medio if gasto_medio > 0 else 0.0
        
        self.box_gasto_medio.configure(text=f"${gasto_medio:,.2f}/mes")
        self.box_runway.configure(text=f"{runway:.1f} meses")
        
        if runway < 3.0: self.box_runway.configure(text_color="#EF4444")     
        elif runway < 6.0: self.box_runway.configure(text_color="#F59E0B")   
        else: self.box_runway.configure(text_color="#10B981")                

        self.renderizar_grafico_solvencia(runway)

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
