-- Keyframe cho từng shot. Dán vào Supabase > SQL Editor > Run (chạy sau save_script.sql).

alter table shots
  add column if not exists keyframe_prompt text,
  add column if not exists keyframe_url text;

-- Gom mỗi shot cùng nhân vật và bối cảnh liên quan (Asset Bible) thành một "job" để n8n dựng prompt.
create or replace function get_keyframe_jobs(pid uuid)
returns jsonb
language sql
stable
as $$
  select coalesce(jsonb_agg(t.job order by t.scene_number, t.shot_order), '[]'::jsonb)
  from (
    select
      sc.number as scene_number,
      sh.shot_order as shot_order,
      jsonb_build_object(
        'shot_id', sh.id,
        'slug', sh.slug,
        'camera', sh.camera,
        'action', sh.action,
        'setting', sc.setting,
        'time_of_day', sc.time_of_day,
        'mood', sc.mood,
        'location', jsonb_build_object(
          'name', l.name,
          'description', l.description,
          'lighting', l.lighting
        ),
        'characters', coalesce((
          select jsonb_agg(jsonb_build_object(
            'slug', c.slug,
            'name', c.name,
            'gender', c.gender,
            'age', c.age,
            'appearance', c.appearance,
            'outfit', c.outfit,
            'accessories', c.accessories
          ))
          from characters c
          where c.project_id = sh.project_id and c.slug = any(sh.characters)
        ), '[]'::jsonb)
      ) as job
    from shots sh
    join scenes sc on sc.id = sh.scene_id
    left join locations l on l.id = sc.location_id
    where sh.project_id = pid
  ) t;
$$;

-- Ghi prompt và ảnh vào một shot.
create or replace function set_keyframe(sid uuid, prompt text, url text)
returns void
language sql
as $$
  update shots set keyframe_prompt = prompt, keyframe_url = url where id = sid;
$$;

-- Chỉ service_role (n8n) được gọi.
revoke all on function get_keyframe_jobs(uuid) from public, anon, authenticated;
revoke all on function set_keyframe(uuid, text, text) from public, anon, authenticated;
grant execute on function get_keyframe_jobs(uuid) to service_role;
grant execute on function set_keyframe(uuid, text, text) to service_role;
