-- Hàm lưu cả kết quả parse (JSON từ Gemini) vào 5 bảng trong một lần.
-- Dán vào Supabase > SQL Editor > Run (chạy sau schema.sql).

create or replace function save_script(payload jsonb)
returns uuid
language plpgsql
as $$
declare
  pid uuid;
begin
  insert into projects (title, genre, overall_tone, target_duration_sec)
  values (
    payload->'project'->>'title',
    payload->'project'->>'genre',
    payload->'project'->>'overall_tone',
    (payload->'project'->>'target_duration_sec')::int
  )
  returning id into pid;

  insert into characters (project_id, slug, name, gender, age, appearance, outfit, accessories, voice)
  select
    pid, t.c->>'id', t.c->>'name', t.c->>'gender', (t.c->>'age')::int,
    t.c->>'appearance', t.c->>'outfit',
    array(select jsonb_array_elements_text(t.c->'accessories')),
    t.c->>'voice'
  from jsonb_array_elements(coalesce(payload->'characters', '[]'::jsonb)) as t(c);

  insert into locations (project_id, slug, name, description, lighting)
  select pid, t.l->>'id', t.l->>'name', t.l->>'description', t.l->>'lighting'
  from jsonb_array_elements(coalesce(payload->'locations', '[]'::jsonb)) as t(l);

  insert into scenes (project_id, slug, number, setting, location_id, time_of_day, mood)
  select
    pid, t.s->>'id', (t.s->>'number')::int, t.s->>'setting',
    (select l.id from locations l where l.project_id = pid and l.slug = t.s->>'location_id'),
    t.s->>'time_of_day', t.s->>'mood'
  from jsonb_array_elements(coalesce(payload->'scenes', '[]'::jsonb)) as t(s);

  insert into shots (project_id, scene_id, slug, shot_order, action, characters, dialogue, camera, duration_sec, status, version)
  select
    pid,
    (select sc.id from scenes sc where sc.project_id = pid and sc.slug = t.sh->>'scene_id'),
    t.sh->>'id', (t.sh->>'order')::int, t.sh->>'action',
    array(select jsonb_array_elements_text(t.sh->'characters')),
    coalesce(t.sh->'dialogue', '[]'::jsonb),
    t.sh->>'camera', (t.sh->>'duration_sec')::int,
    coalesce(t.sh->>'status', 'pending'),
    coalesce((t.sh->>'version')::int, 1)
  from jsonb_array_elements(coalesce(payload->'shots', '[]'::jsonb)) as t(sh);

  return pid;
end;
$$;

-- Chỉ service_role (n8n) được gọi hàm này, anon key thì không.
revoke all on function save_script(jsonb) from public, anon, authenticated;
grant execute on function save_script(jsonb) to service_role;
