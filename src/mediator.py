from src.main import consts
from src.wrappers.hpo import HPO_Wrapper
from src.wrappers.drugbank import DrugBank_Wrapper
from src.wrappers.omim import OMIM_Wrapper
from src.wrappers.sider import SIDER_Wrapper

class Mediator:
    def __init__(self):
        consts()
        self.hpo = HPO_Wrapper()
        self.drugbank = DrugBank_Wrapper()
        self.omim = OMIM_Wrapper()
        self.sider = SIDER_Wrapper()

    def get_statistics(self):
        """Retourne les statistiques des données insérées (Bonus)"""
        db = self.drugbank.data
        
        omim_with_cui = db.execute("SELECT COUNT(*) FROM omim_diseases WHERE cui != ''").fetchone()[0]
        sider_se_links = db.execute('SELECT COUNT(*) FROM sider_side_effects').fetchone()[0]
        
        overlap_sider_drugbank = db.execute("SELECT COUNT(DISTINCT s.label) FROM sider_drugs s JOIN drugs d ON s.label = d.name").fetchone()[0]
        
        avg_se_sider = db.execute("SELECT AVG(cnt) FROM (SELECT COUNT(*) as cnt FROM sider_side_effects GROUP BY stitch_id)").fetchone()[0] or 0
        avg_ind_sider = db.execute("SELECT AVG(cnt) FROM (SELECT COUNT(*) as cnt FROM sider_indications GROUP BY stitch_id)").fetchone()[0] or 0
        
        return {
            "--- QUALITÉ DES MAPPINGS (Bonus) ---": "",
            "Maladies OMIM corrélées avec un CUI": f"{omim_with_cui:,}",
            "Médicaments en commun direct (DrugBank <-> SIDER via label)": f"{overlap_sider_drugbank:,}",
            "--- LOIS DE REPARTITION (Bonus) ---": "",
            "Total Liens Effets Secondaires SIDER": f"{sider_se_links:,}",
            "Moyenne d'Effets Secondaires par Médicament SIDER": f"{avg_se_sider:.2f}",
            "Total Liens Indications SIDER": f"{db.execute('SELECT COUNT(*) FROM sider_indications').fetchone()[0]:,}",
            "Moyenne d'Indications par Médicament SIDER": f"{avg_ind_sider:.2f}",
            "--- VOLUMETRIE GLOBALE ---": "",
            "Total HPO (Signes/Symptômes)": f"{db.execute('SELECT COUNT(*) FROM hpo_terms').fetchone()[0]:,}",
            "Total OMIM (Maladies)": f"{db.execute('SELECT COUNT(*) FROM omim_diseases').fetchone()[0]:,}",
            "Total DrugBank (Médicaments)": f"{db.execute('SELECT COUNT(*) FROM drugs').fetchone()[0]:,}",
            "Total SIDER (Médicaments)": f"{db.execute('SELECT COUNT(*) FROM sider_drugs').fetchone()[0]:,}",
        }


    def query_symptoms(self, query: str, verbose: bool = True):
        if verbose:
            print(f"\n--- Requête: {query} ---")

        lower_q = query.lower()
        or_groups = [g.strip() for g in lower_q.split(" or ")]

        all_symptoms = set()
        disease_results = {}
        drug_results = {}

        def register_result(bucket, name, source, symptom):
            entry = bucket.setdefault(
                name,
                {
                    "name": name,
                    "hits": 0,
                    "sources": set(),
                    "matched_symptoms": set(),
                },
            )
            entry["hits"] += 1
            entry["sources"].add(source)
            if symptom:
                entry["matched_symptoms"].add(symptom)
            is_drug = any(s.startswith("DrugBank") or "SIDER" in s for s in entry["sources"]) 
            if is_drug:
                entry["score"] = entry["hits"]
            else:
                entry["score"] = entry["hits"] + len(entry["sources"]) - 1
            return entry

        def merge_result(bucket, entry, symptom):
            merged = bucket.setdefault(
                entry["name"],
                {
                    "name": entry["name"],
                    "hits": 0,
                    "sources": set(),
                    "matched_symptoms": set(),
                },
            )
            merged["hits"] += entry["hits"]
            merged["sources"].update(entry["sources"])
            if symptom:
                merged["matched_symptoms"].add(symptom)
            is_drug = any(s.startswith("DrugBank") or "SIDER" in s for s in merged["sources"]) 
            if is_drug:
                merged["score"] = merged["hits"]
            else:
                merged["score"] = merged["hits"] + len(merged["sources"]) - 1
            return merged

        for group in or_groups:
            symptoms = [s.strip() for s in group.split(" and ")]
            all_symptoms.update(symptoms)

            per_symptom_disease_buckets = []
            per_symptom_drug_buckets = []

            for symptom in symptoms:
                search_term = symptom.replace("*", "%")

                local_disease_results = {}
                local_drug_results = {}

                omim_results = self.omim.retrieve_disease_by_symptom(search_term)
                hpo_id_data = self.hpo.retrieve_pathologyEffectId(search_term)

                for _, disease_name in omim_results:
                    register_result(local_disease_results, disease_name, "OMIM", symptom)

                if hpo_id_data:
                    hpo_id = hpo_id_data[0]
                    hpo_results = self.hpo.retrieve_diseasesFromSideEffect(hpo_id)
                    if hpo_results:
                        for _, disease_name in hpo_results:
                            register_result(local_disease_results, disease_name, "HPO", symptom)

                drug_se_results = self.drugbank.retrieve_drugs_by_side_effect(search_term)
                for _, drug_name in drug_se_results:
                    register_result(local_drug_results, drug_name, "DrugBank", symptom)

                sider_se_results = self.sider.retrieve_drugs_by_side_effect(search_term)
                for _, drug_name, freq in sider_se_results:
                    source_str = f"SIDER ({freq})" if freq else "SIDER"
                    register_result(local_drug_results, drug_name, source_str, symptom)

                per_symptom_disease_buckets.append(local_disease_results)
                per_symptom_drug_buckets.append(local_drug_results)

            if per_symptom_disease_buckets:
                common_diseases = set.intersection(
                    *(set(bucket.keys()) for bucket in per_symptom_disease_buckets)
                )
                for disease_name in common_diseases:
                    for symptom, bucket in zip(symptoms, per_symptom_disease_buckets):
                        merge_result(disease_results, bucket[disease_name], symptom)

            if per_symptom_drug_buckets:
                common_drugs = set.intersection(
                    *(set(bucket.keys()) for bucket in per_symptom_drug_buckets)
                )
                for drug_name in common_drugs:
                    for symptom, bucket in zip(symptoms, per_symptom_drug_buckets):
                        merge_result(drug_results, bucket[drug_name], symptom)

        sorted_diseases = sorted(
            disease_results.values(),
            key=lambda entry: (-entry["score"], entry["name"].lower()),
        )
        sorted_drugs = sorted(
            drug_results.values(),
            key=lambda entry: (-entry["score"], entry["name"].lower()),
        )

        if verbose:
            print(f"\nMaladies causant {query} (OMIM + HPO):")
            for disease in sorted_diseases[:10]:
                sources = ", ".join(sorted(disease["sources"]))
                symptoms = ", ".join(sorted(disease["matched_symptoms"]))
                print(f" - {disease['name']} [score={disease['score']} | sources={sources} | symptômes={symptoms}]")

        if verbose:
            print(f"\nMédicaments causant {query} comme effet secondaire (DrugBank + SIDER):")
            for drug in sorted_drugs[:10]:
                sources = ", ".join(sorted(drug["sources"]))
                symptoms = ", ".join(sorted(drug["matched_symptoms"]))
                print(f" - {drug['name']} [score={drug['score']} | sources={sources} | symptômes={symptoms}]")

        treatment_candidates = {}
        for disease in sorted_diseases[:5]:
            disease_name = disease["name"]
            keywords = [disease_name.lower()]
            for token in disease_name.replace(',', ' ').split():
                t = token.strip().lower()
                if len(t) > 3:
                    keywords.append(t)

            # Collect treatment hits from DrugBank and SIDER for all keywords
            treatments_db = []
            treatments_sider = []
            for kw in keywords:
                try:
                    treatments_db.extend(self.drugbank.retrieve_drugs_by_indication(kw))
                except Exception:
                    pass
                try:
                    treatments_sider.extend(self.sider.retrieve_drugs_by_indication(kw))
                except Exception:
                    pass

            # Deduplicate based on name and aggregate sources
            treatments_combined = {}
            for _, t_name in treatments_db:
                treatments_combined.setdefault(t_name, set()).add("DrugBank")
            for _, t_name in treatments_sider:
                treatments_combined.setdefault(t_name, set()).add("SIDER")

            if treatments_combined:
                # sort by number of distinct sources (desc) then name
                sorted_items = sorted(treatments_combined.items(), key=lambda i: (-len(i[1]), i[0].lower()))
                treatment_candidates[disease_name] = [
                    {
                        "name": t_name,
                        "score": len(srcs),
                        "sources": sorted(list(srcs)),
                    }
                    for t_name, srcs in sorted_items[:5]
                ]
                if verbose:
                    print(f" [Traitement potentiel pour: {disease_name}]")
                    for t_name, srcs in sorted_items[:5]:
                        print(f"  -> {t_name} [sources={', '.join(sorted(srcs))}]")
        direct_symptom_treatments = {}
        for symptom in sorted(all_symptoms):
            symptom_treatments_db = self.drugbank.retrieve_drugs_by_indication(symptom)
            symptom_treatments_sider = self.sider.retrieve_drugs_by_indication(symptom)
            
            # Deduplicate
            treatments_combined = {}
            for _, t_name in symptom_treatments_db:
                treatments_combined[t_name] = {"DrugBank"}
            for _, t_name in symptom_treatments_sider:
                if t_name not in treatments_combined:
                    treatments_combined[t_name] = set()
                treatments_combined[t_name].add("SIDER")
                    
            if treatments_combined:
                direct_symptom_treatments[symptom] = [
                    {
                        "name": t_name,
                        "score": len(srcs),
                        "sources": list(srcs),
                    }
                    for t_name, srcs in sorted(treatments_combined.items(), key=lambda i: len(i[1]), reverse=True)[:5]
                ]
                if verbose:
                    print(f" [Traitement direct pour: {symptom}]")
                    for t_name, srcs in sorted(treatments_combined.items(), key=lambda i: len(i[1]), reverse=True)[:5]:
                        print(f"  -> {t_name} [sources={', '.join(srcs)}]")

        return {
            "query": query,
            "diseases": sorted_diseases,
            "drugs_causing": sorted_drugs,
            "treatments_by_disease": treatment_candidates,
            "direct_treatments_by_symptom": direct_symptom_treatments
        }

if __name__ == "__main__":
    mediator = Mediator()
    mediator.query_symptoms("fever AND Blood in urine")
