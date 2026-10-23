-- StoryForge schema. Dán vào Supabase > SQL Editor > Run.

create table projects (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  genre text,
  overall_tone text,
  target_duration_sec int,
  created_at timestamptz not null default now()
);

create table characters (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  slug text not null,
  name text not null,
  gender text,
  age int,
  appearance text,
  outfit text,
  accessories text[] not null default '{}',
  voice text,
  unique (project_id, slug)
);

create table locations (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  slug text not null,
  name text not null,
  description text,
  lighting text,
  unique (project_id, slug)
);

create table scenes (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  slug text not null,
  number int not null,
  setting text,
  location_id uuid references locations(id) on delete set null,
  time_of_day text,
  mood text,
  unique (project_id, slug)
);

create table shots (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  scene_id uuid not null references scenes(id) on delete cascade,
  slug text not null,
  shot_order int not null,
  action text,
  characters text[] not null default '{}',
  dialogue jsonb not null default '[]'::jsonb,
  camera text check (camera in ('wide', 'medium', 'close-up', 'insert', 'two-shot')),
  duration_sec int,
  status text not null default 'pending'
    check (status in ('pending', 'approved', 'failed')),
  version int not null default 1 check (version >= 1),
  unique (project_id, slug)
);

create index on characters (project_id);
create index on locations (project_id);
create index on scenes (project_id);
create index on shots (project_id);
create index on shots (scene_id);

alter table projects   enable row level security;
alter table characters enable row level security;
alter table locations  enable row level security;
alter table scenes     enable row level security;
alter table shots      enable row level security;
