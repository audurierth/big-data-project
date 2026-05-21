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

        self.disease_tree = self._build_result_tree(self.tab_diseases)

        self.drug_tree = self._build_result_tree(self.tab_drugs)

        self.treat_text = ScrolledText(self.tab_treatments, wrap="word", font=("Courier", 11))
        self.treat_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _on_clear(self):
        self.query_var.set("")
        self.summary_var.set("Pret")
        self._set_tree(self.disease_tree, [])
        self._set_tree(self.drug_tree, [])
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

        diseases = result.get("diseases", [])
        drugs = result.get("drugs_causing", [])
        by_disease = result.get("treatments_by_disease", {})
        by_symptom = result.get("direct_treatments_by_symptom", {})

        self.summary_var.set(
            f"Resultats: {len(diseases)} maladie(s), {len(drugs)} medicament(s) causant ces symptomes"
        )

        self._set_tree(self.disease_tree, [(format_disease_name(disease["name"]), disease["score"], ", ".join(sorted(disease.get("sources", [])))) for disease in diseases[:200]])
        if not diseases:
            self._set_tree(self.disease_tree, [])

        self._set_tree(self.drug_tree, [(drug["name"], drug["score"], ", ".join(sorted(drug.get("sources", [])))) for drug in drugs[:200]])
        if not drugs:
            self._set_tree(self.drug_tree, [])

        treat_lines = ["Traitements potentiels par maladie:"]
        if by_disease:
            for disease in sorted(by_disease.keys(), key=str.lower):
                treat_lines.append(f"- {format_disease_name(disease)}")
                for drug in by_disease[disease]:
                    treat_lines.append(f"    -> {self._format_result_line(drug['name'], drug)}")
        else:
            treat_lines.append("Aucun traitement potentiel trouve via les maladies.")

        treat_lines.append("")
        treat_lines.append("Traitements directs par symptome:")
        if by_symptom:
            for symptom in sorted(by_symptom.keys(), key=str.lower):
                treat_lines.append(f"- {symptom}")
                for drug in by_symptom[symptom]:
                    treat_lines.append(f"    -> {self._format_result_line(drug['name'], drug)}")
        else:
            treat_lines.append("Aucun traitement direct trouve.")

        self._set_text(self.treat_text, "\n".join(treat_lines))

    @staticmethod
    def _build_result_tree(parent: ttk.Frame) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        tree = ttk.Treeview(frame, columns=("name", "score", "source"), show="headings")
        tree.heading("name", text="Nom")
        tree.heading("score", text="Score")
        tree.heading("source", text="Source")
        tree.column("name", width=520, minwidth=260, stretch=True, anchor="w")
        tree.column("score", width=90, minwidth=70, stretch=False, anchor="center")
        tree.column("source", width=260, minwidth=160, stretch=True, anchor="w")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        xscrollbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=scrollbar.set, xscrollcommand=xscrollbar.set)

        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        xscrollbar.pack(side="bottom", fill="x")
        return tree

    @staticmethod
    def _set_tree(tree: ttk.Treeview, rows):
        for item in tree.get_children():
            tree.delete(item)
        for name, score, source in rows:
            tree.insert("", "end", values=(name, score, source))

    @staticmethod
    def _set_text(widget: ScrolledText, text: str):
        widget.configure(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.configure(state="disabled")

    @staticmethod
    def _format_result_line(name: str, entry: dict) -> str:
        score = entry.get("score", 0)
        sources = ", ".join(sorted(entry.get("sources", [])))
        if sources:
            return f"{name} [score={score} | source={sources}]"
        return f"{name} [score={score}]"

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = MedicalSearchGUI()
    app.run()
