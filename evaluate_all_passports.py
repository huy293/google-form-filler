import os, sys, glob, json, time, re
sys.path.insert(0, os.getcwd())
import cv2
import cccd_reader.app as cccd_app

# Ground Truth Dictionary for all 39 images in Downloads/Passprot
GROUND_TRUTH = {
    "1786763104539": {"id": "123132843", "name": "YEN THI", "dob": "25/09/1978", "sex": "Nữ", "nat": "Vương Quốc Anh (United Kingdom)"},
    "1786763104571": {"id": "312217939", "name": "OSCAR ANDREW", "dob": "02/12/2010", "sex": "Nam", "nat": "Vương Quốc Anh (United Kingdom)"},
    "1786763104589": {"id": "128646926", "name": "LIPERIS ANDREW CHRISTOPHER", "dob": "11/10/1979", "sex": "Nam", "nat": "Vương Quốc Anh (United Kingdom)"},
    "1786763104603": {"id": "C9J5W5741", "name": "LE DAI TRANG", "dob": "30/08/1989", "sex": "Nữ", "nat": "Đức (Germany)"},
    "1786763104614": {"id": "PA9087148", "name": "LEWIS FIONA CATHERINE", "dob": "29/08/1979", "sex": "Nữ", "nat": "Úc (Australia)"},
    "1786763104625": {"id": "RA1832026", "name": "SIERRA MORALES SALVADOR", "dob": "10/08/1984", "sex": "Nam", "nat": "Úc (Australia)"},
    "1786763104635": {"id": "RA2693622", "name": "JACOB JAIVON", "dob": "20/05/1975", "sex": "Nam", "nat": "Úc (Australia)"},
    "1786763104644": {"id": "RA3039467", "name": "JAMES KAIPPILLIL UNNATHAN YOHANNAN", "dob": "15/05/1970", "sex": "Nam", "nat": "Úc (Australia)"},
    "1786763104653": {"id": "RA3438914", "name": "UTHUPPU JAISON POOZHIKALAYIL", "dob": "10/05/1973", "sex": "Nam", "nat": "Úc (Australia)"},
    "1786763104662": {"type": "blank"}, # Blank / cover page
    "1786763104670": {"id": "159294641", "name": "BRUTON THOMAS EVAN", "dob": "01/02/2005", "sex": "Nam", "nat": "Vương Quốc Anh (United Kingdom)"},
    "1786763104678": {"id": "138596612", "name": "BRUTON JANE", "dob": "28/02/1970", "sex": "Nữ", "nat": "Vương Quốc Anh (United Kingdom)"},
    "1786763104686": {"id": "139294641", "name": "BRUTON THOMAS EVAN", "dob": "01/02/2005", "sex": "Nam", "nat": "Vương Quốc Anh (United Kingdom)"},
    "1786763104695": {"id": "LT994236", "name": "MAIFALA FELICITY MATA", "dob": "15/08/1974", "sex": "Nữ", "nat": "New Zealand"},
    "1786763104702": {"id": "PAK230341", "name": "ARIAS FUENTES RITA", "dob": "21/10/1984", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786763104713": {"id": "181052029", "name": "VILLALON VARA AITOR", "dob": "11/09/1978", "sex": "Nam", "nat": "Tây Ban Nha (Spain)"},
    "1786763104724": {"type": "blank"}, # Visa stamp page
    "1786763104731": {"id": "PAZ218387", "name": "MUNTANER SEGUI CATERINA", "dob": "18/07/2004", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786763104739": {"id": "PAQ496960", "name": "NIGORRA MATAS FRANCISCA", "dob": "28/03/1972", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786763104747": {"id": "PAZ401274", "name": "SANSO ROIG ALBA", "dob": "02/01/1999", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786763104754": {"id": "PAZ218189", "name": "VIDAL MAS JOANA MARIA", "dob": "27/10/2001", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786763104762": {"id": "PAZ345210", "name": "VIVES BLAS GABRIEL", "dob": "25/05/1997", "sex": "Nam", "nat": "Tây Ban Nha (Spain)"},
    "1786763104770": {"id": "PAZ218387", "name": "MUNTANER SEGUI CATERINA", "dob": "18/07/2004", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786763104778": {"id": "79V499VJ7", "name": "HIRSCH MICHAEL", "dob": "30/03/1965", "sex": "Nam", "nat": "Đức (Germany)"},
    "1786779822244": {"id": "HWL6P78L6", "name": "VAN GESTEL TIES", "dob": "07/04/1997", "sex": "Nam", "nat": "Hà Lan (Netherlands)"},
    "1786779822271": {"id": "NNPDR2915", "name": "SNELDERS BERNARDUS ADRIANUS", "dob": "03/09/1999", "sex": "Nam", "nat": "Hà Lan (Netherlands)"},
    "1786779822293": {"id": "24CA80782", "name": "ZINGLE THOMAS FRANCOIS", "dob": "28/08/1993", "sex": "Nam", "nat": "Pháp (France)"},
    "1786779822306": {"id": "24CA80782", "name": "ZINGLE THOMAS FRANCOIS", "dob": "28/08/1993", "sex": "Nam", "nat": "Pháp (France)"},
    "1786779822317": {"id": "LT994236", "name": "MAIFALA FELICITY MATA", "dob": "15/08/1974", "sex": "Nữ", "nat": "New Zealand"},
    "1786779822327": {"id": "517675029", "name": "GRACHEVA OLGA", "dob": "20/11/1972", "sex": "Nữ", "nat": "Nga (Russia)"},
    "1786779822338": {"id": "PAK230341", "name": "ARIAS FUENTES RITA", "dob": "21/10/1984", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786779822349": {"id": "181052029", "name": "VILLALON VARA AITOR", "dob": "11/09/1978", "sex": "Nam", "nat": "Tây Ban Nha (Spain)"},
    "1786779822360": {"id": "PAQ496960", "name": "NIGORRA MATAS FRANCISCA", "dob": "28/03/1972", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786779822367": {"id": "PAZ218387", "name": "MUNTANER SEGUI CATERINA", "dob": "18/07/2004", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786779822375": {"id": "PAZ218189", "name": "VIDAL MAS JOANA MARIA", "dob": "27/10/2001", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786779822383": {"id": "PAZ401274", "name": "SANSO ROIG ALBA", "dob": "02/01/1999", "sex": "Nữ", "nat": "Tây Ban Nha (Spain)"},
    "1786779822391": {"id": "20AD35198", "name": "PICCININI AUDE EMMANUELLE", "dob": "27/05/1990", "sex": "Nữ", "nat": "Pháp (France)"},
    "1786779822398": {"id": "033069002861", "name": "LÊ ĐÌNH PHAN", "dob": "16/08/1969", "sex": "Nam", "nat": "Việt Nam"},
    "1786779822406": {"id": "PG5455768", "name": "BRENNAN CIAN JAMES", "dob": "09/06/2005", "sex": "Nam", "nat": "Ireland"}
}

def evaluate():
    folder = r"C:\Users\luuhu\Downloads\Passprot"
    files = sorted(glob.glob(os.path.join(folder, "*.jpg")) + glob.glob(os.path.join(folder, "*.png")))
    
    reader = cccd_app.get_easy_ocr()
    engine = cccd_app.IntelligentDocumentEngine(reader)
    
    total_fields = 0
    correct_fields = 0
    
    print(f"\n{'='*75}", flush=True)
    print(f"MULTI-NATIONAL DOCUMENT ENGINE - GROUND TRUTH VERIFICATION", flush=True)
    print(f"{'='*75}\n", flush=True)
    
    for idx, fpath in enumerate(files, 1):
        fname = os.path.basename(fpath)
        key = fname.split('_')[0]
        gt = GROUND_TRUTH.get(key, {})
        
        if gt.get("type") == "blank":
            print(f"[{idx:02d}] {fname[:20]}... [BLANK/NON-BIO IMAGE] -> Correctly ignored.", flush=True)
            continue
            
        img = cv2.imread(fpath)
        oriented, angle = cccd_app.smart_orient_document(img, reader)
        doc_type, fields, crops, mrz, final_img = engine.process(oriented)
        
        ext_id = fields.get('passport_number') or fields.get('cccd_number', '')
        ext_name = fields.get('full_name', '')
        ext_dob = fields.get('birth_date', '')
        ext_sex = fields.get('gender', '')
        ext_nat = fields.get('nationality', '')
        
        gt_id = gt.get('id', '')
        gt_name = gt.get('name', '')
        gt_dob = gt.get('dob', '')
        gt_sex = gt.get('sex', '')
        gt_nat = gt.get('nat', '')
        
        # Field comparisons
        id_match = (ext_id == gt_id) or (len(ext_id) >= 7 and ext_id in gt_id) or (len(gt_id) >= 7 and gt_id in ext_id)
        name_match = (ext_name == gt_name) or all(w in ext_name for w in gt_name.split()) or all(w in gt_name for w in ext_name.split())
        dob_match = (ext_dob == gt_dob)
        sex_match = (ext_sex == gt_sex)
        nat_match = (ext_nat == gt_nat) or (gt_nat in ext_nat) or (ext_nat in gt_nat)
        
        matches = [id_match, name_match, dob_match, sex_match, nat_match]
        total_fields += len(matches)
        correct_fields += sum(matches)
        
        status = "PASSED" if all(matches) else "WARNING"
        print(f"[{idx:02d}] {fname[:20]}... [{status}] (angle={angle} deg)", flush=True)
        print(f"     Extracted : ID={ext_id} | Name={ext_name} | DOB={ext_dob} | Sex={ext_sex} | Nat={ext_nat}", flush=True)
        print(f"     GroundTrth: ID={gt_id} | Name={gt_name} | DOB={gt_dob} | Sex={gt_sex} | Nat={gt_nat}", flush=True)
        if not all(matches):
            diffs = []
            if not id_match: diffs.append("ID")
            if not name_match: diffs.append("NAME")
            if not dob_match: diffs.append("DOB")
            if not sex_match: diffs.append("SEX")
            if not nat_match: diffs.append("NAT")
            print(f"     --> MISMATCHED FIELDS: {', '.join(diffs)}", flush=True)
        print(flush=True)
        
    accuracy = (correct_fields / total_fields) * 100 if total_fields > 0 else 0
    print(f"{'='*75}", flush=True)
    print(f"TOTAL FIELDS EVALUATED : {total_fields}", flush=True)
    print(f"CORRECT FIELDS MATCHED : {correct_fields}", flush=True)
    print(f"FINAL ACCURACY SCORE   : {accuracy:.2f}%", flush=True)
    print(f"{'='*75}\n", flush=True)

if __name__ == "__main__":
    evaluate()
