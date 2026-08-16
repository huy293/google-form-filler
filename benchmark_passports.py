import os, sys, time, json, glob
sys.path.insert(0, os.getcwd())
import cv2
import cccd_reader.app as cccd_app

def run_benchmark():
    folder = r"C:\Users\luuhu\Downloads\Passprot"
    files = sorted(glob.glob(os.path.join(folder, "*.jpg")) + glob.glob(os.path.join(folder, "*.png")))
    print(f"Total files found: {len(files)}")
    
    reader = cccd_app.get_easy_ocr()
    engine = cccd_app.IntelligentDocumentEngine(reader)
    
    results = []
    total_t0 = time.time()
    
    for idx, filepath in enumerate(files, 1):
        filename = os.path.basename(filepath)
        img = cv2.imread(filepath)
        if img is None:
            print(f"[{idx}/{len(files)}] {filename}: FAILED TO LOAD IMAGE")
            continue
            
        h, w = img.shape[:2]
        t0 = time.time()
        oriented, angle = cccd_app.smart_orient_document(img, reader)
        t_orient = time.time() - t0
        
        t1 = time.time()
        doc_type, fields, crops, mrz, final_img = engine.process(oriented)
        t_proc = time.time() - t1
        
        total_time = t_orient + t_proc
        
        res_entry = {
            "index": idx,
            "filename": filename,
            "dimensions": f"{w}x{h}",
            "orientation_angle": angle,
            "time_orient_s": round(t_orient, 2),
            "time_proc_s": round(t_proc, 2),
            "total_time_s": round(total_time, 2),
            "fields": fields,
            "mrz": mrz
        }
        results.append(res_entry)
        
        id_val = fields.get('passport_number') or fields.get('cccd_number', 'N/A')
        print(f"[{idx:02d}/{len(files)}] {filename[:22]}... ({angle:3d} deg, {total_time:4.2f}s): "
              f"ID={id_val:<10} | "
              f"Name={fields.get('full_name', 'N/A')[:25]:<25} | "
              f"DOB={fields.get('birth_date', 'N/A'):<10} | "
              f"Sex={fields.get('gender', 'N/A'):<3} | "
              f"Nat={fields.get('nationality', 'N/A')}", flush=True)
              
    out_json = "benchmark_results.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    print(f"\n[COMPLETE] Processed {len(results)}/{len(files)} files in {time.time()-total_t0:.2f}s", flush=True)
    print(f"Results saved to {out_json}", flush=True)

if __name__ == "__main__":
    run_benchmark()
