"""Đạo diễn: soạn yêu cầu cho Gemini và ghép prompt cuối cho từng shot từ ghi chú của Gemini.
Toàn bộ logic prompt nằm ở đây (không nằm trong n8n) để chỉnh và build lại dễ dàng."""
import json

SYSTEM = (
    "You are the director and cinematographer of a short film, and you write image prompts for a text-to-image model (FLUX). "
    "The user message is JSON describing the whole film: project (title, genre, tone, optional style_guide), characters, "
    "and scenes with their shots in story order (camera, action, dialogue, characters present). "
    "Reply with ONLY one JSON object: "
    '{"style_guide": string, "characters": {slug: string}, "scenes": {scene_slug: string}, "shots": {shot_slug: string}, "motions": {shot_slug: string}}. '
    "Rules. "
    "(1) style_guide, 40 to 60 words: ONE look for the whole film: name 3 or 4 concrete colors of the palette, the quality of light, "
    "the time of day and weather that apply to the whole film, the film stock and lens look, grain and mood. "
    "If the project already has a style_guide, return it unchanged. "
    "(2) characters, 25 to 40 words each: a compact English visual description (age, gender, Vietnamese, hair, glasses, outfit, accessories) "
    "using exactly the items given. If a character has fixed_description, return it unchanged. "
    "(3) scenes, 35 to 55 words each: the physical set of the scene: layout, key furniture, windows, props, light sources and what is visible "
    "behind the people, consistent with the style_guide's time of day and weather. If a scene has fixed_set, return it unchanged. "
    "(4) shots, 45 to 80 words each: camera framing (wide, medium, close-up, insert, two-shot); who is where in the frame "
    "(left, right, foreground, background); where each person looks (people talking to each other look at each other, not at the camera); "
    "facial expression and body language that match the dialogue and the mood; the action. The picture must serve what is being said in that shot: "
    "if a character speaks about an object or a detail (for example a bracelet), show that character glancing at or reaching toward it, and keep the "
    "object visible and recognizable in the frame; the speaker's gaze and expression must fit the line (a curious question is not a romantic smile). "
    "Refer to people by name only because their full "
    "descriptions are added automatically. Do not repeat the style or the set. Keep story continuity with the previous shot: same positions "
    "unless the action moves people. For an insert shot show only the detail (for example a hand), no face. "
    "No text, captions, logos or signs in any image. "
    "(5) motions, 25 to 45 words each: for EVERY shot, an English prompt for an image-to-video model that animates the still image of that shot "
    "over about 5 seconds: one simple camera move (slow push-in, slow pull-out, gentle pan, static), the natural small movements of the people "
    "(blinking, breathing, a slow head turn, a hand gesture), and ambient motion (rain falling, steam rising, lights flickering). "
    "If someone speaks in that shot, say that their lips move naturally as they speak. Describe only motion, not appearance. Keep it realistic and subtle."
)


def build_request(context):
    """Trả về body yêu cầu gửi cho Gemini (generateContent)."""
    project = context.get("project") or {}
    payload = {
        "project": {"title": project.get("title"), "genre": project.get("genre"), "tone": project.get("tone"),
                    "style_guide": project.get("style_prompt")},
        "characters": [
            {"slug": c["slug"], "name": c["name"], "gender": c.get("gender"), "age": c.get("age"),
             "appearance": c.get("appearance"), "outfit": c.get("outfit"), "accessories": c.get("accessories"),
             "fixed_description": c.get("desc_en")}
            for c in context.get("characters", [])
        ],
        "scenes": [
            {"slug": sc["slug"], "number": sc.get("number"), "setting": sc.get("setting"),
             "time_of_day": sc.get("time_of_day"), "mood": sc.get("mood"), "location": sc.get("location"),
             "fixed_set": sc.get("set_prompt"),
             "shots": [
                 {"slug": sh["slug"], "camera": sh.get("camera"), "action": sh.get("action"),
                  "dialogue": sh.get("dialogue") or [], "characters": sh.get("characters") or []}
                 for sh in sc.get("shots", [])
             ]}
            for sc in context.get("scenes", [])
        ],
    }
    return {
        "system_instruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
    }


def _gemini_text(gemini):
    parts = gemini["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def project_seed(context, project_id):
    """Một seed chung cho cả phim, suy ra từ mã project, để các shot cùng "tông" nhiễu."""
    return int(str(project_id).replace("-", "")[:8], 16) % 2_000_000_000


def _has_glasses(character, desc):
    text = " ".join(str(x) for x in (character.get("appearance"), character.get("accessories"),
                                     character.get("outfit"), desc) if x).lower()
    return "kính" in text or "glasses" in text


def _person(p, any_glasses):
    """Mô tả một nhân vật trong shot, kèm tuổi cụ thể và nói rõ ai KHÔNG đeo kính
    (nếu không, mô hình ảnh hay chép kính của người này sang người kia)."""
    parts = [f"{p['name']}: {p['desc']}"]
    if p.get("age"):
        parts.append(f"{p['name']} looks exactly {p['age']} years old, not older.")
    if any_glasses and not p["glasses"]:
        parts.append(f"{p['name']} does not wear glasses.")
    return " ".join(parts)


def parse_plan(context, gemini, only_slug=None, project_id=""):
    """Đọc ghi chú của Gemini, ưu tiên giá trị đã lưu (không cho trôi), rồi ghép prompt cuối cho từng shot."""
    text = _gemini_text(gemini)
    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError("Gemini trả về JSON không hợp lệ: " + text[:300])

    project = context.get("project") or {}
    style = project.get("style_prompt") or plan.get("style_guide")
    if not style:
        raise ValueError("Gemini không viết quy chuẩn hình ảnh (style_guide)")

    chars = {}
    for c in context.get("characters", []):
        desc = c.get("desc_en") or (plan.get("characters") or {}).get(c["slug"])
        if not desc:
            raise ValueError("Gemini không mô tả nhân vật " + c["slug"])
        chars[c["slug"]] = {"name": c["name"], "gender": c.get("gender"), "age": c.get("age"), "desc": str(desc),
                            "glasses": _has_glasses(c, desc)}
    any_glasses = any(c["glasses"] for c in chars.values())

    motions = {}
    sets, shots = {}, []
    for sc in context.get("scenes", []):
        set_text = sc.get("set_prompt") or (plan.get("scenes") or {}).get(sc["slug"])
        if not set_text:
            raise ValueError("Gemini không mô tả bối cảnh cảnh " + sc["slug"])
        sets[sc["slug"]] = str(set_text)
        for sh in sc.get("shots", []):
            if only_slug and sh["slug"] != only_slug:
                continue
            body = (plan.get("shots") or {}).get(sh["slug"])
            if not body:
                raise ValueError("Gemini không dàn cảnh shot " + sh["slug"])
            present = [chars[s] for s in sorted(sh.get("characters") or []) if s in chars]
            insert = sh.get("camera") == "insert"
            people = "" if insert or not present else " Characters: " + " ".join(
                _person(p, any_glasses) for p in present)
            prompt = (f"{str(body).strip()}{people} Setting: {sets[sc['slug']]} "
                      f"Visual style, identical in every shot of the film: {str(style).strip()} "
                      "Photorealistic cinematic film still, natural skin texture, no text or logos.")
            motion = (plan.get("motions") or {}).get(sh["slug"])
            if not motion:
                raise ValueError("Gemini không viết mô tả chuyển động cho shot " + sh["slug"])
            motions[sh["slug"]] = str(motion).strip()
            shots.append({
                "shot_id": sh["id"], "slug": sh["slug"], "version": sh.get("version") or 1, "camera": sh.get("camera"),
                "prompt": prompt,
                "characters": [] if insert else [
                    {"slug": s, "name": chars[s]["name"], "gender": chars[s]["gender"]}
                    for s in sorted(sh.get("characters") or []) if s in chars],
            })
    if only_slug and not shots:
        raise ValueError("Không thấy shot " + only_slug)
    cameras = {sh["slug"]: sh.get("camera") for sc in context.get("scenes", []) for sh in sc.get("shots", [])}
    outdoor = {sh["slug"]: str(sc.get("setting", "")).upper().startswith(("NGO", "EXT"))
               for sc in context.get("scenes", []) for sh in sc.get("shots", [])}
    return {
        "motions": motions,
        "cameras": cameras,
        "outdoor": outdoor,
        "notes": {"style": style, "scenes": sets, "characters": {k: v["desc"] for k, v in chars.items()}},
        "seed": project_seed(context, project_id),
        "shots": shots,
    }
