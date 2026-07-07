import customtkinter as ctk
import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from datetime import datetime
from tkinter import messagebox
from tabs.tesoreria import CATEGORIAS_GASTOS
from database import CATEGORIA_AHORRO


def mes_anterior(mes):
    """'2026-07' → '2026-06'"""
    anio, m = map(int, mes.split("-"))
    m -= 1
    if m == 0:
        anio, m = anio - 1, 12
    return f"{anio:04d}-{m:02d}"


def simular_pago_deuda(deudas, abono_mensual):
    """Simula el pago mes a mes de deudas revolventes.
    deudas: [(nombre, saldo, tasa_anual_%)] YA ordenadas por prioridad de pago.
    Devuelve (meses, intereses_totales) o None si el abono no alcanza a vencer
    el interés (la deuda diverge)."""
    saldos = [s for _, s, _ in deudas]
    tasas = [t / 100.0 / 12.0 for _, _, t in deudas]
    intereses_totales = 0.0
    meses = 0
    while sum(saldos) > 0.01:
        meses += 1
        if meses > 600:
            return None
        for i in range(len(saldos)):
            interes = saldos[i] * tasas[i]
            saldos[i] += interes
            intereses_totales += interes
        restante = abono_mensual
        for i in range(len(saldos)):  # respeta el orden de prioridad
            pago = min(saldos[i], restante)
            saldos[i] -= pago
            restante -= pago
            if restante <= 0:
                break
    return meses, intereses_totales


class PlaneacionTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.ultima_simulacion = None
        self.setup_ui()
        self.actualizar_msi()
        self.actualizar_categorias()
        self.actualizar_presupuestos()
        self.actualizar_plan_deuda()
        self.actualizar_metas()

    def setup_ui(self):
        # Página scrolleable (como el Dashboard): cada sección con su tamaño
        # cómodo en vez de comprimirse para caber en una sola pantalla
        self.pagina = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.pagina.pack(fill="both", expand=True)
        self.pagina.grid_columnconfigure(0, weight=1, uniform="cols")
        self.pagina.grid_columnconfigure(1, weight=1, uniform="cols")

        # =========================================================
        # PANEL IZQUIERDO: GESTIÓN DE DEUDA Y MSI
        # =========================================================
        self.frame_msi = ctk.CTkFrame(self.pagina)
        self.frame_msi.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(self.frame_msi, text="Control de Pasivos (MSI)", font=("Urbanist", 18, "bold"), text_color="#A855F7").pack(pady=15)

        self.e_msi_desc = ctk.CTkEntry(self.frame_msi, placeholder_text="Descripción (ej: Pantalla 4K)", height=34)
        self.e_msi_desc.pack(pady=5, padx=20, fill="x")

        self.e_msi_monto = ctk.CTkEntry(self.frame_msi, placeholder_text="Monto Total a Pagar ($ MXN)", height=34)
        self.e_msi_monto.pack(pady=5, padx=20, fill="x")

        self.e_msi_meses = ctk.CTkEntry(self.frame_msi, placeholder_text="Plazo en Meses (ej: 12)", height=34)
        self.e_msi_meses.pack(pady=5, padx=20, fill="x")

        self.e_msi_tasa = ctk.CTkEntry(self.frame_msi, placeholder_text="Tasa de interés anual % (vacío o 0 = MSI)", height=34)
        self.e_msi_tasa.pack(pady=5, padx=20, fill="x")

        ctk.CTkButton(self.frame_msi, text="Registrar Deuda", fg_color="#A855F7", hover_color="#9333EA", command=self.guardar_msi).pack(pady=12, padx=20, fill="x")

        # Historial de Deudas Activas (crece con el contenido; la página scrollea)
        self.lista_msi = ctk.CTkFrame(self.frame_msi, fg_color="transparent")
        self.lista_msi.pack(pady=5, padx=10, fill="both", expand=True)

        # =========================================================
        # PANEL DERECHO: SIMULADOR DE ESCENARIOS "WHAT-IF"
        # =========================================================
        self.frame_sim = ctk.CTkFrame(self.pagina)
        self.frame_sim.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        ctk.CTkLabel(self.frame_sim, text="Simulador 'What-If' (Pareto)", font=("Urbanist", 18, "bold"), text_color="#F59E0B").pack(pady=15)

        # Selector de Categoría (Se llena dinámicamente desde la BD)
        self.var_cat = ctk.StringVar(value="Seleccionar Categoría")
        self.menu_cat = ctk.CTkOptionMenu(self.frame_sim, variable=self.var_cat, values=["Cargando..."])
        self.menu_cat.pack(pady=5, padx=20, fill="x")

        self.lbl_slider = ctk.CTkLabel(self.frame_sim, text="Meta de Reducción: 0%", font=("Urbanist", 13, "bold"))
        self.lbl_slider.pack(pady=(12, 0))

        # Control deslizante de elasticidad de gasto
        self.slider_red = ctk.CTkSlider(self.frame_sim, from_=0, to=100, button_color="#F59E0B", progress_color="#FCD34D", command=self.actualizar_label_slider)
        self.slider_red.set(0)
        self.slider_red.pack(pady=5, padx=20, fill="x")

        ctk.CTkButton(self.frame_sim, text="Ejecutar Simulación Matemática", fg_color="#F59E0B", hover_color="#D97706", text_color="black", font=("Urbanist", 12, "bold"), command=self.correr_simulacion).pack(pady=(12, 5), padx=20, fill="x")

        # Cierre del ciclo conductual: simulación → compromiso (presupuesto persistido)
        self.btn_adoptar = ctk.CTkButton(self.frame_sim, text="Adoptar como presupuesto (corre una simulación)",
                                          fg_color="#334155", hover_color="#475569", state="disabled",
                                          font=("Urbanist", 11), command=self.adoptar_presupuesto)
        self.btn_adoptar.pack(pady=(0, 8), padx=20, fill="x")

        # Contenedor del Gráfico Comparativo
        self.canvas_sim_frame = ctk.CTkFrame(self.frame_sim, fg_color="transparent")
        self.canvas_sim_frame.pack(pady=5, padx=10, fill="both", expand=True)
        ctk.CTkLabel(self.canvas_sim_frame,
                     text="Elige una categoría, mueve el slider\ny ejecuta la simulación para ver la gráfica.",
                     font=("Urbanist", 12), text_color="#64748B").pack(pady=40)

        # Resultados numéricos de la simulación (fuera de matplotlib: no se recortan)
        self.lbl_resultado_sim = ctk.CTkLabel(self.frame_sim, text="", font=("Urbanist", 14, "bold"),
                                               text_color="#F59E0B")
        self.lbl_resultado_sim.pack(pady=(0, 12), padx=20)

        # =========================================================
        # PANEL INFERIOR: PRESUPUESTOS MENSUALES POR CATEGORÍA
        # =========================================================
        self.frame_presupuestos = ctk.CTkFrame(self.pagina)
        self.frame_presupuestos.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")

        ctk.CTkLabel(self.frame_presupuestos, text="Presupuestos Mensuales por Categoría",
                     font=("Urbanist", 18, "bold"), text_color="#38BDF8").pack(anchor="w", padx=15, pady=(12, 2))
        self.lbl_cumplimiento = ctk.CTkLabel(self.frame_presupuestos, text="",
                                              font=("Urbanist", 12), text_color="#94A3B8")
        self.lbl_cumplimiento.pack(anchor="w", padx=15)

        fila_form = ctk.CTkFrame(self.frame_presupuestos, fg_color="transparent")
        fila_form.pack(fill="x", padx=15, pady=(2, 6))
        self.c_pres_cat = ctk.CTkOptionMenu(fila_form, values=CATEGORIAS_GASTOS, width=200)
        self.c_pres_cat.pack(side="left", padx=(0, 5))
        self.e_pres_limite = ctk.CTkEntry(fila_form, placeholder_text="Límite mensual $", width=170, height=32)
        self.e_pres_limite.pack(side="left", padx=5)
        ctk.CTkButton(fila_form, text="Guardar límite", width=130, fg_color="#3B82F6",
                      hover_color="#2563EB", command=self.guardar_presupuesto).pack(side="left", padx=5)

        # Lista sin scroll propio: crece con el contenido y la página scrollea
        self.lista_presupuestos = ctk.CTkFrame(self.frame_presupuestos, fg_color="transparent")
        self.lista_presupuestos.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        # =========================================================
        # PANEL: PLAN DE PAGO DE TARJETAS (AVALANCHA vs BOLA DE NIEVE)
        # =========================================================
        self.frame_plan = ctk.CTkFrame(self.pagina)
        self.frame_plan.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")

        ctk.CTkLabel(self.frame_plan, text="Plan de Pago de Tarjetas de Crédito",
                     font=("Urbanist", 18, "bold"), text_color="#EF4444").pack(anchor="w", padx=15, pady=(12, 2))
        ctk.CTkLabel(self.frame_plan,
                     text="Captura el CAT/tasa anual de cada tarjeta y cuánto puedes abonar al mes. Las deudas MSI al 0% no entran: prepagarlas no ahorra intereses.",
                     font=("Urbanist", 11), text_color="#94A3B8", wraplength=900, justify="left").pack(anchor="w", padx=15, pady=(0, 6))

        self.frame_tarjetas_plan = ctk.CTkFrame(self.frame_plan, fg_color="transparent")
        self.frame_tarjetas_plan.pack(fill="x", padx=15)

        fila_abono = ctk.CTkFrame(self.frame_plan, fg_color="transparent")
        fila_abono.pack(fill="x", padx=15, pady=6)
        ctk.CTkLabel(fila_abono, text="Abono mensual disponible:", font=("Urbanist", 13)).pack(side="left")
        self.e_abono_plan = ctk.CTkEntry(fila_abono, placeholder_text="$ al mes", width=140, height=32)
        self.e_abono_plan.pack(side="left", padx=8)
        ctk.CTkButton(fila_abono, text="Calcular estrategia", width=160, fg_color="#EF4444",
                      hover_color="#DC2626", font=("Urbanist", 12, "bold"),
                      command=self.calcular_plan_deuda).pack(side="left", padx=8)

        self.txt_plan = ctk.CTkTextbox(self.frame_plan, font=("Courier New", 12), height=260,
                                        fg_color="#0F172A", text_color="#E2E8F0")
        self.txt_plan.pack(fill="both", expand=True, padx=15, pady=(4, 15))

        # =========================================================
        # PANEL: METAS DE AHORRO (progreso = saldo de la cuenta vinculada)
        # =========================================================
        self.frame_metas = ctk.CTkFrame(self.pagina)
        self.frame_metas.grid(row=3, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="nsew")

        ctk.CTkLabel(self.frame_metas, text="🎯 Metas de Ahorro",
                     font=("Urbanist", 18, "bold"), text_color="#10B981").pack(anchor="w", padx=15, pady=(12, 2))
        ctk.CTkLabel(self.frame_metas,
                     text="El progreso se mide con el saldo de la cuenta vinculada (ej. tus Cajitas). La proyección usa tu aporte neto de los últimos 90 días.",
                     font=("Urbanist", 11), text_color="#94A3B8", wraplength=900, justify="left").pack(anchor="w", padx=15, pady=(0, 6))

        fila_meta = ctk.CTkFrame(self.frame_metas, fg_color="transparent")
        fila_meta.pack(fill="x", padx=15, pady=(0, 6))
        self.e_meta_nombre = ctk.CTkEntry(fila_meta, placeholder_text="Meta (ej: Fondo de emergencia)", width=230, height=32)
        self.e_meta_nombre.pack(side="left", padx=(0, 5))
        self.e_meta_objetivo = ctk.CTkEntry(fila_meta, placeholder_text="Objetivo $", width=120, height=32)
        self.e_meta_objetivo.pack(side="left", padx=5)
        self.c_meta_cuenta = ctk.CTkOptionMenu(fila_meta, values=["(sin cuentas)"], width=160)
        self.c_meta_cuenta.pack(side="left", padx=5)
        ctk.CTkButton(fila_meta, text="Crear meta", width=110, fg_color="#10B981",
                      hover_color="#059669", command=self.crear_meta).pack(side="left", padx=5)

        self.lista_metas = ctk.CTkFrame(self.frame_metas, fg_color="transparent")
        self.lista_metas.pack(fill="both", expand=True, padx=10, pady=(0, 12))

    # --- Lógica de UI ---
    def actualizar_label_slider(self, value):
        self.lbl_slider.configure(text=f"Meta de Reducción: {int(value)}%")

    # --- Lógica de Base de Datos y MSI ---
    def actualizar_categorias(self):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT categoria FROM gastos")
        cats_db = [row[0] for row in cursor.fetchall()]
        conn.close()
        # Catálogo completo de Tesorería + categorías históricas que ya no estén en él
        cats = list(CATEGORIAS_GASTOS) + [c for c in cats_db if c not in CATEGORIAS_GASTOS]
        cats = [c for c in cats if c != CATEGORIA_AHORRO]  # ahorrar no es consumo simulable
        self.menu_cat.configure(values=cats)
        if self.var_cat.get() not in cats:
            self.var_cat.set(cats[0])

    def guardar_msi(self):
        desc = self.e_msi_desc.get().strip()
        try:
            monto_total = float(self.e_msi_monto.get().strip())
            meses_totales = int(self.e_msi_meses.get().strip())
            tasa_txt = self.e_msi_tasa.get().strip()
            tasa_anual = float(tasa_txt) if tasa_txt else 0.0
            if monto_total <= 0 or meses_totales <= 0 or tasa_anual < 0: raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Ingresa números válidos y mayores a cero en los montos financieros.")
            return

        if tasa_anual > 0:
            # Amortización francesa: M = P·r / (1 - (1+r)^-n), con r mensual
            r = tasa_anual / 100.0 / 12.0
            mensualidad = monto_total * r / (1 - (1 + r) ** -meses_totales)
        else:
            mensualidad = monto_total / meses_totales

        conn = sqlite3.connect("data.db")
        conn.cursor().execute("""
            INSERT INTO deudas_msi (desc, monto_total, mensualidad, meses_totales, meses_pagados, tasa_interes)
            VALUES (?,?,?,?,0,?)
        """, (desc, monto_total, mensualidad, meses_totales, tasa_anual))
        conn.commit()
        conn.close()

        self.e_msi_desc.delete(0, 'end')
        self.e_msi_monto.delete(0, 'end')
        self.e_msi_meses.delete(0, 'end')
        self.e_msi_tasa.delete(0, 'end')
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
        if not messagebox.askyesno("Confirmar", "¿Eliminar esta deuda y su progreso de pagos?"):
            return
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("DELETE FROM deudas_msi WHERE id=?", (msi_id,))
        conn.commit()
        conn.close()
        self.actualizar_msi()

    def actualizar_msi(self):
        for w in self.lista_msi.winfo_children(): w.destroy()

        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, desc, mensualidad, meses_totales, meses_pagados, monto_total, COALESCE(tasa_interes, 0) FROM deudas_msi")

        for mid, d, men, mt, mp, monto_total, tasa in cursor.fetchall():
            row = ctk.CTkFrame(self.lista_msi, fg_color="#1e293b")
            row.pack(fill="x", pady=5, padx=4)

            if tasa > 0:
                costo_total = men * mt
                intereses = costo_total - (monto_total or 0)
                info_texto = (f"🟣 {d}\n${men:,.2f}/mes · {mp}/{mt} meses\n"
                              f"{tasa:g}% anual · int. ${intereses:,.0f}")
            else:
                info_texto = f"🟣 {d}\n${men:,.2f}/mes · {mp}/{mt} meses\nMSI 0%"
            # Botones primero: si el espacio aprieta, se trunca el texto, no los controles
            btn_frame = ctk.CTkFrame(row, fg_color="transparent")
            btn_frame.pack(side="right", padx=8, pady=4)

            ctk.CTkButton(btn_frame, text="Abonar 1 Mes", width=95, fg_color="#10B981", hover_color="#059669", font=("Urbanist", 10), command=lambda i=mid, p=mp, t=mt: self.abonar_msi(i, p, t)).pack(pady=2)
            ctk.CTkButton(btn_frame, text="Eliminar", width=95, fg_color="#EF4444", hover_color="#DC2626", font=("Urbanist", 10), command=lambda i=mid: self.eliminar_msi(i)).pack(pady=2)

            ctk.CTkLabel(row, text=info_texto, font=("Urbanist", 13), justify="left",
                         anchor="w").pack(side="left", padx=12, pady=8, fill="x", expand=True)
            
        conn.close()

    # =========================================================
    # PRESUPUESTOS: CRUD Y SEMÁFORO DE CONSUMO MENSUAL
    # =========================================================
    def guardar_presupuesto(self, categoria=None, limite=None):
        if categoria is None:
            categoria = self.c_pres_cat.get()
            try:
                limite = float(self.e_pres_limite.get().strip())
                if limite <= 0: raise ValueError
            except ValueError:
                messagebox.showerror("Error", "El límite debe ser un número mayor a cero.")
                return
            self.e_pres_limite.delete(0, 'end')

        conn = sqlite3.connect("data.db")
        conn.cursor().execute("INSERT OR REPLACE INTO presupuestos (categoria, limite) VALUES (?, ?)", (categoria, limite))
        conn.commit()
        conn.close()
        self.actualizar_presupuestos()

    def adoptar_presupuesto(self):
        if not self.ultima_simulacion:
            return
        categoria, tope = self.ultima_simulacion
        self.guardar_presupuesto(categoria, round(tope, 2))
        messagebox.showinfo("Presupuesto Adoptado",
                            f"Límite mensual de '{categoria}' fijado en ${tope:,.2f}.\nLo verás en el semáforo y en los avisos de Tesorería.")

    def eliminar_presupuesto(self, categoria):
        if not messagebox.askyesno("Confirmar", f"¿Eliminar el presupuesto de '{categoria}'?"):
            return
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("DELETE FROM presupuestos WHERE categoria=?", (categoria,))
        conn.commit()
        conn.close()
        self.actualizar_presupuestos()

    def actualizar_presupuestos(self):
        for w in self.lista_presupuestos.winfo_children(): w.destroy()

        mes_actual = datetime.now().strftime("%Y-%m")
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.categoria, p.limite,
                   COALESCE((SELECT SUM(g.monto) FROM gastos g
                             WHERE g.categoria = p.categoria AND strftime('%Y-%m', g.fecha) = ?), 0)
            FROM presupuestos p ORDER BY p.categoria
        """, (mes_actual,))
        filas = cursor.fetchall()

        # Cumplimiento histórico: usa los límites ACTUALES sobre meses cerrados
        # (no hay historial de límites; simplificación documentada)
        cursor.execute("SELECT categoria, strftime('%Y-%m', fecha), COALESCE(SUM(monto), 0) FROM gastos GROUP BY 1, 2")
        gasto_mensual = {(cat, mes): tot for cat, mes, tot in cursor.fetchall()}
        cursor.execute("SELECT MIN(strftime('%Y-%m', fecha)) FROM gastos")
        primer_mes = cursor.fetchone()[0]
        conn.close()

        def calcular_racha(cat, limite):
            """Meses cerrados consecutivos cumpliendo (gasto 0 cuenta como cumplido)."""
            if not primer_mes:
                return 0
            racha, m = 0, mes_anterior(mes_actual)
            while m >= primer_mes and gasto_mensual.get((cat, m), 0) <= limite:
                racha += 1
                m = mes_anterior(m)
            return racha

        mes_pasado = mes_anterior(mes_actual)
        if filas and primer_mes and mes_pasado >= primer_mes:
            cumplidas = sum(1 for cat, lim, _g in filas if gasto_mensual.get((cat, mes_pasado), 0) <= lim)
            self.lbl_cumplimiento.configure(
                text=f"Mes pasado ({mes_pasado}): {cumplidas}/{len(filas)} categorías dentro del presupuesto")
        else:
            self.lbl_cumplimiento.configure(text="")

        if not filas:
            ctk.CTkLabel(self.lista_presupuestos,
                         text="Sin presupuestos definidos. Fija un límite arriba o adóptalo desde el simulador.",
                         text_color="#64748B", font=("Urbanist", 12)).pack(pady=15)
            return

        for categoria, limite, gastado in filas:
            uso = gastado / limite if limite > 0 else 0
            if uso < 0.8: color = "#10B981"
            elif uso <= 1.0: color = "#F59E0B"
            else: color = "#EF4444"

            row = ctk.CTkFrame(self.lista_presupuestos, fg_color="#1e293b")
            row.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(row, text=categoria, font=("Urbanist", 13, "bold"), width=130, anchor="w").pack(side="left", padx=(12, 5), pady=10)
            barra = ctk.CTkProgressBar(row, progress_color=color, width=260, height=14)
            barra.set(min(uso, 1.0))
            barra.pack(side="left", padx=8, fill="x", expand=True)
            ctk.CTkLabel(row, text=f"${gastado:,.0f} / ${limite:,.0f}  ({uso*100:.0f}%)",
                         font=("Urbanist", 13), text_color=color, width=200).pack(side="left", padx=8)
            racha = calcular_racha(categoria, limite)
            ctk.CTkLabel(row, text=f"🔥 {racha}m" if racha else "· 0m",
                         font=("Urbanist", 12, "bold"),
                         text_color="#F59E0B" if racha else "#475569", width=60).pack(side="left", padx=4)
            ctk.CTkButton(row, text="🗑", width=30, fg_color="#EF4444", hover_color="#DC2626",
                          command=lambda c=categoria: self.eliminar_presupuesto(c)).pack(side="right", padx=10)

    # =========================================================
    # PLAN DE PAGO DE TARJETAS
    # =========================================================
    def obtener_tarjetas_con_deuda(self):
        import database
        return [(cid, nombre, tasa, -saldo)
                for cid, nombre, tipo, tasa, saldo in database.obtener_saldos_cuentas()
                if tipo == "Crédito" and saldo < -0.01]  # deuda en positivo

    def actualizar_plan_deuda(self):
        for w in self.frame_tarjetas_plan.winfo_children(): w.destroy()
        self.entries_tasa = {}

        tarjetas = self.obtener_tarjetas_con_deuda()
        if not tarjetas:
            ctk.CTkLabel(self.frame_tarjetas_plan,
                         text="Sin deuda de tarjetas 🎉 (o sin cuentas de crédito con saldo negativo).",
                         text_color="#10B981", font=("Urbanist", 13)).pack(pady=10)
            return

        for cid, nombre, tasa, deuda in tarjetas:
            fila = ctk.CTkFrame(self.frame_tarjetas_plan, fg_color="#1e293b")
            fila.pack(fill="x", pady=3)
            ctk.CTkLabel(fila, text=f"💳 {nombre} — deuda ${deuda:,.2f}",
                         font=("Urbanist", 13, "bold"), anchor="w").pack(side="left", padx=12, pady=8)
            entry = ctk.CTkEntry(fila, width=90, height=30)
            entry.insert(0, f"{tasa:g}")
            entry.pack(side="right", padx=(4, 12))
            ctk.CTkLabel(fila, text="CAT/tasa anual %:", font=("Urbanist", 12),
                         text_color="#94A3B8").pack(side="right")
            self.entries_tasa[cid] = entry

    def calcular_plan_deuda(self):
        tarjetas = self.obtener_tarjetas_con_deuda()
        if not tarjetas:
            return
        try:
            abono = float(self.e_abono_plan.get().strip())
            if abono <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Captura cuánto puedes abonar al mes (número positivo).")
            return

        # Persistir las tasas capturadas
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        deudas = []
        for cid, nombre, _tasa_vieja, deuda in tarjetas:
            try:
                tasa = float(self.entries_tasa[cid].get().strip() or 0)
                if tasa < 0: raise ValueError
            except ValueError:
                conn.close()
                messagebox.showerror("Error", f"Tasa inválida en {nombre}.")
                return
            cursor.execute("UPDATE cuentas SET tasa_anual=? WHERE id=?", (tasa, cid))
            deudas.append((nombre, deuda, tasa))
        conn.commit()
        conn.close()

        deuda_total = sum(d for _, d, _ in deudas)
        interes_mensual_hoy = sum(d * t / 100.0 / 12.0 for _, d, t in deudas)

        avalancha = sorted(deudas, key=lambda x: x[2], reverse=True)   # mayor tasa primero
        nieve = sorted(deudas, key=lambda x: x[1])                     # menor saldo primero
        res_av = simular_pago_deuda(avalancha, abono)
        res_ni = simular_pago_deuda(nieve, abono)

        L = []
        L.append("=== PLAN DE PAGO DE TARJETAS ===")
        L.append(f"Deuda total: ${deuda_total:,.2f}  |  Abono: ${abono:,.2f}/mes")
        L.append(f"Cargar estos saldos te cuesta HOY: ${interes_mensual_hoy:,.2f}/mes en intereses")
        L.append("")
        if res_av is None:
            L.append("[!] ABONO INSUFICIENTE: no alcanza a vencer los intereses.")
            L.append(f"    Necesitas abonar más de ${interes_mensual_hoy:,.2f}/mes solo para no crecer.")
        else:
            def describir(nombre_estrategia, orden, resultado):
                meses, intereses = resultado
                secuencia = " → ".join(f"{n} ({t:g}%)" for n, _, t in orden)
                anio = datetime.now().year + (datetime.now().month - 1 + meses) // 12
                mes_fin = (datetime.now().month - 1 + meses) % 12 + 1
                L.append(f"{nombre_estrategia}")
                L.append(f"  Orden de ataque: {secuencia}")
                L.append(f"  Libre de deuda en {meses} meses (≈ {anio}-{mes_fin:02d})")
                L.append(f"  Intereses totales pagados: ${intereses:,.2f}")
                L.append("")

            describir("AVALANCHA (mayor tasa primero — óptimo matemático)", avalancha, res_av)
            describir("BOLA DE NIEVE (menor saldo primero — óptimo psicológico)", nieve, res_ni)

            ahorro = res_ni[1] - res_av[1]
            if ahorro > 1:
                L.append(f">>> La avalancha te ahorra ${ahorro:,.2f} en intereses.")
            else:
                L.append(">>> Con tus números, ambas estrategias cuestan casi lo mismo:")
                L.append("    elige bola de nieve si necesitas victorias rápidas.")
            if all(t == 0 for _, _, t in deudas):
                L.append("")
                L.append("[i] Todas tus tasas están en 0%. Captura el CAT real de cada")
                L.append("    tarjeta (viene en tu estado de cuenta) para un plan realista.")

        self.txt_plan.delete("1.0", "end")
        self.txt_plan.insert("1.0", "\n".join(L))

    # =========================================================
    # METAS DE AHORRO
    # =========================================================
    def medalla_meta(self, pct):
        if pct >= 100: return "🏆"
        if pct >= 75: return "🥇"
        if pct >= 50: return "🥈"
        if pct >= 25: return "🥉"
        return "🎯"

    def crear_meta(self):
        import database
        nombre = self.e_meta_nombre.get().strip()
        try:
            objetivo = float(self.e_meta_objetivo.get().strip())
            if objetivo <= 0: raise ValueError
        except ValueError:
            messagebox.showerror("Error", "El objetivo debe ser un número mayor a cero.")
            return
        if not nombre:
            messagebox.showerror("Error", "Ponle nombre a la meta.")
            return
        cuentas = {nombre_c: cid for cid, nombre_c, _t, _ta, _s in database.obtener_saldos_cuentas()}
        cuenta_id = cuentas.get(self.c_meta_cuenta.get())
        if cuenta_id is None:
            messagebox.showerror("Error", "Vincula la meta a una cuenta (créala en Tesorería si falta).")
            return

        conn = sqlite3.connect("data.db")
        conn.cursor().execute("INSERT INTO metas (nombre, monto_objetivo, cuenta_id, activo) VALUES (?,?,?,1)",
                              (nombre, objetivo, cuenta_id))
        conn.commit()
        conn.close()
        self.e_meta_nombre.delete(0, 'end')
        self.e_meta_objetivo.delete(0, 'end')
        self.actualizar_metas()

    def editar_meta(self, meta_id):
        conn = sqlite3.connect("data.db")
        fila = conn.cursor().execute("SELECT nombre, monto_objetivo FROM metas WHERE id=?", (meta_id,)).fetchone()
        conn.close()
        if not fila:
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Editar Meta")
        dialog.geometry("340x220")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Nombre:", font=("Urbanist", 11), text_color="#94A3B8").pack(pady=(12, 0), padx=20, anchor="w")
        e_nom = ctk.CTkEntry(dialog)
        e_nom.insert(0, fila[0])
        e_nom.pack(pady=2, padx=20, fill="x")
        ctk.CTkLabel(dialog, text="Objetivo $:", font=("Urbanist", 11), text_color="#94A3B8").pack(padx=20, anchor="w")
        e_obj = ctk.CTkEntry(dialog)
        e_obj.insert(0, f"{fila[1]:g}")
        e_obj.pack(pady=2, padx=20, fill="x")

        def guardar_edicion():
            try:
                objetivo = float(e_obj.get().strip())
                if objetivo <= 0: raise ValueError
            except ValueError:
                messagebox.showerror("Error", "El objetivo debe ser mayor a cero.", parent=dialog)
                return
            nombre = e_nom.get().strip()
            if not nombre:
                messagebox.showerror("Error", "Ponle nombre.", parent=dialog)
                return
            conn = sqlite3.connect("data.db")
            conn.cursor().execute("UPDATE metas SET nombre=?, monto_objetivo=? WHERE id=?", (nombre, objetivo, meta_id))
            conn.commit()
            conn.close()
            dialog.destroy()
            self.actualizar_metas()

        ctk.CTkButton(dialog, text="Guardar cambios", fg_color="#3B82F6", hover_color="#2563EB",
                      command=guardar_edicion).pack(pady=14, padx=20, fill="x")

    def eliminar_meta(self, meta_id):
        if not messagebox.askyesno("Confirmar", "¿Eliminar esta meta? (La cuenta y su dinero no se tocan)"):
            return
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("DELETE FROM metas WHERE id=?", (meta_id,))
        conn.commit()
        conn.close()
        self.actualizar_metas()

    def actualizar_metas(self):
        import database
        for w in self.lista_metas.winfo_children(): w.destroy()

        nombres_cuentas = [n for _c, n, _t, _ta, _s in database.obtener_saldos_cuentas()]
        if nombres_cuentas:
            actual = self.c_meta_cuenta.get()
            self.c_meta_cuenta.configure(values=nombres_cuentas)
            if actual not in nombres_cuentas:
                self.c_meta_cuenta.set(nombres_cuentas[0])

        metas = database.obtener_metas_con_progreso()
        if not metas:
            ctk.CTkLabel(self.lista_metas, text="Sin metas activas. Sugerencia: 'Fondo de emergencia' = 3× tu gasto adverso mensual.",
                         text_color="#64748B", font=("Urbanist", 12)).pack(pady=10)
            return

        for mid, nombre, objetivo, cta, saldo, aporte, _fecha_lim in metas:
            pct = max(0.0, saldo / objetivo * 100) if objetivo > 0 else 0
            restante = objetivo - saldo

            row = ctk.CTkFrame(self.lista_metas, fg_color="#1e293b")
            row.pack(fill="x", pady=4, padx=4)
            ctk.CTkButton(row, text="🗑", width=30, fg_color="#EF4444", hover_color="#DC2626",
                          command=lambda i=mid: self.eliminar_meta(i)).pack(side="right", padx=10)
            ctk.CTkButton(row, text="✏", width=30, fg_color="#3B82F6", hover_color="#2563EB",
                          command=lambda i=mid: self.editar_meta(i)).pack(side="right")

            ctk.CTkLabel(row, text=f"{self.medalla_meta(pct)} {nombre} ({cta})",
                         font=("Urbanist", 13, "bold"), width=260, anchor="w").pack(side="left", padx=(12, 5), pady=10)
            barra = ctk.CTkProgressBar(row, progress_color="#10B981" if pct < 100 else "#FBBF24", width=220, height=14)
            barra.set(min(pct / 100, 1.0))
            barra.pack(side="left", padx=8, fill="x", expand=True)

            if pct >= 100:
                detalle = f"¡Cumplida! ${saldo:,.0f} / ${objetivo:,.0f} 🎉"
                color_detalle = "#FBBF24"
            elif aporte > 0:
                meses_restantes = int(np.ceil(restante / aporte))
                anio = datetime.now().year + (datetime.now().month - 1 + meses_restantes) // 12
                mes_f = (datetime.now().month - 1 + meses_restantes) % 12 + 1
                detalle = f"{pct:.0f}% · faltan ${restante:,.0f} · ≈ {anio}-{mes_f:02d} (+${aporte:,.0f}/mes)"
                color_detalle = "#94A3B8"
            else:
                detalle = f"{pct:.0f}% · faltan ${restante:,.0f} · sin aportes netos recientes"
                color_detalle = "#EF4444"
            ctk.CTkLabel(row, text=detalle, font=("Urbanist", 12), text_color=color_detalle,
                         width=320, anchor="w").pack(side="left", padx=8)

    def actualizar(self):
        """Punto de entrada del dispatch de main.py al cambiar a esta pestaña."""
        self.actualizar_msi()
        self.actualizar_categorias()
        self.actualizar_presupuestos()
        self.actualizar_plan_deuda()
        self.actualizar_metas()

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
        cursor.execute("SELECT strftime('%Y-%m', fecha) as periodo, SUM(monto) FROM gastos WHERE categoria != ? GROUP BY periodo ORDER BY periodo ASC", (CATEGORIA_AHORRO,))
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

        # Habilitar el compromiso: convertir el escenario simulado en presupuesto real
        self.ultima_simulacion = (categoria, presupuesto_tope)
        self.btn_adoptar.configure(state="normal", fg_color="#10B981", hover_color="#059669",
                                    text=f"Adoptar ${presupuesto_tope:,.0f}/mes para {categoria}")
        
        # --- Renderizado de Matplotlib ---
        fig, ax = plt.subplots(figsize=(5.9, 4.2), dpi=95)
        fig.patch.set_facecolor('#0f172a')
        fig.subplots_adjust(bottom=0.17, left=0.13, top=0.86, right=0.97)
        ax.set_facecolor('#0f172a')
        ax.tick_params(colors='white', labelsize=10)
        for spine in ax.spines.values(): spine.set_color('#334155')

        # Graficamos el diferencial de trayectorias
        ax.plot(np.append(x_vals, next_x), tendencia_orig, color="#EF4444", linestyle="--", linewidth=2, label="Trayectoria Actual")
        ax.plot(np.append(x_vals, next_x), tendencia_sim, color="#10B981", linestyle="-", linewidth=3, label="Trayectoria Optimizada")

        ax.set_xticks(list(x_vals) + [next_x])
        ax.set_xticklabels(periodos + ["+1"], rotation=25, ha="right")

        # Título corto; los números accionables van en la etiqueta bajo la gráfica
        ax.set_title(f"Recorte del {int(reduccion*100)}% en {categoria}",
                     color="white", fontsize=12, fontweight="bold", pad=10)
        ax.legend(facecolor='#1e293b', edgecolor='none', labelcolor='white', fontsize=10, loc="lower left")
        self.lbl_resultado_sim.configure(
            text=f"Meta a no gastar: ${meta_monetaria_ahorro:,.0f}\nTu nuevo límite mensual: ${presupuesto_tope:,.0f}")
        ax.grid(True, linestyle=":", alpha=0.15)
        
        canvas = FigureCanvasTkAgg(fig, master=self.canvas_sim_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True) 
