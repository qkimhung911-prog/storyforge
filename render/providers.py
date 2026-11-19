"""Nhà cung cấp video AI (adapter). Mỗi model là một mục trong MODELS: endpoint, cách dựng yêu cầu, giá tham khảo.
Chỉ gọi được các model liệt kê ở đây (không nhận endpoint tùy ý). Khóa fal.ai đến từ header Authorization do n8n gắn
từ credential; mô-đun này chỉ chuyển tiếp, không lưu và không ghi nhật ký.

Giá (USD mỗi giây video) lấy từ trang model trên fal.ai ngày 12/11/2026, cần đối chiếu lại trước khi tiêu tiền thật."""
import json
import os
import time
import urllib.error
import urllib.request

FAL_QUEUE = os.environ.get("FAL_QUEUE_URL", "https://queue.fal.run").rstrip("/")
MAX_SECONDS = 15
POLL_EVERY = 4
MAX_WAIT = 900
MAX_DOWNLOAD = 200 * 1024 * 1024

# audio: "none" = video im lặng (StoryForge chèn giọng TTS tiếng Việt),
#        "target" = đưa file giọng TTS cho model làm tiếng của clip (thử xem môi có khớp không).
# Kling v3 chỉ nói tiếng Anh và tiếng Trung tự nhiên (ngôn ngữ khác bị dịch sang tiếng Anh) nên không dùng tiếng của Kling.
MODELS = {
    "kling": {"endpoint": "fal-ai/kling-video/v3/standard/image-to-video", "price": 0.084, "audio": "none",
              "min_s": 3, "label": "Kling v3 Standard (im lặng)"},
    "kling-pro": {"endpoint": "fal-ai/kling-video/v3/pro/image-to-video", "price": 0.112, "audio": "none",
                  "min_s": 3, "label": "Kling v3 Pro (im lặng)"},
    "h3max": {"endpoint": "minimax/h3-max/image-to-video", "price": 0.08, "audio": "target",
              "min_s": 2, "label": "MiniMax H3 Max (tiếng TTS)"},
}


class FalError(Exception):
    pass


def seconds_for(model, shot_seconds, audio_seconds):
    """Thời lượng clip yêu cầu: đủ cho shot và cho câu thoại, kẹp trong giới hạn của model."""
    need = max(float(shot_seconds), audio_seconds + 0.6 if audio_seconds else 0)
    return int(min(MAX_SECONDS, max(MODELS[model]["min_s"], round(need + 0.49))))


def estimate(model, seconds):
    return round(MODELS[model]["price"] * seconds, 3)


def build_input(model, image_uri, motion, seconds, audio_uri=None):
    """Dựng body yêu cầu theo đúng tên trường trong tài liệu fal.ai của từng model."""
    prompt = (f"{motion.strip()} Photorealistic, natural realistic motion, consistent face and clothing, "
              "no text, no subtitles, no logos.")
    if model in ("kling", "kling-pro"):
        return {"start_image_url": image_uri, "prompt": prompt, "duration": str(seconds), "generate_audio": False,
                "negative_prompt": "blur, distort, low quality, text, subtitles, extra fingers, deformed face"}
    if model == "h3max":
        body = {"prompt": prompt + (" The person's lips move naturally in sync with the speech." if audio_uri else ""),
                "image_url": image_uri, "duration": float(seconds), "resolution": "768P",
                "prompt_expansion_mode": "balanced"}
        if audio_uri:
            body["target_audio_url"] = audio_uri
        return body
    raise FalError("model không được hỗ trợ: " + model)


def _call(method, url, auth, body=None, timeout=60):
    if not url.startswith(FAL_QUEUE + "/"):
        raise FalError("địa chỉ phản hồi không thuộc fal.ai, dừng để bảo vệ khóa")
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": auth, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise FalError(f"fal.ai báo lỗi {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")
    except urllib.error.URLError as e:
        raise FalError(f"không nối được fal.ai: {e.reason}")


def run_model(model, auth, body):
    """Gửi vào hàng đợi fal.ai, chờ xong, tải video về. Trả về bytes của file mp4."""
    submit = _call("POST", f"{FAL_QUEUE}/{MODELS[model]['endpoint']}", auth, body)
    for key in ("request_id", "status_url", "response_url"):
        if key not in submit:
            raise FalError("fal.ai không trả " + key)
    deadline = time.time() + MAX_WAIT
    while True:
        status = _call("GET", submit["status_url"], auth)
        state = status.get("status")
        if state == "COMPLETED":
            if status.get("error"):
                raise FalError("fal.ai báo lỗi khi tạo video: " + str(status.get("error"))[:300])
            break
        if state not in ("IN_QUEUE", "IN_PROGRESS"):
            raise FalError("trạng thái lạ từ fal.ai: " + str(state))
        if time.time() > deadline:
            raise FalError("chờ quá lâu, fal.ai chưa tạo xong video")
        time.sleep(POLL_EVERY)
    result = _call("GET", submit["response_url"], auth, timeout=120)
    video_url = (result.get("video") or {}).get("url")
    if not video_url:
        raise FalError("kết quả không có video.url")
    # File video nằm trên CDN của fal.ai, tải về không cần khóa.
    with urllib.request.urlopen(urllib.request.Request(video_url), timeout=180) as resp:
        data = resp.read(MAX_DOWNLOAD + 1)
    if not data or len(data) > MAX_DOWNLOAD:
        raise FalError("file video rỗng hoặc quá lớn")
    return data
