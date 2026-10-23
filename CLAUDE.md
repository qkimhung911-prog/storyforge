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
- FFmpeg để ghép video (sau)
- Giao diện web (sau). Thiết kế đã chốt: landing page + 5 trang web, nền sáng, gradient cam hồng tím. Bản phác: https://claude.ai/artifact/RLihgZAfQEGcPwMezK626B

## Tiến độ
Đã xong:
- Repo GitHub qkimhung911-prog/storyforge, Docker và n8n chạy được
- docs/demo-script.md (kịch bản demo Đêm mưa: Minh và Lan, 2 bối cảnh, 3 cảnh)
- docs/schema.md và docs/example-output.json (cấu trúc dữ liệu: project, characters, locations, scenes, shots)
- n8n/01-parse-script.json: workflow webhook, gọi Gemini, trả JSON. Chạy thành công, kết quả thật ở docs/actual-output.json (2 nhân vật, 2 bối cảnh, 3 cảnh, 8 shot)
- Dự án Supabase "storyforge" đã tạo
- supabase/schema.sql đã chạy trên Supabase: 5 bảng projects, characters, locations, scenes, shots (shots có status và version, id chữ lưu ở cột slug, dialogue kiểu jsonb, bật RLS, chưa có policy)

Đang làm: nối n8n với Supabase để tự lưu kết quả (n8n dùng service_role key đặt trong n8n Credentials).

Tiếp theo: sau đó keyframe/ảnh, video, giọng thoại, ghép timeline, giao diện web.

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