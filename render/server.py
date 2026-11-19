"""Dịch vụ render mock: nhận danh sách keyframe (SVG data URI) và thời lượng từng shot,
làm mỗi shot thành một clip (kèm tiếng thoại nếu có trong /output/<project_id>/audio)
rồi ghép thành một file mp4 trong /output."""
import base64
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import director
import providers

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
    if name.startswith("char-"):
        make_reference(project_id, name, path)
    return path, w, h


def make_reference(project_id, name, src, top=False):
    """Chân dung nhân vật (tên bắt đầu bằng char-) có thêm bản 448x448 làm ảnh tham chiếu.
    FLUX.2 yêu cầu ảnh tham chiếu nhỏ hơn 512x512. top=True cắt vuông từ phía trên (ảnh dọc, mặt nằm trên)."""
    ref_dir = os.path.join(OUT_DIR, project_id, "refs")
    os.makedirs(ref_dir, exist_ok=True)
    crop = "crop=448:448:(iw-448)/2:0" if top else "crop=448:448"
    run(["ffmpeg", "-y", "-i", src, "-vf", f"scale=448:448:force_original_aspect_ratio=increase,{crop}",
         "-q:v", "3", os.path.join(ref_dir, f"{name}.jpg")])


MAX_PORTRAIT_BYTES = 20 * 1024 * 1024


def save_prop(handler):
    """Nhận ảnh phụ kiện của một nhân vật (ví dụ chiếc vòng tay) để đính kèm làm ảnh tham chiếu khi tạo clip.
    Lưu thành output/<project>/props/<nhân vật>-<số thứ tự phụ kiện>.jpg (tối đa 1024 px)."""
    project_id = handler.headers.get("X-Project", "")
    slug = handler.headers.get("X-Char", "")
    item = handler.headers.get("X-Item", "")
    if not UUID_RE.match(project_id) or not NAME_RE.match(slug) or not re.fullmatch(r"[0-9]{1,2}", item):
        raise ValueError("thiếu hoặc sai header X-Project, X-Char, X-Item")
    length = int(handler.headers.get("Content-Length", 0))
    if not 0 < length <= MAX_PORTRAIT_BYTES:
        raise ValueError("file rỗng hoặc lớn hơn 20 MB")
    folder = os.path.join(OUT_DIR, project_id, "props")
    os.makedirs(folder, exist_ok=True)
    out = os.path.join(folder, f"{slug}-{int(item)}.jpg")
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "upload")
        with open(raw, "wb") as f:
            f.write(handler.rfile.read(length))
        try:
            run(["ffmpeg", "-y", "-i", raw, "-frames:v", "1", "-vf",
                 "scale='if(gt(iw,ih),min(1024,iw),-2)':'if(gt(iw,ih),-2,min(1024,ih))'", "-q:v", "2", out])
        except subprocess.CalledProcessError:
            raise ValueError("file không phải ảnh đọc được (dùng JPG, PNG hoặc WebP)")
    return {"file": os.path.relpath(out, OUT_DIR), "size_bytes": os.path.getsize(out)}


def save_portrait(handler):
    """Nhận ảnh chân dung do người dùng tải lên (JPG, PNG, WebP), đổi về JPG tối đa 1024 px
    và tạo bản tham chiếu. Thay chân dung cũ của nhân vật đó."""
    project_id = handler.headers.get("X-Project", "")
    slug = handler.headers.get("X-Char", "")
    if not UUID_RE.match(project_id) or not NAME_RE.match(slug):
        raise ValueError("thiếu hoặc sai header X-Project, X-Char")
    length = int(handler.headers.get("Content-Length", 0))
    if not 0 < length <= MAX_PORTRAIT_BYTES:
        raise ValueError("file rỗng hoặc lớn hơn 20 MB")
    image_dir = os.path.join(OUT_DIR, project_id, "images")
    os.makedirs(image_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "upload")
        with open(raw, "wb") as f:
            f.write(handler.rfile.read(length))
        out = os.path.join(image_dir, f"char-{slug}.jpg")
        try:
            run(["ffmpeg", "-y", "-i", raw, "-frames:v", "1", "-vf",
                 "scale='if(gt(iw,ih),min(1024,iw),-2)':'if(gt(iw,ih),-2,min(1024,ih))'", "-q:v", "2", out])
        except subprocess.CalledProcessError:
            raise ValueError("file không phải ảnh đọc được (dùng JPG, PNG hoặc WebP)")
    old_png = os.path.join(image_dir, f"char-{slug}.png")
    if os.path.exists(old_png):
        os.remove(old_png)
    make_reference(project_id, f"char-{slug}", out, top=True)
    _, w, h = image_info(open(out, "rb").read())
    return {"file": os.path.relpath(out, OUT_DIR), "width": w, "height": h, "size_bytes": os.path.getsize(out)}


CF_ACCOUNT_RE = re.compile(r"^[0-9a-f]{32}$")
CF_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"


class CloudflareError(Exception):
    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def build_reference(project_id, characters):
    """Ghép chân dung (refs/char-<slug>.jpg) của các nhân vật có trong shot thành một ảnh tham chiếu.
    Trả về (ảnh JPEG dạng bytes hoặc None, danh sách nhân vật đã dùng theo thứ tự trái sang phải)."""
    root = os.path.join(OUT_DIR, project_id, "refs")
    found = []
    for c in characters[:3]:
        slug = c.get("slug", "")
        path = os.path.join(root, f"char-{slug}.jpg")
        if NAME_RE.match(slug) and os.path.isfile(path):
            found.append((c, path))
    if not found:
        return None, []
    used = [c for c, _ in found]
    if len(found) == 1:
        with open(found[0][1], "rb") as f:
            return f.read(), used
    side = 504 // len(found)  # mỗi mặt một ô vuông, tổng bề ngang nhỏ hơn 512
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "sheet.jpg")
        inputs = [arg for _, p in found for arg in ("-i", p)]
        scaled = "".join(f"[{i}]scale={side}:{side}[v{i}];" for i in range(len(found)))
        stack = "".join(f"[v{i}]" for i in range(len(found))) + f"hstack=inputs={len(found)}"
        run(["ffmpeg", "-y", *inputs, "-filter_complex", scaled + stack, "-q:v", "3", out])
        with open(out, "rb") as f:
            return f.read(), used


def reference_prefix(used):
    """Câu dặn model dùng ảnh tham chiếu: ai ở đâu, giữ nguyên khuôn mặt và kiểu tóc."""
    def who(c):
        male = str(c.get("gender", "")).lower().startswith("nam")
        return f"the {'man' if male else 'woman'} {c.get('name', '')}".strip()
    # Chỉ giữ khuôn mặt và kiểu tóc từ ảnh tham chiếu; quần áo và khung hình theo mô tả trong prompt.
    follow = ("Take only the face and hairstyle from the reference. The clothing, pose, framing, lighting, "
              "time of day, weather and atmosphere are all described in the text below, so follow that text for them. ")
    if len(used) == 1:
        return (f"Image 0 is a reference portrait of {who(used[0])}. "
                "Keep exactly this person's face and hairstyle. " + follow)
    names = ", ".join(who(c) for c in used)
    return (f"Image 0 is a reference sheet showing {len(used)} people side by side, from left to right: {names}. "
            "Keep exactly their faces and hairstyles. Each person keeps only their own accessories: never give one "
            "person's glasses or jewelry to another person. " + follow)


def multipart_body(fields, files):
    boundary = uuid.uuid4().hex
    parts = []
    for key, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    for key, filename, content_type, data in files:
        head = (f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'
                f'Content-Type: {content_type}\r\n\r\n').encode()
        parts.append(head + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def cloudflare_image(auth, account_id, prompt, width, height, reference, seed=None):
    """Gọi FLUX.2 klein trên Cloudflare. Khóa (auth) do n8n gửi kèm yêu cầu, không lưu và không ghi nhật ký."""
    fields = {"prompt": prompt, "width": str(width), "height": str(height)}
    if seed is not None:
        fields["seed"] = str(int(seed))
    files = [("input_image_0", "reference.jpg", "image/jpeg", reference)] if reference else []
    body, content_type = multipart_body(fields, files)
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{CF_MODEL}"
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Authorization": auth, "Content-Type": content_type})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise CloudflareError(e.code, e.read()[:300].decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        raise CloudflareError(502, f"không kết nối được Cloudflare: {e.reason}")
    image = (data.get("result") or {}).get("image") or data.get("image")
    if not image:
        raise CloudflareError(502, json.dumps(data)[:300])
    return image


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
# Chỉnh màu nhẹ giống nhau cho mọi shot (tương phản, bão hòa, hơi ấm, tối góc, hạt phim) để cả phim cùng một "tông".
GRADE = "eq=contrast=1.03:saturation=0.95:brightness=0.015,colorbalance=rm=0.012:bm=-0.012,vignette=PI/10,noise=alls=3:allf=t"
VIDEO_CODEC = ["-r", "25", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
FPS = 25


def film_info(project_id):
    """Ghi chú phim do bước đạo diễn ghi ra (quy chuẩn hình ảnh, loại shot), đọc để chọn chuyển động camera."""
    try:
        with open(os.path.join(OUT_DIR, project_id, "film.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_film_info(project_id, plan):
    """Ghi quy chuẩn hình ảnh và loại shot ra output/<project_id>/film.json cho bước render."""
    folder = os.path.join(OUT_DIR, project_id)
    os.makedirs(folder, exist_ok=True)
    info = film_info(project_id)
    info.update({"style": plan["notes"]["style"], "seed": plan["seed"]})
    info.setdefault("cameras", {}).update(plan.get("cameras", {}))
    info.setdefault("outdoor", {}).update(plan.get("outdoor", {}))
    info.setdefault("motions", {}).update(plan.get("motions", {}))
    with open(os.path.join(folder, "film.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False)


def motion_for(camera, index):
    """Chọn kiểu camera theo loại shot: cận mặt thì đẩy vào, cảnh rộng thì lùi ra, cận chi tiết thì lia ngang."""
    if camera == "close-up":
        return "push"
    if camera == "wide":
        return "pull"
    if camera == "insert":
        return "pan_left" if index % 2 else "pan_right"
    if camera == "two-shot":
        return "pan_right" if index % 2 else "pan_left"
    return "push_soft" if index % 2 == 0 else "pan_right"


def video_filter(motion, seconds):
    """Phóng ảnh lên rồi cho camera trượt (zoom, lia) êm, có giảm tốc ở đầu và cuối, sau đó chỉnh màu chung.
    Phóng lên 3840x2160 trước để việc làm tròn theo điểm ảnh không gây giật lăn tăn."""
    n = max(int(seconds * FPS), 2)
    p = f"(on/{n})"
    ease = f"({p}*{p}*(3-2*{p}))"  # smoothstep: chậm, nhanh dần, chậm lại
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if motion == "push":
        z, x, y = f"1.0+0.10*{ease}", cx, f"{cy}-8*{ease}"
    elif motion == "pull":
        z, x, y = f"1.10-0.10*{ease}", cx, cy
    elif motion == "push_soft":
        z, x, y = f"1.0+0.06*{ease}", cx, cy
    elif motion == "pan_left":
        z, x, y = "1.14", f"(iw-iw/zoom)*(1-{ease})", cy
    else:  # pan_right
        z, x, y = "1.14", f"(iw-iw/zoom)*{ease}", cy
    zoompan = f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s=1280x720:fps={FPS}"
    return ("scale=3840:2160:force_original_aspect_ratio=increase:flags=lanczos,crop=3840:2160,"
            + zoompan + "," + GRADE)


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


RAIN_LAYER = os.path.join(OUT_DIR, "_assets", "rain-v2.mp4")
RAIN_BLEND = "blend=all_mode=screen:all_opacity=0.16"  # trộn trong không gian RGB nên không đổi sắc thái ảnh


def ensure_rain_layer():
    """Lớp mưa rơi (vệt mảnh trôi xuống, lặp liền mạch mỗi 4 giây), tạo một lần rồi dùng lại."""
    if not os.path.isfile(RAIN_LAYER):
        os.makedirs(os.path.dirname(RAIN_LAYER), exist_ok=True)
        expr = ("format=gray,geq=lum=if(gt(mod(sin(floor(X/2)*12.9898+floor((Y+T*400)/40)*78.233)*43758.5453\\,1)\\,0.993)\\,110\\,0)"
                ":cb=128:cr=128,gblur=sigma=1.1:sigmaV=4,format=yuv420p")
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"nullsrc=s=1280x720:r={FPS}", "-t", "4", "-vf", expr,
             "-pix_fmt", "yuv420p", RAIN_LAYER])
    return RAIN_LAYER


def make_clip(png, duration, wavs, clip, motion="push_soft", rain=False):
    """Clip một shot: ảnh có camera chuyển động + tiếng thoại (hoặc im lặng), tùy chọn lớp mưa rơi.
    Trả về (thời lượng thật của clip, danh sách câu thoại với giây bắt đầu tính từ đầu clip)."""
    lengths = [wav_seconds(w) for w in wavs]
    lines, t = [], LEAD_IN
    for w, length in zip(wavs, lengths):
        lines.append({"file": f"audio/{os.path.basename(w)}", "start": t, "duration": length})
        t += length
    # Câu thoại dài hơn shot thì kéo dài clip cho khỏi bị cắt tiếng.
    total = max(duration, sum(lengths) + LEAD_IN + TAIL) if wavs else duration

    cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-loop", "1", "-i", png]
    index = 1
    # format=yuv420p ép về cùng dải màu với lớp mưa (ảnh JPEG dùng dải full, sai dải sẽ làm tối và đậm màu).
    video = f"[0:v]{video_filter(motion, total)},format=yuv420p[base]"
    if rain:
        cmd += ["-stream_loop", "-1", "-i", ensure_rain_layer()]
        # Thứ tự quan trọng: ảnh phim là lớp thứ nhất (nền), lớp mưa là lớp thứ hai.
        video += f";[base]format=gbrp[b];[{index}:v]format=gbrp[r];[b][r]{RAIN_BLEND},format=yuv420p[v]"
        index += 1
    else:
        video += ";[base]null[v]"
    if wavs:
        for w in wavs:
            cmd += ["-i", w]
        labels = "".join(f"[{index + k}:a]" for k in range(len(wavs)))
        delay_ms = int(LEAD_IN * 1000)
        audio = f";{labels}concat=n={len(wavs)}:v=0:a=1,adelay={delay_ms}:all=1,apad,aresample=24000[a]"
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono"]
        audio = f";[{index}:a]anull[a]"
    cmd += ["-filter_complex", video + audio, "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
            *VIDEO_CODEC, *AUDIO_OPTS, clip]
    run(cmd)
    return total, lines


def user_clip_path(project_id, slug):
    return os.path.join(OUT_DIR, project_id, "clips", f"{slug}.mp4")


def has_audio(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                            "stream=codec_type", "-of", "csv=p=0", path], capture_output=True, text=True)
    return "audio" in probe.stdout


def video_seconds(path):
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                           capture_output=True, text=True)
    return float(probe.stdout.strip())


def make_clip_from_video(src, duration, wavs, clip):
    """Clip một shot từ video do người dùng nhập (đã chuẩn hóa 1280x720, 25 fps).
    Video có sẵn tiếng (giọng nói, tiếng nền do AI video tạo) thì giữ nguyên cả hình lẫn tiếng, không chèn TTS.
    Video không tiếng thì cắt cho vừa thời lượng shot, chỉnh màu chung, ghép giọng thoại của StoryForge."""
    if has_audio(src):
        shutil.copyfile(src, clip)
        return video_seconds(src), []
    lengths = [wav_seconds(w) for w in wavs]
    lines, t = [], LEAD_IN
    for w, length in zip(wavs, lengths):
        lines.append({"file": f"audio/{os.path.basename(w)}", "start": t, "duration": length})
        t += length
    total = max(duration, sum(lengths) + LEAD_IN + TAIL) if wavs else duration
    cmd = ["ffmpeg", "-y", "-i", src]
    video = (f"[0:v]fps={FPS},tpad=stop_mode=clone:stop_duration=20,trim=duration={total:.3f},"
             f"setpts=PTS-STARTPTS,{GRADE},format=yuv420p[v]")
    if wavs:
        for w in wavs:
            cmd += ["-i", w]
        labels = "".join(f"[{1 + k}:a]" for k in range(len(wavs)))
        delay_ms = int(LEAD_IN * 1000)
        audio = f";{labels}concat=n={len(wavs)}:v=0:a=1,adelay={delay_ms}:all=1,apad,aresample=24000[a]"
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono"]
        audio = ";[1:a]anull[a]"
    cmd += ["-filter_complex", video + audio, "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
            *VIDEO_CODEC, *AUDIO_OPTS, clip]
    run(cmd)
    return total, lines


MAX_CLIP_BYTES = 200 * 1024 * 1024


def save_user_clip(handler):
    """Nhận video thô (tải lên trực tiếp), chuẩn hóa về mp4 1280x720 25 fps không tiếng rồi lưu cho shot đó."""
    project_id = handler.headers.get("X-Project", "")
    slug = handler.headers.get("X-Shot", "")
    if not UUID_RE.match(project_id) or not NAME_RE.match(slug):
        raise ValueError("thiếu hoặc sai header X-Project, X-Shot")
    length = int(handler.headers.get("Content-Length", 0))
    if not 0 < length <= MAX_CLIP_BYTES:
        raise ValueError("file rỗng hoặc lớn hơn 200 MB")
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "upload")
        remaining = length
        with open(raw, "wb") as f:
            while remaining > 0:
                chunk = handler.rfile.read(min(1 << 20, remaining))
                if not chunk:
                    raise ValueError("tải lên bị đứt giữa chừng")
                f.write(chunk)
                remaining -= len(chunk)
        return store_clip(raw, project_id, slug)


def store_clip(raw, project_id, slug):
    """Chuẩn hóa một video thô (do người dùng tải lên hoặc do video AI trả về) thành clip 1280x720 25 fps của shot."""
    os.makedirs(os.path.join(OUT_DIR, project_id, "clips"), exist_ok=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height:format=duration", "-of", "json", raw],
                           capture_output=True, text=True)
    try:
        info = json.loads(probe.stdout)
        duration = float(info["format"]["duration"])
        info["streams"][0]
    except (ValueError, KeyError, IndexError):
        raise ValueError("file không phải video đọc được")
    if duration < 0.3:
        raise ValueError("video quá ngắn")
    out = user_clip_path(project_id, slug)
    audio = has_audio(raw)
    run(["ffmpeg", "-y", "-i", raw, "-vf",
         f"scale=1280:720:force_original_aspect_ratio=increase:flags=lanczos,crop=1280:720,fps={FPS}",
         *VIDEO_CODEC, "-crf", "18", *(AUDIO_OPTS if audio else ["-an"]), out])
    return {"file": os.path.relpath(out, OUT_DIR), "duration": round(duration, 2),
            "size_bytes": os.path.getsize(out), "has_audio": audio}


def data_uri(path, mime):
    with open(path, "rb") as f:
        return f"data:{mime};base64," + base64.b64encode(f.read()).decode()


def join_audio(wavs, out):
    """Nối các câu thoại của một shot thành một file wav (shot có một câu thì chỉ cần câu đó)."""
    if len(wavs) == 1:
        return wavs[0]
    cmd = ["ffmpeg", "-y"]
    for w in wavs:
        cmd += ["-i", w]
    cmd += ["-filter_complex", "".join(f"[{i}:a]" for i in range(len(wavs))) + f"concat=n={len(wavs)}:v=0:a=1[a]",
            "-map", "[a]", out]
    run(cmd)
    return out


def make_video(auth, payload):
    """Tạo clip video AI cho một shot từ keyframe của nó. dry_run chỉ tính giá, không gọi dịch vụ nào."""
    project_id, slug, model = payload["project_id"], payload["slug"], payload.get("model", "kling")
    if not NAME_RE.match(slug):
        raise ValueError("slug không hợp lệ")
    if model not in providers.MODELS:
        raise ValueError("model không hỗ trợ: " + model + " (có: " + ", ".join(providers.MODELS) + ")")
    cfg = providers.MODELS[model]
    wavs = shot_audio_files(project_id, slug) if cfg["audio"] == "target" else []
    audio_seconds = sum(wav_seconds(w) for w in wavs)
    seconds = providers.seconds_for(model, payload.get("duration_sec") or 4, audio_seconds)
    image = resolve_output_image(payload["url"], slug)
    motion = (film_info(project_id).get("motions") or {}).get(slug) or "Slow gentle camera push-in, the person breathes and blinks naturally."
    cost = providers.estimate(model, seconds)
    summary = {"slug": slug, "model": model, "label": cfg["label"], "seconds": seconds, "estimate_usd": cost,
               "audio": "target" if wavs else "none"}
    if payload.get("dry_run"):
        return {**summary, "dry_run": True}
    if not auth.startswith("Key "):
        raise ValueError("thiếu header Authorization: Key ... (credential fal.ai trong n8n)")
    if cost > float(payload.get("max_usd", 2.0)):
        raise ValueError(f"shot {slug} ước tính ${cost} vượt mức tối đa cho phép mỗi clip")
    with tempfile.TemporaryDirectory() as tmp:
        audio_uri = data_uri(join_audio(wavs, os.path.join(tmp, "line.wav")), "audio/wav") if wavs else None
        body = providers.build_input(model, data_uri(image, "image/jpeg"), motion, seconds, audio_uri)
        raw = os.path.join(tmp, "ai.mp4")
        with open(raw, "wb") as f:
            f.write(providers.run_model(model, auth, body))
        stored = store_clip(raw, project_id, slug)
    return {**summary, "dry_run": False, "clip": stored}


def render(project_id, shots):
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{project_id}.mp4")
    dialogue_lines = 0
    used_clips = 0
    native_audio = False
    manifest_shots, cursor = [], 0.0
    info = film_info(project_id)
    cameras, outdoor = info.get("cameras", {}), info.get("outdoor", {})
    rainy = "rain" in str(info.get("style", "")).lower() or "mưa" in str(info.get("style", "")).lower()
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
            user_clip = user_clip_path(project_id, slug)
            if os.path.isfile(user_clip):
                total, lines = make_clip_from_video(user_clip, duration, wavs, clip)
                used_clips += 1
                native_audio = native_audio or has_audio(user_clip)
            else:
                total, lines = make_clip(png, duration, wavs, clip, motion_for(cameras.get(slug), i),
                                         rain=rainy and bool(outdoor.get(slug)))
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
        if rainy and not native_audio:
            # Tiếng mưa nền rất nhỏ chạy dưới toàn bộ phim (cả trong nhà, như mưa ngoài cửa).
            noise = f"anoisesrc=color=pink:sample_rate=24000:amplitude=1:duration={cursor:.3f}"
            run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-f", "lavfi", "-i", noise,
                 "-filter_complex",
                 "[1:a]highpass=f=500,lowpass=f=7000,volume=0.12[n];[0:a][n]amix=inputs=2:duration=first:normalize=0[a]",
                 "-map", "0:v", "-map", "[a]", "-c:v", "copy", *AUDIO_OPTS, out_path])
        else:
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
        if self.path == "/prop":
            try:
                return self.reply(200, save_prop(self))
            except (ValueError, OSError) as e:
                return self.reply(400, {"error": str(e)})
        if self.path == "/portrait":
            try:
                return self.reply(200, save_portrait(self))
            except (ValueError, OSError) as e:
                return self.reply(400, {"error": str(e)})
        if self.path == "/clip":
            try:
                return self.reply(200, save_user_clip(self))
            except subprocess.CalledProcessError as e:
                return self.reply(500, {"error": "ffmpeg lỗi khi xử lý video", "detail": (e.stderr or "")[-300:]})
            except (ValueError, OSError) as e:
                return self.reply(400, {"error": str(e)})
        if self.path not in ("/render", "/audio", "/image", "/cf-image", "/video/make", "/director/request",
                             "/director/parse"):
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
            if self.path == "/director/request":
                return self.reply(200, {"body": director.build_request(payload["context"])})
            if self.path == "/director/parse":
                plan = director.parse_plan(payload["context"], payload["gemini"],
                                           payload.get("shot_slug") or None, project_id)
                save_film_info(project_id, plan)
                return self.reply(200, plan)
            if self.path == "/cf-image":
                auth = self.headers.get("Authorization", "")
                if not auth.startswith("Bearer "):
                    return self.reply(401, {"error": "thiếu header Authorization: Bearer ..."})
                name = payload["name"]
                if not NAME_RE.match(name):
                    raise ValueError("name không hợp lệ (chỉ a-z, 0-9, gạch ngang)")
                account_id = str(payload["account_id"])
                if not CF_ACCOUNT_RE.match(account_id):
                    raise ValueError("account_id phải là 32 ký tự a-f, 0-9")
                width, height = int(payload.get("width", 1024)), int(payload.get("height", 576))
                if not (256 <= width <= 1920 and 256 <= height <= 1920):
                    raise ValueError("width và height phải trong khoảng 256 đến 1920")
                prompt = str(payload["prompt"])
                characters = payload.get("characters") or []
                if not isinstance(characters, list):
                    raise ValueError("characters phải là danh sách")
                reference, used = build_reference(project_id, [c for c in characters if isinstance(c, dict)])
                full_prompt = (reference_prefix(used) + prompt) if used else prompt
                try:
                    image = cloudflare_image(auth, account_id, full_prompt[:2000], width, height, reference,
                                             payload.get("seed"))
                except CloudflareError as e:
                    return self.reply(502, {"error": "Cloudflare báo lỗi", "status": e.status, "detail": e.detail})
                path, w, h = save_image(project_id, name, image)
                return self.reply(200, {"file": os.path.relpath(path, OUT_DIR), "width": w, "height": h,
                                        "used": [c.get("slug") for c in used], "meta": payload.get("meta")})
            if self.path == "/video/make":
                try:
                    return self.reply(200, make_video(self.headers.get("Authorization", ""), payload))
                except providers.FalError as e:
                    return self.reply(502, {"error": "fal.ai báo lỗi", "detail": str(e)})
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
