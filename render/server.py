"""Dịch vụ render mock: nhận danh sách keyframe (SVG data URI) và thời lượng từng shot,
làm mỗi shot thành một clip rồi ghép thành một file mp4 trong /output."""
import base64
import json
import os
import re
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OUT_DIR = "/output"
UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
SVG_RE = re.compile(r"^data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)$")


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def render(project_id, shots):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{project_id}.mp4")
    with tempfile.TemporaryDirectory() as tmp:
        clips = []
        for i, shot in enumerate(shots):
            match = SVG_RE.match(shot["url"])
            if not match:
                raise ValueError(f"shot {shot.get('slug')}: keyframe_url không phải SVG data URI")
            duration = float(shot["duration_sec"])
            if not 0 < duration <= 60:
                raise ValueError(f"shot {shot.get('slug')}: duration_sec không hợp lệ")
            svg, png, clip = (f"{tmp}/{i:02d}.{ext}" for ext in ("svg", "png", "mp4"))
            with open(svg, "wb") as f:
                f.write(base64.b64decode(match.group(1)))
            run(["rsvg-convert", "-w", "1280", "-h", "720", "-o", png, svg])
            run(["ffmpeg", "-y", "-loop", "1", "-i", png, "-t", str(duration), "-r", "25",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", clip])
            clips.append(clip)
        list_path = f"{tmp}/list.txt"
        with open(list_path, "w") as f:
            f.writelines(f"file '{c}'\n" for c in clips)
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path])
    return out_path


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.reply(200, {"ok": True}) if self.path == "/health" else self.reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/render":
            return self.reply(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            project_id = payload["project_id"]
            if not UUID_RE.match(project_id):
                raise ValueError("project_id không hợp lệ")
            shots = payload["shots"]
            if not shots:
                raise ValueError("shots rỗng")
            path = render(project_id, shots)
            self.reply(200, {"file": os.path.basename(path), "shots": len(shots),
                             "size_bytes": os.path.getsize(path)})
        except subprocess.CalledProcessError as e:
            self.reply(500, {"error": "ffmpeg/rsvg lỗi", "detail": (e.stderr or "")[-500:]})
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self.reply(400, {"error": str(e)})
        except OSError as e:
            self.reply(500, {"error": f"lỗi hệ thống: {e}"})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
