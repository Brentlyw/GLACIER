import argparse
import os
import sqlite3
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
import sys
import mmap
from collections import deque
import multiprocessing
from difflib import SequenceMatcher


def hash_chunk(chunk):
    h = 0
    for byte in chunk:
        h = (h * 31 + byte) & 0xFFFFFFFF
    return h.to_bytes(4, 'big')


class RabinFingerprint:
    def __init__(self, poly=0x3DA3358B4DC173, window_size=64):
        self.poly = poly
        self.window_size = window_size
        self.shift = 47
        self.mask = (1 << 13) - 1
        self.hash = 0
        self.multiplier = 1
        for _ in range(self.window_size - 1):
            self.multiplier = (self.multiplier * 256) % poly
        self.window = deque()

    def update(self, byte):
        if len(self.window) == self.window_size:
            removed_byte = self.window.popleft()
            self.hash = (self.hash - removed_byte * self.multiplier) % self.poly
        self.hash = (self.hash * 256 + byte) % self.poly
        self.window.append(byte)
        return self.hash

    def is_chunk_boundary(self):
        return (self.hash & self.mask) == 0


class ContentDefinedChunker:
    def __init__(self, min_chunk=2048, max_chunk=65536, fingerprint=None):
        self.min_chunk = min_chunk
        self.max_chunk = max_chunk
        self.fingerprint = fingerprint or RabinFingerprint()
        
    def chunk_data(self, data):
        chunks = []
        start = 0
        data_len = len(data)
        for i in range(data_len):
            self.fingerprint.update(data[i])
            chunk_size = i - start + 1

            if chunk_size >= self.min_chunk and (self.fingerprint.is_chunk_boundary() or chunk_size >= self.max_chunk):
                chunk = data[start:i+1]
                chunks.append((chunk, start))
                start = i + 1
        if start < data_len:
            chunks.append((data[start:], start))
        
        return chunks


class FuzzyHasher:
    __slots__ = ['min_chunk', 'max_chunk', 'window_size', 'debug', 'chunker']

    def __init__(self, min_chunk=2048, max_chunk=65536, window_size=64, debug=False):
        self.min_chunk = min_chunk
        self.max_chunk = max_chunk
        self.window_size = window_size
        self.debug = debug
        self.chunker = ContentDefinedChunker(self.min_chunk, self.max_chunk)
    
    def normalize_data(self, data):
        try:
            text = data.decode('utf-8')
            normalized = ' '.join(text.replace('\r\n', '\n').split())
            return normalized.encode('utf-8')
        except UnicodeDecodeError:
            return data
    
    def _chunk_data(self, data):
        return self.chunker.chunk_data(data)
    
    def calculate_signature(self, file_path):
        try:
            file_size = os.path.getsize(file_path)
            if self.debug:
                print(f"Processing: {file_path} ({file_size} bytes)")
            if file_size == 0:
                if self.debug:
                    print("Warning: Empty file. Skipping.")
                return None
            with open(file_path, 'rb') as f:
                with mmap.mmap(f.fileno(), length=0, access=mmap.ACCESS_READ) as mm:
                    data = mm[:]
            data = self.normalize_data(data)
            if len(data) < self.min_chunk:
                if self.debug:
                    print(f"File smaller than min chunk size ({self.min_chunk} bytes). Using whole file.")
                h_bytes = hash_chunk(data)
                h_hex = h_bytes.hex()
                if self.debug:
                    print(f"Single chunk hash: {h_hex}")
                return h_hex
            chunks = self._chunk_data(data)
            chunk_hashes = [hash_chunk(chunk).hex() for chunk, _ in chunks]
            signature = ''.join(chunk_hashes)
            return signature
        except Exception as e:
            if self.debug:
                print(f"Error processing {file_path}: {str(e)}")
            return None
    
    def compare_signatures(self, sig1, sig2):
        if not sig1 or not sig2:
            return 0.0
        try:
            matcher = SequenceMatcher(None, sig1, sig2)
            return matcher.ratio()
        except Exception as e:
            if self.debug:
                print(f"Comparison failed: {str(e)}")
            return 0.0
    
    def show_signature(self, sig, label="Signature"):
        if not sig:
            print("No signature to display.")
            return
        print(f"\n{label}:")
        for i in range(0, len(sig), 32):
            row = sig[i:i+32]
            print(' '.join(row[j:j+8] for j in range(0, len(row), 8)))
    
    def create_database(self, folder_path, db_name='Sigs.db', max_workers=None, batch_size=10000):
        if max_workers is None:
            max_workers = multiprocessing.cpu_count()
        file_paths = [
            os.path.join(root, file)
            for root, _, files in os.walk(folder_path)
            for file in files
        ]
        total_files = len(file_paths)
        print(f"Found {total_files} files. Starting signature computation...")
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS signatures
                          (signature TEXT PRIMARY KEY)''')
        cursor.execute("PRAGMA synchronous = OFF;")
        cursor.execute("PRAGMA journal_mode = MEMORY;")
        cursor.execute("PRAGMA cache_size = 100000;")
        conn.commit()
        hasher = self
        def signature_generator():
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(hasher.calculate_signature, fp): fp for fp in file_paths}
                for future in tqdm(as_completed(futures), total=total_files, desc="Hashing files"):
                    try:
                        result = future.result()
                        if result:
                            yield (result,)
                    except Exception as e:
                        if self.debug:
                            print(f"Error processing a file: {str(e)}")
        batch = []
        inserted_count = 0
        try:
            for record in signature_generator():
                batch.append(record)
                if len(batch) >= batch_size:
                    cursor.executemany(
                        "INSERT OR REPLACE INTO signatures (signature) VALUES (?)",
                        batch
                    )
                    conn.commit()
                    inserted_count += len(batch)
                    if self.debug:
                        print(f"Inserted {inserted_count} / {total_files} signatures...")
                    batch.clear()
            if batch:
                cursor.executemany(
                    "INSERT OR REPLACE INTO signatures (signature) VALUES (?)",
                    batch
                )
                conn.commit()
                inserted_count += len(batch)
                if self.debug:
                    print(f"Inserted {inserted_count} / {total_files} signatures...")
        except Exception as e:
            print(f"Error during database insertion: {e}", file=sys.stderr)
        finally:
            conn.close()
        print(f"Database '{db_name}' created successfully with {inserted_count} signatures.")
    
    def scan_file(self, file_path, db_name='Sigs.db', threshold=0.5):
        try:
            signature = self.calculate_signature(file_path)
            if not signature:
                return False, []
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()
            cursor.execute("SELECT signature FROM signatures")
            results = []
            for (db_signature,) in cursor.fetchall():
                similarity = self.compare_signatures(signature, db_signature)
                if similarity > threshold:
                    results.append((db_signature, similarity))
            conn.close()
            return bool(results), results
        except Exception as e:
            if self.debug:
                print(f"Error scanning {file_path}: {str(e)}")
            return False, []
    
    def scan_folder(self, folder_path, db_name='Sigs.db', threshold=0.5, max_workers=None):
        total_files = 0
        matched_files = 0
        error_files = 0
        if max_workers is None:
            max_workers = multiprocessing.cpu_count()
        file_paths = [
            os.path.join(root, file)
            for root, _, files in os.walk(folder_path)
            for file in files
        ]
        total_files = len(file_paths)
        print(f"Found {total_files} files to scan.")
        def process_file(file_path):
            nonlocal matched_files, error_files
            matched, results = self.scan_file(file_path, db_name, threshold)
            if matched:
                matched_files += 1
                print(f"Match found: {file_path}")
                for match_signature, match_similarity in sorted(results, key=lambda x: x[1], reverse=True):
                    print(f"  Similarity: {match_similarity:.2%}")
            return
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_file, fp): fp for fp in file_paths}
            for future in tqdm(as_completed(futures), total=total_files, desc="Scanning files"):
                try:
                    future.result()
                except Exception as e:
                    error_files += 1
                    if self.debug:
                        print(f"Error processing a file: {str(e)}")
        print("\nScan Summary:")
        print(f"Total files scanned: {total_files}")
        print(f"Files with matches: {matched_files}")
        print(f"Files without matches: {total_files - matched_files - error_files}")
        print(f"Files with errors: {error_files}")
        if total_files > 0:
            print(f"Match rate: {matched_files / total_files:.2%}")
        else:
            print("No files scanned.")


def main():
    parser = argparse.ArgumentParser(description="GLACIER: A new fuzzy hashing algorithm.")
    parser.add_argument('files', nargs='*', help='File(s) to hash/compare')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('-db', metavar='FOLDER', help='Create a new database from the specified folder')
    parser.add_argument('-scan', metavar='PATH', help='Scan a file or folder against the signature database')
    parser.add_argument('--threads', type=int, default=None, help='Number of worker processes to use (default: CPU cores)')
    parser.add_argument('--threshold', type=float, default=0.5, help='Similarity threshold for matching (default: 0.5)')
    args = parser.parse_args()
    hasher = FuzzyHasher(debug=args.debug)
    
    if args.db:
        # **Modification Start**
        # Extract the folder name to create {foldername}.db
        folder_path = args.db
        if not os.path.isdir(folder_path):
            print(f"Error: '{folder_path}' is not a valid directory.")
            sys.exit(1)
        folder_name = os.path.basename(os.path.normpath(folder_path))
        db_name = f"{folder_name}.db"
        # Pass the dynamic db_name to create_database
        hasher.create_database(folder_path, db_name=db_name, max_workers=args.threads)
        # **Modification End**
    elif args.scan:
        # Determine the db_name based on the directory containing the database
        # Assuming the database is in the current directory or specify a way to locate it
        # Alternatively, you can allow specifying the db path via another argument
        # For simplicity, we'll assume 'Sigs.db' unless otherwise specified
        if args.db:
            # This block is redundant now since args.db is handled above
            pass
        else:
            db_name = 'Sigs.db'
        if os.path.isfile(db_name):
            pass
        else:
            print(f"Error: Database '{db_name}' does not exist. Please create it using the -db argument first.")
            sys.exit(1)
        if os.path.isfile(args.scan):
            matched, results = hasher.scan_file(args.scan, db_name=db_name, threshold=args.threshold)
            if matched:
                print(f"Matches found for {args.scan}:")
                for match_signature, match_similarity in sorted(results, key=lambda x: x[1], reverse=True):
                    print(f"  Similarity: {match_similarity:.2%}")
            else:
                print(f"No matches found for {args.scan} above {args.threshold:.2%} similarity threshold.")
        elif os.path.isdir(args.scan):
            hasher.scan_folder(args.scan, db_name=db_name, threshold=args.threshold, max_workers=args.threads)
        else:
            print(f"Error: {args.scan} is not a valid file or directory.")
    elif len(args.files) == 1:
        file_path = args.files[0]
        sig = hasher.calculate_signature(file_path)
        if sig:
            hasher.show_signature(sig, label=f"Signature for {file_path}")
        else:
            print(f"Failed to generate signature for {file_path}")
    elif len(args.files) == 2:
        file1, file2 = args.files
        sig1 = hasher.calculate_signature(file1)
        sig2 = hasher.calculate_signature(file2)
        if sig1 and sig2:
            hasher.show_signature(sig1, label=f"Signature for {file1}")
            hasher.show_signature(sig2, label=f"Signature for {file2}")
            similarity = hasher.compare_signatures(sig1, sig2)
            print(f"\nSimilarity: {similarity:.2%}")
        else:
            print("Failed to generate signatures for both files.")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
