import os
import sqlite3
from lxml import etree as ET

from src import main

class DrugBank_Wrapper:
    main.consts()
    PROJECT_ROOT = os.path.dirname(main.ROOT_DIR_PATH)
    DB_PATH = os.path.join(PROJECT_ROOT, "db", "medical_data.db")
    DRUGBANK_FILE_PATH = os.path.join(PROJECT_ROOT, "assets", "DRUGBANK", "drugbank.xml")
    
    def __init__(self):
        self.data = sqlite3.connect(self.DB_PATH, check_same_thread=False)
        self.cursor = self.data.cursor()
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS drugs (
                drugbank_id TEXT PRIMARY KEY,
                name TEXT,
                indication TEXT,
                toxicity TEXT
            )
        """)
        self.data.commit()
        
        self.cursor.execute("SELECT COUNT(*) FROM drugs")
        if self.cursor.fetchone()[0] == 0:
            print("Populating DrugBank database... This may take a moment.")
            self._populate_db()

    def _populate_db(self):
        ns = {"db": "http://www.drugbank.ca"}
        context = ET.iterparse(self.DRUGBANK_FILE_PATH, events=("end",), tag="{http://www.drugbank.ca}drug")
        
        for event, elem in context:
            if elem.getparent().tag == "{http://www.drugbank.ca}drugbank":
                drugbank_id_elem = elem.find("./db:drugbank-id[@primary='true']", namespaces=ns)
                name_elem = elem.find("./db:name", namespaces=ns)
                indication_elem = elem.find("./db:indication", namespaces=ns)
                toxicity_elem = elem.find("./db:toxicity", namespaces=ns)
                
                drugbank_id = drugbank_id_elem.text if drugbank_id_elem is not None else None
                name = name_elem.text.lower() if name_elem is not None and name_elem.text else ""
                indication = indication_elem.text.lower() if indication_elem is not None and indication_elem.text else ""
                toxicity = toxicity_elem.text.lower() if toxicity_elem is not None and toxicity_elem.text else ""
                
                if drugbank_id:
                    self.cursor.execute(
                        "INSERT OR IGNORE INTO drugs VALUES (?, ?, ?, ?)",
                        (drugbank_id, name, indication, toxicity)
                    )
            # Free memory
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
        
        self.data.commit()

    def retrieve_drugs_by_indication(self, indication: str):
        query = "SELECT drugbank_id, name FROM drugs WHERE indication LIKE ?"
        return self.data.execute(query, (f"%{indication.lower()}%",)).fetchall()

    def retrieve_drugs_by_side_effect(self, side_effect: str):
        query = "SELECT drugbank_id, name FROM drugs WHERE toxicity LIKE ?"
        return self.data.execute(query, (f"%{side_effect.lower()}%",)).fetchall()

    def retrieve_drug_by_name(self, name: str):
        query = "SELECT drugbank_id, name FROM drugs WHERE name LIKE ?"
        return self.data.execute(query, (f"%{name.lower()}%",)).fetchall()

    def close(self):
        self.cursor.close()
        self.data.close()
