"""Dịch vụ render mock: nhận danh sách keyframe (SVG data URI) và thời lượng từng shot,
làm mỗi shot thành một clip (kèm tiếng thoại nếu có trong /output/<project_id>/audio)
rồi ghép thành một file mp4 trong /output."""
import base64
import json
import os
import re
import struct
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

OUT_DIR = "/output"
UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")
NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
SVG_RE = re.compile(r"^data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)$")


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def save_audio(project_id, name, data_b64):
    audio_dir = os.path.join(OUT_DIR, project_id, "audio")
    os.makedirs(audio_dir, exist_ok=True)
    path = os.path.join(audio_dir, f"{name}.wav")
    with open(path, "wb") as f:
        f.write(base64.b64decode(data_b64, validate=True))
    return path


def image_info(data):
    """Nhận dạng ảnh JPEG hoặc PNG từ vài byte đầu. Trả về (đuôi file, rộng, cao)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return "png", w, h
    if data[:3] == b"\xff\xd8\xff":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker == 0xFF:
                i += 1
                continue
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return "jpg", w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
        return "jpg", 0, 0
    raise ValueError("không phải ảnh JPEG hoặc PNG")


def save_image(project_id, name, data_b64):
    raw = base64.b64decode(data_b64, validate=True)
    ext, w, h = image_info(raw)
    image_dir = os.path.join(OUT_DIR, project_id, "images")
    os.makedirs(image_dir, exist_ok=True)
    # Mỗi tên chỉ giữ một định dạng: xóa bản cũ khác đuôi để không nhầm.
    for other in ("jpg", "png"):
        old = os.path.join(image_dir, f"{name}.{other}")
        if other != ext and os.path.exists(old):
            os.remove(old)
    path = os.path.join(image_dir, f"{name}.{ext}")
    with open(path, "wb") as f:
        f.write(raw)
    return path, w, h


def shot_audio_files(project_id, slug):
    """File thoại của một shot: <slug>-<số>.wav, xếp theo số thứ tự câu."""
    audio_dir = os.path.join(OUT_DIR, project_id, "audio")
    if not os.path.isdir(audio_dir):
        return []
    pattern = re.compile(rf"^{re.escape(slug)}-(\d+)\.wav$")
    found = [(int(m.group(1)), name) for name in os.listdir(audio_dir)
             if (m := pattern.match(name))]
    return [os.path.join(audio_dir, name) for _, name in sorted(found)]


def wav_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", path], check=True, capture_output=True, text=True)
    return float(out.stdout.strip())


LEAD_IN = 0.3   # giây im lặng trước câu thoại
TAIL = 0.3      # giây im lặng sau câu thoại cuối
AUDIO_OPTS = ["-c:a", "aac", "-ar", "24000", "-ac", "1"]
# Ảnh nào cũng được phóng vừa khung 1280x720 rồi cắt giữa phần thừa (ảnh vuông sẽ mất phần trên và dưới).
VIDEO_OPTS = ["-r", "25", "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
              "-c:v", "libx264", "-pix_fmt", "yuv420p"]


def resolve_output_image(url, slug):
    """Đổi đường dẫn keyframe thật (output/...) thành file trong /output, chặn đường dẫn lạ."""
    if not isinstance(url, str) or not url.startswith("output/"):
        raise ValueError(f"shot {slug}: keyframe_url không phải SVG mock hay đường dẫn ảnh dạng output/...")
    root = os.path.realpath(OUT_DIR)
    path = os.path.realpath(os.path.join(root, url[len("output/"):]))
    if not path.startswith(root + os.sep) or os.path.splitext(path)[1].lower() not in (".jpg", ".png"):
        raise ValueError(f"shot {slug}: đường dẫn ảnh không hợp lệ")
    if not os.path.isfile(path):
        raise ValueError(f"shot {slug}: không thấy file ảnh {url}")
    return path


def make_clip(png, duration, wavs, clip):
    """Clip một shot: ảnh tĩnh + tiếng thoại (hoặc im lặng).
    Trả về (thời lượng thật của clip, danh sách câu thoại với giây bắt đầu tính từ đầu clip)."""
    if not wavs:
        run(["ffmpeg", "-y", "-loop", "1", "-i", png, "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
             "-t", str(duration), *VIDEO_OPTS, *AUDIO_OPTS, clip])
        return duration, []
    lengths = [wav_seconds(w) for w in wavs]
    lines, t = [], LEAD_IN
    for w, length in zip(wavs, lengths):
        lines.append({"file": f"audio/{os.path.basename(w)}", "start": t, "duration": length})
        t += length
    # Câu thoại dài hơn shot thì kéo dài clip cho khỏi bị cắt tiếng.
    total = max(duration, sum(lengths) + LEAD_IN + TAIL)
    inputs = [arg for w in wavs for arg in ("-i", w)]
    labels = "".join(f"[{k + 1}:a]" for k in range(len(wavs)))
    delay_ms = int(LEAD_IN * 1000)
    graph = f"{labels}concat=n={len(wavs)}:v=0:a=1,adelay={delay_ms}:all=1,apad,aresample=24000[a]"
    run(["ffmpeg", "-y", "-loop", "1", "-i", png, *inputs, "-filter_complex", graph,
         "-map", "0:v", "-map", "[a]", "-t", f"{total:.3f}", *VIDEO_OPTS, *AUDIO_OPTS, clip])
    return total, lines


def render(project_id, shots):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{project_id}.mp4")
    dialogue_lines = 0
    manifest_shots, cursor = [], 0.0
    with tempfile.TemporaryDirectory() as tmp:
        clips = []
        for i, shot in enumerate(shots):
            slug = shot.get("slug", "")
            if not NAME_RE.match(slug):
                raise ValueError(f"slug không hợp lệ: {slug!r}")
            duration = float(shot["duration_sec"])
            if not 0 < duration <= 60:
                raise ValueError(f"shot {slug}: duration_sec không hợp lệ")
            svg, png, clip = (f"{tmp}/{i:02d}.{ext}" for ext in ("svg", "png", "mp4"))
            match = SVG_RE.match(shot["url"])
            if match:
                # Keyframe mock: SVG nằm thẳng trong dữ liệu.
                with open(svg, "wb") as f:
                    f.write(base64.b64decode(match.group(1)))
                run(["rsvg-convert", "-w", "1280", "-h", "720", "-o", png, svg])
            else:
                # Keyframe thật: đường dẫn file ảnh dạng output/<project_id>/images/<tên>.jpg
                png = resolve_output_image(shot["url"], slug)
            wavs = shot_audio_files(project_id, slug)
            dialogue_lines += len(wavs)
            total, lines = make_clip(png, duration, wavs, clip)
            clips.append(clip)
            manifest_shots.append({
                "slug": slug, "start": round(cursor, 3), "duration": round(total, 3),
                "lines": [{"file": ln["file"], "start": round(cursor + ln["start"], 3),
                           "duration": round(ln["duration"], 3)} for ln in lines],
            })
            cursor += total
        list_path = f"{tmp}/list.txt"
        with open(list_path, "w") as f:
            f.writelines(f"file '{c}'\n" for c in clips)
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", out_path])
    # Bản ghi thời gian cho trang Timeline: từng shot và từng câu thoại nằm ở giây nào trong video.
    manifest = {"project_id": project_id, "video": os.path.basename(out_path),
                "duration": round(cursor, 3), "shots": manifest_shots}
    with open(os.path.join(OUT_DIR, f"{project_id}.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False)
    return out_path, dialogue_lines


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
        if self.path not in ("/render", "/audio", "/image"):
            return self.reply(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length))
            project_id = payload["project_id"]
            if not UUID_RE.match(project_id):
                raise ValueError("project_id không hợp lệ")
            if self.path == "/audio":
                name = payload["name"]
                if not NAME_RE.match(name):
                    raise ValueError("name không hợp lệ (chỉ a-z, 0-9, gạch ngang)")
                path = save_audio(project_id, name, payload["data"])
                return self.reply(200, {"file": os.path.relpath(path, OUT_DIR),
                                        "size_bytes": os.path.getsize(path)})
            if self.path == "/image":
                name = payload["name"]
                if not NAME_RE.match(name):
                    raise ValueError("name không hợp lệ (chỉ a-z, 0-9, gạch ngang)")
                path, w, h = save_image(project_id, name, payload["data"])
                return self.reply(200, {"file": os.path.relpath(path, OUT_DIR), "width": w, "height": h,
                                        "size_bytes": os.path.getsize(path)})
            shots = payload["shots"]
            if not shots:
                raise ValueError("shots rỗng")
            path, dialogue_lines = render(project_id, shots)
            self.reply(200, {"file": os.path.basename(path), "shots": len(shots),
                             "dialogue_lines": dialogue_lines,
                             "size_bytes": os.path.getsize(path)})
        except subprocess.CalledProcessError as e:
            self.reply(500, {"error": "ffmpeg/rsvg lỗi", "detail": (e.stderr or "")[-500:]})
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            self.reply(400, {"error": str(e)})
        except OSError as e:
            self.reply(500, {"error": f"lỗi hệ thống: {e}"})


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
