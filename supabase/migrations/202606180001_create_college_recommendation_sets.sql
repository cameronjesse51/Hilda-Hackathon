create table if not exists public.college_recommendation_sets (
  id text primary key,
  student_id uuid not null references public.student_profiles(student_id) on delete cascade,
  schema_version text not null,
  query jsonb not null,
  recommendations jsonb not null,
  profile_snapshot jsonb not null,
  created_at timestamptz not null default now(),
  constraint college_recommendation_sets_recommendations_array
    check (jsonb_typeof(recommendations) = 'array'),
  constraint college_recommendation_sets_query_object
    check (jsonb_typeof(query) = 'object'),
  constraint college_recommendation_sets_profile_snapshot_object
    check (jsonb_typeof(profile_snapshot) = 'object')
);

create index if not exists college_recommendation_sets_student_created_idx
  on public.college_recommendation_sets (student_id, created_at desc);

alter table public.college_recommendation_sets enable row level security;

-- This application uses its own signed student session and performs all
-- tenant-scoped access through the service-role backend. No anon/authenticated
-- PostgREST policy is intentionally created.
revoke all on public.college_recommendation_sets from anon, authenticated;
