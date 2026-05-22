import os
import sqlite3
import gzip
import csv

from src import main

class SIDER_Wrapper:
    main.consts()
    PROJECT_ROOT = os.path.dirname(main.ROOT_DIR_PATH)
    DB_PATH = os.path.join(PROJECT_ROOT, "db", "medical_data.db")
    ATC_PATH = os.path.join(PROJECT_ROOT, "assets", "STITCH - ATC", "br08303.keg")
    STITCH_PATH = os.path.join(PROJECT_ROOT, "assets", "STITCH - ATC", "chemical.sources.v5.0.tsv.gz")
    SIDER_SE_PATH = os.path.join(PROJECT_ROOT, "assets", "SIDER", "meddra_all_se.tsv")
    SIDER_IND_PATH = os.path.join(PROJECT_ROOT, "assets", "SIDER", "meddra_all_indications.tsv")
    
    def __init__(self):
        self.data = sqlite3.connect(self.DB_PATH, check_same_thread=False)
        self.cursor = self.data.cursor()
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sider_drugs (
                stitch_id INTEGER PRIMARY KEY,
                atc_code TEXT,
                label TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sider_side_effects (
                stitch_id INTEGER,
                side_effect TEXT,
                FOREIGN KEY(stitch_id) REFERENCES sider_drugs(stitch_id)
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS sider_indications (
                stitch_id INTEGER,
                indication TEXT,
                FOREIGN KEY(stitch_id) REFERENCES sider_drugs(stitch_id)
            )
        """)
        self.data.commit()
        
        self.cursor.execute("SELECT COUNT(*) FROM sider_drugs")
        if self.cursor.fetchone()[0] == 0:
            print("Populating SIDER database... This may take a few minutes (huge files parsing)....")
            self._populate_db()

    def _populate_db(self):
        # 1. Parsing ATC -> Label
        atc_to_label = {}
        with open(self.ATC_PATH, 'r') as f:
            for line in f:
                if line.startswith('E'):
                    parts = line.strip().split(maxsplit=2)
                    if len(parts) >= 3:
                        atc_code = parts[1]
                        label = parts[2].split('[')[0].strip().lower()
                        atc_to_label[atc_code] = label

        # 2. Parsing STITCH -> ATC
        cid_to_atc = {}
        if os.path.exists(self.STITCH_PATH):
            with gzip.open(self.STITCH_PATH, 'rt') as f:
                for line in f:
                    if "\tATC\t" in line:
                        parts = line.strip().split('\t')
                        if len(parts) == 4 and parts[2] == 'ATC':
                            try:
                                cid_int = int(parts[0][4:]) # CIDmXXXX
                                cid_to_atc[cid_int] = parts[3]
                            except Exception:
                                pass
        
        # 3. Process Side Effects
        se_records = set()
        drug_records = {} # stitch_id -> (atc, label)
        
        with open(self.SIDER_SE_PATH, 'r') as f:
            for line in f:
                parts = line.strip().split('\t')
                # CID1 CID2 UMLS_ID TYPE UMLS_MEDDRA SE_NAME
                if len(parts) >= 6 and parts[3] == 'PT':
                    try:
                        cid1 = int(parts[0][4:]) # Remove CID1 and grab 00000085 (starts at 4 instead of 3, watch out "CID1")
                        cid2 = int(parts[1][4:]) # CID0
                    except ValueError:
                        try:
                            # Actually format is "CID100000085". So remove first 4 chars.
                            cid1 = int(parts[0][4:])
                            cid2 = int(parts[1][4:])
                        except:
                            continue
                        
                    stitch_id = None
                    if cid1 in cid_to_atc: stitch_id = cid1
                    elif cid2 in cid_to_atc: stitch_id = cid2
                    elif int(parts[0][3:]) in cid_to_atc: stitch_id = int(parts[0][3:]) # sometimes CID starts with 0
                    
                    if stitch_id:
                        atc = cid_to_atc[stitch_id]
                        label = atc_to_label.get(atc, "unknown")
                        drug_records[stitch_id] = (atc, label)
                        se_records.add((stitch_id, parts[5].strip().lower()))
                        
        # 4. Process Indications
        ind_records = set()
        with open(self.SIDER_IND_PATH, 'r') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 7 and parts[4] == 'PT':
                    try:
                        cid = int(parts[0][3:]) # Here it's CID100000085 without '1/0' ? Wait, the file states CID100000085. Let's strip 4 chars 
                        cid = int(parts[0][4:])
                    except ValueError:
                        continue
                        
                    if cid in cid_to_atc:
                        atc = cid_to_atc[cid]
                        label = atc_to_label.get(atc, "unknown")
                        drug_records[cid] = (atc, label)
                        ind_records.add((cid, parts[6].strip().lower()))
                    # Also try length 3
                    elif int(parts[0][3:]) in cid_to_atc:
                        cid = int(parts[0][3:])
                        atc = cid_to_atc[cid]
                        label = atc_to_label.get(atc, "unknown")
                        drug_records[cid] = (atc, label)
                        ind_records.add((cid, parts[6].strip().lower()))

        # Save to DB
        self.cursor.executemany("INSERT OR IGNORE INTO sider_drugs VALUES (?, ?, ?)",
                                [(k, v[0], v[1]) for k, v in drug_records.items()])
        self.cursor.executemany("INSERT INTO sider_side_effects VALUES (?, ?)", list(se_records))
        self.cursor.executemany("INSERT INTO sider_indications VALUES (?, ?)", list(ind_records))
        
        self.data.commit()

    def retrieve_drugs_by_indication(self, indication: str):
        query = """
            SELECT d.stitch_id, d.label 
            FROM sider_drugs d 
            JOIN sider_indications i ON d.stitch_id = i.stitch_id 
            WHERE i.indication LIKE ? AND d.label != 'unknown'
        """
        return self.data.execute(query, (f"%{indication.lower()}%",)).fetchall()

    def retrieve_drugs_by_side_effect(self, side_effect: str):
        query = """
            SELECT d.stitch_id, d.label 
            FROM sider_drugs d 
            JOIN sider_side_effects s ON d.stitch_id = s.stitch_id 
            WHERE s.side_effect LIKE ? AND d.label != 'unknown'
        """
        return self.data.execute(query, (f"%{side_effect.lower()}%",)).fetchall()

    def close(self):
        self.cursor.close()
        self.data.close()

if __name__ == '__main__':
    wrapper = SIDER_Wrapper()
    print("SIDER DB populated and initialized.")
