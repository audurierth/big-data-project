from src.main import consts
from src.wrappers.hpo import HPO_Wrapper
from src.wrappers.drugbank import DrugBank_Wrapper
from src.wrappers.omim import OMIM_Wrapper

class Mediator:
    def __init__(self):
        consts()
        self.hpo = HPO_Wrapper()
        self.drugbank = DrugBank_Wrapper()
        self.omim = OMIM_Wrapper()

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
            print(f"\nMédicaments causant {query} comme effet secondaire (DrugBank):")
            for drug in sorted_drugs[:10]:
                sources = ", ".join(sorted(drug["sources"]))
                symptoms = ", ".join(sorted(drug["matched_symptoms"]))
                print(f" - {drug['name']} [score={drug['score']} | sources={sources} | symptômes={symptoms}]")

        treatment_candidates = {}
        for disease in sorted_diseases[:5]:
            disease_name = disease["name"]
            disease_keyword = disease_name.split()[0].replace(",", "")
            if len(disease_keyword) > 3:
                treatments = self.drugbank.retrieve_drugs_by_indication(disease_keyword)
                if treatments:
                    treatment_candidates[disease_name] = [
                        {
                            "name": treatment_name,
                            "score": 1,
                            "sources": ["DrugBank"],
                        }
                        for _, treatment_name in treatments[:3]
                    ]
                    if verbose:
                        print(f" [Traitement potentiel pour: {disease_name}]")
                        for _, treatment_name in treatments[:3]:
                            print(f"  -> {treatment_name} [source=DrugBank]")
        direct_symptom_treatments = {}
        for symptom in sorted(all_symptoms):
            symptom_treatments = self.drugbank.retrieve_drugs_by_indication(symptom)
            if symptom_treatments:
                direct_symptom_treatments[symptom] = [
                    {
                        "name": treatment_name,
                        "score": 1,
                        "sources": ["DrugBank"],
                    }
                    for _, treatment_name in symptom_treatments[:3]
                ]
                if verbose:
                    print(f" [Traitement direct pour: {symptom}]")
                    for _, treatment_name in symptom_treatments[:3]:
                        print(f"  -> {treatment_name} [source=DrugBank]")

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
