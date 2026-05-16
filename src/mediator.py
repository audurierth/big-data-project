from src.main import consts
from src.wrappers.hpo import HPO_Wrapper

consts()
hpo_wrapper = HPO_Wrapper()
sec_id = hpo_wrapper.retrieve_pathologyEffectId("fever")

diseases = hpo_wrapper.retrieve_diseasesFromSideEffect(sec_id[0])
print("-- Diseases found --")
for i in diseases:
    id = i[0]
    name = i[1]
    print(f"Id: {id} - Name: {name}")