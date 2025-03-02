import os
import sys
import json
import base64
import struct
import argparse
import shutil
import logging
import multiprocessing
from tqdm import tqdm
from Crypto.Cipher import AES

try:
    import requests
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC, error as ID3Error
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC, Picture
except ImportError:
    print("Please install mutagen, requests, and tqdm: pip install mutagen requests tqdm")
    sys.exit(1)

# Constants for decryption
CORE_KEY = bytes.fromhex("687a4852416d736f356b496e62617857")
META_KEY = bytes.fromhex("2331346C6A6B5F215C5D2630553C2728")

AUDIO_MIME_TYPE = {
    "mp3": "audio/mpeg",
    "flac": "audio/flac"
}
# Recognized audio file extensions (non-NCM)
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.aac', '.ogg', '.wma', '.m4a'}

DEFAULT_ALBUM_PIC = "https://p4.music.126.net/nSsje95JU5hVylFPzLqWHw==/109951163542280093.jpg"

# Setup logger; level will be set later based on -v flag.
logger = logging.getLogger(__name__)
logger_handler = logging.StreamHandler(sys.stdout)
logger_formatter = logging.Formatter('%(levelname)s: %(message)s')
logger_handler.setFormatter(logger_formatter)
logger.addHandler(logger_handler)
logger.setLevel(logging.WARNING)

def pkcs7_unpad(data):
    pad_len = data[-1]
    if pad_len < 1 or pad_len > AES.block_size:
        raise ValueError("Invalid padding")
    return data[:-pad_len]

def convert_ncm(in_file, out_file=None):
    """Convert a single NCM file to its corresponding audio file.
       If out_file is provided, the decrypted audio is saved there;
       otherwise, it is saved alongside in_file with a changed extension.
    """
    logger.info(f"Converting: {in_file}")
    with open(in_file, 'rb') as f:
        file_bytes = f.read()

    # Verify header: first 8 bytes (two little-endian uint32)
    header0, header1 = struct.unpack('<II', file_bytes[0:8])
    if header0 != 0x4e455443 or header1 != 0x4d414446:
        raise ValueError("Not an NCM file")

    offset = 10

    # ---- Decrypt key data ----
    key_len = struct.unpack('<I', file_bytes[offset:offset+4])[0]
    offset += 4
    key_data_encrypted = bytearray(file_bytes[offset:offset+key_len])
    offset += key_len
    for i in range(len(key_data_encrypted)):
        key_data_encrypted[i] ^= 0x64
    cipher_core = AES.new(CORE_KEY, AES.MODE_ECB)
    decrypted = cipher_core.decrypt(bytes(key_data_encrypted))
    decrypted = pkcs7_unpad(decrypted)
    key_data = decrypted[17:]  # skip first 17 bytes

    # ---- Generate key box ----
    box = list(range(256))
    key_data_len = len(key_data)
    j = 0
    for i in range(256):
        j = (box[i] + j + key_data[i % key_data_len]) & 0xff
        box[i], box[j] = box[j], box[i]
    key_box = []
    for i in range(256):
        i1 = (i + 1) & 0xff
        si = box[i1]
        sj = box[(i1 + si) & 0xff]
        key_box.append(box[(si + sj) & 0xff])

    # ---- Process metadata ----
    meta_len = struct.unpack('<I', file_bytes[offset:offset+4])[0]
    offset += 4
    if meta_len == 0:
        music_meta = {"album": "⚠️ meta lost", "albumPic": DEFAULT_ALBUM_PIC}
    else:
        meta_data = bytearray(file_bytes[offset:offset+meta_len])
        offset += meta_len
        for i in range(len(meta_data)):
            meta_data[i] ^= 0x63
        try:
            b64_str = meta_data[22:].decode("utf-8", errors="ignore")
        except Exception:
            b64_str = ""
        try:
            meta_ciphertext = base64.b64decode(b64_str)
        except Exception:
            meta_ciphertext = b""
        cipher_meta = AES.new(META_KEY, AES.MODE_ECB)
        meta_plain = cipher_meta.decrypt(meta_ciphertext)
        meta_plain = pkcs7_unpad(meta_plain)
        meta_json_str = meta_plain[6:].decode("utf-8", errors="ignore").strip()
        try:
            music_meta = json.loads(meta_json_str)
        except Exception:
            music_meta = {"album": "⚠️ meta lost", "albumPic": DEFAULT_ALBUM_PIC}
        if "albumPic" in music_meta:
            music_meta["albumPic"] = music_meta["albumPic"].replace("http:", "https:")

    # ---- Skip additional header information ----
    extra = struct.unpack('<I', file_bytes[offset+5:offset+9])[0]
    offset += extra + 13

    # ---- Decrypt audio data ----
    audio_data = bytearray(file_bytes[offset:])
    for i in range(len(audio_data)):
        audio_data[i] ^= key_box[i & 0xff]

    # Determine file format if not provided in metadata.
    if "format" not in music_meta or not music_meta["format"]:
        if audio_data[:4] == b'fLaC':
            music_meta["format"] = "flac"
        else:
            music_meta["format"] = "mp3"

    # Determine output file name.
    if not out_file:
        out_file = os.path.splitext(in_file)[0] + '.' + music_meta["format"]
    else:
        out_file = os.path.splitext(out_file)[0] + '.' + music_meta["format"]

    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, 'wb') as out_f:
        out_f.write(audio_data)

    logger.info(f"Saved converted file to: {out_file}")
    return {"meta": music_meta, "audio_file": out_file,
            "mime": AUDIO_MIME_TYPE.get(music_meta["format"], "application/octet-stream")}

def embed_metadata(audio_file, music_meta):
    fmt = music_meta.get("format", "mp3")
    title = music_meta.get("musicName", "")
    album = music_meta.get("album", "")
    artist = music_meta.get("artist", [])
    if isinstance(artist, list):
        artist_names = []
        for a in artist:
            if isinstance(a, list) and a:
                artist_names.append(a[0])
            elif isinstance(a, str):
                artist_names.append(a)
        artist_str = ", ".join(artist_names)
    else:
        artist_str = ""
    album_pic_url = music_meta.get("albumPic", "")

    if fmt == "mp3":
        try:
            audio = MP3(audio_file)
        except Exception:
            audio = MP3(audio_file)
            audio.add_tags()
        try:
            audio.tags.add(TIT2(encoding=3, text=title))
            audio.tags.add(TPE1(encoding=3, text=artist_str))
            audio.tags.add(TALB(encoding=3, text=album))
            if album_pic_url:
                try:
                    pic_data = requests.get(album_pic_url).content
                    audio.tags.add(APIC(
                        encoding=3,
                        mime='image/jpeg',
                        type=3,
                        desc='Cover',
                        data=pic_data
                    ))
                except Exception:
                    pass
            audio.save()
        except ID3Error:
            pass
    elif fmt == "flac":
        try:
            audio = FLAC(audio_file)
            audio["title"] = title
            audio["artist"] = artist_str
            audio["album"] = album
            if album_pic_url:
                try:
                    pic_data = requests.get(album_pic_url).content
                    pic = Picture()
                    pic.data = pic_data
                    pic.type = 3  # front cover
                    pic.mime = "image/jpeg"
                    pic.desc = "Cover"
                    audio.clear_pictures()
                    audio.add_picture(pic)
                except Exception:
                    pass
            audio.save()
        except Exception:
            pass

def gather_files(sources, target_base):
    """
    Given a list of source paths (files or directories), return two lists:
      - conv_list: list of tuples (in_file, rel_path) for files ending in .ncm
      - copy_list: list of tuples (in_file, rel_path) for recognized audio files (non-.ncm)
    The relative path is computed so that the destination preserves the source folder structure.
    """
    conv_list = []
    copy_list = []
    for src in sources:
        src = os.path.normpath(src)
        if os.path.isdir(src):
            base_dir = os.path.basename(src)
            for root, _, files in os.walk(src):
                for name in files:
                    ext = os.path.splitext(name)[1].lower()
                    if ext == ".ncm":
                        in_file = os.path.join(root, name)
                        rel_path = os.path.relpath(in_file, src)
                        out_rel = os.path.join(base_dir, rel_path)
                        conv_list.append((in_file, out_rel))
                    elif ext in AUDIO_EXTENSIONS:
                        in_file = os.path.join(root, name)
                        rel_path = os.path.relpath(in_file, src)
                        out_rel = os.path.join(base_dir, rel_path)
                        copy_list.append((in_file, out_rel))
        elif os.path.isfile(src):
            ext = os.path.splitext(src)[1].lower()
            if ext == ".ncm":
                conv_list.append((src, os.path.basename(src)))
            elif ext in AUDIO_EXTENSIONS:
                copy_list.append((src, os.path.basename(src)))
    return conv_list, copy_list

def process_conversion_item(args_tuple):
    """Worker function for multiprocessing.
       args_tuple is (in_file, rel_path, target, embed_flag)
    """
    in_file, rel_path, target, embed_flag = args_tuple
    out_file = os.path.join(target, os.path.splitext(rel_path)[0])
    result = convert_ncm(in_file, out_file)
    if embed_flag:
        embed_metadata(result["audio_file"], result["meta"])
    return result["audio_file"]

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Convert NCM file(s) and copy other audio files while preserving folder structure."
    )
    parser.add_argument("-s", "--sources", nargs="+", required=True,
                        help="Source file(s) and/or folder(s) containing NCM or audio files")
    parser.add_argument("-t", "--target", required=True,
                        help="Target folder to save converted/copied files")
    parser.add_argument("--embed-meta", action="store_true",
                        help="Embed metadata into the converted file(s)")
    parser.add_argument("-w", "--workers", type=int, default=1,
                        help="Number of worker processes to use for conversion (default: 1, -1 to use all cores)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show detailed logging information")
    args = parser.parse_args()

    # Set logger level based on verbose flag.
    if args.verbose:
        logger.setLevel(logging.INFO)

    conv_list, copy_list = gather_files(args.sources, args.target)
    total_conv = len(conv_list)
    total_copy = len(copy_list)

    # Display counts regardless of verbose mode.
    print(f"Total NCM files to convert: {total_conv}")
    print(f"Total audio files to copy: {total_copy}")

    # Determine the number of workers.
    workers = args.workers
    if workers == -1:
        workers = multiprocessing.cpu_count()

    # Process conversion files with multi-core support if requested.
    if total_conv > 0:
        if workers > 1:
            pool = multiprocessing.Pool(processes=workers)
            tasks = [(in_file, rel_path, args.target, args.embed_meta) for in_file, rel_path in conv_list]
            for _ in tqdm(pool.imap_unordered(process_conversion_item, tasks),
                          total=total_conv, desc="Converting NCM files", unit="file"):
                pass
            pool.close()
            pool.join()
        else:
            for in_file, rel_path in tqdm(conv_list, desc="Converting NCM files", unit="file"):
                out_file = os.path.join(args.target, os.path.splitext(rel_path)[0])
                result = convert_ncm(in_file, out_file)
                if args.embed_meta:
                    embed_metadata(result["audio_file"], result["meta"])

    # Process copy files sequentially.
    for in_file, rel_path in copy_list:
        try:
            out_path = os.path.join(args.target, rel_path)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            shutil.copy2(in_file, out_path)
            logger.info(f"Copied: {in_file} -> {out_path}")
        except Exception as e:
            logger.error(f"Error copying {in_file}: {e}")

    print("All files processed.")
