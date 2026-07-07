import customtkinter as ctk
import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from datetime import datetime

# Supuestos macro — actualizar periódicamente (CETES 28d: banxico.org.mx; INPC: inegi.org.mx)
TASA_CETES_NOMINAL = 0.11
INFLACION_ANUAL = 0.045
# Rendimiento real (ecuación de Fisher): lo que de verdad gana tu poder de compra
RENDIMIENTO_REAL = (1 + TASA_CETES_NOMINAL) / (1 + INFLACION_ANUAL) - 1

class BalanceGeneralTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.setup_ui()
        self.cargar_mes_actual()

    def setup_ui(self):
        # =========================================================
        # PANEL IZQUIERDO: CAPTURA NIF B-6 (ACTIVOS Y PASIVOS)
        # =========================================================
        self.frame_inputs = ctk.CTkFrame(self)
        self.frame_inputs.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.frame_inputs, text="Estado de Situación Financiera", font=("Urbanist", 18, "bold"), text_color="#60A5FA").pack(pady=15)
        
        # --- ACTIVOS ---
        ctk.CTkLabel(self.frame_inputs, text="🟢 ACTIVOS (Lo que posees)", font=("Urbanist", 12, "bold"), text_color="#10B981").pack(anchor="w", padx=20, pady=(5,0))
        
        self.e_act_liquidos = self.crear_input(self.frame_inputs, "Activos Líquidos (Bancos, Efectivo, Cetes):")
        self.e_act_fijos = self.crear_input(self.frame_inputs, "Activos Fijos / Retiro (Afore, PPR, Auto, Casa):")
        
        # --- PASIVOS ---
        ctk.CTkLabel(self.frame_inputs, text="🔴 PASIVOS (Lo que debes)", font=("Urbanist", 12, "bold"), text_color="#EF4444").pack(anchor="w", padx=20, pady=(15,0))
        
        self.e_pas_corto = self.crear_input(self.frame_inputs, "Corto Plazo (Saldo total Tarjetas de Crédito):")
        self.e_pas_largo = self.crear_input(self.frame_inputs, "Largo Plazo (Crédito Hipotecario / Automotriz):")

        # La app ya conoce líquidos y deuda de tarjetas: evitar el error de dedo
        ctk.CTkButton(self.frame_inputs, text="📥 Usar saldos de mis cuentas", fg_color="#334155",
                      hover_color="#475569", font=("Urbanist", 11),
                      command=self.usar_saldos_cuentas).pack(pady=(15, 5), padx=20, fill="x")

        # Botón de Guardar Cierre de Mes
        ctk.CTkButton(self.frame_inputs, text="Cerrar Balance del Mes", fg_color="#3B82F6", hover_color="#2563EB", font=("Urbanist", 12, "bold"), command=self.guardar_balance).pack(pady=(5, 20), padx=20, fill="x")

        # =========================================================
        # PANEL DERECHO: PATRIMONIO NETO Y ESCUDO INFLACIONARIO CETES
        # =========================================================
        self.frame_analytics = ctk.CTkFrame(self)
        self.frame_analytics.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.frame_analytics, text="Indicadores de Riqueza Real", font=("Urbanist", 18, "bold"), text_color="#FBBF24").pack(pady=15)
        
        # Tarjetas de Métricas de Balance
        self.lbl_patrimonio = self.crear_tarjeta_metrica(self.frame_analytics, "PATRIMONIO NETO REAL", "$0.00", "#FBBF24")
        self.lbl_inflacion = self.crear_tarjeta_metrica(
            self.frame_analytics,
            f"Pérdida REAL anual si el efectivo se queda al 0% (inflación {INFLACION_ANUAL*100:.1f}%)",
            "$0.00", "#EF4444")
        self.lbl_cetes = self.crear_tarjeta_metrica(
            self.frame_analytics,
            f"Ganancia REAL anual en CETES ({TASA_CETES_NOMINAL*100:.0f}% nominal − inflación = {RENDIMIENTO_REAL*100:.1f}% real)",
            "$0.00", "#10B981")
        
        # Contenedor para gráfica
        self.canvas_frame = ctk.CTkFrame(self.frame_analytics, fg_color="transparent")
        self.canvas_frame.pack(pady=10, padx=20, fill="both", expand=True)

    def crear_input(self, master, label_text):
        ctk.CTkLabel(master, text=label_text, font=("Urbanist", 11), text_color="#94A3B8").pack(anchor="w", padx=20, pady=(2,0))
        entry = ctk.CTkEntry(master, placeholder_text="0.00")
        entry.pack(padx=20, pady=2, fill="x")
        return entry

    def crear_tarjeta_metrica(self, master, titulo, valor_defecto, color_valor):
        frame = ctk.CTkFrame(master, fg_color="#1E293B", height=65)
        frame.pack(pady=4, padx=20, fill="x")
        ctk.CTkLabel(frame, text=titulo, font=("Urbanist", 11), text_color="#94A3B8").pack(pady=(5, 2), padx=10, anchor="w")
        lbl_val = ctk.CTkLabel(frame, text=valor_defecto, font=("Urbanist", 16, "bold"), text_color=color_valor)
        lbl_val.pack(pady=(0, 5), padx=10, anchor="w")
        return lbl_val

    def usar_saldos_cuentas(self):
        """Prellena activos líquidos y deuda de tarjetas desde los saldos derivados
        de las cuentas — la conciliación cuadra por construcción."""
        import database
        from tkinter import messagebox
        filas = database.obtener_saldos_cuentas()
        if not filas:
            messagebox.showinfo("Sin Cuentas", "Crea tus cuentas en Tesorería (⚙ Administrar) primero.")
            return
        liquido = sum(s for _c, _n, tipo, _t, s in filas if tipo != "Crédito")
        deuda_tarjetas = -sum(s for _c, _n, tipo, _t, s in filas if tipo == "Crédito" and s < 0)

        self.e_act_liquidos.delete(0, 'end')
        self.e_act_liquidos.insert(0, f"{liquido:.2f}")
        self.e_pas_corto.delete(0, 'end')
        self.e_pas_corto.insert(0, f"{deuda_tarjetas:.2f}")
        self.recalcular_patrimonio()

    def cargar_mes_actual(self):
        """Lee el registro del mes en curso si ya existe"""
        fecha_mes = datetime.now().strftime("%Y-%m")
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT activos_liquidos, activos_fijos, pasivos_corto, pasivos_largo FROM balance_general WHERE fecha = ?", (fecha_mes,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            self.e_act_liquidos.insert(0, str(row[0]))
            self.e_act_fijos.insert(0, str(row[1]))
            self.e_pas_corto.insert(0, str(row[2]))
            self.e_pas_largo.insert(0, str(row[3]))
            self.recalcular_patrimonio()

    def guardar_balance(self):
        fecha_mes = datetime.now().strftime("%Y-%m")
        try:
            act_l = float(self.e_act_liquidos.get() or 0)
            act_f = float(self.e_act_fijos.get() or 0)
            pas_c = float(self.e_pas_corto.get() or 0)
            pas_l = float(self.e_pas_largo.get() or 0)
        except ValueError:
            return

        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO balance_general (fecha, activos_liquidos, activos_fijos, pasivos_corto, pasivos_largo)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(fecha) DO UPDATE SET
                activos_liquidos=excluded.activos_liquidos,
                activos_fijos=excluded.activos_fijos,
                pasivos_corto=excluded.pasivos_corto,
                pasivos_largo=excluded.pasivos_largo
        """, (fecha_mes, act_l, act_f, pas_c, pas_l))
        conn.commit()
        conn.close()
        
        self.recalcular_patrimonio()

    def recalcular_patrimonio(self):
        try:
            act_l = float(self.e_act_liquidos.get() or 0)
            act_f = float(self.e_act_fijos.get() or 0)
            pas_c = float(self.e_pas_corto.get() or 0)
            pas_l = float(self.e_pas_largo.get() or 0)
        except ValueError:
            return

        tot_activos = act_l + act_f
        tot_pasivos = pas_c + pas_l
        patrimonio_neto = tot_activos - tot_pasivos
        
        # --- ARBITRAJE MONETARIO E INFLACIÓN ---
        # Efectivo al 0% nominal: pierde poder de compra al ritmo de la inflación
        perdida_inflacion_anual = act_l * INFLACION_ANUAL
        # En CETES lo que importa es el rendimiento REAL (nominal deflactado), no el bruto
        ganancia_real_anual = act_l * RENDIMIENTO_REAL

        # Actualizar UI
        self.lbl_patrimonio.configure(text=f"${patrimonio_neto:,.2f}")
        self.lbl_inflacion.configure(text=f"-${perdida_inflacion_anual:,.2f} al año (menos poder de compra)")
        self.lbl_cetes.configure(text=f"+${ganancia_real_anual:,.2f} al año (poder de compra real)")
        
        if patrimonio_neto < 0:
            self.lbl_patrimonio.configure(text_color="#EF4444") # Quiebra técnica
        else:
            self.lbl_patrimonio.configure(text_color="#10B981")

        self.renderizar_grafico(tot_activos, tot_pasivos)

    def renderizar_grafico(self, activos, pasivos):
        for w in self.canvas_frame.winfo_children(): w.destroy()
        
        fig, ax = plt.subplots(figsize=(4, 2.2), dpi=90)
        fig.patch.set_facecolor('#0f172a')
        ax.set_facecolor('#0f172a')
        
        labels = ['Total Activos', 'Total Pasivos']
        valores = [activos, pasivos]
        colores = ['#10B981', '#EF4444']
        
        bars = ax.bar(labels, valores, color=colores, width=0.4)
        ax.tick_params(colors='white', labelsize=10)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#334155')
        ax.spines['bottom'].set_color('#334155')
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + (max(valores)*0.02),
                    f'${height:,.0f}', ha='center', va='bottom', color='white', fontsize=9, fontweight='bold')
        
        ax.set_title("Estructura de tu Balance ($ MXN)", color="white", fontsize=11, fontweight="bold")
        
        canvas = FigureCanvasTkAgg(fig, master=self.canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
