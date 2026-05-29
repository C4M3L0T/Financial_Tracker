import customtkinter as ctk
import sqlite3
from datetime import datetime
from tkcalendar import Calendar

CATEGORIAS_HABITOS = ["Físico", "Social", "Mental (o intelectual)", "Recreativo (hobbies)", "Higiene", "Otro"]

class HabitosAgendaTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.setup_ui()
        self.actualizar()

    def setup_ui(self):
        # --- COLUMNA IZQUIERDA: HÁBITOS ---
        frame_habitos = ctk.CTkFrame(self)
        frame_habitos.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(frame_habitos, text="Control de Hábitos Diarios", font=("Urbanist", 16, "bold"), text_color="#38BDF8").pack(pady=10)
        
        frame_h_input = ctk.CTkFrame(frame_habitos, fg_color="transparent")
        frame_h_input.pack(pady=5)
        
        self.entry_habito = ctk.CTkEntry(frame_h_input, placeholder_text="Nuevo hábito", width=180)
        self.entry_habito.pack(side="left", padx=5)
        
        self.combo_habito_cat = ctk.CTkOptionMenu(frame_h_input, values=CATEGORIAS_HABITOS, width=110)
        self.combo_habito_cat.pack(side="left", padx=5)
        
        ctk.CTkButton(frame_h_input, text="➕", width=40, command=self.crear_habito).pack(side="left", padx=5)
        
        self.frame_lista_habitos = ctk.CTkScrollableFrame(frame_habitos, height=450)
        self.frame_lista_habitos.pack(pady=10, fill="both", expand=True, padx=10)

        # --- COLUMNA DERECHA: AGENDA Y TEMPO ---
        frame_agenda = ctk.CTkFrame(self)
        frame_agenda.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(frame_agenda, text="Agenda & Planificación Temporal", font=("Urbanist", 16, "bold"), text_color="#10B981").pack(pady=10)
        
        self.cal = Calendar(frame_agenda, selectmode='day', date_pattern='y-mm-dd', 
                            background="#1e293b", foreground="white", headersbackground="#38bdf8")
        self.cal.pack(pady=5, padx=10, fill="x")
        
        self.entry_tarea = ctk.CTkEntry(frame_agenda, placeholder_text="Actividad o Recordatorio")
        self.entry_tarea.pack(pady=5, padx=20, fill="x")
        
        self.entry_hora = ctk.CTkEntry(frame_agenda, placeholder_text="Hora (ej: 14:30)")
        self.entry_hora.pack(pady=5, padx=20, fill="x")
        
        ctk.CTkButton(frame_agenda, text="Agendar Evento", fg_color="#10B981", hover_color="#059669", command=self.guardar_agenda).pack(pady=10, padx=20, fill="x")
        
        self.frame_lista_agenda = ctk.CTkScrollableFrame(frame_agenda, height=200)
        self.frame_lista_agenda.pack(pady=10, fill="both", expand=True, padx=10)

    def crear_habito(self):
        nombre = self.entry_habito.get().strip()
        cat = self.combo_habito_cat.get()
        if nombre:
            conn = sqlite3.connect("data.db")
            conn.cursor().execute("INSERT INTO habitos_lista (nombre, categoria) VALUES (?, ?)", (nombre, cat))
            conn.commit()
            conn.close()
            self.entry_habito.delete(0, 'end')
            self.actualizar_habitos_view()

    def alternar_habito(self, habito_id, var_estado):
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        if var_estado.get() == 1:
            cursor.execute("INSERT OR IGNORE INTO habitos_log (habito_id, fecha) VALUES (?, ?)", (habito_id, fecha_hoy))
        else:
            cursor.execute("DELETE FROM habitos_log WHERE habito_id = ? AND fecha = ?", (habito_id, fecha_hoy))
        conn.commit()
        conn.close()

    def eliminar_habito(self, habito_id):
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM habitos_lista WHERE id = ?", (habito_id,))
        cursor.execute("DELETE FROM habitos_log WHERE habito_id = ?", (habito_id,))
        conn.commit()
        conn.close()
        self.actualizar_habitos_view()

    def guardar_agenda(self):
        fecha = self.cal.get_date()
        tarea = self.entry_tarea.get().strip()
        hora = self.entry_hora.get().strip()
        if tarea and hora:
            conn = sqlite3.connect("data.db")
            conn.cursor().execute("INSERT INTO agenda (tarea, fecha, hora) VALUES (?, ?, ?)", (tarea, fecha, hora))
            conn.commit()
            conn.close()
            self.entry_tarea.delete(0, 'end')
            self.entry_hora.delete(0, 'end')
            self.actualizar_agenda_view()

    def eliminar_agenda(self, agenda_id):
        conn = sqlite3.connect("data.db")
        conn.cursor().execute("DELETE FROM agenda WHERE id = ?", (agenda_id,))
        conn.commit()
        conn.close()
        self.actualizar_agenda_view()

    def actualizar_habitos_view(self):
        for w in self.frame_lista_habitos.winfo_children(): w.destroy()
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, nombre, categoria FROM habitos_lista")
        for hid, nombre, cat in cursor.fetchall():
            cursor.execute("SELECT 1 FROM habitos_log WHERE habito_id = ? AND fecha = ?", (hid, fecha_hoy))
            hecho_hoy = cursor.fetchone() is not None
            
            row = ctk.CTkFrame(self.frame_lista_habitos, fg_color="transparent")
            row.pack(fill="x", pady=4)
            var_chk = ctk.IntVar(value=1 if hecho_hoy else 0)
            chk = ctk.CTkCheckBox(row, text=f"{nombre} [{cat}]", variable=var_chk, command=lambda h=hid, v=var_chk: self.alternar_habito(h, v))
            chk.pack(side="left", padx=5)
            ctk.CTkButton(row, text="🗑️", width=35, fg_color="#EF4444", command=lambda h=hid: self.eliminar_habito(h)).pack(side="right", padx=5)
        conn.close()

    def actualizar_agenda_view(self):
        for w in self.frame_lista_agenda.winfo_children(): w.destroy()
        conn = sqlite3.connect("data.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, tarea, fecha, hora FROM agenda ORDER BY fecha ASC, hora ASC")
        for aid, tarea, fecha, hora in cursor.fetchall():
            row = ctk.CTkFrame(self.frame_lista_agenda, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=f"📌 [{fecha} @ {hora}] {tarea}", font=("Urbanist", 13)).pack(side="left", padx=5)
            ctk.CTkButton(row, text="🗑️", width=30, fg_color="#EF4444", command=lambda i=aid: self.eliminar_agenda(i)).pack(side="right", padx=5)
        conn.close()

    def actualizar(self):
        self.actualizar_habitos_view()
        self.actualizar_agenda_view()
