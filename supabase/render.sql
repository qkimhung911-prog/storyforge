-- Dữ liệu cho bước render video. Dán vào Supabase > SQL Editor > Run (chạy sau keyframes.sql).

alter table projects
  add column if not exists video_path text;

-- Danh sách shot đã có keyframe, đúng thứ tự cảnh rồi tới thứ tự shot.
create or replace function get_render_job(pid uuid)
returns jsonb
language sql
stable
as $$
  select coalesce(jsonb_agg(
    jsonb_build_object(
      'slug', sh.slug,
      'duration_sec', sh.duration_sec,
      'url', sh.keyframe_url
    ) order by sc.number, sh.shot_order
  ), '[]'::jsonb)
  from shots sh
  join scenes sc on sc.id = sh.scene_id
  where sh.project_id = pid
    and sh.keyframe_url is not null
    and sh.duration_sec is not null;
$$;

-- Ghi tên file video vào project.
create or replace function set_video(pid uuid, path text)
returns void
language sql
as $$
  update projects set video_path = path where id = pid;
$$;

-- Chỉ service_role (n8n) được gọi.
revoke all on function get_render_job(uuid) from public, anon, authenticated;
revoke all on function set_video(uuid, text) from public, anon, authenticated;
grant execute on function get_render_job(uuid) to service_role;
grant execute on function set_video(uuid, text) to service_role;
