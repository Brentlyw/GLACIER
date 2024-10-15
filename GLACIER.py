import argparse
import os
from concurrent.futures import ThreadPoolExecutor

class RollingHash:
    def __init__(self, window_size=64, prime=3):
        self.window_size = window_size
        self.prime = prime
        self.base = 256
        self.modulus = (1 << 61) - 1  #Mersenne prime
        self.hash = 0
        self.multiplier = pow(self.base, self.window_size - 1, self.modulus)
        self.window = bytearray()

    def update(self, byte):
        if len(self.window) == self.window_size:
            self.hash = (self.hash - self.window.pop(0) * self.multiplier) % self.modulus
        
        self.hash = (self.hash * self.base + byte) % self.modulus
        self.window.append(byte)
        
        return self.hash

class AdaptiveChunker:
    def __init__(self, min_chunk=2048, max_chunk=65536, bits=13):
        self.min_chunk = min_chunk
        self.max_chunk = max_chunk
        self.mask = (1 << bits) - 1
        self.roller = RollingHash()

    def chunk_data(self, data):
        chunks = []
        start = 0
        data_len = len(data)

        for i in range(data_len):
            fingerprint = self.roller.update(data[i])
            
            chunk_size = i - start + 1
            if chunk_size >= self.min_chunk:
                if (fingerprint & self.mask) == 0 or chunk_size >= self.max_chunk:
                    chunks.append((data[start:i+1], start))
                    start = i + 1

        # Add remaining data
        if start < data_len:
            chunks.append((data[start:], start))

        return chunks

class FuzzyHasher:
    def __init__(self, min_chunk=2048, max_chunk=65536, window_size=64, debug=False):
        self.min_chunk = min_chunk
        self.max_chunk = max_chunk
        self.window_size = window_size
        self.debug = debug

    def normalize_data(self, data):
        try:
            text = data.decode('utf-8')
            #Normalize
            normalized = ' '.join(text.replace('\r\n', '\n').split())
            return normalized.encode('utf-8')
        except UnicodeDecodeError:
            #Non-text data
            return data

    def _hash_chunk(self, chunk):
        h = 0
        for byte in chunk:
            h = (h * 31 + byte) & 0xFFFFFFFF
        return h.to_bytes(4, 'big')

    def _parallel_hash_chunks(self, chunks):
        with ThreadPoolExecutor() as executor:
            return list(executor.map(self._hash_chunk, [chunk for chunk, _ in chunks]))

    def _chunk_data(self, data):
        chunker = AdaptiveChunker(self.min_chunk, self.max_chunk, self.window_size)
        return chunker.chunk_data(data)

    def calculate_signature(self, file_path):
        try:
            file_size = os.path.getsize(file_path)
            print(f"Processing: {file_path} ({file_size} bytes)")

            if file_size == 0:
                print("Warning: Empty file. Skipping.")
                return None

            with open(file_path, 'rb') as f:
                data = f.read()

            data = self.normalize_data(data)

            if len(data) < self.min_chunk:
                print(f"File smaller than min chunk size ({self.min_chunk} bytes). Using whole file.")
                h_hex = self._hash_chunk(data).hex()
                if self.debug:
                    print(f"Single chunk hash: {h_hex}")
                return h_hex

            chunks = self._chunk_data(data)
            chunk_hashes = self._parallel_hash_chunks(chunks)
            signature = ''.join(h.hex() for h in chunk_hashes)

            return signature
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            return None

    def compare_signatures(self, sig1, sig2):
        if not sig1 or not sig2:
            return 0.0

        try:
            # Split signatures into 8-char chunks
            set1 = set(sig1[i:i+8] for i in range(0, len(sig1), 8))
            set2 = set(sig2[i:i+8] for i in range(0, len(sig2), 8))

            # Jaccard similarity
            intersection = set1.intersection(set2)
            union = set1.union(set2)

            return len(intersection) / len(union) if union else 0.0
        except Exception as e:
            print(f"Comparison failed: {str(e)}")
            return 0.0

    def show_signature(self, sig, label="Signature"):
        if not sig:
            print("No signature to display.")
            return

        print(f"\n{label}:")
        #4c grid
        for i in range(0, len(sig), 32):
            row = sig[i:i+32]
            print(' '.join(row[j:j+8] for j in range(0, len(row), 8)))

def main():
    parser = argparse.ArgumentParser(description="Fuzzy Hash Tool")
    parser.add_argument('files', nargs='+', help='File(s) to hash/compare')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    args = parser.parse_args()

    hasher = FuzzyHasher(debug=args.debug)

    if len(args.files) == 1:
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
        print("Please provide one or two file paths.")

if __name__ == "__main__":
    main()
