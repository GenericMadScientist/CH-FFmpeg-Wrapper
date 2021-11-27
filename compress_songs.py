import concurrent.futures
import os
import re
import subprocess
import sys


def get_jobs(directory):
    jobs = {'albums': [], 'audio_files': [], 'delete': []}

    for root, _, files in os.walk(directory):
        for f in files:
            path = os.path.join(root, f)
            if f.lower() in ['album.jpg', 'album.png']:
                jobs['albums'].append(path)
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
    result = subprocess.run([ffmpeg,
                             '-y',
                             '-i',
                             file,
                             '-b:a',
                             '80k',
                             output],
                            capture_output=True)
    if result.returncode == 0:
        os.remove(file)


def image_type_and_size(ffmpeg, file):
    result = subprocess.run(
        [ffmpeg, '-hide_banner', '-i', file], capture_output=True)
    for line in result.stderr.split(b'\n'):
        if line.startswith(b'  Stream #0:0: Video: png'):
            sub_parts = line.split(b'), ')
            if len(sub_parts) < 2:
                return None
            res_str = image_type_and_size.regex.match(sub_parts[1])
            if res_str is None or res_str.start() != 0:
                return None
            x, _, y = res_str.group().partition(b'x')
            return ('png', int(x), int(y))
        elif line.startswith(b'  Stream #0:0: Video: mjpeg ('):
            sub_parts = line.split(b'), ')
            if len(sub_parts) < 3:
                return None
            res_str = image_type_and_size.regex.match(sub_parts[2])
            if res_str is None or res_str.start() != 0:
                return None
            x, _, y = res_str.group().partition(b'x')
            return ('jpeg', int(x), int(y))
    return None


image_type_and_size.regex = re.compile(rb'\d+x\d+')


def resize_and_convert_image(ffmpeg, file):
    data = image_type_and_size(ffmpeg, file)
    if data is None:
        return
    type, x, y = data
    if type == 'jpeg' and max(x, y) <= 500:
        head, tail = os.path.split(file)
        if tail != 'album.jpg':
            os.rename(file, os.path.join(head, 'album.jpg'))
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
                             output.replace('%', '%%')],
                            capture_output=True)
    if result.returncode == 0:
        head, _ = os.path.split(file)
        os.remove(file)
        os.rename(output, os.path.join(head, 'album.jpg'))


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

        for f in jobs['albums']:
            future = executor.submit(resize_and_convert_image, ffmpeg, f)
            futures.append(future)

        for f in jobs['delete']:
            os.remove(f)
