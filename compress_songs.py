import concurrent.futures
import os
import re
import subprocess
import sys


def get_jobs(directory):
    jobs = {'album_jpgs': [], 'album_pngs': [],
            'audio_files': [], 'delete': []}

    for root, _, files in os.walk(directory):
        for f in files:
            path = os.path.join(root, f)
            if f == 'album.jpg':
                jobs['album_jpgs'].append(path)
                continue
            elif f == 'album.png':
                jobs['album_pngs'].append(path)
                continue
            elif f in ['ch.dat', 'notes.eof', 'ps.dat']:
                jobs['delete'].append(path)
                continue
            _, ext = os.path.splitext(path)
            if ext in ['.mp3', '.ogg', '.wav']:
                jobs['audio_files'].append(path)
            elif ext in ['.sfk', '.sfl']:
                jobs['delete'].append(path)

    return jobs


def audio_to_opus(ffmpeg, file):
    root, _ = os.path.splitext(file)
    output = root + '.opus'
    result = subprocess.run(
        [ffmpeg, '-y', '-i', file, '-b:a', '80k', output], capture_output=True)
    if result.returncode == 0:
        os.remove(file)


def jpg_size(ffmpeg, file):
    result = subprocess.run(
        [ffmpeg, '-hide_banner', '-i', file], capture_output=True)
    for line in result.stderr.split(b'\n'):
        if line.startswith(b'  Stream #0:0: Video: mjpeg ('):
            sub_parts = line.split(b'), ')
            if len(sub_parts) < 3:
                return None
            res_str = jpg_size.regex.match(sub_parts[2])
            if res_str is None or res_str.start() != 0:
                return None
            x, _, y = res_str.group().partition(b'x')
            return (int(x), int(y))
    return None


jpg_size.regex = re.compile(rb'\d+x\d+')


def png_size(ffmpeg, file):
    result = subprocess.run(
        [ffmpeg, '-hide_banner', '-i', file], capture_output=True)
    for line in result.stderr.split(b'\n'):
        if line.startswith(b'  Stream #0:0: Video: png'):
            sub_parts = line.split(b'), ')
            if len(sub_parts) < 2:
                return None
            res_str = png_size.regex.match(sub_parts[1])
            if res_str is None or res_str.start() != 0:
                return None
            x, _, y = res_str.group().partition(b'x')
            return (int(x), int(y))
    return None


png_size.regex = re.compile(rb'\d+x\d+')


def resize_jpg(ffmpeg, file):
    resolution = jpg_size(ffmpeg, file)
    if resolution is None:
        return
    x, y = resolution
    if max(x, y) <= 500:
        return
    max_size = max(x, y)
    x = 500 * x // max_size
    y = 500 * y // max_size
    root, _ = os.path.splitext(file)
    output = root + '-tmp-copy.jpg'
    result = subprocess.run([ffmpeg,
                             '-y',
                             '-i',
                             file,
                             '-vf',
                             f'scale={x}:{y}',
                             output],
                            capture_output=True)
    if result.returncode == 0:
        os.replace(output, file)


def png_to_jpg(ffmpeg, file):
    resolution = png_size(ffmpeg, file)
    if resolution is None:
        return
    x, y = resolution
    if max(x, y) > 500:
        max_size = max(x, y)
        x = 500 * x // max_size
        y = 500 * y // max_size
    root, _ = os.path.splitext(file)
    output = root + '.jpg'
    result = subprocess.run([ffmpeg,
                             '-y',
                             '-i',
                             file,
                             '-vf',
                             f'scale={x}:{y}',
                             output],
                            capture_output=True)
    if result.returncode == 0:
        os.remove(file)


if __name__ == '__main__':
    jobs = get_jobs(sys.argv[1])
    ffmpeg = 'ffmpeg.exe'
    if os.name != 'nt':
        ffmpeg = 'ffmpeg'

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = []

        for f in jobs['audio_files']:
            future = executor.submit(audio_to_opus, ffmpeg, f)
            futures.append(future)

        for f in jobs['album_jpgs']:
            future = executor.submit(resize_jpg, ffmpeg, f)
            futures.append(future)

        for f in jobs['album_pngs']:
            future = executor.submit(png_to_jpg, ffmpeg, f)
            futures.append(future)

        for f in jobs['delete']:
            os.remove(f)
