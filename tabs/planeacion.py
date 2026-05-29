import customtkinter as ctk
import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from tkinter import messagebox

class PlaneacionTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.setup_ui()
        self.actualizar_msi()
        self.actualizar_categorias()

    def setup_ui(self):
        # =========================================================
        # PANEL IZQUIERDO: GESTIÓN DE DEUDA Y MSI
        # =========================================================
        self.frame_msi = ctk.CTkFrame(self)
        self.frame_msi.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.frame_msi, text="Control de Pasivos (MSI)", font=("Urbanist", 18, "bold"), text_color="#A855F7").pack(pady=15)
        
        self.e_msi_desc = ctk.CTkEntry(self.frame_msi, placeholder_text="Descripción (ej: Pantalla 4K)")
        self.e_msi_desc.pack(pady=5, padx=20, fill="x")
        
        self.e_msi_monto = ctk.CTkEntry(self.frame_msi, placeholder_text="Monto Total a Pagar ($ MXN)")
        self.e_msi_monto.pack(pady=5, padx=20, fill="x")
        
        self.e_msi_meses = ctk.CTkEntry(self.frame_msi, placeholder_text="Plazo en Meses (ej: 12)")
        self.e_msi_meses.pack(pady=5, padx=20, fill="x")
        
        ctk.CTkButton(self.frame_msi, text="Registrar Deuda", fg_color="#A855F7", hover_color="#9333EA", command=self.guardar_msi).pack(pady=15, padx=20, fill="x")
        
        # Historial de Deudas Activas
        self.lista_msi = ctk.CTkScrollableFrame(self.frame_msi, height=300)
        self.lista_msi.pack(pady=5, padx=10, fill="both", expand=True)

        # =========================================================
        # PANEL DERECHO: SIMULADOR DE ESCENARIOS "WHAT-IF"
        # =========================================================
        self.frame_sim = ctk.CTkFrame(self)
        self.frame_sim.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.frame_sim, text="Simulador 'What-If' (Pareto)", font=("Urbanist", 18, "bold"), text_color="#F59E0B").pack(pady=15)
        
        # Selector de Categoría (Se llena dinámicamente desde la BD)
        self.var_cat = ctk.StringVar(value="Seleccionar Categoría")
        self.menu_cat = ctk.CTkOptionMenu(self.frame_sim, variable=self.var_cat, values=["Cargando..."])
        self.menu_cat.pack(pady=5, padx=20, fill="x")
        
        self.lbl_slider = ctk.CTkLabel(self.frame_sim, text="Meta de Reducción: 0%", font=("Urbanist", 13, "bold"))
        self.lbl_slider.pack(pady=(15, 0))
        
        # Control deslizante de elasticidad de gasto
        self.slider_red = ctk.CTkSlider(self.frame_sim, from_=0, to=100, button_color="#F59E0B", progress_color="#FCD34D", command=self.actualizar_label_slider)
        self.slider_red.set(0)
        self.slider_red.pack(pady=5, padx=20, fill="x")
        
        ctk.CTkButton(self.frame_sim, text="Ejecutar Simulación Matemática", fg_color="#F59E0B", hover_color="#D97706", text_color="black", font=("Urbanist", 12, "bold"), command=self.correr_simulacion).pack(pady=15, padx=20, fill="x")
        
        # Contenedor del Gráfico Comparativo
        self.canvas_sim_frame = ctk.CTkFrame(self.frame_sim, fg_color="transparent")
        self.canvas_sim_frame.pack(pady=5, padx=10, fill="both", expand=True)

    # --- Lógica de UI ---
    def actualizar_label_slider(self, value):
        self.lbl_slider.configure(text=f"Meta de Reducción: {int(value)}%")

    # --- Lógica de Base de Datos y MSI ---
    def actualizar_categorias(self):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT categoria FROM gastos")
        cats = [row[0] for row in cursor.fetchall()]
        conn.close()
        if cats:
            self.menu_cat.configure(values=cats)
            self.var_cat.set(cats[0])

    def guardar_msi(self):
        desc = self.e_msi_desc.get().strip()
        try:
            monto_total = float(self.e_msi_monto.get().strip())
            meses_totales = int(self.e_msi_meses.get().strip())
            if monto_total <= 0 or meses_totales <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Ingresa números válidos y mayores a cero en los montos financieros.")
            return

        mensualidad = monto_total / meses_totales
        
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("""
            INSERT INTO deudas_msi (desc, monto_total, mensualidad, meses_totales, meses_pagados) 
            VALUES (?,?,?,?,0)
        """, (desc, monto_total, mensualidad, meses_totales))
        conn.commit()
        conn.close()
        
        self.e_msi_desc.delete(0, 'end')
        self.e_msi_monto.delete(0, 'end')
        self.e_msi_meses.delete(0, 'end')
        self.actualizar_msi()

    def abonar_msi(self, msi_id, pagados_actuales, totales):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        nuevo_pago = pagados_actuales + 1
        
        if nuevo_pago >= totales:
            cursor.execute("DELETE FROM deudas_msi WHERE id=?", (msi_id,))
            messagebox.showinfo("¡Deuda Liquidada!", "Has terminado de pagar este pasivo. Tu liquidez mensual acaba de aumentar.")
        else:
            cursor.execute("UPDATE deudas_msi SET meses_pagados=? WHERE id=?", (nuevo_pago, msi_id))
            
        conn.commit()
        conn.close()
        self.actualizar_msi()

    def eliminar_msi(self, msi_id):
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("DELETE FROM deudas_msi WHERE id=?", (msi_id,))
        conn.commit()
        conn.close()
        self.actualizar_msi()

    def actualizar_msi(self):
        for w in self.lista_msi.winfo_children(): w.destroy()
        
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, desc, mensualidad, meses_totales, meses_pagados FROM deudas_msi")
        
        for mid, d, men, mt, mp in cursor.fetchall():
            row = ctk.CTkFrame(self.lista_msi, fg_color="#1e293b")
            row.pack(fill="x", pady=4, padx=2)
            
            info_texto = f"🟣 {d}\n${men:,.2f}/mes | Progreso: {mp}/{mt} meses"
            ctk.CTkLabel(row, text=info_texto, font=("Urbanist", 12), justify="left").pack(side="left", padx=10, pady=5)
            
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=5)
            
            ctk.CTkButton(btn_frame, text="Abonar 1 Mes", width=90, fg_color="#10B981", hover_color="#059669", font=("Urbanist", 10), command=lambda i=mid, p=mp, t=mt: self.abonar_msi(i, p, t)).pack(pady=2)
            ctk.CTkButton(btn_frame, text="Eliminar", width=90, fg_color="#EF4444", hover_color="#DC2626", font=("Urbanist", 10), command=lambda i=mid: self.eliminar_msi(i)).pack(pady=2)
            
        conn.close()

# --- Motor Analítico "What-If" ---
    def correr_simulacion(self):
        categoria = self.var_cat.get()
        reduccion = self.slider_red.get() / 100.0
        
        if categoria == "Seleccionar Categoría" or categoria == "Cargando...":
            messagebox.showwarning("Aviso", "Por favor, selecciona una categoría para el modelo.")
            return
            
        # Limpieza del canvas
        for widget in self.canvas_sim_frame.winfo_children(): widget.destroy()
        
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        
        # Extraer gastos consolidados vs gastos de la categoría elegida
        cursor.execute("SELECT strftime('%Y-%m', fecha) as periodo, SUM(monto) FROM gastos GROUP BY periodo ORDER BY periodo ASC")
        datos_totales = dict(cursor.fetchall())
        
        cursor.execute("SELECT strftime('%Y-%m', fecha) as periodo, SUM(monto) FROM gastos WHERE categoria=? GROUP BY periodo ORDER BY periodo ASC", (categoria,))
        datos_cat = dict(cursor.fetchall())
        conn.close()
        
        # Alinear el tiempo a los últimos 8 meses
        periodos = sorted(list(datos_totales.keys()))[-8:]
        if len(periodos) < 2:
            ctk.CTkLabel(self.canvas_sim_frame, text="Insuficientes datos históricos para simular.", text_color="#94A3B8").pack(expand=True)
            return
            
        gastos_orig = np.array([datos_totales.get(p, 0.0) for p in periodos])
        gastos_cat_arr = np.array([datos_cat.get(p, 0.0) for p in periodos])
        
        # EL NÚCLEO DE LA SIMULACIÓN: Inyectar la eficiencia al modelo histórico
        gastos_sim = gastos_orig - (gastos_cat_arr * reduccion)
        
        x_vals = np.arange(len(periodos))
        next_x = len(periodos)
        
        # 1. Regresión Lineal Original (El Status Quo)
        coef_orig = np.polyfit(x_vals, gastos_orig, 1)
        tendencia_orig = np.poly1d(coef_orig)(np.append(x_vals, next_x))
        
        # 2. Regresión Lineal Optimizada (El Escenario What-If)
        coef_sim = np.polyfit(x_vals, gastos_sim, 1)
        tendencia_sim = np.poly1d(coef_sim)(np.append(x_vals, next_x))

        # 3. NUEVO: Sub-Regresión para predecir el límite de la categoría en M+1
        coef_cat = np.polyfit(x_vals, gastos_cat_arr, 1)
        prediccion_cat_base = max(0, np.poly1d(coef_cat)(next_x)) # Prevenir negativos
        
        meta_monetaria_ahorro = prediccion_cat_base * reduccion
        presupuesto_tope = prediccion_cat_base - meta_monetaria_ahorro
        
        # --- Renderizado de Matplotlib ---
        fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
        fig.patch.set_facecolor('#0f172a')
        fig.subplots_adjust(bottom=0.2, left=0.15, top=0.85) # Ajuste para el nuevo título
        ax.set_facecolor('#0f172a')
        ax.tick_params(colors='white', labelsize=8)
        for spine in ax.spines.values(): spine.set_color('#334155')
        
        # Graficamos el diferencial de trayectorias
        ax.plot(np.append(x_vals, next_x), tendencia_orig, color="#EF4444", linestyle="--", linewidth=1.5, label="Trayectoria Actual")
        ax.plot(np.append(x_vals, next_x), tendencia_sim, color="#10B981", linestyle="-", linewidth=2.5, label="Trayectoria Optimizada")
        
        ax.set_xticks(list(x_vals) + [next_x])
        ax.set_xticklabels(periodos + ["+1"], rotation=25, ha="right")
        
        # Título dinámico y accionable
        titulo = (f"Escenario: Recorte del {int(reduccion*100)}% en {categoria}\n"
                  f"Meta a no gastar: ${meta_monetaria_ahorro:,.0f} | Tu nuevo límite: ${presupuesto_tope:,.0f}")
        
        ax.set_title(titulo, color="white", fontsize=10, fontweight="bold", pad=10)
        ax.legend(facecolor='#1e293b', edgecolor='none', labelcolor='white', fontsize=8)
        ax.grid(True, linestyle=":", alpha=0.15)
        
        canvas = FigureCanvasTkAgg(fig, master=self.canvas_sim_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True) 
