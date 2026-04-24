-- ============================================================
-- EcoGuardian AI — Supabase Database Setup
-- Jalankan file ini di Supabase SQL Editor
-- Dashboard: https://supabase.com → Project → SQL Editor
-- ============================================================

-- 1. Tabel sesi chat
create table if not exists sessions (
  id          text primary key,
  messages    jsonb        not null default '[]',
  created_at  timestamptz  not null default now(),
  updated_at  timestamptz  not null default now()
);

-- 2. Tabel riwayat analisis
create table if not exists analysis_history (
  id             bigserial    primary key,
  session_id     text,
  query          text,
  city           text,
  result_summary text,
  risk_level     text,
  created_at     timestamptz  not null default now()
);

-- ============================================================
-- Index untuk performa query
-- ============================================================
create index if not exists idx_analysis_session  on analysis_history(session_id);
create index if not exists idx_analysis_city     on analysis_history(city);
create index if not exists idx_analysis_created  on analysis_history(created_at desc);

-- ============================================================
-- Row Level Security (RLS) — aktifkan agar aman
-- ============================================================
alter table sessions         enable row level security;
alter table analysis_history enable row level security;

-- Policy: izinkan semua operasi dari anon key (untuk aplikasi ini)
create policy "allow_all_sessions"
  on sessions for all
  using (true)
  with check (true);

create policy "allow_all_analysis"
  on analysis_history for all
  using (true)
  with check (true);

-- ============================================================
-- Verifikasi — jalankan ini untuk cek tabel sudah terbuat
-- ============================================================
-- select table_name from information_schema.tables
-- where table_schema = 'public'
-- and table_name in ('sessions', 'analysis_history');
