# NCM Converter

A Python tool to convert encrypted `.ncm` files (from NetEase Cloud Music) into playable audio formats (e.g. MP3 or FLAC). It also preserves the folder structure when copying existing audio files (such as MP3, FLAC, WAV, etc.) to a target folder. Additionally, it supports metadata embedding and multi-core processing.

## Features

- **Decrypt and Convert**: Converts `.ncm` files into their corresponding audio format by decrypting the embedded keys.
- **Metadata Extraction and Embedding**: Extracts metadata from the NCM file and optionally embeds it into the resulting audio file (using Mutagen).
- **Preserve Folder Structure**: Recursively scans source directories and reproduces the original folder structure in the destination folder.
- **Copy Existing Audio Files**: Recognizes and copies non-NCM audio files (e.g. MP3, FLAC, WAV) to the target folder.
- **Multi-core Processing**: Supports parallel conversion using multiple cores.
- **Verbose Logging**: Optional verbose mode for detailed logging.

## Installation

Ensure you have [Python 3](https://www.python.org/) installed. Then, install the required Python packages using pip: \
`pip install pycryptodome mutagen requests tqdm`



## Usage

Run the script with the following command-line options: \
`python3 convert.py -s <source_paths> -t <target_folder> [--embed-meta] [-w WORKERS] [-v]`


### Options

- **-s, --sources**  
  One or more source files and/or folders containing NCM or other audio files.  
  *Example:* `-s A B c.ncm`

- **-t, --target**  
  Target folder where the converted and copied files will be saved.  
  *Example:* `-t /path/to/target`

- **--embed-meta**  
  Optional flag to embed extracted metadata (such as title, album, artist, and cover art) into the converted audio files.

- **-w, --workers**  
  Number of worker processes to use for conversion.  
  - Default is `1` (single-core).  
  - Use `-w -1` to use all available CPU cores.  
  *Example:* `-w 4` or `-w -1`

- **-v, --verbose**  
  Enable verbose logging to show detailed processing information in the terminal.

### Example

Convert all NCM files from folders `A`, `B`, and file `c.ncm` into the `/path/to/target` directory, embed metadata, use all CPU cores, and show detailed logs: \
`python3 convert.py -s A B c.ncm -t /path/to/target --embed-meta -w -1 -v `

## Dependencies

- **Python 3**
- [PyCryptodome](https://www.pycryptodome.org/) – For AES decryption.
- [Mutagen](https://mutagen.readthedocs.io/) – For embedding metadata into audio files.
- [Requests](https://docs.python-requests.org/) – For downloading album art.
- [tqdm](https://tqdm.github.io/) – For displaying a progress bar.

## License

This project is provided under the [MIT License](https://opensource.org/licenses/MIT).

