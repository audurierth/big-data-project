import os
import re
import sqlite3

from src import main

class HPO_Wrapper:
    # Initialize ROOT_DIR_PATH from main module
    main.consts()
    PROJECT_ROOT = os.path.dirname(main.ROOT_DIR_PATH)
    DB_PATH = os.path.join(PROJECT_ROOT, "db", "medical_data.db")
    HPO_ANNOTATIONS_PATH = os.path.join(PROJECT_ROOT, "assets", "HPO", "hpo_annotations.sqlite")
    HPO_FILE_PATH = os.path.join(PROJECT_ROOT, "assets", "HPO", "hpo.obo")

    data = sqlite3.connect(DB_PATH)
    cursor = data.cursor()
    hpo_annotations_data = sqlite3.connect(HPO_ANNOTATIONS_PATH)
    hpo_annotations_cursor = hpo_annotations_data.cursor()
    def __init__(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS hpo_terms (
                hpo_id TEXT PRIMARY KEY,
                name TEXT,
                synonyms TEXT
            )
        """)

        with open(self.HPO_FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read().split("[Term]")
            for term in content[1:]:
                hpo_id_match = re.search(r"^id: (HP:\d+)", term, re.M)
                name_match = re.search(r"^name: (.*)", term, re.M)

                if hpo_id_match and name_match:
                    hpo_id = hpo_id_match.group(1)
                    name = name_match.group(1).lower()
                    synonyms = "|".join(re.findall(r'synonym: "(.*)"', term)).lower()
                    self.cursor.execute(
                        "INSERT OR REPLACE INTO hpo_terms VALUES (?, ?, ?)",
                        (hpo_id, name, synonyms),
                    )

        self.data.commit()

    def retrieve_pathologyEffectId(self, secondaryEffect: str):
        details = self.data.execute(f"SELECT hpo_id,name,synonyms FROM hpo_terms WHERE name='{secondaryEffect}'").fetchone()
        if details is None:
            print("Retrieved no data from HPO secondary effect term.")
            return None
        else:
            print(f"Retrieved {details[0]} id, {details[1]} name, {details[2]} synonyms.")
            return details[0], details[1], details[2]

    def retrieve_diseasesFromSideEffect(self, secondaryEffectId: str):
        details = self.hpo_annotations_data.execute(f"SELECT disease_db_and_id, disease_label FROM phenotype_annotation WHERE sign_id = '{secondaryEffectId}'").fetchall()
        if details is None:
            print("Retrieved no data from HPO secondary effect term.")
            return None
        else:
            print(f"Retrieved {len(details)} medicaments for {secondaryEffectId} id.")
            return details



    def close(self):
        self.cursor.close()
        self.data.close()
        self.hpo_annotations_cursor.close()
        self.hpo_annotations_data.close()
