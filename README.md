![Alt text](https://i.ibb.co/gVSWXMZ/phonto.jpg)

GLACIER (Grouped Locality-sensitive Adaptive Chunking with Integrated Efficient Rolling) is an adaptive fuzzy hashing algorithm and signaturing tool which provides resilient and efficient similarity detection between samples. It is an attempt to improve upon existing fuzzy hashing algorithms like **SSDEEP** and **TLSH**.

## Features

1. **Adaptive Chunking**
   - Dynamic chunk size based on content (Rabin Fingerprinting)
   - Resilient to data insertions and deletions
   - Improves hash stability for similar files
2. **Rolling Hash Computation**
   - Efficient updates for streaming data
   - Allows for real-time processing of large files
3. **Ratcliff/Obershelp Similarity Measurement**
   - Accurate file similarity assessment
4. **Content-Defined Boundaries**
   - Uses rolling hash for intelligent chunk boundaries
   - Improves resilience to file modifications
5. **Configurable Parameters**
    - Adjustable window size, chunk size limits, and other parameters
    - Allows fine-tuning for specific use cases
6. **Database Creation**
    - Create a signature database from a folder
7. **Scanning Functionality**
    - Scan a file/folder against your curated signature database

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

### Creation of a signature database

To generate a SQLite database of signatures for a folder

```bash
python glacier.py -db {folderpath}
```

### Scan a file against signature database

To scan a file (or folder) against your curated signature database.

```bash
python glacier.py -scan {filepath/folderpath}
```
## Comparison with SSDEEP and TLSH

### Pros of GLACIER

1. **Parallel Processing**: Potentially faster than both TLSH and SSDEEP on multi-core systems.
2. **Flexible Chunk Size**: Adapts to file content, unlike SSDEEP's fixed 64-byte chunks or TLSH's 256-byte sliding window.
3. **Ratcliff/Obershelp Algorithm**: Offers a different similarity metric (Ratcliff/Obershelp algorithm) compared to TLSH's Hamming distance or SSDEEP's edit distance Levenshtein algorithm.

### Cons of GLACIER

- **Potentially Larger Signatures**: Adaptive chunking via Rabin fingerprinting may result in a long hash for files >1MB.



## Consolidate.py

### Features:
1. **Consolidation**: Calling this script with -auto will automatically consolidate, rename, and vaccum your signature database.
3. **Threshold Customization**: Users can specify via args the similarity threshold (using --threshold), or take manual control of the grouping process.
