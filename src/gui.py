import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from src.mediator import Mediator
from src.utils import format_disease_name


class MedicalSearchGUI:
    def __init__(self):
        self.mediator = Mediator()

        self.root = tk.Tk()
        self.root.title("Medical Data Explorer")
        self.root.geometry("980x680")

        self._build_ui()

    def _build_ui(self):
        container = ttk.Frame(self.root, padding=12)
        container.pack(fill="both", expand=True)

        title = ttk.Label(
            container,
            text="Recherche de maladies et médicaments",
            font=("Helvetica", 16, "bold"),
        )
        title.pack(anchor="w", pady=(0, 8))

        help_text = (
            "Saisir les symptomes avec AND (ex: fever AND blood in urine). "
        )
        ttk.Label(container, text=help_text, wraplength=900).pack(anchor="w", pady=(0, 10))

        query_row = ttk.Frame(container)
        query_row.pack(fill="x", pady=(0, 10))

        ttk.Label(query_row, text="Requete:").pack(side="left")
        self.query_var = tk.StringVar(value="fever AND blood in urine")
        self.query_entry = ttk.Entry(query_row, textvariable=self.query_var)
        self.query_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.query_entry.bind("<Return>", self._on_search)

        ttk.Button(query_row, text="Rechercher", command=self._on_search).pack(side="left", padx=(0, 8))
        ttk.Button(query_row, text="Effacer", command=self._on_clear).pack(side="left")

        self.summary_var = tk.StringVar(value="Pret")
        ttk.Label(container, textvariable=self.summary_var, foreground="#444").pack(anchor="w", pady=(0, 8))

        notebooks = ttk.Notebook(container)
        notebooks.pack(fill="both", expand=True)

        self.tab_diseases = ttk.Frame(notebooks)
        self.tab_drugs = ttk.Frame(notebooks)
        self.tab_treatments = ttk.Frame(notebooks)

        notebooks.add(self.tab_diseases, text="Maladies")
        notebooks.add(self.tab_drugs, text="Effets secondaires")
        notebooks.add(self.tab_treatments, text="Traitements")

        self.disease_text = ScrolledText(self.tab_diseases, wrap="word", font=("Courier", 11))
        self.disease_text.pack(fill="both", expand=True, padx=8, pady=8)

        self.drug_text = ScrolledText(self.tab_drugs, wrap="word", font=("Courier", 11))
        self.drug_text.pack(fill="both", expand=True, padx=8, pady=8)

        self.treat_text = ScrolledText(self.tab_treatments, wrap="word", font=("Courier", 11))
        self.treat_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _on_clear(self):
        self.query_var.set("")
        self.summary_var.set("Pret")
        self._set_text(self.disease_text, "")
        self._set_text(self.drug_text, "")
        self._set_text(self.treat_text, "")

    def _on_search(self, _event=None):
        query = self.query_var.get().strip()
        if not query:
            self.summary_var.set("Veuillez saisir une requete.")
            return

        try:
            result = self.mediator.query_symptoms(query, verbose=False)
        except Exception as exc:
            self.summary_var.set(f"Erreur: {exc}")
            return

        diseases = sorted(result.get("diseases", []))
        drugs = sorted(result.get("drugs_causing", []))
        by_disease = result.get("treatments_by_disease", {})
        by_symptom = result.get("direct_treatments_by_symptom", {})

        self.summary_var.set(
            f"Resultats: {len(diseases)} maladie(s), {len(drugs)} medicament(s) causant ces symptomes"
        )

        disease_lines = []
        for disease in diseases[:200]:
            disease_lines.append(format_disease_name(disease))
        if not disease_lines:
            disease_lines = ["Aucune maladie trouvee."]
        self._set_text(self.disease_text, "\n".join(disease_lines))

        drug_lines = []
        for drug in drugs[:200]:
            drug_lines.append(f"{drug}")
        if not drug_lines:
            drug_lines = ["Aucun medicament trouve."]
        self._set_text(self.drug_text, "\n".join(drug_lines))

        treat_lines = ["Traitements potentiels par maladie:"]
        if by_disease:
            for disease in sorted(by_disease.keys()):
                treat_lines.append(f"- {format_disease_name(disease)}")
                for drug in by_disease[disease]:
                    treat_lines.append(f"    -> {drug}")
        else:
            treat_lines.append("Aucun traitement potentiel trouve via les maladies.")

        treat_lines.append("")
        treat_lines.append("Traitements directs par symptome:")
        if by_symptom:
            for symptom in sorted(by_symptom.keys()):
                treat_lines.append(f"- {symptom}")
                for drug in by_symptom[symptom]:
                    treat_lines.append(f"    -> {drug}")
        else:
            treat_lines.append("Aucun traitement direct trouve.")

        self._set_text(self.treat_text, "\n".join(treat_lines))

    @staticmethod
    def _set_text(widget: ScrolledText, text: str):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state="disabled")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = MedicalSearchGUI()
    app.run()
