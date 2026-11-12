-- "Đạo diễn": ghi chú hình ảnh dùng chung cho cả phim (quy chuẩn màu, bố cục từng cảnh, mô tả nhân vật).
-- Dán vào Supabase > SQL Editor > Run (chạy sau portraits.sql). Chạy lại nhiều lần vẫn an toàn.

alter table projects add column if not exists style_prompt text;
alter table scenes add column if not exists set_prompt text;
alter table characters add column if not exists desc_en text;

-- Toàn bộ dữ liệu một phim, theo thứ tự cảnh và shot, để đạo diễn (Gemini) đọc một lần.
create or replace function get_film_context(pid uuid)
returns jsonb
language sql
stable
as $$
  select jsonb_build_object(
    'project', (select jsonb_build_object('title', p.title, 'genre', p.genre, 'tone', p.overall_tone,
                                           'style_prompt', p.style_prompt)
                from projects p where p.id = pid),
    'characters', coalesce((select jsonb_agg(jsonb_build_object(
        'slug', c.slug, 'name', c.name, 'gender', c.gender, 'age', c.age, 'appearance', c.appearance,
        'outfit', c.outfit, 'accessories', c.accessories, 'desc_en', c.desc_en,
        'has_portrait', c.portrait_url is not null) order by c.name)
      from characters c where c.project_id = pid), '[]'::jsonb),
    'scenes', coalesce((select jsonb_agg(jsonb_build_object(
        'slug', sc.slug, 'number', sc.number, 'setting', sc.setting, 'time_of_day', sc.time_of_day,
        'mood', sc.mood, 'set_prompt', sc.set_prompt,
        'location', (select jsonb_build_object('name', l.name, 'description', l.description, 'lighting', l.lighting)
                     from locations l where l.id = sc.location_id),
        'shots', coalesce((select jsonb_agg(jsonb_build_object(
            'id', sh.id, 'slug', sh.slug, 'order', sh.shot_order, 'camera', sh.camera, 'action', sh.action,
            'dialogue', sh.dialogue, 'characters', sh.characters, 'duration_sec', sh.duration_sec,
            'version', sh.version) order by sh.shot_order)
          from shots sh where sh.scene_id = sc.id), '[]'::jsonb)
      ) order by sc.number)
      from scenes sc where sc.project_id = pid), '[]'::jsonb)
  );
$$;

-- Lưu ghi chú đạo diễn: quy chuẩn hình ảnh của phim, mô tả bối cảnh từng cảnh, mô tả nhân vật tiếng Anh.
-- scenes_json dạng {"s1": "mô tả bối cảnh", ...}, characters_json dạng {"minh": "mô tả", ...}.
create or replace function save_film_notes(pid uuid, style text, scenes_json jsonb, characters_json jsonb)
returns void
language plpgsql
as $$
declare
  k text;
begin
  if style is not null then
    update projects set style_prompt = style where id = pid;
  end if;
  for k in select jsonb_object_keys(coalesce(scenes_json, '{}'::jsonb)) loop
    update scenes set set_prompt = scenes_json ->> k where project_id = pid and slug = k;
  end loop;
  for k in select jsonb_object_keys(coalesce(characters_json, '{}'::jsonb)) loop
    update characters set desc_en = characters_json ->> k where project_id = pid and slug = k;
  end loop;
end;
$$;

-- Chỉ service_role (n8n) được gọi.
revoke all on function get_film_context(uuid) from public, anon, authenticated;
revoke all on function save_film_notes(uuid, text, jsonb, jsonb) from public, anon, authenticated;
grant execute on function get_film_context(uuid) to service_role;
grant execute on function save_film_notes(uuid, text, jsonb, jsonb) to service_role;
