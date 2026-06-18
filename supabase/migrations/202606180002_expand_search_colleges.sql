-- Expand semantic college search so the RPC returns the structured fields used
-- by recommendation cards and can enforce every advertised hard constraint.
-- Dropping by OID avoids leaving an older overload callable after this signature
-- gains school-size and requested-program parameters.
do $$
declare
  function_signature text;
begin
  for function_signature in
    select p.oid::regprocedure::text
    from pg_proc p
    join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public' and p.proname = 'search_colleges'
  loop
    execute format('drop function %s', function_signature);
  end loop;
end
$$;

create function public.search_colleges(
  query_embedding public.vector,
  max_net_price integer default null,
  filter_visa boolean default null,
  filter_state text[] default null,
  min_admission_rate double precision default null,
  max_admission_rate double precision default null,
  requires_nursing boolean default false,
  requires_cs boolean default false,
  requires_engineering boolean default false,
  match_count integer default 5,
  filter_hbcu boolean default null,
  filter_ncaa text default null,
  filter_prestige text[] default null,
  filter_women_only boolean default null,
  filter_school_size text default null,
  requested_program text default null
)
returns table (
  unitid text,
  name text,
  city text,
  state text,
  admission_rate double precision,
  sat_avg double precision,
  enrollment integer,
  control integer,
  size_category text,
  net_price_pub integer,
  net_price_priv integer,
  net_price_income1 integer,
  graduation_rate double precision,
  transfer_rate double precision,
  pct_international double precision,
  pct_pell double precision,
  pct_cs double precision,
  pct_engineering double precision,
  pct_biology double precision,
  pct_nursing double precision,
  median_earnings_10y integer,
  median_grad_debt integer,
  hbcu boolean,
  women_only boolean,
  prestige_tier text,
  ranking integer,
  ncaa_division text,
  sports_programs text[],
  vibe_description text,
  programs text[],
  program_cip_codes text[],
  program_awards_last_year bigint,
  similarity double precision
)
language sql
stable
security invoker
set search_path = public
as $$
  select
    college.unitid,
    college.name,
    college.city,
    college.state,
    college.admission_rate,
    college.sat_avg,
    college.enrollment,
    college.control,
    college.size_category,
    college.net_price_pub,
    college.net_price_priv,
    college.net_price_income1,
    college.graduation_rate,
    college.transfer_rate,
    college.pct_international,
    college.pct_pell,
    college.pct_cs,
    college.pct_engineering,
    college.pct_biology,
    college.pct_nursing,
    college.median_earnings_10y,
    college.median_grad_debt,
    college.hbcu,
    college.women_only,
    college.prestige_tier,
    college.ranking,
    college.ncaa_division,
    college.sports_programs,
    college.vibe_description,
    specialty.programs,
    specialty.cip_codes,
    specialty.awards_last_year,
    1 - (college.embedding <=> query_embedding) as similarity
  from public.college_embeddings as college
  left join lateral (
    select
      array_agg(distinct specialty_row."CIPDESC")
        filter (where specialty_row."CIPDESC" is not null) as programs,
      array_agg(distinct specialty_row."CIPCODE"::text)
        filter (where specialty_row."CIPCODE" is not null) as cip_codes,
      sum(coalesce(specialty_row."AWARDS_LAST_YEAR", 0)) as awards_last_year
    from public.institution_specialties as specialty_row
    where requested_program is not null
      and specialty_row."UNITID" = college.unitid
      and specialty_row."CIPDESC" ilike '%' || requested_program || '%'
  ) as specialty on true
  where college.embedding is not null
    and (
      max_net_price is null
      or coalesce(
        case
          when college.control = 1 then college.net_price_pub
          when college.control in (2, 3) then college.net_price_priv
        end,
        college.net_price_pub,
        college.net_price_priv
      ) <= max_net_price
    )
    and (filter_visa is null or college.visa_friendly = filter_visa)
    and (filter_state is null or college.state = any(filter_state))
    and (min_admission_rate is null or college.admission_rate >= min_admission_rate)
    and (max_admission_rate is null or college.admission_rate <= max_admission_rate)
    and (not requires_nursing or college.pct_nursing > 0)
    and (not requires_cs or college.pct_cs > 0)
    and (not requires_engineering or college.pct_engineering > 0)
    and (filter_hbcu is null or college.hbcu = filter_hbcu)
    and (filter_ncaa is null or college.ncaa_division = filter_ncaa)
    and (filter_prestige is null or college.prestige_tier = any(filter_prestige))
    and (filter_women_only is null or college.women_only = filter_women_only)
    and (filter_school_size is null or college.size_category = filter_school_size)
    and (requested_program is null or specialty.programs is not null)
  order by college.embedding <=> query_embedding
  limit greatest(1, least(coalesce(match_count, 5), 10));
$$;

revoke all on function public.search_colleges(
  public.vector,
  integer,
  boolean,
  text[],
  double precision,
  double precision,
  boolean,
  boolean,
  boolean,
  integer,
  boolean,
  text,
  text[],
  boolean,
  text,
  text
) from public, anon, authenticated;

grant execute on function public.search_colleges(
  public.vector,
  integer,
  boolean,
  text[],
  double precision,
  double precision,
  boolean,
  boolean,
  boolean,
  integer,
  boolean,
  text,
  text[],
  boolean,
  text,
  text
) to service_role;
