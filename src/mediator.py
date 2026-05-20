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
        final_diseases = set()
        final_drugs_se = set()

        for group in or_groups:
            symptoms = [s.strip() for s in group.split(" and ")]
            all_symptoms.update(symptoms)

            per_symptom_disease_sets = []
            per_symptom_drug_sets = []

            for symptom in symptoms:
                current_symptom_diseases = set()
                search_term = symptom.replace("*", "%")

                omim_results = self.omim.retrieve_disease_by_symptom(search_term)
                for d in omim_results:
                    current_symptom_diseases.add(d[1])
                hpo_id_data = self.hpo.retrieve_pathologyEffectId(search_term.replace("%", ""))
                hpo_id_data = self.hpo.retrieve_pathologyEffectId(search_term.replace("%", ""))
                if hpo_id_data:
                    hpo_id = hpo_id_data[0]
                    hpo_results = self.hpo.retrieve_diseasesFromSideEffect(hpo_id)
                    if hpo_results:
                        for d in hpo_results:
                            current_symptom_diseases.add(d[1])

                per_symptom_disease_sets.append(current_symptom_diseases)
                
                drug_se_results = self.drugbank.retrieve_drugs_by_side_effect(search_term)
                per_symptom_drug_sets.append(set([d[1] for d in drug_se_results]))

            group_diseases = set.intersection(*per_symptom_disease_sets) if per_symptom_disease_sets else set()
            group_drugs = set.intersection(*per_symptom_drug_sets) if per_symptom_drug_sets else set()

            
            final_diseases |= group_diseases
            final_drugs_se |= group_drugs

        if verbose:
            print(f"\nMaladies causant {query} (OMIM + HPO):")
            for d in list(final_diseases)[:10]:
                print(f" - {d}")

        if verbose:
            print(f"\nMédicaments causant {query} comme effet secondaire (DrugBank):")
            for d in list(final_drugs_se)[:10]:
                print(f" - {d}")

        treatment_candidates = {}
        for disease in list(final_diseases)[:5]:
            disease_keyword = disease.split()[0].replace(",", "")
            if len(disease_keyword) > 3:
                treatments = self.drugbank.retrieve_drugs_by_indication(disease_keyword)
                if treatments:
                    treatment_candidates[disease] = [t[1] for t in treatments[:3]]
                    if verbose:
                        print(f" [Traitement potentiel pour: {disease}]")
                        for t in treatments[:3]:
                            print(f"  -> {t[1]}")
        direct_symptom_treatments = {}
        for symptom in sorted(all_symptoms):
            symptom_treatments = self.drugbank.retrieve_drugs_by_indication(symptom)
            if symptom_treatments:
                direct_symptom_treatments[symptom] = [t[1] for t in symptom_treatments[:3]]
                if verbose:
                    print(f" [Traitement direct pour: {symptom}]")
                    for t in symptom_treatments[:3]:
                        print(f"  -> {t[1]}")

        return {
            "query": query,
            "diseases": list(final_diseases),
            "drugs_causing": list(final_drugs_se),
            "treatments_by_disease": treatment_candidates,
            "direct_treatments_by_symptom": direct_symptom_treatments
        }

if __name__ == "__main__":
    mediator = Mediator()
    mediator.query_symptoms("fever AND Blood in urine")
