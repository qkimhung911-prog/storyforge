-- Cho giao diện web (khóa công khai anon) ĐỌC 5 bảng. Không cho ghi.
-- Dán vào Supabase > SQL Editor > Run (chạy sau dialogue.sql). Chạy lại nhiều lần vẫn an toàn.
-- Lưu ý: ai có khóa anon đều đọc được dữ liệu này. Chỉ dùng cho demo/portfolio, đừng để dữ liệu nhạy cảm.

grant select on projects, characters, locations, scenes, shots to anon;

drop policy if exists "web doc projects" on projects;
create policy "web doc projects" on projects for select to anon using (true);

drop policy if exists "web doc characters" on characters;
create policy "web doc characters" on characters for select to anon using (true);

drop policy if exists "web doc locations" on locations;
create policy "web doc locations" on locations for select to anon using (true);

drop policy if exists "web doc scenes" on scenes;
create policy "web doc scenes" on scenes for select to anon using (true);

drop policy if exists "web doc shots" on shots;
create policy "web doc shots" on shots for select to anon using (true);
