import warnings
warnings.filterwarnings("ignore")

import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import re

from src.mediator import Mediator
from src.utils import format_disease_name


class MedicalSearchGUI:
    def __init__(self):
        self.mediator = Mediator()

        self.root = tk.Tk()
        self.root.title("Exploreur de données médicales")
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
            "Saisir les symptomes avec OR ou AND (ex: fever and nausea). "
            "Vous pouvez utiliser '*' comme joker partiel dans un symptome (ex: fev*)."
        )
        ttk.Label(container, text=help_text, wraplength=900).pack(anchor="w", pady=(0, 10))

        query_row = ttk.Frame(container)
        query_row.pack(fill="x", pady=(0, 10))

        ttk.Label(query_row, text="Requete:").pack(side="left")
        self.query_var = tk.StringVar(value="fever OR hemorrhage OR rash OR fatigue OR headache OR conjunctivitis")
        self.query_entry = ttk.Entry(query_row, textvariable=self.query_var)
        self.query_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.query_entry.bind("<Return>", self._on_search)

        ttk.Button(query_row, text="Rechercher", command=self._on_search).pack(side="left", padx=(0, 8))
        ttk.Button(query_row, text="Effacer", command=self._on_clear).pack(side="left", padx=(0, 8))
        ttk.Button(query_row, text="Statistiques", command=self._on_stats).pack(side="left", padx=(0, 8))
        ttk.Button(query_row, text="Visualiser", command=self._on_visualize).pack(side="left", padx=(0, 16))

        ttk.Label(query_row, text="Trier par :").pack(side="left", padx=(0, 4))
        self.sort_var = tk.StringVar(value="Défaut (Nb symptômes > Proba SIDER)")
        self.sort_cb = ttk.Combobox(
            query_row, 
            textvariable=self.sort_var, 
            values=["Défaut (Nb symptômes > Proba SIDER)", "Proba SIDER totale (Décroissant)"],
            state="readonly",
            width=35
        )
        self.sort_cb.pack(side="left")
        self.sort_cb.bind("<<ComboboxSelected>>", self._on_search)

        self.summary_var = tk.StringVar(value="Pret")
        ttk.Label(container, textvariable=self.summary_var, foreground="#444").pack(anchor="w", pady=(0, 8))

        notebooks = ttk.Notebook(container)
        self.notebooks = notebooks
        notebooks.pack(fill="both", expand=True)

        self.tab_diseases = ttk.Frame(notebooks)
        self.tab_drugs = ttk.Frame(notebooks)
        self.tab_treatments = ttk.Frame(notebooks)
        self.tab_stats = ttk.Frame(notebooks)

        notebooks.add(self.tab_diseases, text="Maladies")
        notebooks.add(self.tab_drugs, text="Effets secondaires")
        notebooks.add(self.tab_treatments, text="Traitements")
        notebooks.add(self.tab_stats, text="Statistiques")

        self.disease_tree = self._build_result_tree(self.tab_diseases)

        self.drug_tree = self._build_result_tree(self.tab_drugs)

        self.treat_text = ScrolledText(self.tab_treatments, wrap="word", font=("Courier", 11))
        self.treat_text.pack(fill="both", expand=True, padx=8, pady=8)

        self.stats_text = ScrolledText(self.tab_stats, wrap="word", font=("Courier", 11))
        self.stats_text.pack(fill="both", expand=True, padx=8, pady=8)

    def _on_clear(self):
        self.query_var.set("")
        self.summary_var.set("Pret")
        self._set_tree(self.disease_tree, [])
        self._set_tree(self.drug_tree, [])
        self._set_text(self.treat_text, "")
        self._set_text(self.stats_text, "")

    def _on_stats(self):
        try:
            stats = self.mediator.get_statistics()
            lines = ["--- Statistiques des sources de données ---", ""]
            for k, v in stats.items():
                if v == "":
                    lines.append(f"\n{k}")
                else:
                    lines.append(f"{k}: {v}")
            self._set_text(self.stats_text, "\n".join(lines))
            self.summary_var.set("Statistiques affichées dans l'onglet Statistiques.")
            self.notebooks.select(self.tab_stats)
        except Exception as exc:
            self.summary_var.set(f"Erreur lors du calcul des statistiques: {exc}")

    @staticmethod
    def _combine_sider_sources(sources):
        sider_sources = [s for s in sources if 'sider' in str(s).lower()]
        if not sider_sources:
            return sources
        
        best_sider = "SIDER"
        best_proba = -1.0
        
        for s in sider_sources:
            m = re.search(r'(\d+(?:\.\d+)?)%', str(s))
            if m:
                val = float(m.group(1))
                if val > best_proba:
                    best_proba = val
                    best_sider = str(s)
                    
        if best_proba == -1.0:
            for s in sider_sources:
                if "(" in str(s):
                    best_sider = str(s)
                    break
        
        # Filtre les autres sources non-sider
        combined = [str(s) for s in sources if 'sider' not in str(s).lower()]
        combined.append(best_sider)
        return combined

    def _get_sort_key_fn(self):
        sort_method = self.sort_var.get()
        def get_max_proba(sources):
            mm = 0.0
            for s in sources:
                m = re.search(r'(\d+(?:\.\d+)?)%', str(s))
                if m: mm = max(mm, float(m.group(1)))
            return mm
            
        def sort_item(x):
            nb_symptoms = x.get('score', 0)
            proba = get_max_proba(x.get('sources', []))
            
            if "Proba SIDER totale" in sort_method:
                return (-proba, -nb_symptoms)
            else: # Default
                return (-nb_symptoms, -proba)
        return sort_item

    def _on_visualize(self):
        query = self.query_var.get().strip()
        if not query:
            self.summary_var.set("Veuillez chercher une requête d'abord pour la visualisation.")
            return
        
        try:
            result = self.mediator.query_symptoms(query, verbose=False)
            diseases = result.get("diseases", [])
            drugs = result.get("drugs_causing", [])
            
            sort_fn = self._get_sort_key_fn()
            diseases = sorted(diseases, key=sort_fn)[:10]
            drugs = sorted(drugs, key=sort_fn)[:10]
            
            if not diseases and not drugs:
                self.summary_var.set("Aucun résultat à visualiser pour cette requête.")
                return
                
            fig, axes = plt.subplots(1, 2, figsize=(14, 6))
            fig.suptitle(f"Analyse des classements pour : {query}", fontsize=14, fontweight='bold')
            
            if diseases:
                df_d = pd.DataFrame(diseases)
                # Ajout des sources directement dans le label Y pour plus d'ergonomie
                df_d['name_short'] = df_d.apply(
                    lambda row: format_disease_name(row['name'])[:45] + ("..." if len(format_disease_name(row['name'])) > 45 else "") + f"\n[{', '.join(sorted(self._combine_sider_sources(row['sources'])))}]", 
                    axis=1
                )
                sns.barplot(data=df_d, y='name_short', x='score', hue='name_short', dodge=False, legend=False, ax=axes[0], palette='crest')
                axes[0].xaxis.set_major_locator(plt.MaxNLocator(integer=True))
                axes[0].set_title('Top Maladies (Scores & Sources)')
                axes[0].set_xlabel('Score Fédéré')
                axes[0].set_ylabel('')
                
            if drugs:
                df_dr = pd.DataFrame(drugs)
                # Pareil pour les médicaments avec ajout des pourcentages s'ils existent
                df_dr['label_full'] = df_dr.apply(
                    lambda row: row['name'][:45] + ("..." if len(row['name']) > 45 else "") + f"\n[{', '.join(sorted(self._combine_sider_sources(row['sources'])))}]", 
                    axis=1
                )
                sns.barplot(data=df_dr, y='label_full', x='score', hue='label_full', dodge=False, legend=False, ax=axes[1], palette='flare')
                axes[1].xaxis.set_major_locator(plt.MaxNLocator(integer=True))
                axes[1].set_title('Top Médicaments (Toxicité & Sources)')
                axes[1].set_xlabel('Score Fédéré')
                axes[1].set_ylabel('')
                
            plt.tight_layout()
            plt.show()
            self.summary_var.set("Visualisation générée avec succès.")
        except Exception as exc:
            self.summary_var.set(f"Erreur UI Visualisation: {exc}")

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

        sort_fn = self._get_sort_key_fn()
        diseases = sorted(diseases, key=sort_fn)
        drugs = sorted(drugs, key=sort_fn)

        self.summary_var.set(
            f"Resultats: {len(diseases)} maladie(s), {len(drugs)} medicament(s) causant ces symptomes"
        )

        self._set_tree(self.disease_tree, [(format_disease_name(disease["name"]), disease["score"], ", ".join(sorted(self._combine_sider_sources(disease.get("sources", []))))) for disease in diseases[:200]])
        if not diseases:
            self._set_tree(self.disease_tree, [])

        self._set_tree(self.drug_tree, [(drug["name"], drug["score"], ", ".join(sorted(self._combine_sider_sources(drug.get("sources", []))))) for drug in drugs[:200]])
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
