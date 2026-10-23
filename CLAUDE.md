# StoryForge: hướng dẫn cho Claude Code

## Về người dùng
- Tên: Jake. Là người mới, chưa biết code (vibe coder). Luôn trả lời bằng tiếng Việt, ngắn gọn, từng bước một, nói rõ mở app nào, bấm gì, gõ gì.
- Máy: MacBook Air M4 (macOS). Mỗi lần chỉ làm một việc, chạy được rồi mới sang việc kế.
- Trước khi sửa nhiều file hoặc chạy lệnh lạ, giải thích ngắn bạn sắp làm gì.

## Dự án
StoryForge: người dùng dán kịch bản (cảnh, nhân vật, thoại, mood), hệ thống tự động tạo video AI chỉnh sửa được. Điều phối bằng n8n. Đây là dự án portfolio để xin việc, ưu tiên MIỄN PHÍ (chế độ mock/free trước, dịch vụ trả phí như Higgsfield để sau, cắm qua lớp adapter).

Ý tưởng cốt lõi: tách "Asset Bible" (nhân vật, bối cảnh, phụ kiện đã khóa) khỏi "Shot". Mỗi shot là một đối tượng độc lập có status (pending, approved, failed) và version để tạo lại riêng từng shot.

## Stack
- n8n chạy bằng Docker (localhost:5678)
- Gemini API free tier (model gemini-3.8-flash), key nằm trong n8n Credentials
- Supabase free (Postgres, khu vực Tokyo)
- FFmpeg để ghép video, chạy trong container render (thư mục render/)
- Giao diện web: HTML/CSS/JS thuần (không Node, không build), phục vụ bằng container nginx "storyforge-web" tại http://localhost:8080 (thư mục web/, cấu hình nginx/default.conf). Thiết kế đã chốt: landing page + 5 trang web, nền sáng, gradient cam hồng tím. Bản phác: https://claude.ai/artifact/RLihgZAfQEGcPwMezK626B

## Tiến độ
Đã xong:
- Repo GitHub qkimhung911-prog/storyforge, Docker và n8n chạy được
- docs/demo-script.md (kịch bản demo Đêm mưa: Minh và Lan, 2 bối cảnh, 3 cảnh)
- docs/schema.md và docs/example-output.json (cấu trúc dữ liệu: project, characters, locations, scenes, shots)
- n8n/01-parse-script.json: workflow webhook, gọi Gemini, trả JSON. Chạy thành công, kết quả thật ở docs/actual-output.json (2 nhân vật, 2 bối cảnh, 3 cảnh, 8 shot)
- Dự án Supabase "storyforge" đã tạo
- supabase/schema.sql đã chạy trên Supabase: 5 bảng projects, characters, locations, scenes, shots (shots có status và version, id chữ lưu ở cột slug, dialogue kiểu jsonb, bật RLS, chưa có policy)
- supabase/save_script.sql: hàm save_script(payload jsonb) lưu cả JSON parse vào 5 bảng trong một lần (chỉ service_role gọi được). Workflow n8n có thêm node "Lưu vào Supabase" gọi hàm này qua REST (credential Supabase API trong n8n); đã lưu thử kịch bản Đêm Mưa đủ 1 project, 2 nhân vật, 2 bối cảnh, 3 cảnh, 8 shot

- Workflow 01 đã chạy thử trọn vẹn từ webhook tới "Trả kết quả" (6 node xanh, trả JSON kèm project_id, dữ liệu vào đủ 5 bảng). Webhook mới chạy ở chế độ test (bấm Execute workflow trước); chưa Publish

- supabase/keyframes.sql: thêm cột keyframe_prompt, keyframe_url cho shots và hai hàm get_keyframe_jobs, set_keyframe (chỉ service_role gọi được)
- n8n/02-keyframes.json: workflow keyframe mock. Nhận project_id, lấy shot cùng nhân vật và bối cảnh, dựng prompt từ Asset Bible, node adapter "Chọn nhà cung cấp ảnh" (provider = mock) vẽ ảnh SVG gradient lưu thẳng vào keyframe_url (data URI), trả tóm tắt. Đã chạy thử trên Đêm Mưa, mọi shot có prompt và ảnh. Nhánh false của adapter để trống, chờ cắm dịch vụ ảnh thật

- render/: dịch vụ render chạy trong container riêng "storyforge-render" (Alpine + FFmpeg + rsvg-convert + font-dejavu, server Python nhỏ, cổng 8000). Nhận danh sách keyframe SVG và duration_sec, làm mỗi shot thành clip rồi ghép thành mp4 trong thư mục output/ (đã .gitignore). Mỗi lần render còn ghi output/<project_id>.json (bản ghi thời gian: từng shot bắt đầu giây nào, dài bao lâu, từng câu thoại ở giây nào) cho trang Timeline; video render trước khi có tính năng này phải render lại một lần. Sửa render/ thì chạy lại: docker compose up -d --build render
- supabase/render.sql: cột projects.video_path và hai hàm get_render_job, set_video (chỉ service_role gọi được)
- n8n/03-render.json: workflow render video. Nhận project_id, lấy shot đúng thứ tự cảnh, gọi http://render:8000/render, lưu video_path. Đã chạy thử trên Đêm Mưa: 7 shot, mp4 1280x720 dài 31 giây, chưa có tiếng và chưa có phụ đề

- Giọng thoại (TTS) bằng Gemini TTS (model gemini-3.8-flash-tts, miễn phí ở gói free): supabase/dialogue.sql (hàm get_dialogue_jobs), n8n/04-tts-test.json (thử một câu), n8n/05-tts.json (mọi câu thoại; giọng chọn theo giới tính: nam Charon, nữ Leda; phong cách nói lấy từ cột voice của nhân vật; mỗi câu lưu thành output/<project_id>/audio/<slug-shot>-<số>.wav qua cổng /audio của container render). render/server.py tự tìm file thoại theo slug shot, ghép vào clip (kéo dài clip nếu câu thoại dài hơn shot, shot không thoại thì im lặng). Đã chạy thử trên Đêm Mưa: 5 câu thoại, video 31,6 giây có tiếng, nghe đạt

- web/index.html + web/styles.css: Landing đúng thiết kế đã chốt (nền kem, gradient cam hồng tím, nút viên thuốc đen, font Bricolage Grotesque và Space Mono). Container web gắn ./web chỉ-đọc, ./output ở /srv/output (nginx phục vụ /output/ cho video và file thoại). Bật: docker compose up -d web. Đã xem lại bản máy tính và điện thoại

Đang làm: giao diện web theo 6 bước: (1) khung và Landing: xong; (2) cho trình duyệt đọc dữ liệu Supabase bằng khóa công khai + RLS chỉ-đọc: xong (supabase/web-read.sql, web/kiem-tra.html báo 5 bảng đọc được); (3) trang Bible và Storyboard: xong (web/app.js dùng chung đọc Supabase và dựng banner + thanh 5 bước, web/bible.html, web/storyboard.html; hiển thị dữ liệu thật, chưa có nút Duyệt/Sinh lại và chưa có trạng thái khóa vì DB chưa có cột đó); (4) trang Timeline phát video thật: xong (web/timeline.html: trình phát, làn Hình và làn Thoại bấm để nhảy, vạch chạy theo video, danh sách thoại, nút Tải MP4; làn Nhạc, Phụ đề và nút OTIO ghi "Sắp có" vì chưa làm); (5) trang Tiến trình và Kịch bản: xong (web/kich-ban.html dán kịch bản hoặc dùng docs/demo-script.md qua nút mẫu, gọi /api/storyforge-parse; web/tien-trinh.html có 3 thẻ giai đoạn Keyframe, Giọng thoại, Render video chạy bằng nút, đếm số file thoại thật bằng HEAD, bảng từng shot, nhật ký phiên; workflow 01, 02, 03, 05 đã Publish; nginx chuyển tiếp /api/storyforge-parse, -keyframes, -tts, -render tới webhook production của n8n, chỉ đúng 4 địa chỉ này; n8n giờ chỉ nghe 127.0.0.1:5678); (6) nút Duyệt và Sinh lại từng shot (tăng version).

Quy ước n8n: sửa workflow rồi phải bấm Publish lại thì webhook production (/webhook/...) mới nhận bản mới; bản test (/webhook-test/...) chỉ chạy khi bấm Execute workflow. File n8n/*.json trong repo là bản ghi lại, import vào n8n sẽ mất credential và model_id nên chỉ import workflow mới. Workflow 03 trả về project_id, video, shots, size_bytes (không có dialogue_lines).

Quy ước web: trình duyệt chỉ dùng khóa công khai (anon/publishable) của Supabase, đặt trong web/config.js (bị .gitignore, mẫu ở web/config.example.js). Tuyệt đối không đặt service_role hay secret key trong web/. Ghi dữ liệu đi qua n8n. Khóa dạng eyJ (legacy anon) gửi cả header apikey và Authorization; khóa sb_publishable_ chỉ gửi apikey. nginx đặt Cache-Control no-cache nên sửa file web là thấy ngay; nếu trình duyệt vẫn hiện bản cũ thì nạp lại cứng bằng Cmd+Shift+R. Các đường dẫn styles.css và app.js trong HTML có ?v=2: sửa các file này thì tăng số ?v= trong mọi trang HTML (trình duyệt hay giữ bản cũ). Sửa nginx/default.conf thì phải chạy docker compose up -d --force-recreate web (nạp lại bằng nginx -s reload có thể đọc nhầm file dở dang).

Hạn mức Gemini TTS (gemini-3.8-flash-tts, gói free): 3 yêu cầu mỗi phút VÀ 10 yêu cầu mỗi ngày cho mỗi model (hồi lại lúc nửa đêm giờ Mỹ, khoảng 14 giờ chiều giờ Việt Nam). Mỗi lần tạo giọng cho kịch bản 5 câu tốn 5 yêu cầu, kể cả lần chạy bị chặn giữa chừng. Workflow 05 để batchInterval 30000 ms giữa các câu. Hết hạn mức thì chờ hoặc thử model khác (hạn mức tính riêng từng model, ví dụ gemini-3.8-flash-lite-tts). Việc cần cải thiện: workflow 05 nên bỏ qua câu đã có file và lưu từng câu ngay khi xong (hiện phải xong cả 5 câu mới lưu).

Workflow 01 đang chạy trong n8n trả {"data": "<mã project>"} (không phải JSON đầy đủ như file n8n/01-parse-script.json); web/kich-ban.html nhận cả hai dạng và tự đếm số nhân vật, cảnh, shot từ Supabase. Xem chi tiết một lần chạy workflow khi tab Executions không đủ rõ: docker exec storyforge-n8n node đọc /home/node/.n8n/database.sqlite (bảng execution_entity, execution_data, dùng node:sqlite và module flatted trong n8n).

Lưu ý: Gemini free tier đôi khi treo (timeout 120s); thử lại hoặc đổi model_id (ví dụ gemini-3.5-flash-lite). Mỗi lần chạy workflow tạo thêm một project mới trong Supabase. Gemini TTS gọi qua API interactions (POST /v1beta/interactions), không phải generateContent; hạn mức free của TTS chưa rõ nên chạy cách nhau vài giây. Thứ tự tạo video: workflow 01 (parse) -> 02 (keyframe) -> 05 (giọng thoại) -> 03 (render).

Tiếp theo: phụ đề, ảnh AI thật (cắm vào nhánh trống của adapter trong workflow 02).

## Quy tắc an toàn (bắt buộc)
- Không bao giờ ghi API key, secret key hay mật khẩu vào file trong repo. Không đọc file .env. Không in key ra màn hình. Key chỉ nằm trong n8n Credentials.
- Không commit, push hoặc xóa file khi chưa hỏi Jake.
- Không dùng ANTHROPIC_API_KEY (Jake dùng gói Claude Pro, không dùng API).
- Luôn tạo file đúng từ thư mục gốc của repo, tránh lỗi lồng thư mục kiểu docs/docs.

## Cấu trúc thư mục
- docker-compose.yml
- docs/ (kịch bản, schema, kết quả mẫu)
- n8n/ (workflow xuất ra JSON)
- supabase/ (SQL)
- render/ (dịch vụ render video bằng FFmpeg, chạy trong Docker)
- output/ (video xuất ra, không commit)
- web/ (giao diện web tĩnh: HTML, CSS, JS)
- nginx/ (cấu hình nginx cho container web)