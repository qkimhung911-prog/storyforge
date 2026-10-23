# Cấu trúc dữ liệu (schema) của StoryForge

Một kịch bản sau khi được phân tích sẽ thành một đối tượng JSON gồm 5 phần.

## 5 phần chính

- project: thông tin chung (title, genre, overall_tone, target_duration_sec)
- characters: danh sách nhân vật. Mỗi người có id, name, gender, age, appearance, outfit, accessories, voice
- locations: danh sách bối cảnh. Mỗi nơi có id, name, description, lighting
- scenes: danh sách cảnh. Mỗi cảnh có id, number, setting (NỘI hoặc NGOẠI), location_id, time_of_day, mood
- shots: danh sách shot. Mỗi shot có id, scene_id, order, action, characters, dialogue, camera, duration_sec, status, version

## Quy tắc

- id viết thường, không dấu, nối bằng gạch ngang
- characters trong shot và location_id trong scene chỉ được trỏ tới id đã có
- camera: wide, medium, close-up, insert, two-shot
- status: pending, approved, failed
- version bắt đầu từ 1, mỗi lần tạo lại một shot thì tăng thêm 1

## Vì sao thiết kế như vậy

Nhân vật và bối cảnh (phần Bible) được tách khỏi shot. Ta khóa nhân vật và bối cảnh trước, rồi mỗi shot chỉ được dùng những thứ đã khóa. Mỗi shot là một đối tượng độc lập có trạng thái và phiên bản, nên có thể tạo lại riêng từng shot mà không phải làm lại cả phim.

File example-output.json là kết quả mẫu cho kịch bản demo (docs/demo-script.md).