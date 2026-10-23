-- Danh sách câu thoại cho bước giọng thoại. Dán vào Supabase > SQL Editor > Run (chạy sau render.sql).

-- Mỗi câu thoại kèm shot, thứ tự trong shot, và thông tin giọng của nhân vật (Asset Bible).
create or replace function get_dialogue_jobs(pid uuid)
returns jsonb
language sql
stable
as $$
  select coalesce(jsonb_agg(
    jsonb_build_object(
      'shot_slug', sh.slug,
      'idx', d.ord - 1,
      'character_slug', d.value->>'character_id',
      'name', c.name,
      'gender', c.gender,
      'voice', c.voice,
      'line', d.value->>'line'
    ) order by sc.number, sh.shot_order, d.ord
  ), '[]'::jsonb)
  from shots sh
  join scenes sc on sc.id = sh.scene_id
  cross join lateral jsonb_array_elements(sh.dialogue) with ordinality as d(value, ord)
  left join characters c
    on c.project_id = sh.project_id and c.slug = d.value->>'character_id'
  where sh.project_id = pid;
$$;

-- Chỉ service_role (n8n) được gọi.
revoke all on function get_dialogue_jobs(uuid) from public, anon, authenticated;
grant execute on function get_dialogue_jobs(uuid) to service_role;
