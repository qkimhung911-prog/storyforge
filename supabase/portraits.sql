-- Chân dung nhân vật (ảnh tham chiếu để khuôn mặt nhất quán giữa các shot).
-- Dán vào Supabase > SQL Editor > Run (chạy sau shots.sql). Chạy lại nhiều lần vẫn an toàn.

alter table characters add column if not exists portrait_url text;

-- Danh sách nhân vật cần tạo chân dung. char_slug để trống thì lấy cả project.
create or replace function get_character_jobs(pid uuid, char_slug text default null)
returns jsonb
language sql
stable
as $$
  select coalesce(jsonb_agg(
    jsonb_build_object(
      'id', c.id,
      'slug', c.slug,
      'name', c.name,
      'gender', c.gender,
      'age', c.age,
      'appearance', c.appearance,
      'outfit', c.outfit,
      'accessories', c.accessories
    ) order by c.name
  ), '[]'::jsonb)
  from characters c
  where c.project_id = pid and (char_slug is null or c.slug = char_slug);
$$;

-- Ghi đường dẫn chân dung cho một nhân vật.
create or replace function set_portrait(cid uuid, url text)
returns void
language sql
as $$
  update characters set portrait_url = url where id = cid;
$$;

-- Chỉ service_role (n8n) được gọi.
revoke all on function get_character_jobs(uuid, text) from public, anon, authenticated;
revoke all on function set_portrait(uuid, text) from public, anon, authenticated;
grant execute on function get_character_jobs(uuid, text) to service_role;
grant execute on function set_portrait(uuid, text) to service_role;
