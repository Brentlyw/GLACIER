# GLACIER: A New Adaptive Fuzzy Hashing Algorithm

GLACIER (Grouped Locality-sensitive Adaptive Chunking with Integrated Efficient Rolling) is an adaptive fuzzy hashing algorithm which provides resilient and efficient similarity detection between samples. It leverages adaptive chunking and parallel processing to improve upon existing fuzzy hashing algorithms like **SSDEEP** and **TLSH**.

## Table of Contents

- [Features](#features)
- [Usage](#usage)
  - [Generating a Signature](#generating-a-signature)
  - [Comparing Two Files](#comparing-two-files)
- [Comparison with SSDEEP and TLSH](#comparison-with-ssdeep-and-tlsh)
  - [Pros of GLACIER](#pros-of-glacier)
  - [Cons of GLACIER](#cons-of-glacier)
- [Code Overview](#code-overview)

## Features

1. **Adaptive Chunking**
   - Dynamic chunk size based on content
   - Resilient to data insertions and deletions
   - Improves hash stability for similar files

2. **Parallel Processing**
   - Scalable performance for large files and datasets

3. **Rolling Hash Computation**
   - Efficient updates for streaming data
   - Allows for real-time processing of large files

4. **Jaccard Similarity Measurement**
   - Accurate file similarity assessment

5. **Flexible Chunk Size Range**
   - Configurable minimum and maximum chunk sizes

6. **Content-Defined Boundaries**
   - Uses rolling hash for intelligent chunk boundaries
   - Improves resilience to file modifications

7. **Compact Signature Generation**
   - Creates fixed-size signatures regardless of file size

8. **Cross-Platform Compatibility**
   - Implemented in pure Python for easy portability
   - No external dependencies required

9. **Normalization**
   - Text normalization for improved matching of text-based files
   - Configurable to handle various file encodings

10. **Configurable Parameters**
    - Adjustable window size, chunk size limits, and other parameters
    - Allows fine-tuning for specific use cases


## Usage

### Generating a Signature

To generate a GLACIER signature for a file:

```bash
python glacier.py {filepath}
```

### Comparing Two Files

To compare two files and compute their similarity:

```bash
python glacier.py {file1} {file2}
```

**Output:**

```
Processing: samples/file1.txt (20480 bytes)
Processing: samples/file2.txt (21504 bytes)

Signature for samples/file1.txt:
e3b0c442 98fc1c14 9afbf4c8 996fb924

Signature for samples/file2.txt:
e3b0c442 98fc1c14 9afbf4c8 7a9cbf11

Similarity: 75.00%
```

## Comparison with SSDEEP and TLSH

### Pros of GLACIER

1. **Parallel Processing**: Potentially faster than both TLSH and SSDEEP on multi-core systems.
2. **Flexible Chunk Size**: Adapts to file content, unlike SSDEEP's fixed 64-byte chunks or TLSH's 256-byte sliding window.
3. **Jaccard Similarity**: Offers a different similarity metric compared to TLSH's Hamming distance or SSDEEP's edit distance.

### Cons of GLACIER

- **Potentially Larger Signatures**: Adaptive chunking might result in more varied signature sizes compared to TLSH's fixed 35-byte hash.


## Code Overview

The main components of the GLACIER algorithm are:

- **RollingHash**: Implements a rolling hash function for efficient recalculations during chunking.
- **AdaptiveChunker**: Divides the data into chunks based on content-defined boundaries.
- **FuzzyHasher**: Orchestrates the hashing process, normalizes data, and computes the final signature.
- **Jaccard Similarity Computation**: Compares two signatures to determine their similarity.

### RollingHash Class

A rolling hash function that updates the hash value when sliding the window over the data.

```python
class RollingHash:
    def __init__(self, window_size=64, prime=3):
        # Initialization code
    def update(self, byte):
        # Updates the rolling hash with a new byte
```

### AdaptiveChunker Class

Uses the rolling hash to determine chunk boundaries adaptively.

```python
class AdaptiveChunker:
    def __init__(self, min_chunk=2048, max_chunk=65536, bits=13):
        # Initialization code
    def chunk_data(self, data):
        # Returns a list of data chunks
```

### FuzzyHasher Class

Handles the hashing process, including data normalization and parallel chunk hashing.

```python
class FuzzyHasher:
    def __init__(self, min_chunk=2048, max_chunk=65536, window_size=64, debug=False):
        # Initialization code
    def calculate_signature(self, file_path):
        # Calculates the signature of a file
    def compare_signatures(self, sig1, sig2):
        # Computes Jaccard similarity between two signatures
```

### Main Function

Parses command-line arguments and invokes the appropriate methods.

```python
def main():
    parser = argparse.ArgumentParser(description="Fuzzy Hash Tool")
    # Argument parsing code
    hasher = FuzzyHasher(debug=args.debug)
    # Processing logic
```

