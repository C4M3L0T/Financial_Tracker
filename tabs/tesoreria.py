import customtkinter as ctk
import sqlite3
from datetime import datetime
from tkinter import messagebox

CATEGORIAS_GASTOS = ["Vivienda", "Comida", "Transporte", "Impuestos", "Ahorros", "Salud", "Recreación", "Suscripciones", "Seguros","Servicios", "Vestimenta", "Personal", "Mascota", "Deuda", "Otros"]
FUENTES_INGRESO = ["Salario", "Freelance", "Rendimientos", "Ventas", "Otros"]

class TesoreriaTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.setup_ui()
        self.actualizar()

    def setup_ui(self):
        # --- PANEL IZQUIERDO: EGRESOS (GASTOS) ---
        panel_gastos = ctk.CTkFrame(self)
        panel_gastos.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(panel_gastos, text="Registrar Gasto (Salida)", font=("Urbanist", 18, "bold"), text_color="#EF4444").pack(pady=10)

        self.e_gdesc = ctk.CTkEntry(panel_gastos, placeholder_text="Descripción (ej: Compra de café)")
        self.e_gdesc.pack(pady=5, padx=20, fill="x")
        self.e_gmonto = ctk.CTkEntry(panel_gastos, placeholder_text="Monto Numérico ($ MXN)")
        self.e_gmonto.pack(pady=5, padx=20, fill="x")
        self.c_gcat = ctk.CTkOptionMenu(panel_gastos, values=CATEGORIAS_GASTOS)
        self.c_gcat.pack(pady=5, padx=20, fill="x")
        
        # Checkboxes de Control SAT
        self.var_factura = ctk.IntVar()
        self.var_deducible = ctk.IntVar()
        ctk.CTkCheckBox(panel_gastos, text="Solicité Factura (CFDI)", variable=self.var_factura).pack(pady=5, padx=20, anchor="w")
        ctk.CTkCheckBox(panel_gastos, text="Es Deducible (Escudo Fiscal LISR)", variable=self.var_deducible, text_color="#10B981").pack(pady=5, padx=20, anchor="w")

        ctk.CTkButton(panel_gastos, text="Registrar Salida Financiera", fg_color="#EF4444", hover_color="#DC2626", command=self.guardar_gasto).pack(pady=15, padx=20, fill="x")
        
        self.frame_historial_gastos = ctk.CTkScrollableFrame(panel_gastos, height=250)
        self.frame_historial_gastos.pack(pady=10, fill="both", expand=True, padx=10)

        # --- PANEL DERECHO: INGRESOS ---
        panel_ingresos = ctk.CTkFrame(self)
        panel_ingresos.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(panel_ingresos, text="Registrar Ingreso (Entrada)", font=("Urbanist", 18, "bold"), text_color="#10B981").pack(pady=10)

        self.e_idesc = ctk.CTkEntry(panel_ingresos, placeholder_text="Origen (ej: Pago de Cliente)")
        self.e_idesc.pack(pady=5, padx=20, fill="x")
        self.e_imonto = ctk.CTkEntry(panel_ingresos, placeholder_text="Monto Numérico ($ MXN)")
        self.e_imonto.pack(pady=5, padx=20, fill="x")
        self.c_ifuen = ctk.CTkOptionMenu(panel_ingresos, values=FUENTES_INGRESO)
        self.c_ifuen.pack(pady=5, padx=20, fill="x")

        ctk.CTkButton(panel_ingresos, text="Registrar Entrada Liquidez", fg_color="#10B981", hover_color="#059669", command=self.guardar_ingreso).pack(pady=15, padx=20, fill="x")
        
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
        conn = sqlite3.connect("data.db")
        conn.cursor().execute(
            "INSERT INTO gastos (desc, monto, categoria, fecha, con_factura, es_deducible) VALUES (?,?,?,?,?,?)",
            (desc, monto_validado, self.c_gcat.get(), fecha, self.var_factura.get(), self.var_deducible.get())
        )
        conn.commit()
        conn.close()
        
        self.e_gdesc.delete(0, 'end')
        self.e_gmonto.delete(0, 'end')
        self.actualizar()

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
        conn = sqlite3.connect("data.db")
        conn.cursor().execute(
            "INSERT INTO ingresos (desc, monto, fuente, fecha) VALUES (?,?,?,?)",
            (desc, monto_validado, self.c_ifuen.get(), fecha)
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

    def actualizar(self):
        for w in self.frame_historial_gastos.winfo_children(): w.destroy()
        for w in self.frame_historial_ingresos.winfo_children(): w.destroy()
        
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, desc, monto, categoria FROM gastos ORDER BY id DESC LIMIT 20")
        for gid, d, m, c in cursor.fetchall():
            row = ctk.CTkFrame(self.frame_historial_gastos, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"📉 ${m:,.2f} - {d} ({c})", font=("Urbanist", 13)).pack(side="left", padx=5)
            ctk.CTkButton(row, text="🗑️", width=30, fg_color="#EF4444", command=lambda i=gid: self.eliminar_gasto(i)).pack(side="right")
            
        cursor.execute("SELECT id, desc, monto, fuente FROM ingresos ORDER BY id DESC LIMIT 20")
        for iid, d, m, f in cursor.fetchall():
            row = ctk.CTkFrame(self.frame_historial_ingresos, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"📈 ${m:,.2f} - {d} ({f})", font=("Urbanist", 13)).pack(side="left", padx=5)
            ctk.CTkButton(row, text="🗑️", width=30, fg_color="#EF4444", command=lambda i=iid: self.eliminar_ingreso(i)).pack(side="right")
            
        conn.close()
