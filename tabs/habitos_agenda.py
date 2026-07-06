import customtkinter as ctk
import sqlite3
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.patches import Circle, FancyBboxPatch, Polygon
from matplotlib.colors import to_rgba
from datetime import date, datetime, timedelta
from tkinter import messagebox

# =========================================================
# CONFIGURACIÓN DEL HABIT GAME
# =========================================================
DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
TIPOS_DIA_BASE = ["Push", "Pull", "Legs", "Upper", "Lower", "Descanso"]

XP_POR_EJERCICIO = 10
XP_BONUS_DIA = 30
XP_BASE_NATACION = 15
XP_POR_50M = 1
XP_SEMANA_PERFECTA = 100
XP_POR_HABITO_CUSTOM = 5
XP_POR_NIVEL = 150

# Grupos musculares del holograma y qué tanto trabaja cada tipo de día / natación
REGIONES = ["Pecho", "Espalda", "Hombros", "Brazos", "Core", "Piernas", "Pantorrillas"]
PESOS_MUSCULOS = {
    "Push":     {"Pecho": 1.0, "Hombros": 0.8, "Brazos": 0.6},
    "Pull":     {"Espalda": 1.0, "Brazos": 0.6, "Hombros": 0.3},
    "Legs":     {"Piernas": 1.0, "Pantorrillas": 0.8, "Core": 0.3},
    "Upper":    {"Pecho": 0.7, "Espalda": 0.7, "Hombros": 0.7, "Brazos": 0.6},
    "Lower":    {"Piernas": 0.8, "Pantorrillas": 0.6, "Core": 0.5},
    "Natacion": {"Espalda": 0.6, "Hombros": 0.6, "Core": 0.5, "Piernas": 0.3, "Brazos": 0.3},
}
UMBRAL_HISTORICO = 20.0
UMBRAL_RECIENTE = 6.0

# Geometría anatómica del holograma (lado izquierdo; el derecho se espeja en x)
def _mirror(puntos):
    return [(10 - x, y) for x, y in puntos]

FORMA_DELTOIDE_IZQ = [(2.55, 11.7), (3.05, 12.05), (3.35, 11.75), (3.25, 11.05), (2.75, 10.95), (2.45, 11.25)]
FORMA_PEC_IZQ = [(3.3, 11.85), (4.95, 12.0), (4.95, 10.35), (3.65, 10.15), (3.05, 10.9)]
FORMA_BICEP_IZQ = [(2.35, 10.9), (2.75, 11.0), (2.65, 9.3), (2.25, 9.05), (2.0, 9.8)]
FORMA_QUAD_IZQ = [(3.55, 7.6), (4.85, 7.6), (4.65, 4.2), (3.75, 4.2)]
FORMA_CALF_IZQ = [(3.85, 4.2), (4.55, 4.2), (4.4, 2.6), (4.15, 1.1), (3.75, 2.6)]
FORMA_ESPALDA = [(3.0, 12.0), (7.0, 12.0), (7.6, 9.0), (6.6, 7.6), (3.4, 7.6), (2.4, 9.0)]

# Rangos: (nivel_minimo, nombre, icono, color hex del holograma)
RANGOS = [
    (0, "Novato", "🥉", "#64748B"),
    (5, "Aprendiz", "🥈", "#38BDF8"),
    (10, "Atleta", "🥇", "#22D3EE"),
    (15, "Competidor", "💎", "#A855F7"),
    (20, "Élite", "👑", "#FBBF24"),
    (30, "Leyenda", "🔥", "#F97316"),
]


class HabitosAgendaTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.offset_semanas = 0
        self.brillo_musculos = {r: 0.05 for r in REGIONES}
        self.rango_color = RANGOS[0][3]
        self.tick_animacion = 0
        self.dias_expandidos = {}

        self.setup_ui()
        self.actualizar()
        self._tick_holograma()

    # =========================================================
    # UI
    # =========================================================
    def setup_ui(self):
        frame_top = ctk.CTkFrame(self, fg_color="transparent")
        frame_top.pack(fill="x", padx=15, pady=(8, 6))

        # --- Holograma ---
        frame_holo = ctk.CTkFrame(frame_top, fg_color="#020617")
        frame_holo.pack(side="left", padx=(0, 10))

        fig = plt.Figure(figsize=(2.6, 2.75), dpi=90)
        self.ax_holograma = fig.add_subplot(111)
        fig.patch.set_facecolor("#020617")
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.fig_holograma = fig
        self.canvas_holograma = FigureCanvasTkAgg(fig, master=frame_holo)
        self.canvas_holograma.get_tk_widget().pack(padx=4, pady=4)

        # --- XP / Rango ---
        card_xp = ctk.CTkFrame(frame_top, fg_color="#1e293b")
        card_xp.pack(side="left", fill="both", expand=True, pady=4)

        ctk.CTkLabel(card_xp, text="🎮 Habit Game: Fuerza, Natación & Agenda",
                     font=("Urbanist", 14, "bold"), text_color="#38BDF8").pack(pady=(10, 6), padx=15, anchor="w")

        self.lbl_rango = ctk.CTkLabel(card_xp, text="🥉 Novato · Nivel 1",
                                       font=("Urbanist", 15, "bold"), text_color="#FBBF24")
        self.lbl_rango.pack(pady=(0, 3), padx=15, anchor="w")

        self.progress_nivel = ctk.CTkProgressBar(card_xp, progress_color="#38BDF8")
        self.progress_nivel.set(0)
        self.progress_nivel.pack(pady=4, padx=15, fill="x")

        self.lbl_xp_detalle = ctk.CTkLabel(card_xp, text=f"0 / {XP_POR_NIVEL} XP",
                                            font=("Urbanist", 11), text_color="#94A3B8")
        self.lbl_xp_detalle.pack(pady=(0, 10), padx=15, anchor="w")

        # --- Navegación semanal ---
        frame_nav = ctk.CTkFrame(self, fg_color="transparent")
        frame_nav.pack(fill="x", padx=15, pady=(0, 4))

        ctk.CTkButton(frame_nav, text="◀ Semana anterior", width=140,
                      command=lambda: self.cambiar_semana(-1)).pack(side="left")
        self.lbl_semana = ctk.CTkLabel(frame_nav, text="", font=("Urbanist", 13, "bold"), text_color="#E2E8F0")
        self.lbl_semana.pack(side="left", expand=True)
        ctk.CTkButton(frame_nav, text="Semana siguiente ▶", width=140,
                      command=lambda: self.cambiar_semana(1)).pack(side="right")

        # --- Grid semanal (tarjetas apiladas y colapsables, una por día) ---
        self.frame_semana = ctk.CTkScrollableFrame(self, height=430)
        self.frame_semana.pack(fill="both", expand=True, padx=15, pady=(4, 12))

    # =========================================================
    # UTILIDADES DE FECHA / SEMANA
    # =========================================================
    def obtener_fechas_semana(self):
        hoy = date.today()
        lunes_actual = hoy - timedelta(days=hoy.isoweekday() - 1)
        lunes_mostrado = lunes_actual + timedelta(weeks=self.offset_semanas)
        return [lunes_mostrado + timedelta(days=i) for i in range(7)]

    def obtener_semana_iso(self, fechas_semana):
        iso_year, iso_week, _ = fechas_semana[0].isocalendar()
        return f"{iso_year}-W{iso_week:02d}"

    def cambiar_semana(self, delta):
        self.offset_semanas += delta
        self.actualizar_grid_semana()

    def alternar_expansion(self, nombre_dia):
        self.dias_expandidos[nombre_dia] = not self.dias_expandidos.get(nombre_dia, False)
        self.actualizar_grid_semana()

    def construir_resumen_dia(self, cursor, tipo_dia, fecha_str, nombre_dia, ejercicios_marcados, habitos_custom):
        partes = []
        if tipo_dia != "Descanso":
            cursor.execute("SELECT id FROM entrenamiento_ejercicios WHERE dia_tipo=?", (tipo_dia,))
            ids_tipo = {row[0] for row in cursor.fetchall()}
            hechos = len(ids_tipo & ejercicios_marcados)
            partes.append(f"{hechos}/{len(ids_tipo)} ejercicios" if ids_tipo else "sin ejercicios")
        else:
            partes.append("😴 descanso")

        cursor.execute("SELECT COUNT(*) FROM natacion_log WHERE fecha=?", (fecha_str,))
        n_nat = cursor.fetchone()[0] or 0
        if n_nat:
            partes.append(f"🏊 {n_nat}")

        habitos_del_dia = [h for h in habitos_custom if nombre_dia in (h[2] or "").split(",")]
        if habitos_del_dia:
            cursor.execute("SELECT habito_id FROM habitos_custom_log WHERE fecha=?", (fecha_str,))
            marcados = {row[0] for row in cursor.fetchall()}
            hechos_h = sum(1 for h in habitos_del_dia if h[0] in marcados)
            partes.append(f"✨ {hechos_h}/{len(habitos_del_dia)}")

        cursor.execute("SELECT COUNT(*), COALESCE(SUM(completada),0) FROM tareas WHERE fecha=?", (fecha_str,))
        total_t, hechas_t = cursor.fetchone()
        if total_t:
            partes.append(f"📋 {hechas_t}/{total_t}")

        cursor.execute("SELECT COUNT(*) FROM agenda WHERE fecha=?", (fecha_str,))
        n_ev = cursor.fetchone()[0] or 0
        if n_ev:
            partes.append(f"📅 {n_ev}")

        return " · ".join(partes)

    # =========================================================
    # MOTOR DE XP / NIVEL / RANGO
    # =========================================================
    def obtener_rango_info(self, nivel):
        info = RANGOS[0]
        for umbral, nombre, icono, color in RANGOS:
            if nivel >= umbral:
                info = (umbral, nombre, icono, color)
        return info[1], info[2], info[3]

    def calcular_xp_total(self):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()

        cursor.execute("SELECT id, dia_tipo FROM entrenamiento_ejercicios")
        total_por_tipo = {}
        for _id, tipo in cursor.fetchall():
            total_por_tipo[tipo] = total_por_tipo.get(tipo, 0) + 1

        cursor.execute("""
            SELECT el.semana, ee.dia_tipo, COUNT(*)
            FROM entrenamiento_log el
            JOIN entrenamiento_ejercicios ee ON ee.id = el.ejercicio_id
            GROUP BY el.semana, ee.dia_tipo
        """)
        completados_por_semana_tipo = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM entrenamiento_log")
        total_ejercicios_marcados = cursor.fetchone()[0] or 0

        cursor.execute("SELECT semana, COUNT(*) FROM natacion_log GROUP BY semana")
        sesiones_por_semana = dict(cursor.fetchall())

        cursor.execute("SELECT COALESCE(SUM(distancia_m), 0) FROM natacion_log")
        distancia_total = cursor.fetchone()[0] or 0.0

        cursor.execute("SELECT meta_sesiones FROM natacion_config WHERE id=1")
        row = cursor.fetchone()
        meta_sesiones = row[0] if row else 3

        cursor.execute("SELECT COUNT(*) FROM habitos_custom_log")
        total_habitos_custom = cursor.fetchone()[0] or 0

        conn.close()

        xp = total_ejercicios_marcados * XP_POR_EJERCICIO
        xp += int(distancia_total // 50) * XP_POR_50M
        xp += sum(sesiones_por_semana.values()) * XP_BASE_NATACION
        xp += total_habitos_custom * XP_POR_HABITO_CUSTOM

        dias_completos_por_semana = {}
        for semana, tipo, count in completados_por_semana_tipo:
            if total_por_tipo.get(tipo, 0) > 0 and count >= total_por_tipo[tipo]:
                xp += XP_BONUS_DIA
                dias_completos_por_semana.setdefault(semana, set()).add(tipo)

        tipos_requeridos = {"Push", "Pull", "Legs", "Upper", "Lower"}
        for semana, tipos_completos in dias_completos_por_semana.items():
            if tipos_completos >= tipos_requeridos and sesiones_por_semana.get(semana, 0) >= meta_sesiones:
                xp += XP_SEMANA_PERFECTA

        return int(xp)

    def calcular_brillo_musculos(self):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ee.dia_tipo, el.fecha
            FROM entrenamiento_log el
            JOIN entrenamiento_ejercicios ee ON ee.id = el.ejercicio_id
        """)
        eventos = [(tipo, fecha) for tipo, fecha in cursor.fetchall()]

        cursor.execute("SELECT fecha FROM natacion_log")
        eventos += [("Natacion", fecha) for (fecha,) in cursor.fetchall()]

        conn.close()

        hoy = date.today()
        hace_4_semanas = hoy - timedelta(weeks=4)

        historico = {r: 0.0 for r in REGIONES}
        reciente = {r: 0.0 for r in REGIONES}

        for tipo, fecha_str in eventos:
            pesos = PESOS_MUSCULOS.get(tipo, {})
            try:
                fecha_evento = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except (TypeError, ValueError):
                continue
            for region, peso in pesos.items():
                historico[region] += peso
                if fecha_evento >= hace_4_semanas:
                    reciente[region] += peso

        brillo = {}
        for region in REGIONES:
            base = min(0.6, historico[region] / UMBRAL_HISTORICO)
            boost = min(0.4, reciente[region] / UMBRAL_RECIENTE)
            brillo[region] = max(0.05, min(1.0, base + boost))
        return brillo

    def renderizar_xp(self):
        xp_total = self.calcular_xp_total()
        nivel = 1 + xp_total // XP_POR_NIVEL
        xp_en_nivel = xp_total % XP_POR_NIVEL
        nombre_rango, icono_rango, color_rango = self.obtener_rango_info(nivel)

        self.lbl_rango.configure(text=f"{icono_rango} {nombre_rango} · Nivel {nivel}")
        self.lbl_xp_detalle.configure(text=f"{xp_en_nivel} / {XP_POR_NIVEL} XP  (Total acumulado: {xp_total} XP)")
        self.progress_nivel.set(xp_en_nivel / XP_POR_NIVEL)

        self.rango_color = color_rango
        self.brillo_musculos = self.calcular_brillo_musculos()

    # =========================================================
    # HOLOGRAMA ANIMADO
    # =========================================================
    def _tick_holograma(self):
        if self.winfo_viewable():
            self.dibujar_holograma()
        self.tick_animacion += 1
        self.after(150, self._tick_holograma)

    def dibujar_holograma(self):
        ax = self.ax_holograma
        ax.clear()
        ax.set_xlim(0.5, 9.5)
        ax.set_ylim(0, 14.2)
        ax.set_aspect("equal")
        ax.set_facecolor("#020617")
        ax.axis("off")

        pulso = 0.5 + 0.5 * np.sin(self.tick_animacion / 6.0)
        color = self.rango_color
        b = self.brillo_musculos

        def rgba(alpha):
            return to_rgba(color, max(0.0, min(1.0, alpha)))

        # Líneas de escaneo (efecto holograma)
        for i in range(7):
            y = (i * (14.2 / 7) + (self.tick_animacion * 0.13) % (14.2 / 7))
            ax.axhline(y=y, color=color, alpha=0.05 + 0.05 * pulso, linewidth=1)

        # Espalda: aura en forma de "V" detrás del torso (no visible de frente, pero se insinúa)
        alpha_espalda = (0.06 + b["Espalda"] * 0.3) * (0.85 + 0.15 * pulso)
        ax.add_patch(Polygon(FORMA_ESPALDA, closed=True, facecolor=rgba(alpha_espalda),
                              edgecolor=rgba(0.18 + 0.1 * pulso), linewidth=1.0))

        # Cabeza: siempre visible con brillo tenue, no es una zona entrenable
        ax.add_patch(Circle((5, 13.2), 0.62, facecolor=rgba(0.26 + 0.12 * pulso),
                             edgecolor=rgba(0.4), linewidth=1.0))
        # Cuello
        ax.add_patch(Polygon([(4.6, 12.35), (5.4, 12.35), (5.25, 12.65), (4.75, 12.65)], closed=True,
                              facecolor=rgba(0.2), edgecolor=rgba(0.35), linewidth=0.8))

        def dibujar_par(forma_izq, region):
            alpha_face = (0.12 + b[region] * 0.72) * (0.85 + 0.15 * pulso)
            alpha_edge = 0.3 + 0.15 * pulso
            fc, ec = rgba(alpha_face), rgba(alpha_edge)
            ax.add_patch(Polygon(forma_izq, closed=True, facecolor=fc, edgecolor=ec, linewidth=1.1))
            ax.add_patch(Polygon(_mirror(forma_izq), closed=True, facecolor=fc, edgecolor=ec, linewidth=1.1))

        dibujar_par(FORMA_DELTOIDE_IZQ, "Hombros")
        dibujar_par(FORMA_PEC_IZQ, "Pecho")
        dibujar_par(FORMA_BICEP_IZQ, "Brazos")
        dibujar_par(FORMA_QUAD_IZQ, "Piernas")
        dibujar_par(FORMA_CALF_IZQ, "Pantorrillas")

        # Abdomen: 6-pack, 3 filas x 2 columnas
        alpha_core = (0.14 + b["Core"] * 0.72) * (0.85 + 0.15 * pulso)
        fc_core, ec_core = rgba(alpha_core), rgba(0.3 + 0.15 * pulso)
        for y_top in (9.85, 9.05, 8.25):
            ax.add_patch(FancyBboxPatch((4.05, y_top - 0.62), 0.78, 0.62, boxstyle="round,pad=0.05",
                                         facecolor=fc_core, edgecolor=ec_core, linewidth=1.0))
            ax.add_patch(FancyBboxPatch((5.17, y_top - 0.62), 0.78, 0.62, boxstyle="round,pad=0.05",
                                         facecolor=fc_core, edgecolor=ec_core, linewidth=1.0))

        self.canvas_holograma.draw()

    # =========================================================
    # RENDERIZADO DEL GRID SEMANAL
    # =========================================================
    def actualizar_grid_semana(self):
        for w in self.frame_semana.winfo_children(): w.destroy()

        fechas_semana = self.obtener_fechas_semana()
        semana_iso = self.obtener_semana_iso(fechas_semana)
        self.lbl_semana.configure(
            text=f"Semana del {fechas_semana[0].strftime('%d/%m')} al {fechas_semana[6].strftime('%d/%m/%Y')}"
        )

        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()

        cursor.execute("SELECT dia_semana, dia_tipo FROM entrenamiento_dias")
        tipo_por_dia = dict(cursor.fetchall())

        cursor.execute("SELECT ejercicio_id FROM entrenamiento_log WHERE semana=?", (semana_iso,))
        ejercicios_marcados = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT id, nombre, dias_semana, categoria FROM habitos_custom")
        habitos_custom = cursor.fetchall()

        for idx, nombre_dia in enumerate(DIAS_SEMANA):
            fecha_dia = fechas_semana[idx]
            fecha_str = fecha_dia.strftime("%Y-%m-%d")
            tipo_dia = tipo_por_dia.get(nombre_dia, "Descanso")

            if nombre_dia not in self.dias_expandidos:
                self.dias_expandidos[nombre_dia] = (fecha_dia == date.today())
            expandido = self.dias_expandidos[nombre_dia]

            card = ctk.CTkFrame(self.frame_semana, fg_color="#1e293b")
            card.pack(fill="x", pady=4, padx=4)

            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=12, pady=(8, 8 if expandido else 8))
            ctk.CTkButton(header, text=("▾" if expandido else "▸"), width=28, height=24,
                          fg_color="#334155", hover_color="#475569",
                          command=lambda d=nombre_dia: self.alternar_expansion(d)).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(header, text=f"{nombre_dia} — {fecha_dia.strftime('%d/%m/%Y')}",
                         font=("Urbanist", 14, "bold"), text_color="#38BDF8").pack(side="left")
            ctk.CTkLabel(header, text=f"[{tipo_dia}]", font=("Urbanist", 12, "bold"),
                         text_color="#FBBF24").pack(side="left", padx=8)
            if not expandido:
                resumen = self.construir_resumen_dia(cursor, tipo_dia, fecha_str, nombre_dia, ejercicios_marcados, habitos_custom)
                ctk.CTkLabel(header, text=resumen, font=("Urbanist", 11), text_color="#94A3B8").pack(side="left", padx=10)
            ctk.CTkButton(header, text="⚙ Cambiar tipo", width=110, height=24, fg_color="#334155",
                          hover_color="#475569", font=("Urbanist", 10),
                          command=lambda d=nombre_dia, t=tipo_dia: self.abrir_dialogo_tipo_dia(d, t)).pack(side="right")

            if not expandido:
                continue

            # --- Gimnasio ---
            if tipo_dia != "Descanso":
                cursor.execute("SELECT id, nombre FROM entrenamiento_ejercicios WHERE dia_tipo=? ORDER BY id", (tipo_dia,))
                for ej_id, nombre_ej in cursor.fetchall():
                    fila = ctk.CTkFrame(card, fg_color="transparent")
                    fila.pack(fill="x", padx=20, pady=1)
                    var = ctk.IntVar(value=1 if ej_id in ejercicios_marcados else 0)
                    ctk.CTkCheckBox(fila, text=nombre_ej, variable=var,
                                    command=lambda e=ej_id, v=var, s=semana_iso: self.alternar_ejercicio(e, v, s)).pack(side="left", padx=2)
                    ctk.CTkButton(fila, text="✏", width=26, fg_color="#3B82F6", hover_color="#2563EB",
                                  command=lambda e=ej_id, n=nombre_ej: self.editar_ejercicio(e, n)).pack(side="right", padx=(2, 0))
                    ctk.CTkButton(fila, text="🗑", width=26, fg_color="#EF4444", hover_color="#DC2626",
                                  command=lambda e=ej_id: self.eliminar_ejercicio(e)).pack(side="right")

                fila_add = ctk.CTkFrame(card, fg_color="transparent")
                fila_add.pack(fill="x", padx=20, pady=(2, 8))
                entry_nuevo = ctk.CTkEntry(fila_add, placeholder_text="Nuevo ejercicio...")
                entry_nuevo.pack(side="left", fill="x", expand=True, padx=(0, 5))
                ctk.CTkButton(fila_add, text="➕", width=32,
                              command=lambda t=tipo_dia, en=entry_nuevo: self.agregar_ejercicio(t, en)).pack(side="left")
            else:
                ctk.CTkLabel(card, text="😴 Día de descanso", font=("Urbanist", 12), text_color="#64748B").pack(anchor="w", padx=20, pady=4)

            # --- Natación ---
            cursor.execute("SELECT id, distancia_m FROM natacion_log WHERE fecha=? ORDER BY id", (fecha_str,))
            sesiones_natacion = cursor.fetchall()
            fila_natacion = ctk.CTkFrame(card, fg_color="transparent")
            fila_natacion.pack(fill="x", padx=20, pady=(6, 2))
            ctk.CTkLabel(fila_natacion, text="🏊 Natación:", font=("Urbanist", 12, "bold"), text_color="#10B981").pack(side="left")
            for sid, dist in sesiones_natacion:
                ctk.CTkLabel(fila_natacion, text=f"{dist:,.0f} m", font=("Urbanist", 11)).pack(side="left", padx=6)
                ctk.CTkButton(fila_natacion, text="🗑", width=22, fg_color="#EF4444", hover_color="#DC2626",
                              command=lambda i=sid: self.eliminar_sesion_natacion(i)).pack(side="left")
            ctk.CTkButton(fila_natacion, text="+ Nadar", width=70, height=22, fg_color="#10B981", hover_color="#059669",
                          font=("Urbanist", 10), command=lambda f=fecha_str, s=semana_iso: self.abrir_dialogo_natacion(f, s)).pack(side="right")

            # --- Hábitos personalizados asignados a este día ---
            habitos_del_dia = [h for h in habitos_custom if nombre_dia in (h[2] or "").split(",")]
            if habitos_del_dia:
                ctk.CTkLabel(card, text="✨ Hábitos:", font=("Urbanist", 12, "bold"), text_color="#A855F7").pack(anchor="w", padx=20, pady=(8, 0))
                cursor.execute("SELECT habito_id FROM habitos_custom_log WHERE fecha=?", (fecha_str,))
                marcados_hoy = {row[0] for row in cursor.fetchall()}
                for hid, hnombre, _dias, hcat in habitos_del_dia:
                    fila = ctk.CTkFrame(card, fg_color="transparent")
                    fila.pack(fill="x", padx=20, pady=1)
                    var = ctk.IntVar(value=1 if hid in marcados_hoy else 0)
                    texto = f"{hnombre} [{hcat}]" if hcat else hnombre
                    ctk.CTkCheckBox(fila, text=texto, variable=var,
                                    command=lambda h=hid, v=var, f=fecha_str: self.alternar_habito_custom(h, v, f)).pack(side="left", padx=2)
                    ctk.CTkButton(fila, text="✏", width=26, fg_color="#3B82F6", hover_color="#2563EB",
                                  command=lambda h=hid: self.abrir_dialogo_habito_custom(h)).pack(side="right", padx=(2, 0))
                    ctk.CTkButton(fila, text="🗑", width=26, fg_color="#EF4444", hover_color="#DC2626",
                                  command=lambda h=hid: self.eliminar_habito_custom(h)).pack(side="right")

            ctk.CTkButton(card, text="➕ Nuevo hábito personalizado", fg_color="#A855F7", hover_color="#9333EA",
                          font=("Urbanist", 10), height=24,
                          command=lambda: self.abrir_dialogo_habito_custom(None)).pack(anchor="w", padx=20, pady=(4, 8))

            # --- Tareas ---
            cursor.execute("SELECT id, descripcion, completada FROM tareas WHERE fecha=? ORDER BY id", (fecha_str,))
            tareas_dia = cursor.fetchall()
            ctk.CTkLabel(card, text="📋 Tareas:", font=("Urbanist", 12, "bold"), text_color="#F59E0B").pack(anchor="w", padx=20, pady=(4, 0))
            for tid, desc, completada in tareas_dia:
                fila = ctk.CTkFrame(card, fg_color="transparent")
                fila.pack(fill="x", padx=20, pady=1)
                var = ctk.IntVar(value=completada)
                ctk.CTkCheckBox(fila, text=desc, variable=var,
                                command=lambda t=tid, v=var: self.alternar_tarea(t, v)).pack(side="left", padx=2)
                ctk.CTkButton(fila, text="✏", width=26, fg_color="#3B82F6", hover_color="#2563EB",
                              command=lambda t=tid, d=desc: self.editar_tarea(t, d)).pack(side="right", padx=(2, 0))
                ctk.CTkButton(fila, text="🗑", width=26, fg_color="#EF4444", hover_color="#DC2626",
                              command=lambda t=tid: self.eliminar_tarea(t)).pack(side="right")

            fila_add_tarea = ctk.CTkFrame(card, fg_color="transparent")
            fila_add_tarea.pack(fill="x", padx=20, pady=(2, 8))
            entry_tarea = ctk.CTkEntry(fila_add_tarea, placeholder_text="Nueva tarea...")
            entry_tarea.pack(side="left", fill="x", expand=True, padx=(0, 5))
            ctk.CTkButton(fila_add_tarea, text="➕", width=32,
                          command=lambda f=fecha_str, en=entry_tarea: self.agregar_tarea(f, en)).pack(side="left")

            # --- Eventos ---
            cursor.execute("SELECT id, tarea, hora FROM agenda WHERE fecha=? ORDER BY hora", (fecha_str,))
            eventos_dia = cursor.fetchall()
            ctk.CTkLabel(card, text="📅 Eventos:", font=("Urbanist", 12, "bold"), text_color="#10B981").pack(anchor="w", padx=20, pady=(4, 0))
            for eid, tarea_ev, hora in eventos_dia:
                fila = ctk.CTkFrame(card, fg_color="transparent")
                fila.pack(fill="x", padx=20, pady=1)
                ctk.CTkLabel(fila, text=f"🕒 {hora} — {tarea_ev}", font=("Urbanist", 12)).pack(side="left", padx=2)
                ctk.CTkButton(fila, text="✏", width=26, fg_color="#3B82F6", hover_color="#2563EB",
                              command=lambda e=eid, t=tarea_ev, h=hora: self.editar_evento(e, t, h)).pack(side="right", padx=(2, 0))
                ctk.CTkButton(fila, text="🗑", width=26, fg_color="#EF4444", hover_color="#DC2626",
                              command=lambda e=eid: self.eliminar_evento(e)).pack(side="right")

            fila_add_evento = ctk.CTkFrame(card, fg_color="transparent")
            fila_add_evento.pack(fill="x", padx=20, pady=(2, 10))
            entry_ev_desc = ctk.CTkEntry(fila_add_evento, placeholder_text="Actividad...")
            entry_ev_desc.pack(side="left", fill="x", expand=True, padx=(0, 5))
            entry_ev_hora = ctk.CTkEntry(fila_add_evento, placeholder_text="Hora (14:30)", width=100)
            entry_ev_hora.pack(side="left", padx=(0, 5))
            ctk.CTkButton(fila_add_evento, text="➕", width=32,
                          command=lambda f=fecha_str, ed=entry_ev_desc, eh=entry_ev_hora: self.agregar_evento(f, ed, eh)).pack(side="left")

        conn.close()

    # =========================================================
    # DIÁLOGO GENÉRICO DE TEXTO
    # =========================================================
    def abrir_dialogo_input(self, titulo, campos, on_guardar):
        dialog = ctk.CTkToplevel(self)
        dialog.title(titulo)
        dialog.transient(self)
        dialog.grab_set()

        entradas = {}
        for key, label, valor in campos:
            ctk.CTkLabel(dialog, text=label, font=("Urbanist", 12)).pack(pady=(12, 2), padx=20, anchor="w")
            entry = ctk.CTkEntry(dialog)
            entry.insert(0, valor)
            entry.pack(pady=2, padx=20, fill="x")
            entradas[key] = entry

        def guardar():
            valores = {k: e.get().strip() for k, e in entradas.items()}
            if on_guardar(valores):
                dialog.destroy()

        ctk.CTkButton(dialog, text="Guardar", fg_color="#3B82F6", hover_color="#2563EB",
                      command=guardar).pack(pady=15, padx=20, fill="x")
        dialog.geometry(f"320x{140 + len(campos) * 68}")

    # =========================================================
    # ACCIONES: GIMNASIO
    # =========================================================
    def agregar_ejercicio(self, dia_tipo, entry_widget):
        nombre = entry_widget.get().strip()
        if not nombre:
            return
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("INSERT INTO entrenamiento_ejercicios (dia_tipo, nombre) VALUES (?, ?)", (dia_tipo, nombre))
        conn.commit()
        conn.close()
        self.actualizar_grid_semana()

    def editar_ejercicio(self, ejercicio_id, nombre_actual):
        def guardar(valores):
            nuevo_nombre = valores["nombre"]
            if not nuevo_nombre:
                messagebox.showerror("Error", "El nombre no puede estar vacío.")
                return False
            conn = sqlite3.connect("data.db")
            conn.cursor().execute("UPDATE entrenamiento_ejercicios SET nombre=? WHERE id=?", (nuevo_nombre, ejercicio_id))
            conn.commit()
            conn.close()
            self.actualizar_grid_semana()
            return True

        self.abrir_dialogo_input("Editar Ejercicio", [("nombre", "Nombre del ejercicio:", nombre_actual)], guardar)

    def eliminar_ejercicio(self, ejercicio_id):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM entrenamiento_ejercicios WHERE id=?", (ejercicio_id,))
        cursor.execute("DELETE FROM entrenamiento_log WHERE ejercicio_id=?", (ejercicio_id,))
        conn.commit()
        conn.close()
        self.actualizar()

    def alternar_ejercicio(self, ejercicio_id, var_estado, semana_iso):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        if var_estado.get() == 1:
            cursor.execute("INSERT OR IGNORE INTO entrenamiento_log (ejercicio_id, semana, fecha) VALUES (?, ?, ?)",
                           (ejercicio_id, semana_iso, date.today().strftime("%Y-%m-%d")))
        else:
            cursor.execute("DELETE FROM entrenamiento_log WHERE ejercicio_id=? AND semana=?", (ejercicio_id, semana_iso))
        conn.commit()
        conn.close()
        self.actualizar()

    def abrir_dialogo_tipo_dia(self, dia_semana, tipo_actual):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT dia_tipo FROM entrenamiento_ejercicios")
        tipos_existentes = [row[0] for row in cursor.fetchall()]
        conn.close()

        opciones = list(dict.fromkeys(TIPOS_DIA_BASE + tipos_existentes))

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Tipo de día — {dia_semana}")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Selecciona un tipo existente:", font=("Urbanist", 12)).pack(pady=(20, 5), padx=20)
        var_tipo = ctk.StringVar(value=tipo_actual if tipo_actual in opciones else opciones[0])
        ctk.CTkOptionMenu(dialog, variable=var_tipo, values=opciones).pack(pady=5, padx=20, fill="x")

        ctk.CTkLabel(dialog, text="...o crea un tipo nuevo:", font=("Urbanist", 12)).pack(pady=(15, 5), padx=20)
        entry_nuevo = ctk.CTkEntry(dialog, placeholder_text="ej: Cardio")
        entry_nuevo.pack(pady=5, padx=20, fill="x")

        def guardar():
            nuevo_tipo = entry_nuevo.get().strip() or var_tipo.get()
            conn = sqlite3.connect("data.db")
            conn.cursor().execute("""
                INSERT INTO entrenamiento_dias (dia_semana, dia_tipo) VALUES (?, ?)
                ON CONFLICT(dia_semana) DO UPDATE SET dia_tipo=excluded.dia_tipo
            """, (dia_semana, nuevo_tipo))
            conn.commit()
            conn.close()
            dialog.destroy()
            self.actualizar_grid_semana()

        ctk.CTkButton(dialog, text="Guardar", fg_color="#3B82F6", hover_color="#2563EB",
                      command=guardar).pack(pady=15, padx=20, fill="x")

    # =========================================================
    # ACCIONES: NATACIÓN
    # =========================================================
    def abrir_dialogo_natacion(self, fecha_str, semana_iso):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Registrar Sesión de Natación")
        dialog.geometry("300x160")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=f"Distancia nadada el {fecha_str} (metros):", font=("Urbanist", 12)).pack(pady=(20, 5), padx=20)
        entry_dist = ctk.CTkEntry(dialog, placeholder_text="ej: 1000")
        entry_dist.pack(pady=5, padx=20, fill="x")

        def guardar():
            try:
                distancia = float(entry_dist.get().strip())
                if distancia <= 0: raise ValueError
            except ValueError:
                messagebox.showerror("Distancia Inválida", "Ingresa un número positivo de metros.")
                return

            conn = sqlite3.connect("data.db")
            conn.cursor().execute("INSERT INTO natacion_log (semana, fecha, distancia_m) VALUES (?, ?, ?)",
                                  (semana_iso, fecha_str, distancia))
            conn.commit()
            conn.close()
            dialog.destroy()
            self.actualizar()

        ctk.CTkButton(dialog, text="Guardar", fg_color="#10B981", hover_color="#059669",
                      command=guardar).pack(pady=15, padx=20, fill="x")

    def eliminar_sesion_natacion(self, sesion_id):
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("DELETE FROM natacion_log WHERE id=?", (sesion_id,))
        conn.commit()
        conn.close()
        self.actualizar()

    # =========================================================
    # ACCIONES: HÁBITOS PERSONALIZADOS
    # =========================================================
    def abrir_dialogo_habito_custom(self, habito_id):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        nombre_actual, categoria_actual, dias_actuales = "", "", []
        if habito_id is not None:
            cursor.execute("SELECT nombre, categoria, dias_semana FROM habitos_custom WHERE id=?", (habito_id,))
            row = cursor.fetchone()
            if row:
                nombre_actual, categoria_actual, dias_str = row
                dias_actuales = (dias_str or "").split(",")
        conn.close()

        dialog = ctk.CTkToplevel(self)
        dialog.title("Hábito Personalizado")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Nombre del hábito:", font=("Urbanist", 12)).pack(pady=(15, 2), padx=20, anchor="w")
        entry_nombre = ctk.CTkEntry(dialog)
        entry_nombre.insert(0, nombre_actual)
        entry_nombre.pack(pady=2, padx=20, fill="x")

        ctk.CTkLabel(dialog, text="Categoría (opcional):", font=("Urbanist", 12)).pack(pady=(10, 2), padx=20, anchor="w")
        entry_cat = ctk.CTkEntry(dialog, placeholder_text="ej: Salud, Mental...")
        entry_cat.insert(0, categoria_actual or "")
        entry_cat.pack(pady=2, padx=20, fill="x")

        ctk.CTkLabel(dialog, text="Días de la semana:", font=("Urbanist", 12)).pack(pady=(10, 2), padx=20, anchor="w")
        frame_dias = ctk.CTkFrame(dialog, fg_color="transparent")
        frame_dias.pack(pady=2, padx=20, fill="x")
        vars_dias = {}
        for d in DIAS_SEMANA:
            v = ctk.IntVar(value=1 if d in dias_actuales else 0)
            ctk.CTkCheckBox(frame_dias, text=d[:3], variable=v, width=70).pack(side="left")
            vars_dias[d] = v

        def guardar():
            nombre = entry_nombre.get().strip()
            categoria = entry_cat.get().strip()
            dias_sel = [d for d, v in vars_dias.items() if v.get() == 1]
            if not nombre or not dias_sel:
                messagebox.showerror("Datos Incompletos", "Ingresa un nombre y selecciona al menos un día.")
                return
            dias_str = ",".join(dias_sel)

            conn = sqlite3.connect("data.db")
            cursor = conn.cursor()
            if habito_id is None:
                cursor.execute("INSERT INTO habitos_custom (nombre, dias_semana, categoria) VALUES (?, ?, ?)",
                              (nombre, dias_str, categoria))
            else:
                cursor.execute("UPDATE habitos_custom SET nombre=?, dias_semana=?, categoria=? WHERE id=?",
                              (nombre, dias_str, categoria, habito_id))
            conn.commit()
            conn.close()
            dialog.destroy()
            self.actualizar_grid_semana()

        ctk.CTkButton(dialog, text="Guardar", fg_color="#A855F7", hover_color="#9333EA",
                      command=guardar).pack(pady=15, padx=20, fill="x")
        dialog.geometry("360x320")

    def eliminar_habito_custom(self, habito_id):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM habitos_custom WHERE id=?", (habito_id,))
        cursor.execute("DELETE FROM habitos_custom_log WHERE habito_id=?", (habito_id,))
        conn.commit()
        conn.close()
        self.actualizar()

    def alternar_habito_custom(self, habito_id, var_estado, fecha_str):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        if var_estado.get() == 1:
            cursor.execute("INSERT OR IGNORE INTO habitos_custom_log (habito_id, fecha) VALUES (?, ?)", (habito_id, fecha_str))
        else:
            cursor.execute("DELETE FROM habitos_custom_log WHERE habito_id=? AND fecha=?", (habito_id, fecha_str))
        conn.commit()
        conn.close()
        self.actualizar()

    # =========================================================
    # ACCIONES: TAREAS
    # =========================================================
    def agregar_tarea(self, fecha_str, entry_widget):
        desc = entry_widget.get().strip()
        if not desc:
            return
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("INSERT INTO tareas (descripcion, fecha, completada) VALUES (?, ?, 0)", (desc, fecha_str))
        conn.commit()
        conn.close()
        self.actualizar_grid_semana()

    def editar_tarea(self, tarea_id, desc_actual):
        def guardar(valores):
            desc = valores["descripcion"]
            if not desc:
                messagebox.showerror("Error", "La descripción no puede estar vacía.")
                return False
            conn = sqlite3.connect("data.db")
            conn.cursor().execute("UPDATE tareas SET descripcion=? WHERE id=?", (desc, tarea_id))
            conn.commit()
            conn.close()
            self.actualizar_grid_semana()
            return True

        self.abrir_dialogo_input("Editar Tarea", [("descripcion", "Descripción:", desc_actual)], guardar)

    def alternar_tarea(self, tarea_id, var_estado):
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("UPDATE tareas SET completada=? WHERE id=?", (var_estado.get(), tarea_id))
        conn.commit()
        conn.close()

    def eliminar_tarea(self, tarea_id):
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("DELETE FROM tareas WHERE id=?", (tarea_id,))
        conn.commit()
        conn.close()
        self.actualizar_grid_semana()

    # =========================================================
    # ACCIONES: EVENTOS (agenda)
    # =========================================================
    def agregar_evento(self, fecha_str, entry_desc, entry_hora):
        desc = entry_desc.get().strip()
        hora = entry_hora.get().strip()
        if not desc or not hora:
            return
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("INSERT INTO agenda (tarea, fecha, hora) VALUES (?, ?, ?)", (desc, fecha_str, hora))
        conn.commit()
        conn.close()
        self.actualizar_grid_semana()

    def editar_evento(self, evento_id, desc_actual, hora_actual):
        def guardar(valores):
            desc, hora = valores["descripcion"], valores["hora"]
            if not desc or not hora:
                messagebox.showerror("Error", "Descripción y hora son obligatorias.")
                return False
            conn = sqlite3.connect("data.db")
            conn.cursor().execute("UPDATE agenda SET tarea=?, hora=? WHERE id=?", (desc, hora, evento_id))
            conn.commit()
            conn.close()
            self.actualizar_grid_semana()
            return True

        self.abrir_dialogo_input("Editar Evento", [("descripcion", "Descripción:", desc_actual),
                                                    ("hora", "Hora:", hora_actual)], guardar)

    def eliminar_evento(self, evento_id):
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("DELETE FROM agenda WHERE id=?", (evento_id,))
        conn.commit()
        conn.close()
        self.actualizar_grid_semana()

    # =========================================================
    # REFRESCO GENERAL
    # =========================================================
    def actualizar(self):
        self.renderizar_xp()
        self.actualizar_grid_semana()
