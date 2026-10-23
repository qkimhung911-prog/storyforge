-- Duyệt và sinh lại từng shot. Dán vào Supabase > SQL Editor > Run (chạy sau web-read.sql).
-- Chạy lại nhiều lần vẫn an toàn.

-- Dữ liệu của MỘT shot (cùng cấu trúc get_keyframe_jobs, thêm version), dùng khi sinh lại keyframe.
create or replace function get_shot_job(pid uuid, shot_slug text)
returns jsonb
language sql
stable
as $$
  select coalesce(jsonb_agg(
    jsonb_build_object(
      'shot_id', sh.id,
      'slug', sh.slug,
      'version', sh.version,
      'camera', sh.camera,
      'action', sh.action,
      'setting', sc.setting,
      'time_of_day', sc.time_of_day,
      'mood', sc.mood,
      'location', jsonb_build_object('name', l.name, 'description', l.description, 'lighting', l.lighting),
      'characters', coalesce((
        select jsonb_agg(jsonb_build_object(
          'slug', c.slug, 'name', c.name, 'gender', c.gender, 'age', c.age,
          'appearance', c.appearance, 'outfit', c.outfit, 'accessories', c.accessories))
        from characters c
        where c.project_id = sh.project_id and c.slug = any(sh.characters)
      ), '[]'::jsonb)
    )
  ), '[]'::jsonb)
  from shots sh
  join scenes sc on sc.id = sh.scene_id
  left join locations l on l.id = sc.location_id
  where sh.project_id = pid and sh.slug = shot_slug;
$$;

-- Duyệt: đổi trạng thái sang approved. Trả về {slug, status, version}.
create or replace function approve_shot(pid uuid, shot_slug text)
returns jsonb
language plpgsql
as $$
declare
  result jsonb;
begin
  update shots set status = 'approved'
  where project_id = pid and slug = shot_slug
  returning jsonb_build_object('slug', slug, 'status', status, 'version', version) into result;
  if result is null then
    raise exception 'shot không tồn tại: %', shot_slug;
  end if;
  return result;
end;
$$;

-- Sinh lại: tăng version của riêng shot này, đặt lại pending, trả về dữ liệu để dựng keyframe mới.
create or replace function regenerate_shot(pid uuid, shot_slug text)
returns jsonb
language plpgsql
as $$
begin
  update shots set version = version + 1, status = 'pending'
  where project_id = pid and slug = shot_slug;
  if not found then
    raise exception 'shot không tồn tại: %', shot_slug;
  end if;
  return get_shot_job(pid, shot_slug);
end;
$$;

-- Chỉ service_role (n8n) được gọi.
revoke all on function get_shot_job(uuid, text) from public, anon, authenticated;
revoke all on function approve_shot(uuid, text) from public, anon, authenticated;
revoke all on function regenerate_shot(uuid, text) from public, anon, authenticated;
grant execute on function get_shot_job(uuid, text) to service_role;
grant execute on function approve_shot(uuid, text) to service_role;
grant execute on function regenerate_shot(uuid, text) to service_role;
