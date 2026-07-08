import customtkinter as ctk
import database
from datetime import datetime
from tkinter import messagebox

CATEGORIAS_GASTOS = ["Vivienda", "Comida", "Transporte", "Impuestos", "Ahorros", "Salud", "Deportes", "Recreación", "Suscripciones", "Seguros","Servicios", "Vestimenta", "Personal", "Mascota", "Deuda", "Otros"]
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
        fila_monto_g = ctk.CTkFrame(panel_gastos, fg_color="transparent")
        fila_monto_g.pack(fill="x", padx=20, pady=5)
        self.e_gmonto = ctk.CTkEntry(fila_monto_g, placeholder_text="Monto Numérico ($ MXN)")
        self.e_gmonto.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.e_gfecha = ctk.CTkEntry(fila_monto_g, placeholder_text="Fecha (vacío = hoy)", width=150)
        self.e_gfecha.pack(side="left")
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

        self.e_buscar_g = ctk.CTkEntry(panel_gastos, placeholder_text="🔍 Buscar gasto (descripción o categoría)...", height=30)
        self.e_buscar_g.pack(pady=(0, 2), padx=10, fill="x")
        self.e_buscar_g.bind("<KeyRelease>", lambda e: self.actualizar_historiales())

        self.frame_historial_gastos = ctk.CTkScrollableFrame(panel_gastos, height=250)
        self.frame_historial_gastos.pack(pady=(2, 10), fill="both", expand=True, padx=10)

        # --- PANEL DERECHO: INGRESOS ---
        panel_ingresos = ctk.CTkFrame(self)
        panel_ingresos.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(panel_ingresos, text="Registrar Ingreso (Entrada)", font=("Urbanist", 18, "bold"), text_color="#10B981").pack(pady=10)

        self.e_idesc = ctk.CTkEntry(panel_ingresos, placeholder_text="Origen (ej: Pago de Cliente)")
        self.e_idesc.pack(pady=5, padx=20, fill="x")
        fila_monto_i = ctk.CTkFrame(panel_ingresos, fg_color="transparent")
        fila_monto_i.pack(fill="x", padx=20, pady=5)
        self.e_imonto = ctk.CTkEntry(fila_monto_i, placeholder_text="Monto Numérico ($ MXN)")
        self.e_imonto.pack(side="left", expand=True, fill="x", padx=(0, 5))
        self.e_ifecha = ctk.CTkEntry(fila_monto_i, placeholder_text="Fecha (vacío = hoy)", width=150)
        self.e_ifecha.pack(side="left")
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

        self.e_buscar_i = ctk.CTkEntry(panel_ingresos, placeholder_text="🔍 Buscar ingreso (descripción o fuente)...", height=30)
        self.e_buscar_i.pack(pady=(0, 2), padx=10, fill="x")
        self.e_buscar_i.bind("<KeyRelease>", lambda e: self.actualizar_historiales())

        self.frame_historial_ingresos = ctk.CTkScrollableFrame(panel_ingresos, height=250)
        self.frame_historial_ingresos.pack(pady=(2, 10), fill="both", expand=True, padx=10)

    def resolver_fecha(self, entry_fecha):
        """Fecha opcional de captura: vacío = hoy; devuelve None si es inválida
        (para capturar con retraso sin el doble paso de corregir con 📅)."""
        texto = entry_fecha.get().strip()
        if not texto:
            return datetime.now().strftime("%Y-%m-%d")
        try:
            datetime.strptime(texto, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Fecha Inválida", f"'{texto}' no es válida. Usa YYYY-MM-DD o déjala vacía para hoy.")
            return None
        entry_fecha.delete(0, 'end')
        return texto

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

        fecha = self.resolver_fecha(self.e_gfecha)
        if fecha is None:
            return
        tipo_deduccion = self.c_tipo_deduccion.get() if self.var_deducible.get() == 1 else None
        cuenta_id = self.cuentas_map.get(self.c_gcuenta.get())
        conn = database.conectar()
        conn.cursor().execute(
            "INSERT INTO gastos (`desc`, monto, categoria, fecha, con_factura, es_deducible, tipo_deduccion, cuenta_id) VALUES (?,?,?,?,?,?,?,?)",
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
        conn = database.conectar()
        cursor = conn.cursor()
        cursor.execute("SELECT limite FROM presupuestos WHERE categoria=?", (categoria,))
        row = cursor.fetchone()
        if not row or not row[0] or row[0] <= 0:
            conn.close()
            return
        limite = row[0]
        cursor.execute("SELECT COALESCE(SUM(monto),0) FROM gastos WHERE categoria=? AND LEFT(fecha, 7)=?",
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

        fecha = self.resolver_fecha(self.e_ifecha)
        if fecha is None:
            return
        cuenta_id = self.cuentas_map.get(self.c_icuenta.get())
        conn = database.conectar()
        conn.cursor().execute(
            "INSERT INTO ingresos (`desc`, monto, fuente, fecha, cuenta_id) VALUES (?,?,?,?,?)",
            (desc, monto_validado, self.c_ifuen.get(), fecha, cuenta_id)
        )
        conn.commit()
        conn.close()
        
        self.e_idesc.delete(0, 'end')
        self.e_imonto.delete(0, 'end')
        self.actualizar()

    def eliminar_gasto(self, gid):
        if not messagebox.askyesno("Confirmar", "¿Eliminar este gasto?"):
            return
        conn = database.conectar()
        conn.cursor().execute("DELETE FROM gastos WHERE id=?", (gid,))
        conn.commit()
        conn.close()
        self.actualizar()

    def eliminar_ingreso(self, iid):
        if not messagebox.askyesno("Confirmar", "¿Eliminar este ingreso?"):
            return
        conn = database.conectar()
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

            conn = database.conectar()
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
        """Delegado a database.obtener_saldos_cuentas() (fuente única de saldos)."""
        return [(cid, nombre, tipo, saldo)
                for cid, nombre, tipo, _tasa, saldo in database.obtener_saldos_cuentas()]

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
                      hover_color="#475569", command=self.abrir_admin_cuentas).pack(side="right", padx=(5, 15), pady=8)
        ctk.CTkButton(self.frame_cuentas, text="⇄ Pagar tarjeta / Transferir", width=170, fg_color="#3B82F6",
                      hover_color="#2563EB", command=self.abrir_transferencia).pack(side="right", padx=5, pady=8)
        ctk.CTkButton(self.frame_cuentas, text="🔁 Recurrentes", width=120, fg_color="#A855F7",
                      hover_color="#9333EA", command=self.abrir_recurrentes).pack(side="right", padx=5, pady=8)
        ctk.CTkButton(self.frame_cuentas, text="⬇ CSV", width=70, fg_color="#10B981",
                      hover_color="#059669", command=self.exportar_csv).pack(side="right", padx=5, pady=8)

        # Refrescar selectores de cuenta en ambos formularios
        opciones = [SIN_CUENTA] + list(self.cuentas_map.keys())
        for menu in (self.c_gcuenta, self.c_icuenta):
            actual = menu.get()
            menu.configure(values=opciones)
            if actual not in opciones:
                menu.set(SIN_CUENTA)

    def abrir_transferencia(self):
        """Pago de tarjeta o movimiento entre cuentas propias: ajusta saldos
        sin registrar ingreso ni gasto (el gasto real ocurrió en la compra)."""
        cuentas = self.obtener_cuentas_con_saldo()
        if len(cuentas) < 2:
            messagebox.showinfo("Faltan Cuentas", "Necesitas al menos dos cuentas para transferir.\nCréalas con ⚙ Administrar.")
            return

        nombres = [f"{nombre} (${saldo:,.2f})" for _, nombre, _, saldo in cuentas]
        ids_por_nombre = {n: cuentas[i][0] for i, n in enumerate(nombres)}
        credito_idx = next((i for i, c in enumerate(cuentas) if c[2] == "Crédito"), None)

        dialog = ctk.CTkToplevel(self)
        dialog.title("Pagar Tarjeta / Transferir")
        dialog.geometry("400x420")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Cuenta de ORIGEN (de dónde sale el dinero):",
                     font=("Urbanist", 11), text_color="#94A3B8").pack(pady=(15, 2), padx=20, anchor="w")
        c_origen = ctk.CTkOptionMenu(dialog, values=nombres)
        c_origen.pack(pady=2, padx=20, fill="x")

        ctk.CTkLabel(dialog, text="Cuenta de DESTINO (tarjeta a pagar u otra cuenta):",
                     font=("Urbanist", 11), text_color="#94A3B8").pack(pady=(10, 2), padx=20, anchor="w")
        c_destino = ctk.CTkOptionMenu(dialog, values=nombres)
        if credito_idx is not None:
            c_destino.set(nombres[credito_idx])
        c_destino.pack(pady=2, padx=20, fill="x")

        e_monto = ctk.CTkEntry(dialog, placeholder_text="Monto ($)")
        e_monto.pack(pady=(10, 2), padx=20, fill="x")
        e_desc = ctk.CTkEntry(dialog, placeholder_text="Descripción (ej: Pago tarjeta julio)")
        e_desc.pack(pady=2, padx=20, fill="x")

        def transferir():
            origen, destino = c_origen.get(), c_destino.get()
            if origen == destino:
                messagebox.showerror("Error", "Origen y destino deben ser cuentas distintas.", parent=dialog)
                return
            try:
                monto = float(e_monto.get().strip())
                if monto <= 0: raise ValueError
            except ValueError:
                messagebox.showerror("Error", "El monto debe ser un número mayor a cero.", parent=dialog)
                return

            conn = database.conectar()
            conn.cursor().execute(
                "INSERT INTO transferencias (cuenta_origen, cuenta_destino, monto, fecha, descripcion) VALUES (?,?,?,?,?)",
                (ids_por_nombre[origen], ids_por_nombre[destino], monto,
                 datetime.now().strftime("%Y-%m-%d"), e_desc.get().strip() or "Transferencia"))
            conn.commit()
            conn.close()
            dialog.destroy()
            self.actualizar_cuentas()

        ctk.CTkButton(dialog, text="Ejecutar Transferencia", fg_color="#3B82F6", hover_color="#2563EB",
                      command=transferir).pack(pady=12, padx=20, fill="x")

        # Últimas transferencias, con opción de deshacer
        ctk.CTkLabel(dialog, text="Últimas transferencias:", font=("Urbanist", 11),
                     text_color="#94A3B8").pack(pady=(5, 2), padx=20, anchor="w")
        lista_tr = ctk.CTkScrollableFrame(dialog, height=110)
        lista_tr.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        def refrescar_transferencias():
            for w in lista_tr.winfo_children(): w.destroy()
            conn = database.conectar()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, co.nombre, cd.nombre, t.monto, t.fecha
                FROM transferencias t
                LEFT JOIN cuentas co ON co.id = t.cuenta_origen
                LEFT JOIN cuentas cd ON cd.id = t.cuenta_destino
                ORDER BY t.id DESC LIMIT 5
            """)
            filas = cursor.fetchall()
            conn.close()
            for tid, org, dst, monto, fecha in filas:
                row = ctk.CTkFrame(lista_tr, fg_color="transparent")
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(row, text=f"{fecha}: {org or '?'} → {dst or '?'} ${monto:,.2f}",
                             font=("Urbanist", 11)).pack(side="left", padx=2)
                ctk.CTkButton(row, text="🗑", width=26, fg_color="#EF4444", hover_color="#DC2626",
                              command=lambda i=tid: borrar_transferencia(i)).pack(side="right")

        def borrar_transferencia(tid):
            if not messagebox.askyesno("Confirmar", "¿Deshacer esta transferencia?", parent=dialog):
                return
            conn = database.conectar()
            conn.cursor().execute("DELETE FROM transferencias WHERE id=?", (tid,))
            conn.commit()
            conn.close()
            refrescar_transferencias()
            self.actualizar_cuentas()

        refrescar_transferencias()

    def abrir_recurrentes(self):
        """Plantillas que se materializan solas cada mes (quincenas, renta,
        suscripciones): eliminan la captura manual repetitiva."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Movimientos Recurrentes")
        dialog.geometry("520x560")
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Se generan solos al llegar su día del mes (aunque la app esté cerrada, el bot los registra).",
                     font=("Urbanist", 11), text_color="#94A3B8", wraplength=470).pack(pady=(12, 4), padx=20, anchor="w")

        # --- Formulario ---
        fila1 = ctk.CTkFrame(dialog, fg_color="transparent")
        fila1.pack(fill="x", padx=20, pady=3)
        var_tipo = ctk.StringVar(value="Gasto")
        c_categoria = ctk.CTkOptionMenu(fila1, values=CATEGORIAS_GASTOS, width=200)

        def cambiar_tipo(valor):
            c_categoria.configure(values=FUENTES_INGRESO if valor == "Ingreso" else CATEGORIAS_GASTOS)
            c_categoria.set(FUENTES_INGRESO[0] if valor == "Ingreso" else CATEGORIAS_GASTOS[0])

        ctk.CTkOptionMenu(fila1, variable=var_tipo, values=["Gasto", "Ingreso"], width=110,
                          command=cambiar_tipo).pack(side="left", padx=(0, 5))
        c_categoria.pack(side="left", padx=5)

        e_desc = ctk.CTkEntry(dialog, placeholder_text="Descripción (ej: Renta / Quincena 1)")
        e_desc.pack(pady=3, padx=20, fill="x")

        fila2 = ctk.CTkFrame(dialog, fg_color="transparent")
        fila2.pack(fill="x", padx=20, pady=3)
        e_monto = ctk.CTkEntry(fila2, placeholder_text="Monto $", width=140)
        e_monto.pack(side="left", padx=(0, 5))
        e_dia = ctk.CTkEntry(fila2, placeholder_text="Día del mes (1-31)", width=150)
        e_dia.pack(side="left", padx=5)
        c_cuenta = ctk.CTkOptionMenu(fila2, values=[SIN_CUENTA] + list(self.cuentas_map.keys()), width=150)
        c_cuenta.pack(side="left", padx=5)

        lista = ctk.CTkScrollableFrame(dialog, height=230)

        def refrescar_lista():
            for w in lista.winfo_children(): w.destroy()
            conn = database.conectar()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.id, r.tipo, r.descripcion, r.monto, r.categoria, r.dia_mes, r.activo, c.nombre
                FROM recurrentes r LEFT JOIN cuentas c ON c.id = r.cuenta_id ORDER BY r.dia_mes
            """)
            filas = cursor.fetchall()
            conn.close()
            if not filas:
                ctk.CTkLabel(lista, text="Sin recurrentes definidos.", text_color="#64748B").pack(pady=15)
            for rid, tipo, desc, monto, cat, dia, activo, cta in filas:
                row = ctk.CTkFrame(lista, fg_color="#1e293b")
                row.pack(fill="x", pady=2, padx=2)
                ctk.CTkButton(row, text="🗑", width=28, fg_color="#EF4444", hover_color="#DC2626",
                              command=lambda i=rid: eliminar(i)).pack(side="right", padx=6, pady=4)
                ctk.CTkButton(row, text="✏", width=28, fg_color="#3B82F6", hover_color="#2563EB",
                              command=lambda i=rid: editar(i)).pack(side="right", padx=2)
                var_act = ctk.IntVar(value=activo)
                ctk.CTkCheckBox(row, text="", variable=var_act, width=24,
                                command=lambda i=rid, v=var_act: alternar(i, v)).pack(side="right")
                icono = "📈" if tipo == "ingreso" else "📉"
                extra = f" → {cta}" if cta else ""
                ctk.CTkLabel(row, text=f"{icono} Día {dia}: {desc} ${monto:,.2f} ({cat}){extra}",
                             font=("Urbanist", 12), anchor="w").pack(side="left", padx=8, pady=6, fill="x", expand=True)

        def crear():
            desc = e_desc.get().strip()
            try:
                monto = float(e_monto.get().strip())
                dia = int(e_dia.get().strip())
                if monto <= 0 or not (1 <= dia <= 31): raise ValueError
            except ValueError:
                messagebox.showerror("Error", "Monto positivo y día entre 1 y 31.", parent=dialog)
                return
            if not desc:
                messagebox.showerror("Error", "Ponle descripción.", parent=dialog)
                return
            tipo = "ingreso" if var_tipo.get() == "Ingreso" else "gasto"
            cuenta_id = self.cuentas_map.get(c_cuenta.get())
            conn = database.conectar()
            conn.cursor().execute("""
                INSERT INTO recurrentes (tipo, descripcion, monto, categoria, dia_mes, cuenta_id, activo)
                VALUES (?,?,?,?,?,?,1)
            """, (tipo, desc, monto, c_categoria.get(), dia, cuenta_id))
            conn.commit()
            conn.close()
            e_desc.delete(0, 'end'); e_monto.delete(0, 'end'); e_dia.delete(0, 'end')
            # Materializar de una vez si el día de este mes ya pasó
            database.generar_recurrentes()
            refrescar_lista()
            self.actualizar()

        def editar(rid):
            conn = database.conectar()
            fila = conn.cursor().execute("SELECT descripcion, monto, dia_mes FROM recurrentes WHERE id=?", (rid,)).fetchone()
            conn.close()
            if not fila:
                return
            d2 = ctk.CTkToplevel(dialog)
            d2.title("Editar Recurrente")
            d2.geometry("340x280")
            d2.transient(dialog)
            d2.grab_set()

            e_d = ctk.CTkEntry(d2)
            e_d.insert(0, fila[0])
            ctk.CTkLabel(d2, text="Descripción:", font=("Urbanist", 11), text_color="#94A3B8").pack(pady=(12, 0), padx=20, anchor="w")
            e_d.pack(pady=2, padx=20, fill="x")
            ctk.CTkLabel(d2, text="Monto $:", font=("Urbanist", 11), text_color="#94A3B8").pack(padx=20, anchor="w")
            e_m = ctk.CTkEntry(d2)
            e_m.insert(0, f"{fila[1]:g}")
            e_m.pack(pady=2, padx=20, fill="x")
            ctk.CTkLabel(d2, text="Día del mes (1-31):", font=("Urbanist", 11), text_color="#94A3B8").pack(padx=20, anchor="w")
            e_di = ctk.CTkEntry(d2)
            e_di.insert(0, str(fila[2]))
            e_di.pack(pady=2, padx=20, fill="x")

            def guardar_edicion():
                try:
                    monto_n = float(e_m.get().strip())
                    dia_n = int(e_di.get().strip())
                    if monto_n <= 0 or not (1 <= dia_n <= 31): raise ValueError
                except ValueError:
                    messagebox.showerror("Error", "Monto positivo y día entre 1 y 31.", parent=d2)
                    return
                desc_n = e_d.get().strip()
                if not desc_n:
                    messagebox.showerror("Error", "Ponle descripción.", parent=d2)
                    return
                conn = database.conectar()
                conn.cursor().execute("UPDATE recurrentes SET descripcion=?, monto=?, dia_mes=? WHERE id=?",
                                      (desc_n, monto_n, dia_n, rid))
                conn.commit()
                conn.close()
                d2.destroy()
                refrescar_lista()

            ctk.CTkButton(d2, text="Guardar cambios", fg_color="#3B82F6", hover_color="#2563EB",
                          command=guardar_edicion).pack(pady=14, padx=20, fill="x")

        def eliminar(rid):
            if not messagebox.askyesno("Confirmar", "¿Eliminar esta plantilla recurrente?\n(Los movimientos ya generados se conservan)", parent=dialog):
                return
            conn = database.conectar()
            conn.cursor().execute("DELETE FROM recurrentes WHERE id=?", (rid,))
            conn.commit()
            conn.close()
            refrescar_lista()

        def alternar(rid, var):
            conn = database.conectar()
            conn.cursor().execute("UPDATE recurrentes SET activo=? WHERE id=?", (var.get(), rid))
            conn.commit()
            conn.close()

        ctk.CTkButton(dialog, text="➕ Crear Recurrente", fg_color="#A855F7", hover_color="#9333EA",
                      command=crear).pack(pady=8, padx=20, fill="x")
        ctk.CTkLabel(dialog, text="Activos (✓) / pausados:", font=("Urbanist", 11),
                     text_color="#94A3B8").pack(pady=(4, 2), padx=20, anchor="w")
        lista.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        refrescar_lista()

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
                ctk.CTkButton(row, text="✏", width=28, fg_color="#3B82F6", hover_color="#2563EB",
                              command=lambda i=cid: editar(i)).pack(side="right")

        def editar(cuenta_id):
            conn = database.conectar()
            fila = conn.cursor().execute(
                "SELECT nombre, tipo, saldo_inicial, COALESCE(tasa_anual, 0) FROM cuentas WHERE id=?",
                (cuenta_id,)).fetchone()
            conn.close()
            if not fila:
                return
            d2 = ctk.CTkToplevel(dialog)
            d2.title("Editar Cuenta")
            d2.geometry("360x360")
            d2.transient(dialog)
            d2.grab_set()

            ctk.CTkLabel(d2, text="Nombre:", font=("Urbanist", 11), text_color="#94A3B8").pack(pady=(12, 0), padx=20, anchor="w")
            e_nom = ctk.CTkEntry(d2)
            e_nom.insert(0, fila[0])
            e_nom.pack(pady=2, padx=20, fill="x")
            c_tip = ctk.CTkOptionMenu(d2, values=TIPOS_CUENTA)
            c_tip.set(fila[1])
            c_tip.pack(pady=6, padx=20, fill="x")
            ctk.CTkLabel(d2, text="Saldo inicial (crédito en negativo):", font=("Urbanist", 11), text_color="#94A3B8").pack(padx=20, anchor="w")
            e_sal = ctk.CTkEntry(d2)
            e_sal.insert(0, f"{fila[2]:g}")
            e_sal.pack(pady=2, padx=20, fill="x")
            ctk.CTkLabel(d2, text="CAT/tasa anual % (solo crédito):", font=("Urbanist", 11), text_color="#94A3B8").pack(padx=20, anchor="w")
            e_tas = ctk.CTkEntry(d2)
            e_tas.insert(0, f"{fila[3]:g}")
            e_tas.pack(pady=2, padx=20, fill="x")

            def guardar_edicion():
                nombre_nuevo = e_nom.get().strip()
                try:
                    saldo_ini = float(e_sal.get().strip())
                    tasa = float(e_tas.get().strip() or 0)
                    if tasa < 0: raise ValueError
                except ValueError:
                    messagebox.showerror("Error", "Saldo y tasa deben ser numéricos.", parent=d2)
                    return
                if not nombre_nuevo:
                    messagebox.showerror("Error", "El nombre no puede quedar vacío.", parent=d2)
                    return
                conn = database.conectar()
                try:
                    conn.cursor().execute(
                        "UPDATE cuentas SET nombre=?, tipo=?, saldo_inicial=?, tasa_anual=? WHERE id=?",
                        (nombre_nuevo, c_tip.get(), saldo_ini, tasa, cuenta_id))
                    conn.commit()
                except database.IntegrityError:
                    messagebox.showerror("Error", "Ya existe otra cuenta con ese nombre.", parent=d2)
                    return
                finally:
                    conn.close()
                d2.destroy()
                refrescar_lista()
                self.actualizar_cuentas()

            ctk.CTkButton(d2, text="Guardar cambios", fg_color="#3B82F6", hover_color="#2563EB",
                          command=guardar_edicion).pack(pady=14, padx=20, fill="x")

        def eliminar(cuenta_id):
            if not messagebox.askyesno("Confirmar", "¿Eliminar esta cuenta?\nSus movimientos se conservan pero quedan sin cuenta asignada.", parent=dialog):
                return
            # Los movimientos históricos se conservan; solo pierden la asignación
            conn = database.conectar()
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
            conn = database.conectar()
            try:
                conn.cursor().execute(
                    "INSERT INTO cuentas (nombre, tipo, saldo_inicial, fecha_inicial) VALUES (?,?,?,?)",
                    (nombre, c_tipo.get(), saldo_inicial, datetime.now().strftime("%Y-%m-%d")))
                conn.commit()
            except database.IntegrityError:
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

    def exportar_csv(self):
        """Exporta gastos e ingresos completos (con cuenta) a exportes/ — respaldo
        legible y análisis externo en Excel/Sheets."""
        import csv
        import os
        os.makedirs("exportes", exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d_%H%M")
        ruta_gastos = os.path.join("exportes", f"gastos_{marca}.csv")
        ruta_ingresos = os.path.join("exportes", f"ingresos_{marca}.csv")

        conn = database.conectar()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT g.id, g.fecha, g.`desc`, g.monto, g.categoria, g.con_factura,
                   g.es_deducible, COALESCE(g.tipo_deduccion, ''), COALESCE(c.nombre, '')
            FROM gastos g LEFT JOIN cuentas c ON c.id = g.cuenta_id ORDER BY g.fecha, g.id
        """)
        gastos = cursor.fetchall()
        cursor.execute("""
            SELECT i.id, i.fecha, i.`desc`, i.monto, i.fuente, COALESCE(c.nombre, '')
            FROM ingresos i LEFT JOIN cuentas c ON c.id = i.cuenta_id ORDER BY i.fecha, i.id
        """)
        ingresos = cursor.fetchall()
        conn.close()

        # utf-8-sig: Excel abre los acentos correctamente
        with open(ruta_gastos, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["id", "fecha", "descripcion", "monto", "categoria", "con_factura", "es_deducible", "tipo_deduccion", "cuenta"])
            w.writerows(gastos)
        with open(ruta_ingresos, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["id", "fecha", "descripcion", "monto", "fuente", "cuenta"])
            w.writerows(ingresos)

        messagebox.showinfo("Exportado",
                            f"{len(gastos)} gastos → {ruta_gastos}\n{len(ingresos)} ingresos → {ruta_ingresos}")

    def actualizar_historiales(self):
        for w in self.frame_historial_gastos.winfo_children(): w.destroy()
        for w in self.frame_historial_ingresos.winfo_children(): w.destroy()

        conn = database.conectar()
        cursor = conn.cursor()

        filtro_g = self.e_buscar_g.get().strip()
        if filtro_g:
            like = f"%{filtro_g}%"
            cursor.execute("""SELECT id, `desc`, monto, categoria, fecha FROM gastos
                              WHERE `desc` LIKE ? OR categoria LIKE ? ORDER BY id DESC LIMIT 30""", (like, like))
        else:
            cursor.execute("SELECT id, `desc`, monto, categoria, fecha FROM gastos ORDER BY id DESC LIMIT 20")
        for gid, d, m, c, fe in cursor.fetchall():
            row = ctk.CTkFrame(self.frame_historial_gastos, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"📉 ${m:,.2f} - {d} ({c}) [{fe}]", font=("Urbanist", 13)).pack(side="left", padx=5)
            ctk.CTkButton(row, text="🗑", width=30, fg_color="#EF4444", command=lambda i=gid: self.eliminar_gasto(i)).pack(side="right")
            ctk.CTkButton(row, text="📅", width=30, fg_color="#3B82F6", hover_color="#2563EB", command=lambda i=gid, fe=fe: self.abrir_editor_fecha("gastos", i, fe)).pack(side="right", padx=3)

        filtro_i = self.e_buscar_i.get().strip()
        if filtro_i:
            like = f"%{filtro_i}%"
            cursor.execute("""SELECT id, `desc`, monto, fuente, fecha FROM ingresos
                              WHERE `desc` LIKE ? OR fuente LIKE ? ORDER BY id DESC LIMIT 30""", (like, like))
        else:
            cursor.execute("SELECT id, `desc`, monto, fuente, fecha FROM ingresos ORDER BY id DESC LIMIT 20")
        for iid, d, m, f, fe in cursor.fetchall():
            row = ctk.CTkFrame(self.frame_historial_ingresos, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"📈 ${m:,.2f} - {d} ({f}) [{fe}]", font=("Urbanist", 13)).pack(side="left", padx=5)
            ctk.CTkButton(row, text="🗑", width=30, fg_color="#EF4444", command=lambda i=iid: self.eliminar_ingreso(i)).pack(side="right")
            ctk.CTkButton(row, text="📅", width=30, fg_color="#3B82F6", hover_color="#2563EB", command=lambda i=iid, fe=fe: self.abrir_editor_fecha("ingresos", i, fe)).pack(side="right", padx=3)

        conn.close()

    def actualizar(self):
        self.actualizar_cuentas()
        self.actualizar_historiales()
