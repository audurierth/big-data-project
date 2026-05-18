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

    def query_symptoms(self, query: str):
        # Format query: "fever AND pain" -> ["fever", "pain"]
        symptoms = [s.strip().lower() for s in query.split(" AND ")]
        print(f"\n--- Requête pour les symptômes: {symptoms} ---")
        
        disease_sets = []
        drug_side_effect_sets = []
        
        for symptom in symptoms:
            current_symptom_diseases = set()
            
            # Gestion des jokers: remplacer * par % pour la requête SQL
            search_term = symptom.replace("*", "%")
            
            # 1a. Maladies causant le symptôme (via OMIM)
            omim_results = self.omim.retrieve_disease_by_symptom(search_term)
            for d in omim_results:
                current_symptom_diseases.add(d[1]) # title
                
            # 1b. Maladies causant le symptôme (via HPO)
            hpo_id_data = self.hpo.retrieve_pathologyEffectId(search_term.replace("%", ""))
            if hpo_id_data:
                hpo_id = hpo_id_data[0]
                hpo_results = self.hpo.retrieve_diseasesFromSideEffect(hpo_id)
                if hpo_results:
                    for d in hpo_results:
                        current_symptom_diseases.add(d[1]) # disease label
                        
            disease_sets.append(current_symptom_diseases)
            
            # 2. Médicaments causant le symptôme (via DrugBank Toxicity)
            drug_se_results = self.drugbank.retrieve_drugs_by_side_effect(search_term)
            drug_side_effect_sets.append(set([d[1] for d in drug_se_results]))
            
        # Intersections
        intersect_diseases = set.intersection(*disease_sets) if disease_sets else set()
        intersect_drugs_se = set.intersection(*drug_side_effect_sets) if drug_side_effect_sets else set()
        
        print(f"\nMaladies causant {query} (OMIM + HPO):")
        for d in list(intersect_diseases)[:10]:
            print(f" - {d}")
            
        print(f"\nMédicaments causant {query} comme effet secondaire (DrugBank):")
        for d in list(intersect_drugs_se)[:10]:
            print(f" - {d}")
            
        print(f"\nMédicaments pouvant traiter ces maladies (DrugBank):")
        for disease in list(intersect_diseases)[:5]:
            disease_keyword = disease.split()[0].replace(",", "")
            # Basic matching heuristic
            if len(disease_keyword) > 3:
                treatments = self.drugbank.retrieve_drugs_by_indication(disease_keyword)
                if treatments:
                    print(f" [Traitement potentiel pour: {disease}]")
                    for t in treatments[:3]:
                        print(f"  -> {t[1]}")

        # Pour les médicaments traitant l'effet indésirable lui-même (symptôme)
        print(f"\nMédicaments pouvant traiter directement ces symptômes (DrugBank):")
        for symptom in symptoms:
            symptom_treatments = self.drugbank.retrieve_drugs_by_indication(symptom)
            if symptom_treatments:
                print(f" [Traitement direct pour: {symptom}]")
                for t in symptom_treatments[:3]:
                    print(f"  -> {t[1]}")
                    
        return {
            "query": query,
            "diseases": list(intersect_diseases),
            "drugs_causing": list(intersect_drugs_se)
        }

if __name__ == "__main__":
    mediator = Mediator()
    mediator.query_symptoms("fever AND Blood in urine")
