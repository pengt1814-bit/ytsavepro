from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import threading
import time
import uuid

app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)

DOWNLOAD_DIR = tempfile.gettempdir()

def cleanup_file(path, delay=60):
    def _del():
        time.sleep(delay)
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass
    threading.Thread(target=_del, daemon=True).start()

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'No URL'}), 400
    try:
        ydl_opts = {
            'quiet': True,
            'skip_download': True,
            'nocheckcertificate': True,
            'geo_bypass': True,
            'cookiefile': '/app/cookies.txt',
            'extractor_args': {'youtube': {'player_client': ['android']}},
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title', ''),
                'duration': info.get('duration_string', ''),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', '')
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url', '').strip()
    mode = data.get('mode', 'video')
    quality = data.get('quality', '1080p')
    if not url:
        return jsonify({'error': 'No URL'}), 400
    job_id = str(uuid.uuid4())
    out_path = os.path.join(DOWNLOAD_DIR, job_id)
    try:
        if mode == 'audio':
            kbps = quality.replace('kbps', '')
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': out_path + '.%(ext)s',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': kbps,
                }],
                'quiet': True,
                'nocheckcertificate': True,
                'geo_bypass': True,
                'cookiefile': '/app/cookies.txt',
                'extractor_args': {'youtube': {'player_client': ['android']}},
            }
            ext = 'mp3'
            mime = 'audio/mpeg'
        else:
            height = quality.replace('p', '')
            ydl_opts = {
                'format': f'bestvideo[height<={height}]+bestaudio/best/bestvideo+bestaudio/best',
                'outtmpl': out_path + '.%(ext)s',
                'merge_output_format': 'mp4',
                'quiet': True,
                'nocheckcertificate': True,
                'geo_bypass': True,
                'cookiefile': '/app/cookies.txt',
                'extractor_args': {'youtube': {'player_client': ['android']}},
            }
            ext = 'mp4'
            mime = 'video/mp4'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')

        final_path = None
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(job_id):
                final_path = os.path.join(DOWNLOAD_DIR, f)
                break

        if not final_path:
            return jsonify({'error': 'File not found'}), 500

        safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip()[:60]
        cleanup_file(final_path, delay=120)
        return send_file(final_path, mimetype=mime, as_attachment=True, download_name=f"{safe_title}.{ext}")

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
