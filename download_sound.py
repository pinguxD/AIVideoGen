import sys
from radar.sound_finder import download_url

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: py download_sound.py DIRECT_AUDIO_URL [filename.mp3]')
        raise SystemExit(1)
    out = download_url(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else None)
    print(f'Saved: {out}')
