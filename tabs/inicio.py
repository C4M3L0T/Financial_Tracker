import customtkinter as ctk
import database
import numpy as np
from datetime import datetime
from database import CATEGORIA_AHORRO, CATEGORIAS_NECESIDAD


def mes_previo(mes):
    """'2026-07' → '2026-06'"""
    anio, m = map(int, mes.split("-"))
    m -= 1
    if m == 0:
        anio, m = anio - 1, 12
    return f"{anio:04d}-{m:02d}"

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


class InicioTab(ctk.CTkFrame):
    """Resumen del día: las 4 cifras clave + lo que requiere atención + agenda de hoy.
    Responde '¿cómo voy?' sin recorrer las 7 pestañas."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.setup_ui()
        self.actualizar()

    def setup_ui(self):
        hoy = datetime.now()
        titulo = f"{DIAS[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1]} de {hoy.year}"
        ctk.CTkLabel(self, text=f"📍 {titulo}", font=("Urbanist", 20, "bold"),
                     text_color="#38BDF8").pack(pady=(15, 6))

        # --- Score de salud financiera ---
        self.frame_score = ctk.CTkFrame(self, fg_color="#1e293b")
        self.frame_score.pack(fill="x", padx=15, pady=(0, 6))
        self.lbl_score = ctk.CTkLabel(self.frame_score, text="Salud Financiera: —",
                                       font=("Urbanist", 18, "bold"), text_color="#94A3B8")
        self.lbl_score.pack(pady=(10, 0))
        self.lbl_score_detalle = ctk.CTkLabel(self.frame_score, text="",
                                               font=("Urbanist", 11), text_color="#94A3B8")
        self.lbl_score_detalle.pack(pady=(0, 10))

        # --- Fila de 4 tarjetas clave ---
        self.frame_tarjetas = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_tarjetas.pack(fill="x", padx=15)
        for i in range(4):
            self.frame_tarjetas.grid_columnconfigure(i, weight=1, uniform="tarjetas")

        self.card_neto = self.crear_tarjeta(0, "Neto en cuentas")
        self.card_gasto = self.crear_tarjeta(1, "Consumo del mes")
        self.card_deuda = self.crear_tarjeta(2, "Deudas / mes")
        self.card_runway = self.crear_tarjeta(3, "Runway conservador")

        # --- Regla 50/30/20 ---
        self.frame_regla = ctk.CTkFrame(self)
        self.frame_regla.pack(fill="x", padx=15, pady=(12, 0))
        self.lbl_regla_titulo = ctk.CTkLabel(self.frame_regla, text="⚖ Regla 50/30/20",
                                              font=("Urbanist", 16, "bold"), text_color="#38BDF8")
        self.lbl_regla_titulo.pack(anchor="w", padx=15, pady=(10, 2))
        self.lista_regla = ctk.CTkFrame(self.frame_regla, fg_color="transparent")
        self.lista_regla.pack(fill="x", padx=15, pady=(0, 10))

        # --- Atención ---
        self.frame_atencion = ctk.CTkFrame(self)
        self.frame_atencion.pack(fill="x", padx=15, pady=(12, 0))
        ctk.CTkLabel(self.frame_atencion, text="🔔 Atención", font=("Urbanist", 16, "bold"),
                     text_color="#F59E0B").pack(anchor="w", padx=15, pady=(10, 2))
        self.lista_atencion = ctk.CTkFrame(self.frame_atencion, fg_color="transparent")
        self.lista_atencion.pack(fill="x", padx=15, pady=(0, 10))

        # --- Metas ---
        self.frame_metas = ctk.CTkFrame(self)
        self.frame_metas.pack(fill="x", padx=15, pady=(12, 0))
        ctk.CTkLabel(self.frame_metas, text="🎯 Metas", font=("Urbanist", 16, "bold"),
                     text_color="#10B981").pack(anchor="w", padx=15, pady=(10, 2))
        self.lista_metas = ctk.CTkFrame(self.frame_metas, fg_color="transparent")
        self.lista_metas.pack(fill="x", padx=15, pady=(0, 10))

        # --- Hoy ---
        self.frame_hoy = ctk.CTkFrame(self)
        self.frame_hoy.pack(fill="both", expand=True, padx=15, pady=(12, 15))
        ctk.CTkLabel(self.frame_hoy, text="📌 Hoy", font=("Urbanist", 16, "bold"),
                     text_color="#10B981").pack(anchor="w", padx=15, pady=(10, 2))
        self.lista_hoy = ctk.CTkFrame(self.frame_hoy, fg_color="transparent")
        self.lista_hoy.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    def crear_tarjeta(self, columna, titulo):
        frame = ctk.CTkFrame(self.frame_tarjetas, fg_color="#1e293b")
        frame.grid(row=0, column=columna, padx=5, sticky="nsew")
        ctk.CTkLabel(frame, text=titulo, font=("Urbanist", 12), text_color="#94A3B8",
                     wraplength=220).pack(pady=(12, 2), padx=12)
        lbl_valor = ctk.CTkLabel(frame, text="—", font=("Urbanist", 20, "bold"), text_color="#E2E8F0")
        lbl_valor.pack(padx=12)
        lbl_sub = ctk.CTkLabel(frame, text="", font=("Urbanist", 11), text_color="#64748B",
                                wraplength=220, justify="center")
        lbl_sub.pack(pady=(0, 12), padx=12)
        return lbl_valor, lbl_sub

    # =========================================================
    # DATOS
    # =========================================================
    def actualizar(self):
        hoy_str = datetime.now().strftime("%Y-%m-%d")
        mes_actual = datetime.now().strftime("%Y-%m")
        conn = database.conectar()
        cursor = conn.cursor()

        # --- Tarjeta 1: neto en cuentas (líquido − tarjetas) ---
        saldos = [(tipo, saldo) for _cid, _n, tipo, _t, saldo in database.obtener_saldos_cuentas()]
        if saldos:
            liquido = sum(s for tipo, s in saldos if tipo != "Crédito")
            credito = sum(s for tipo, s in saldos if tipo == "Crédito")
            neto = liquido + credito
            self.card_neto[0].configure(text=f"${neto:,.2f}",
                                         text_color="#10B981" if neto >= 0 else "#EF4444")
            self.card_neto[1].configure(text=f"líquido ${liquido:,.0f}\ntarjetas ${credito:,.0f}")
        else:
            self.card_neto[0].configure(text="—", text_color="#64748B")
            self.card_neto[1].configure(text="crea tus cuentas en Tesorería")

        # --- Tarjeta 2: consumo del mes vs presupuesto total ---
        cursor.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE LEFT(fecha, 7)=? AND categoria != ?",
                       (mes_actual, CATEGORIA_AHORRO))
        consumo_mes = cursor.fetchone()[0]
        cursor.execute("SELECT COALESCE(SUM(limite),0) FROM presupuestos WHERE categoria != ?", (CATEGORIA_AHORRO,))
        presupuesto_total = cursor.fetchone()[0]
        if presupuesto_total > 0:
            uso = consumo_mes / presupuesto_total
            color = "#10B981" if uso < 0.8 else ("#F59E0B" if uso <= 1.0 else "#EF4444")
            self.card_gasto[0].configure(text=f"${consumo_mes:,.2f}", text_color=color)
            self.card_gasto[1].configure(text=f"presupuesto ${presupuesto_total:,.0f}\n({uso*100:.0f}% usado)")
        else:
            self.card_gasto[0].configure(text=f"${consumo_mes:,.2f}", text_color="#E2E8F0")
            self.card_gasto[1].configure(text="sin presupuestos definidos")

        # --- Tarjeta 3: compromiso mensual de deudas ---
        cursor.execute("SELECT COALESCE(SUM(mensualidad),0), COUNT(*) FROM deudas_msi WHERE meses_pagados < meses_totales")
        compromiso, num_deudas = cursor.fetchone()
        self.card_deuda[0].configure(text=f"${compromiso:,.2f}",
                                      text_color="#A855F7" if compromiso > 0 else "#10B981")
        self.card_deuda[1].configure(text=f"{num_deudas} deuda(s) activa(s)" if num_deudas else "sin deudas a plazos 🎉")

        # --- Tarjeta 4: runway conservador (liquidez / gasto adverso VaR95) ---
        cursor.execute("""
            SELECT SUM(monto) FROM gastos WHERE categoria != ?
            GROUP BY LEFT(fecha, 7) ORDER BY LEFT(fecha, 7)
        """, (CATEGORIA_AHORRO,))
        serie = [r[0] for r in cursor.fetchall()]
        liquido_total = sum(s for tipo, s in saldos if tipo != "Crédito") if saldos else 0.0
        runway_conservador = None
        if len(serie) >= 2 and liquido_total > 0:
            mu, sigma = float(np.mean(serie)), float(np.std(serie))
            var95 = mu + 1.96 * sigma
            runway_conservador = liquido_total / var95 if var95 > 0 else 0
            color = "#EF4444" if runway_conservador < 3 else ("#F59E0B" if runway_conservador < 6 else "#10B981")
            self.card_runway[0].configure(text=f"{runway_conservador:.1f} meses", text_color=color)
            self.card_runway[1].configure(text=f"gasto adverso\n${var95:,.0f}/mes")
        else:
            self.card_runway[0].configure(text="—", text_color="#64748B")
            self.card_runway[1].configure(text="necesita cuentas y\n≥2 meses de datos")

        # --- Regla 50/30/20: mes con ingresos más reciente ---
        for w in self.lista_regla.winfo_children(): w.destroy()
        mes_regla = mes_actual
        cursor.execute("SELECT COALESCE(SUM(monto),0) FROM ingresos WHERE LEFT(fecha, 7)=?", (mes_regla,))
        ingreso_regla = cursor.fetchone()[0]
        if ingreso_regla <= 0:
            mes_regla = mes_previo(mes_actual)
            cursor.execute("SELECT COALESCE(SUM(monto),0) FROM ingresos WHERE LEFT(fecha, 7)=?", (mes_regla,))
            ingreso_regla = cursor.fetchone()[0]

        if ingreso_regla <= 0:
            self.lbl_regla_titulo.configure(text="⚖ Regla 50/30/20")
            ctk.CTkLabel(self.lista_regla, text="Captura ingresos para ver tu distribución.",
                         font=("Urbanist", 12), text_color="#64748B").pack(anchor="w", pady=1)
        else:
            marcadores = ",".join("?" * len(CATEGORIAS_NECESIDAD))
            cursor.execute(f"""SELECT COALESCE(SUM(monto),0) FROM gastos
                               WHERE LEFT(fecha, 7)=? AND categoria IN ({marcadores})""",
                           (mes_regla, *CATEGORIAS_NECESIDAD))
            necesidades = cursor.fetchone()[0]
            cursor.execute(f"""SELECT COALESCE(SUM(monto),0) FROM gastos
                               WHERE LEFT(fecha, 7)=? AND categoria NOT IN ({marcadores}) AND categoria != ?""",
                           (mes_regla, *CATEGORIAS_NECESIDAD, CATEGORIA_AHORRO))
            deseos = cursor.fetchone()[0]
            ahorro_monto = ingreso_regla - necesidades - deseos
            pct_n = necesidades / ingreso_regla * 100
            pct_d = deseos / ingreso_regla * 100
            pct_a = 100 - pct_n - pct_d

            self.lbl_regla_titulo.configure(
                text=f"⚖ Regla 50/30/20 — {mes_regla} (ingreso ${ingreso_regla:,.0f})")
            renglones = [
                ("Necesidades", pct_n, necesidades, "ideal ≤50%", pct_n <= 50),
                ("Deseos", pct_d, deseos, "ideal ≤30%", pct_d <= 30),
                ("Ahorro (lo que no gastaste)", pct_a, ahorro_monto, "ideal ≥20%", pct_a >= 20),
            ]
            for nombre, pct, monto, ideal, ok in renglones:
                fila = ctk.CTkFrame(self.lista_regla, fg_color="transparent")
                fila.pack(fill="x", pady=1)
                color = "#10B981" if ok else "#EF4444"
                ctk.CTkLabel(fila, text=f"{nombre}: {pct:.0f}% (${monto:,.0f}) · {ideal}",
                             font=("Urbanist", 13), text_color=color, width=380, anchor="w").pack(side="left")
                barra = ctk.CTkProgressBar(fila, progress_color=color, width=250, height=10)
                barra.set(max(0.0, min(pct / 100, 1.0)))
                barra.pack(side="right", padx=10)

        # --- Score de salud financiera (índice compuesto 0-100) ---
        componentes = {}
        if saldos:
            deuda_tarjetas = -sum(s for tipo, s in saldos if tipo == "Crédito" and s < 0)
            if deuda_tarjetas > 0:
                # Razón circulante 2.0 = puntaje perfecto
                componentes["Liquidez"] = min(liquido_total / deuda_tarjetas / 2.0, 1.0) * 100
            else:
                componentes["Liquidez"] = 100.0

        cursor.execute("SELECT activos_liquidos, activos_fijos, pasivos_corto, pasivos_largo FROM balance_general ORDER BY fecha DESC LIMIT 1")
        fila_bal = cursor.fetchone()
        if fila_bal:
            activos_b = fila_bal[0] + fila_bal[1]
            pasivos_b = fila_bal[2] + fila_bal[3]
            if activos_b > 0:
                # Apalancamiento: ≤30% pleno, 80% = cero
                apalancamiento = pasivos_b / activos_b
                componentes["Deuda"] = max(0.0, min((0.8 - apalancamiento) / 0.5, 1.0)) * 100

        if runway_conservador is not None:
            componentes["Colchón"] = min(runway_conservador / 6.0, 1.0) * 100  # 6 meses = pleno

        if ingreso_regla > 0:
            componentes["Ahorro"] = max(0.0, min(pct_a / 20.0, 1.0)) * 100  # 20% = pleno

        cursor.execute("SELECT MIN(LEFT(fecha, 7)) FROM gastos")
        primer_mes = cursor.fetchone()[0]
        mes_pasado_str = mes_previo(mes_actual)
        cursor.execute("""
            SELECT p.limite,
                   COALESCE((SELECT SUM(g.monto) FROM gastos g
                             WHERE g.categoria = p.categoria AND LEFT(g.fecha, 7) = ?), 0)
            FROM presupuestos p WHERE p.limite > 0
        """, (mes_pasado_str,))
        pres_pasado = cursor.fetchall()
        if pres_pasado and primer_mes and mes_pasado_str >= primer_mes:
            componentes["Presupuestos"] = sum(1 for lim, g in pres_pasado if g <= lim) / len(pres_pasado) * 100

        PESOS = {"Liquidez": 0.25, "Deuda": 0.20, "Colchón": 0.25, "Ahorro": 0.15, "Presupuestos": 0.15}
        if componentes:
            peso_total = sum(PESOS[k] for k in componentes)
            score = sum(v * PESOS[k] for k, v in componentes.items()) / peso_total
            color_s = "#10B981" if score >= 75 else ("#F59E0B" if score >= 50 else "#EF4444")
            icono_s = "💚" if score >= 75 else ("🟡" if score >= 50 else "🔴")
            self.lbl_score.configure(text=f"{icono_s} Salud Financiera: {score:.0f}/100", text_color=color_s)
            self.lbl_score_detalle.configure(text="  ·  ".join(f"{k} {v:.0f}" for k, v in componentes.items()))
        else:
            self.lbl_score.configure(text="Salud Financiera: — (faltan datos)", text_color="#64748B")
            self.lbl_score_detalle.configure(text="")

        # --- Atención ---
        for w in self.lista_atencion.winfo_children(): w.destroy()
        avisos = []

        cursor.execute("""
            SELECT p.categoria, p.limite,
                   COALESCE((SELECT SUM(g.monto) FROM gastos g
                             WHERE g.categoria = p.categoria AND LEFT(g.fecha, 7) = ?), 0)
            FROM presupuestos p
        """, (mes_actual,))
        for cat, limite, gastado in cursor.fetchall():
            if limite > 0 and gastado / limite >= 0.8:
                icono = "🚨" if gastado > limite else "⚠️"
                avisos.append((icono, f"{cat}: ${gastado:,.0f} de ${limite:,.0f} ({gastado/limite*100:.0f}%)",
                               "#EF4444" if gastado > limite else "#F59E0B"))

        cursor.execute("SELECT `desc` FROM deudas_msi WHERE meses_totales - meses_pagados = 1")
        for (desc,) in cursor.fetchall():
            avisos.append(("🎉", f"'{desc}': último pago este mes — tu liquidez sube pronto", "#10B981"))

        cursor.execute("SELECT COUNT(*) FROM balance_general WHERE fecha = ?", (mes_actual,))
        if cursor.fetchone()[0] == 0:
            avisos.append(("📋", f"No has cerrado el Balance General de {mes_actual}", "#94A3B8"))

        if not avisos:
            avisos.append(("✅", "Todo en orden", "#10B981"))
        for icono, texto, color in avisos[:5]:
            ctk.CTkLabel(self.lista_atencion, text=f"{icono} {texto}", font=("Urbanist", 13),
                         text_color=color, anchor="w").pack(anchor="w", pady=1)

        # --- Metas ---
        for w in self.lista_metas.winfo_children(): w.destroy()
        metas = database.obtener_metas_con_progreso()
        if not metas:
            ctk.CTkLabel(self.lista_metas, text="Sin metas activas (créalas en Planeación).",
                         font=("Urbanist", 12), text_color="#64748B", anchor="w").pack(anchor="w", pady=1)
        for _mid, nombre, objetivo, _cta, saldo, _aporte, _fl in metas[:4]:
            pct = max(0.0, saldo / objetivo * 100) if objetivo > 0 else 0
            medalla = "🏆" if pct >= 100 else ("🥇" if pct >= 75 else ("🥈" if pct >= 50 else ("🥉" if pct >= 25 else "🎯")))
            fila = ctk.CTkFrame(self.lista_metas, fg_color="transparent")
            fila.pack(fill="x", pady=1)
            ctk.CTkLabel(fila, text=f"{medalla} {nombre}: ${saldo:,.0f} / ${objetivo:,.0f} ({pct:.0f}%)",
                         font=("Urbanist", 13), anchor="w").pack(side="left")
            barra = ctk.CTkProgressBar(fila, progress_color="#10B981", width=180, height=10)
            barra.set(min(pct / 100, 1.0))
            barra.pack(side="right", padx=10)

        # --- Hoy ---
        for w in self.lista_hoy.winfo_children(): w.destroy()
        pendientes = []
        cursor.execute("SELECT hora, tarea FROM agenda WHERE fecha = ? ORDER BY hora", (hoy_str,))
        for hora, tarea in cursor.fetchall():
            pendientes.append(f"🕒 {hora} — {tarea}")
        cursor.execute("SELECT descripcion FROM tareas WHERE fecha = ? AND completada = 0", (hoy_str,))
        for (desc,) in cursor.fetchall():
            pendientes.append(f"☐ {desc}")

        if not pendientes:
            pendientes.append("Sin eventos ni tareas para hoy.")
        for texto in pendientes[:8]:
            ctk.CTkLabel(self.lista_hoy, text=texto, font=("Urbanist", 13),
                         anchor="w").pack(anchor="w", pady=1)

        conn.close()
