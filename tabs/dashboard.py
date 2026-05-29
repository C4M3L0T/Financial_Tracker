import customtkinter as ctk
import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np

class DashboardTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.periodicidad = "Mensual"
        self.setup_ui()

    def setup_ui(self):
        self.header_frame = ctk.CTkFrame(self, height=80, fg_color="#0f172a")
        self.header_frame.pack(fill="x", pady=5, padx=10)
        
        lbl_selector = ctk.CTkLabel(self.header_frame, text="Temporalidad:", font=("Urbanist", 12, "bold"), text_color="#94A3B8")
        lbl_selector.pack(side="left", padx=20, pady=10)
        
        self.menu_periodo = ctk.CTkOptionMenu(
            self.header_frame, 
            values=["Diario", "Mensual", "Anual"],
            command=self.cambiar_periodicidad,
            fg_color="#334155", button_color="#475569"
        )
        self.menu_periodo.set(self.periodicidad)
        self.menu_periodo.pack(side="left", padx=5, pady=10)
        
        self.lbl_flujo = ctk.CTkLabel(self.header_frame, text="Flujo Neto: $0.00", font=("JetBrains Mono", 20, "bold"))
        self.lbl_flujo.pack(side="right", padx=30, pady=10)

        # Contenedor scrolleable o expandible para las 6 gráficas
        self.canvas_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.canvas_frame.pack(fill="both", expand=True, padx=10, pady=5)

    def cambiar_periodicidad(self, nueva_periodicidad):
        self.periodicidad = nueva_periodicidad
        self.actualizar()

    def obtener_formato_sqlite(self):
        if self.periodicidad == "Diario": return "%Y-%m-%d"
        elif self.periodicidad == "Mensual": return "%Y-%m"
        else: return "%Y"

    def actualizar(self):
        for widget in self.canvas_frame.winfo_children(): widget.destroy()

        formato_temporal = self.obtener_formato_sqlite()
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()

        # ========================================================
        # 1. EXTRACCIÓN DE DATOS Y KPI CENTRAL
        # ========================================================
        cursor.execute("SELECT SUM(monto) FROM ingresos")
        total_in = cursor.fetchone()[0] or 0.0
        cursor.execute("SELECT SUM(monto) FROM gastos")
        total_out = cursor.fetchone()[0] or 0.0
        flujo_neto = total_in - total_out
        
        color_flujo = "#10B981" if flujo_neto >= 0 else "#EF4444"
        self.lbl_flujo.configure(text=f"Flujo Total Neto: ${flujo_neto:,.2f}", text_color=color_flujo)

        query_in = f"SELECT strftime('{formato_temporal}', fecha) as periodo, SUM(monto) FROM ingresos GROUP BY periodo ORDER BY periodo ASC"
        query_out = f"SELECT strftime('{formato_temporal}', fecha) as periodo, SUM(monto) FROM gastos GROUP BY periodo ORDER BY periodo ASC"
        
        datos_ingresos = dict(cursor.execute(query_in).fetchall())
        datos_gastos = dict(cursor.execute(query_out).fetchall())
        
        todos_los_periodos = sorted(list(set(list(datos_ingresos.keys()) + list(datos_gastos.keys()))))
        periodos_x = todos_los_periodos[-8:] # Últimos 8 periodos para las gráficas de tiempo
        
        ingresos_y = [datos_ingresos.get(p, 0.0) for p in periodos_x]
        gastos_y = [datos_gastos.get(p, 0.0) for p in periodos_x]

        # ========================================================
        # INICIALIZACIÓN DEL MOTOR MATPLOTLIB (GRID 3x2)
        # ========================================================
        fig, axs = plt.subplots(3, 2, figsize=(10, 8.5), dpi=100)
        fig.patch.set_facecolor('#1e293b')
        plt.subplots_adjust(hspace=0.6, wspace=0.3)

        for ax in axs.flat:
            ax.set_facecolor('#1e293b')
            ax.tick_params(colors='white', labelsize=8)
            for spine in ax.spines.values(): spine.set_color('#334155')

        # --- [0,0] Históricos de Liquidez ---
        x_indices = np.arange(len(periodos_x))
        width = 0.35
        if len(periodos_x) > 0:
            axs[0, 0].bar(x_indices - width/2, ingresos_y, width, label='In', color="#10B981")
            axs[0, 0].bar(x_indices + width/2, gastos_y, width, label='Out', color="#EF4444")
            axs[0, 0].set_xticks(x_indices)
            axs[0, 0].set_xticklabels(periodos_x, rotation=15, ha="right")
            axs[0, 0].legend(facecolor='#1e293b', edgecolor='none', labelcolor='white', fontsize=7)
        axs[0, 0].set_title(f"Flujos de Efectivo", color="white", fontsize=10, fontweight="bold")
        axs[0, 0].grid(True, linestyle=":", alpha=0.1)

        # --- [0,1] Eficiencia Fiscal (SAT) ---
        cursor.execute("SELECT SUM(monto) FROM gastos WHERE es_deducible=1")
        deducible = cursor.fetchone()[0] or 0.0
        no_deducible = total_out - deducible
        if total_out > 0:
            axs[0, 1].pie([deducible, no_deducible], labels=["Deducible", "No Deducible"], 
                          autopct='%1.1f%%', colors=["#38BDF8", "#475569"], textprops={'color': "w", 'fontsize': 8})
            axs[0, 1].set_title("Escudo Fiscal LISR", color="white", fontsize=10, fontweight="bold")
        else:
            axs[0, 1].text(0.5, 0.5, 'Sin Datos', color='white', ha='center', va='center')

        # --- [1,0] Velocidad del Patrimonio (Cálculo Diferencial dW/dt) ---
        flujos_periodo = np.array(ingresos_y) - np.array(gastos_y)
        riqueza_acumulada = np.cumsum(flujos_periodo)
        velocidad_riqueza = np.insert(np.diff(riqueza_acumulada), 0, 0.0) if len(riqueza_acumulada) > 1 else np.zeros(len(riqueza_acumulada))
        
        if len(periodos_x) > 0:
            axs[1, 0].plot(periodos_x, velocidad_riqueza, color="#22C55E", marker='o', linewidth=2)
            axs[1, 0].axhline(0, color="#64748B", linestyle="--", linewidth=1)
            axs[1, 0].set_xticklabels(periodos_x, rotation=15, ha="right")
            axs[1, 0].set_title("Aceleración Riqueza ($dW/dt$)", color="white", fontsize=10, fontweight="bold")
            axs[1, 0].grid(True, linestyle=":", alpha=0.1)

        # --- [1,1] RECUPERADO: Algoritmo de Proyección MSI ---
        cursor.execute("SELECT mensualidad, meses_totales, meses_pagados FROM deudas_msi")
        deudas = cursor.fetchall()
        proyecciones_msi = [0.0] * 6
        meses_futuros = ["M+1", "M+2", "M+3", "M+4", "M+5", "M+6"]
        
        for mensualidad, m_tot, m_pag in deudas:
            meses_restantes = m_tot - m_pag
            for m in range(1, 7):
                if meses_restantes >= m: proyecciones_msi[m-1] += mensualidad
                    
        axs[1, 1].plot(meses_futuros, proyecciones_msi, color="#A855F7", marker='o', linewidth=2)
        axs[1, 1].fill_between(meses_futuros, proyecciones_msi, color="#A855F7", alpha=0.1)
        axs[1, 1].set_title("Deuda y MSI a 6 Meses", color="white", fontsize=10, fontweight="bold")
        axs[1, 1].grid(True, linestyle=":", alpha=0.1)

        # --- [2,0] Estructura de Costos Microeconómicos (Pareto) ---
        cursor.execute("SELECT categoria, SUM(monto) FROM gastos GROUP BY categoria ORDER BY SUM(monto) ASC")
        datos_cat = cursor.fetchall()
        if datos_cat:
            cats = [d[0] for d in datos_cat]
            montos = [d[1] for d in datos_cat]
            axs[2, 0].barh(cats, montos, color="#F59E0B", height=0.5)
            axs[2, 0].set_title("Pareto de Costos", color="white", fontsize=10, fontweight="bold")
            axs[2, 0].grid(True, linestyle=":", alpha=0.1)

        # --- [2,1] NUEVO: Machine Learning - Regresión Lineal de Gastos ---
        if len(periodos_x) > 1:
            x_vals = np.arange(len(periodos_x))
            y_vals = np.array(gastos_y)
            
            # Entrenamiento del modelo OLS (Grado 1)
            coeficientes = np.polyfit(x_vals, y_vals, 1) 
            polinomio = np.poly1d(coeficientes)
            tendencia = polinomio(x_vals)
            
            # Predicción (Inferencia) para t+1
            next_x = len(periodos_x)
            prediccion_monto = polinomio(next_x)
            
            # Prevenir proyecciones de gasto negativas
            if prediccion_monto < 0: prediccion_monto = 0.0

            axs[2, 1].plot(x_vals, y_vals, marker='o', color="#EF4444", label="Histórico", linewidth=1)
            axs[2, 1].plot(x_vals, tendencia, linestyle="--", color="#F87171", label="Tendencia", alpha=0.6)
            axs[2, 1].scatter([next_x], [prediccion_monto], color="#F59E0B", s=60, zorder=5, label=f"Pronóstico")
            
            axs[2, 1].set_xticks(list(x_vals) + [next_x])
            axs[2, 1].set_xticklabels(periodos_x + ["+1"], rotation=20, ha="right")
            axs[2, 1].legend(facecolor='#1e293b', edgecolor='none', labelcolor='white', fontsize=7)
            axs[2, 1].set_title(f"Pronóstico de Gasto: ${prediccion_monto:,.0f}", color="white", fontsize=10, fontweight="bold")
            axs[2, 1].grid(True, linestyle=":", alpha=0.1)
        else:
            axs[2, 1].text(0.5, 0.5, 'Insuficientes datos para ML', color='#94A3B8', ha='center', va='center')

        # Inyección del canvas
        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        conn.close()


