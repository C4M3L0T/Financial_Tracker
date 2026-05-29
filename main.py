import customtkinter as ctk
import database
from tabs.habitos_agenda import HabitosAgendaTab
from tabs.tesoreria import TesoreriaTab
from tabs.planeacion import PlaneacionTab
from tabs.impuestos_inversion import ImpuestosInversionTab
from tabs.balance_general import BalanceGeneralTab # <-- IMPORTACIÓN NUEVA
from tabs.dashboard import DashboardTab
from tabs.auditoria import AuditoriaTab

class ArchProductivityApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Arch Productivity Hub - Enterprise v6.5")
        self.geometry("1200x800")
        self.minsize(1100, 750)
        
        # Inicializar capa de datos unificada
        database.init_db()

        # Inicialización de la Vista de Pestañas (Tabs)
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)
        
        self.tab_habitos = self.tabview.add("Hábitos & Agenda")
        self.tab_tesoreria = self.tabview.add("Tesorería")
        self.tab_planeacion = self.tabview.add("Planeación (MSI)")
        self.tab_impuestos = self.tabview.add("Impuestos e Inversión")
        self.tab_balance = self.tabview.add("Balance General")
        self.tab_dashboard = self.tabview.add("Dashboard Financiero")
        self.tab_auditoria = self.tabview.add("Auditoría Patrimonial")

        # Inyección de dependencias de los módulos desacoplados
        self.habitos_ui = HabitosAgendaTab(self.tab_habitos)
        self.habitos_ui.pack(fill="both", expand=True)

        self.tesoreria_ui = TesoreriaTab(self.tab_tesoreria)
        self.tesoreria_ui.pack(fill="both", expand=True)

        self.planeacion_ui = PlaneacionTab(self.tab_planeacion)
        self.planeacion_ui.pack(fill="both", expand=True)

        self.impuestos_ui = ImpuestosInversionTab(self.tab_impuestos)
        self.impuestos_ui.pack(fill="both", expand=True)


        self.balance_ui = BalanceGeneralTab(self.tab_balance)
        self.balance_ui.pack(fill="both", expand=True)

        self.dashboard_ui = DashboardTab(self.tab_dashboard)
        self.dashboard_ui.pack(fill="both", expand=True)

        self.auditoria_ui = AuditoriaTab(self.tab_auditoria)
        self.auditoria_ui.pack(fill="both", expand=True)


        self.tabview.configure(command=self.orquestar_refrescos)

    def orquestar_refrescos(self):
        pestana_activa = self.tabview.get()
        if pestana_activa == "Dashboard Financiero":
            self.dashboard_ui.actualizar()
        elif pestana_activa == "Tesorería":
            self.tesoreria_ui.actualizar()
        elif pestana_activa == "Planeación (MSI)":
            self.planeacion_ui.actualizar()
        elif pestana_activa == "Hábitos & Agenda":
            self.habitos_ui.actualizar()
        elif pestana_activa == "Impuestos e Inversión":
            self.impuestos_ui.recalcular_metricas()
        elif pestana_activa == "Balance General":
            self.balance_ui.recalcular_patrimonio()
        elif pestana_activa == "Auditoría Patrimonial":
            self.auditoria_ui.ejecutar_auditoria()

if __name__ == "__main__":
    app = ArchProductivityApp()
    app.mainloop()
