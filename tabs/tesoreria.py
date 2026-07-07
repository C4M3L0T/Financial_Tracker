import customtkinter as ctk
import sqlite3
from datetime import datetime
from tkinter import messagebox

CATEGORIAS_GASTOS = ["Vivienda", "Comida", "Transporte", "Impuestos", "Ahorros", "Salud", "Recreación", "Suscripciones", "Seguros","Servicios", "Vestimenta", "Personal", "Mascota", "Deuda", "Otros"]
FUENTES_INGRESO = ["Salario", "Freelance", "Rendimientos", "Ventas", "Otros"]

# Clasificación SAT del gasto deducible. Los nombres deben coincidir con los
# topes definidos en tabs/impuestos_inversion.py (TOPES_COLEGIATURA, etc.)
TIPOS_DEDUCCION = [
    "Salud (médicos/hospital)", "Lentes ópticos", "Seguro Gastos Médicos",
    "Colegiatura Preescolar", "Colegiatura Primaria", "Colegiatura Secundaria",
    "Colegiatura Prof. Técnico", "Colegiatura Bachillerato", "Transporte escolar",
    "Retiro (PPR/AFORE)", "Intereses hipotecarios", "Funerarios", "Donativos",
    "Otro (tope general)",
]

TIPOS_CUENTA = ["Efectivo", "Débito", "Crédito", "Inversión"]
SIN_CUENTA = "(sin cuenta)"

class TesoreriaTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.cuentas_map = {}
        self.setup_ui()
        self.actualizar()

    def setup_ui(self):
        # --- BARRA SUPERIOR: CUENTAS CON SALDO CALCULADO ---
        self.frame_cuentas = ctk.CTkFrame(self)
        self.frame_cuentas.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 0), sticky="ew")

        # --- PANEL IZQUIERDO: EGRESOS (GASTOS) ---
        panel_gastos = ctk.CTkFrame(self)
        panel_gastos.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(panel_gastos, text="Registrar Gasto (Salida)", font=("Urbanist", 18, "bold"), text_color="#EF4444").pack(pady=10)

        self.e_gdesc = ctk.CTkEntry(panel_gastos, placeholder_text="Descripción (ej: Compra de café)")
        self.e_gdesc.pack(pady=5, padx=20, fill="x")
        self.e_gmonto = ctk.CTkEntry(panel_gastos, placeholder_text="Monto Numérico ($ MXN)")
        self.e_gmonto.pack(pady=5, padx=20, fill="x")
        # Categoría y cuenta lado a lado (formulario compacto: el historial necesita el espacio)
        fila_cat = ctk.CTkFrame(panel_gastos, fg_color="transparent")
        fila_cat.pack(fill="x", padx=20, pady=4)
        col_cat = ctk.CTkFrame(fila_cat, fg_color="transparent")
        col_cat.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(col_cat, text="Categoría:", font=("Urbanist", 11), text_color="#94A3B8").pack(anchor="w")
        self.c_gcat = ctk.CTkOptionMenu(col_cat, values=CATEGORIAS_GASTOS)
        self.c_gcat.pack(fill="x")
        col_cta = ctk.CTkFrame(fila_cat, fg_color="transparent")
        col_cta.pack(side="left", expand=True, fill="x", padx=(5, 0))
        ctk.CTkLabel(col_cta, text="Cuenta de salida:", font=("Urbanist", 11), text_color="#94A3B8").pack(anchor="w")
        self.c_gcuenta = ctk.CTkOptionMenu(col_cta, values=[SIN_CUENTA])
        self.c_gcuenta.pack(fill="x")

        # Checkboxes de Control SAT en una sola fila
        self.var_factura = ctk.IntVar()
        self.var_deducible = ctk.IntVar()
        fila_chk = ctk.CTkFrame(panel_gastos, fg_color="transparent")
        fila_chk.pack(fill="x", padx=20, pady=4)
        ctk.CTkCheckBox(fila_chk, text="Factura (CFDI)", variable=self.var_factura).pack(side="left")
        ctk.CTkCheckBox(fila_chk, text="Deducible (LISR)", variable=self.var_deducible, text_color="#10B981").pack(side="left", padx=15)

        fila_ded = ctk.CTkFrame(panel_gastos, fg_color="transparent")
        fila_ded.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(fila_ded, text="Tipo deducción:", font=("Urbanist", 11), text_color="#94A3B8").pack(side="left", padx=(0, 8))
        self.c_tipo_deduccion = ctk.CTkOptionMenu(fila_ded, values=TIPOS_DEDUCCION)
        self.c_tipo_deduccion.set("Otro (tope general)")
        self.c_tipo_deduccion.pack(side="left", expand=True, fill="x")

        ctk.CTkButton(panel_gastos, text="Registrar Salida Financiera", fg_color="#EF4444", hover_color="#DC2626", command=self.guardar_gasto).pack(pady=8, padx=20, fill="x")
        
        self.frame_historial_gastos = ctk.CTkScrollableFrame(panel_gastos, height=250)
        self.frame_historial_gastos.pack(pady=10, fill="both", expand=True, padx=10)

        # --- PANEL DERECHO: INGRESOS ---
        panel_ingresos = ctk.CTkFrame(self)
        panel_ingresos.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(panel_ingresos, text="Registrar Ingreso (Entrada)", font=("Urbanist", 18, "bold"), text_color="#10B981").pack(pady=10)

        self.e_idesc = ctk.CTkEntry(panel_ingresos, placeholder_text="Origen (ej: Pago de Cliente)")
        self.e_idesc.pack(pady=5, padx=20, fill="x")
        self.e_imonto = ctk.CTkEntry(panel_ingresos, placeholder_text="Monto Numérico ($ MXN)")
        self.e_imonto.pack(pady=5, padx=20, fill="x")
        fila_fuente = ctk.CTkFrame(panel_ingresos, fg_color="transparent")
        fila_fuente.pack(fill="x", padx=20, pady=4)
        col_fue = ctk.CTkFrame(fila_fuente, fg_color="transparent")
        col_fue.pack(side="left", expand=True, fill="x", padx=(0, 5))
        ctk.CTkLabel(col_fue, text="Fuente:", font=("Urbanist", 11), text_color="#94A3B8").pack(anchor="w")
        self.c_ifuen = ctk.CTkOptionMenu(col_fue, values=FUENTES_INGRESO)
        self.c_ifuen.pack(fill="x")
        col_icta = ctk.CTkFrame(fila_fuente, fg_color="transparent")
        col_icta.pack(side="left", expand=True, fill="x", padx=(5, 0))
        ctk.CTkLabel(col_icta, text="Cuenta de destino:", font=("Urbanist", 11), text_color="#94A3B8").pack(anchor="w")
        self.c_icuenta = ctk.CTkOptionMenu(col_icta, values=[SIN_CUENTA])
        self.c_icuenta.pack(fill="x")

        ctk.CTkButton(panel_ingresos, text="Registrar Entrada Liquidez", fg_color="#10B981", hover_color="#059669", command=self.guardar_ingreso).pack(pady=8, padx=20, fill="x")
        
        self.frame_historial_ingresos = ctk.CTkScrollableFrame(panel_ingresos, height=250)
        self.frame_historial_ingresos.pack(pady=10, fill="both", expand=True, padx=10)

    def guardar_gasto(self):
        desc = self.e_gdesc.get().strip()
        monto_raw = self.e_gmonto.get().strip()
        
        if not desc or not monto_raw:
            messagebox.showwarning("Campos Incompletos", "Por favor llena la descripción y el monto.")
            return

        # Capa de Validación Microeconómica / Sanitización
        try:
            monto_validado = float(monto_raw)
            if monto_validado <= 0:
                messagebox.showerror("Error de Consistencia", "El monto de un egreso debe ser estrictamente mayor a 0.")
                return
        except ValueError:
            messagebox.showerror("Error de Tipo de Dato", f"El valor '{monto_raw}' no es un número válido.\\nRevisa si invertiste los campos.")
            return

        fecha = datetime.now().strftime("%Y-%m-%d")
        tipo_deduccion = self.c_tipo_deduccion.get() if self.var_deducible.get() == 1 else None
        cuenta_id = self.cuentas_map.get(self.c_gcuenta.get())
        conn = sqlite3.connect("data.db")
        conn.cursor().execute(
            "INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible, tipo_deduccion, cuenta_id) VALUES (?,?,?,?,?,?,?,?)",
            (desc, monto_validado, self.c_gcat.get(), fecha, self.var_factura.get(), self.var_deducible.get(), tipo_deduccion, cuenta_id)
        )
        conn.commit()
        conn.close()
        
        self.e_gdesc.delete(0, 'end')
        self.e_gmonto.delete(0, 'end')
        self.actualizar()
        self.verificar_presupuesto(self.c_gcat.get())

    def verificar_presupuesto(self, categoria):
        """Retroalimentación en el momento de captura: el punto de mayor
        apalancamiento conductual para frenar un sobregiro de presupuesto."""
        mes_actual = datetime.now().strftime("%Y-%m")
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT limite FROM presupuestos WHERE categoria=?", (categoria,))
        row = cursor.fetchone()
        if not row or not row[0] or row[0] <= 0:
            conn.close()
            return
        limite = row[0]
        cursor.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE categoria=? AND strftime('%Y-%m', fecha)=?",
                       (categoria, mes_actual))
        gastado = cursor.fetchone()[0]
        conn.close()

        if gastado > limite:
            messagebox.showwarning(
                "Presupuesto Excedido",
                f"'{categoria}' lleva ${gastado:,.2f} este mes.\nLímite: ${limite:,.2f} — excedido por ${gastado - limite:,.2f}.")
        elif gastado >= limite * 0.8:
            messagebox.showinfo(
                "Cerca del Límite",
                f"'{categoria}' lleva ${gastado:,.2f} de ${limite:,.2f}\n({gastado / limite * 100:.0f}% del presupuesto mensual).")

    def guardar_ingreso(self):
        desc = self.e_idesc.get().strip()
        monto_raw = self.e_imonto.get().strip()
        
        if not desc or not monto_raw:
            messagebox.showwarning("Campos Incompletos", "Por favor llena el origen y el monto.")
            return

        # Capa de Validación Microeconómica / Sanitización
        try:
            monto_validado = float(monto_raw)
            if monto_validado <= 0:
                messagebox.showerror("Error de Consistencia", "El monto de un ingreso debe ser mayor a 0.")
                return
        except ValueError:
            messagebox.showerror("Error de Tipo de Dato", f"El valor '{monto_raw}' no es un número contable válido.\\nVerifica tus datos.")
            return

        fecha = datetime.now().strftime("%Y-%m-%d")
        cuenta_id = self.cuentas_map.get(self.c_icuenta.get())
        conn = sqlite3.connect("data.db")
        conn.cursor().execute(
            "INSERT INTO ingresos (desc, monto, fuente, fecha, cuenta_id) VALUES (?,?,?,?,?)",
            (desc, monto_validado, self.c_ifuen.get(), fecha, cuenta_id)
        )
        conn.commit()
        conn.close()
        
        self.e_idesc.delete(0, 'end')
        self.e_imonto.delete(0, 'end')
        self.actualizar()

    def eliminar_gasto(self, gid):
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("DELETE FROM gastos WHERE id=?", (gid,))
        conn.commit()
        conn.close()
        self.actualizar()

    def eliminar_ingreso(self, iid):
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("DELETE FROM ingresos WHERE id=?", (iid,))
        conn.commit()
        conn.close()
        self.actualizar()

    def abrir_editor_fecha(self, tabla, registro_id, fecha_actual):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Editar Fecha")
        dialog.geometry("300x160")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Nueva fecha (YYYY-MM-DD):", font=("Urbanist", 12)).pack(pady=(20, 5), padx=20)
        entry_fecha = ctk.CTkEntry(dialog)
        entry_fecha.insert(0, fecha_actual)
        entry_fecha.pack(pady=5, padx=20, fill="x")

        def guardar():
            nueva_fecha = entry_fecha.get().strip()
            try:
                datetime.strptime(nueva_fecha, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Fecha Inválida", "Usa el formato YYYY-MM-DD (ej: 2026-07-06).")
                return

            conn = sqlite3.connect("data.db")
            conn.cursor().execute(f"UPDATE {tabla} SET fecha=? WHERE id=?", (nueva_fecha, registro_id))
            conn.commit()
            conn.close()
            dialog.destroy()
            self.actualizar()

        ctk.CTkButton(dialog, text="Guardar", fg_color="#3B82F6", hover_color="#2563EB", command=guardar).pack(pady=15, padx=20, fill="x")

    # =========================================================
    # CUENTAS: SALDOS CALCULADOS Y ADMINISTRACIÓN
    # =========================================================
    def obtener_cuentas_con_saldo(self):
        """Saldo real = saldo inicial + Σ ingresos − Σ gastos asignados a la cuenta."""
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.nombre, c.tipo, c.saldo_inicial
                 + COALESCE((SELECT SUM(i.monto) FROM ingresos i WHERE i.cuenta_id = c.id), 0)
                 - COALESCE((SELECT SUM(g.monto) FROM gastos g WHERE g.cuenta_id = c.id), 0)
            FROM cuentas c ORDER BY c.nombre
        """)
        filas = cursor.fetchall()
        conn.close()
        return filas

    def actualizar_cuentas(self):
        for w in self.frame_cuentas.winfo_children(): w.destroy()

        ctk.CTkLabel(self.frame_cuentas, text="💳 Cuentas:", font=("Urbanist", 13, "bold"),
                     text_color="#38BDF8").pack(side="left", padx=(15, 10), pady=8)

        cuentas = self.obtener_cuentas_con_saldo()
        self.cuentas_map = {nombre: cid for cid, nombre, _, _ in cuentas}

        if not cuentas:
            ctk.CTkLabel(self.frame_cuentas, text="Sin cuentas registradas — créalas con ⚙",
                         font=("Urbanist", 12), text_color="#64748B").pack(side="left", padx=5)
        for _cid, nombre, tipo, saldo in cuentas:
            color = "#10B981" if saldo >= 0 else "#EF4444"
            tarjeta = ctk.CTkFrame(self.frame_cuentas, fg_color="#1e293b")
            tarjeta.pack(side="left", padx=4, pady=6)
            ctk.CTkLabel(tarjeta, text=f"{nombre} ({tipo})", font=("Urbanist", 11),
                         text_color="#94A3B8").pack(padx=10, pady=(4, 0))
            ctk.CTkLabel(tarjeta, text=f"${saldo:,.2f}", font=("Urbanist", 13, "bold"),
                         text_color=color).pack(padx=10, pady=(0, 4))

        ctk.CTkButton(self.frame_cuentas, text="⚙ Administrar", width=110, fg_color="#334155",
                      hover_color="#475569", command=self.abrir_admin_cuentas).pack(side="right", padx=15, pady=8)

        # Refrescar selectores de cuenta en ambos formularios
        opciones = [SIN_CUENTA] + list(self.cuentas_map.keys())
        for menu in (self.c_gcuenta, self.c_icuenta):
            actual = menu.get()
            menu.configure(values=opciones)
            if actual not in opciones:
                menu.set(SIN_CUENTA)

    def abrir_admin_cuentas(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Administrar Cuentas")
        dialog.geometry("420x420")
        dialog.transient(self)
        dialog.grab_set()

        lista = ctk.CTkScrollableFrame(dialog, height=180)
        lista.pack(fill="both", expand=True, padx=15, pady=(15, 5))

        def refrescar_lista():
            for w in lista.winfo_children(): w.destroy()
            for cid, nombre, tipo, saldo in self.obtener_cuentas_con_saldo():
                row = ctk.CTkFrame(lista, fg_color="transparent")
                row.pack(fill="x", pady=2)
                ctk.CTkLabel(row, text=f"{nombre} ({tipo}) — ${saldo:,.2f}", font=("Urbanist", 12)).pack(side="left", padx=5)
                ctk.CTkButton(row, text="🗑", width=28, fg_color="#EF4444", hover_color="#DC2626",
                              command=lambda i=cid: eliminar(i)).pack(side="right", padx=5)

        def eliminar(cuenta_id):
            # Los movimientos históricos se conservan; solo pierden la asignación
            conn = sqlite3.connect("data.db")
            cur = conn.cursor()
            cur.execute("UPDATE gastos SET cuenta_id=NULL WHERE cuenta_id=?", (cuenta_id,))
            cur.execute("UPDATE ingresos SET cuenta_id=NULL WHERE cuenta_id=?", (cuenta_id,))
            cur.execute("DELETE FROM cuentas WHERE id=?", (cuenta_id,))
            conn.commit()
            conn.close()
            refrescar_lista()
            self.actualizar_cuentas()

        ctk.CTkLabel(dialog, text="Nueva cuenta (en tarjetas de crédito captura el saldo inicial en negativo):",
                     font=("Urbanist", 11), text_color="#94A3B8", wraplength=380).pack(pady=(5, 2), padx=15, anchor="w")
        e_nombre = ctk.CTkEntry(dialog, placeholder_text="Nombre (ej: BBVA Débito)")
        e_nombre.pack(pady=3, padx=15, fill="x")
        c_tipo = ctk.CTkOptionMenu(dialog, values=TIPOS_CUENTA)
        c_tipo.pack(pady=3, padx=15, fill="x")
        e_saldo = ctk.CTkEntry(dialog, placeholder_text="Saldo inicial hoy ($)")
        e_saldo.pack(pady=3, padx=15, fill="x")

        def crear():
            nombre = e_nombre.get().strip()
            try:
                saldo_inicial = float(e_saldo.get().strip() or 0)
            except ValueError:
                messagebox.showerror("Error", "El saldo inicial debe ser numérico.", parent=dialog)
                return
            if not nombre:
                messagebox.showerror("Error", "Ponle nombre a la cuenta.", parent=dialog)
                return
            conn = sqlite3.connect("data.db")
            try:
                conn.cursor().execute(
                    "INSERT INTO cuentas (nombre, tipo, saldo_inicial, fecha_inicial) VALUES (?,?,?,?)",
                    (nombre, c_tipo.get(), saldo_inicial, datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
            except sqlite3.IntegrityError:
                messagebox.showerror("Error", "Ya existe una cuenta con ese nombre.", parent=dialog)
            finally:
                conn.close()
            e_nombre.delete(0, 'end')
            e_saldo.delete(0, 'end')
            refrescar_lista()
            self.actualizar_cuentas()

        ctk.CTkButton(dialog, text="Crear Cuenta", fg_color="#3B82F6", hover_color="#2563EB",
                      command=crear).pack(pady=12, padx=15, fill="x")
        refrescar_lista()

    def actualizar(self):
        self.actualizar_cuentas()
        for w in self.frame_historial_gastos.winfo_children(): w.destroy()
        for w in self.frame_historial_ingresos.winfo_children(): w.destroy()

        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()

        cursor.execute("SELECT id, desc, monto, categoria, fecha FROM gastos ORDER BY id DESC LIMIT 20")
        for gid, d, m, c, fe in cursor.fetchall():
            row = ctk.CTkFrame(self.frame_historial_gastos, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"📉 ${m:,.2f} - {d} ({c}) [{fe}]", font=("Urbanist", 13)).pack(side="left", padx=5)
            ctk.CTkButton(row, text="🗑", width=30, fg_color="#EF4444", command=lambda i=gid: self.eliminar_gasto(i)).pack(side="right")
            ctk.CTkButton(row, text="📅", width=30, fg_color="#3B82F6", hover_color="#2563EB", command=lambda i=gid, fe=fe: self.abrir_editor_fecha("gastos", i, fe)).pack(side="right", padx=3)

        cursor.execute("SELECT id, desc, monto, fuente, fecha FROM ingresos ORDER BY id DESC LIMIT 20")
        for iid, d, m, f, fe in cursor.fetchall():
            row = ctk.CTkFrame(self.frame_historial_ingresos, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"📈 ${m:,.2f} - {d} ({f}) [{fe}]", font=("Urbanist", 13)).pack(side="left", padx=5)
            ctk.CTkButton(row, text="🗑", width=30, fg_color="#EF4444", command=lambda i=iid: self.eliminar_ingreso(i)).pack(side="right")
            ctk.CTkButton(row, text="📅", width=30, fg_color="#3B82F6", hover_color="#2563EB", command=lambda i=iid, fe=fe: self.abrir_editor_fecha("ingresos", i, fe)).pack(side="right", padx=3)

        conn.close()
