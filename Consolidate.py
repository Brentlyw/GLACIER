import sqlite3
import argparse
import os
from collections import Counter
import random
import string
from difflib import SequenceMatcher
def compare_signatures(sig1, sig2):
    if not sig1 or not sig2:
        return 0.0
    try:
        matcher = SequenceMatcher(None, sig1, sig2)
        return matcher.ratio()
    except Exception as e:
        print(f"Comparison failed: {str(e)}")
        return 0.0

def auto_name(filepaths):
    def process_name(name):
        name_parts = name.split('.')
        return '.'.join(name_parts[:4]) if len(name_parts) > 4 else os.path.splitext(name)[0]

    processed_names = [process_name(os.path.basename(filepath)) for filepath in filepaths]
    name_counts = Counter(processed_names)
    base_name = name_counts.most_common(1)[0][0] if name_counts else "Consolidated.Signature"
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return f"{base_name}.{random_chars}"

def check_against_master(signature, master_signatures, threshold=0.8):
    return any(compare_signatures(signature, master_sig) > threshold for master_sig in master_signatures)

def consolidate_signatures(db_path, master_db_path, existing_master_db=None, similarity_threshold=0.8, auto_mode=False):
    conn = sqlite3.connect(db_path)
    master_conn = sqlite3.connect(master_db_path)
    
    with conn, master_conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("PRAGMA journal_mode = OFF")
        conn.execute("PRAGMA synchronous = OFF")
        master_conn.execute("PRAGMA journal_mode = OFF")
        master_conn.execute("PRAGMA synchronous = OFF")
        
        master_conn.execute('''CREATE TABLE IF NOT EXISTS master_signatures
                               (name TEXT PRIMARY KEY, signature TEXT)''')

        existing_master_signatures = set()
        if existing_master_db:
            with sqlite3.connect(existing_master_db) as existing_master_conn:
                existing_master_signatures = set(row[0] for row in existing_master_conn.execute("SELECT signature FROM master_signatures"))

        all_signatures = conn.execute("SELECT filepath, signature FROM signatures").fetchall()

        consolidated_count = 0
        total_consolidated = 0
        ignored_count = 0
        processed = set()

        for i, (filepath1, sig1) in enumerate(all_signatures):
            if filepath1 in processed:
                continue

            if check_against_master(sig1, existing_master_signatures, similarity_threshold):
                ignored_count += 1
                processed.add(filepath1)
                continue

            group = [(filepath1, sig1)]
            for filepath2, sig2 in all_signatures[i+1:]:
                if filepath2 not in processed and compare_signatures(sig1, sig2) > similarity_threshold:
                    group.append((filepath2, sig2))

            if len(group) > 1:
                master_name = auto_name([filepath for filepath, _ in group])
                master_conn.execute("INSERT OR REPLACE INTO master_signatures (name, signature) VALUES (?, ?)", 
                                    (master_name, group[0][1]))

                filepaths_to_delete = [filepath for filepath, _ in group[1:]]
                conn.executemany("DELETE FROM signatures WHERE filepath = ?", 
                                 [(filepath,) for filepath in filepaths_to_delete])

                consolidated_count += 1
                total_consolidated += len(group) - 1

                if auto_mode:
                    print(f"Consolidated {master_name} from {len(group)} signatures, keeping one.")
                else:
                    print(f"Group consolidated as: {master_name}")

                processed.update(filepath for filepath, _ in group)
            else:
                processed.add(filepath1)

        conn.execute("VACUUM")

    print(f"\nConsolidation complete.")
    print(f"Consolidated groups: {consolidated_count}")
    print(f"Total signatures consolidated: {total_consolidated}")
    print(f"Signatures ignored (matched existing master): {ignored_count}")
    print(f"Original database cleaned and vacuumed.")

def main():
    parser = argparse.ArgumentParser(description="Consolidator for GLACIER generated databases.")
    parser.add_argument('db_path', help='Path to the input SQLite database file')
    parser.add_argument('master_db_path', help='Path to the output master database file')
    parser.add_argument('--threshold', type=float, default=0.8, help='Similarity threshold for consolidation (default: 0.8)')
    parser.add_argument('-auto', action='store_true', help='Enable automatic consolidation without user confirmation')
    parser.add_argument('-exist', metavar='EXISTING_MASTER_DB', help='Path to an existing master database to check against')
    args = parser.parse_args()

    consolidate_signatures(args.db_path, args.master_db_path, args.exist, args.threshold, args.auto)

if __name__ == "__main__":
    main()
