import os
import sqlite3
import csv
from src import main

class OMIM_Wrapper:
    main.consts()
    PROJECT_ROOT = os.path.dirname(main.ROOT_DIR_PATH)
    DB_PATH = os.path.join(PROJECT_ROOT, "db", "medical_data.db")
    OMIM_TXT_PATH = os.path.join(PROJECT_ROOT, "assets", "OMIM", "omim.txt")
    OMIM_ONTO_PATH = os.path.join(PROJECT_ROOT, "assets", "OMIM", "omim_onto.csv")
    
    def __init__(self):
        self.data = sqlite3.connect(self.DB_PATH, check_same_thread=False)
        self.cursor = self.data.cursor()
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS omim_diseases (
                omim_id TEXT PRIMARY KEY,
                title TEXT,
                clinical_synopsis TEXT,
                cui TEXT
            )
        """)
        self.data.commit()
        
        self.cursor.execute("SELECT COUNT(*) FROM omim_diseases")
        if self.cursor.fetchone()[0] == 0:
            print("Populating OMIM database...")
            self._populate_db()

    def _populate_db(self):
        # 1. Parse OMIM to CUI mapping
        cui_mapping = {}
        if os.path.exists(self.OMIM_ONTO_PATH):
            with open(self.OMIM_ONTO_PATH, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
                for row in reader:
                    if len(row) >= 2:
                        omim_id = row[0].replace("OMIM:", "")
                        cui = row[1]
                        cui_mapping[omim_id] = cui

        # 2. Parse omim.txt
        current_id = None
        current_title = ""
        current_cs = ""
        
        in_cs = False
        in_ti = False
        in_no = False
        
        # We need to process huge file carefully
        with open(self.OMIM_TXT_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("*RECORD*"):
                    self._save_record(current_id, current_title, current_cs, cui_mapping)
                    current_id = None
                    current_title = ""
                    current_cs = ""
                    in_cs = False
                    in_ti = False
                    in_no = False
                    continue
                
                if line.startswith("*FIELD* NO"):
                    in_no = True; in_ti = False; in_cs = False
                    continue
                elif line.startswith("*FIELD* TI"):
                    in_no = False; in_ti = True; in_cs = False
                    continue
                elif line.startswith("*FIELD* CS"):
                    in_no = False; in_ti = False; in_cs = True
                    continue
                elif line.startswith("*FIELD*"):
                    in_no = False; in_ti = False; in_cs = False
                    continue
                
                if in_no and not current_id:
                    current_id = line
                elif in_ti:
                    current_title += line + " "
                elif in_cs:
                    current_cs += line + " "
            
            # Save the last one
            self._save_record(current_id, current_title, current_cs, cui_mapping)
        self.data.commit()

    def _save_record(self, omim_id, title, cs, cui_mapping):
        if omim_id:
            cui = cui_mapping.get(omim_id, "")
            self.cursor.execute(
                "INSERT OR IGNORE INTO omim_diseases VALUES (?, ?, ?, ?)",
                (omim_id.strip(), title.strip().lower(), cs.strip().lower(), cui)
            )

    def retrieve_disease_by_symptom(self, symptom: str):
        query = "SELECT omim_id, title FROM omim_diseases WHERE clinical_synopsis LIKE ?"
        return self.data.execute(query, (f"%{symptom.lower()}%",)).fetchall()

    def retrieve_disease_by_name(self, name: str):
        query = "SELECT omim_id, title FROM omim_diseases WHERE title LIKE ?"
        return self.data.execute(query, (f"%{name.lower()}%",)).fetchall()

    def close(self):
        self.cursor.close()
        self.data.close()
