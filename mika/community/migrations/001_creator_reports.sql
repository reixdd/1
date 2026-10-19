-- PREVIEW ONLY: apply to a separate dedicated MIKA Supabase project after RLS security review.
-- DIT and JARVIS projects must not receive this migration.
create schema if not exists mika_private;
revoke all on schema mika_private from public, anon;
create table if not exists mika_private.feedback_reports (
 id uuid primary key default gen_random_uuid(),
 reporter_user_id uuid not null references auth.users(id),
 mint text not null check (mint ~ '^[1-9A-HJ-NP-Za-km-z]{32,44}$'),
 category text not null check (category in ('OTHER','CREATOR_ACTIVITY','TOKEN_TRANSFER','LIQUIDITY','COORDINATED_ACTIVITY')),
 statement text not null check (char_length(statement) between 5 and 600),
 evidence_links jsonb not null default '[]'::jsonb,
 status text not null default 'PENDING' check (status in ('PENDING','APPROVED','REJECTED','WITHDRAWN')),
 submitted_at timestamptz not null default now(),
 reviewed_at timestamptz,
 moderation_reason text
);
alter table mika_private.feedback_reports enable row level security;
-- Authenticated reporter reads own submissions only if private schema access is separately granted.
create policy "owner_reads_own" on mika_private.feedback_reports
 for select to authenticated using (reporter_user_id = (select auth.uid()));
-- No direct authenticated insert/update/delete policies: submission and review through dedicated
-- server endpoints with identity derived from verified auth, bot protection and quota checks.
-- Public projections must expose approved counts and whitelisted evidence URLs only;
-- never publish reporter identity, pending content or raw report statements.
