-- Quiet Hours schema, version 1.
--
-- Conventions
--   * Every time is INTEGER milliseconds since the Unix epoch (UTC).
--   * Ids are random strings with a type prefix (us_, wk_, op_, po_, ln_).
--   * The phase of a week is never stored. It is derived from the week's
--     timestamps at read time (src/phase.ts).
--   * is_demo = 1 marks rows created by the demo seed. They can be listed and
--     removed with DELETE /v1/admin/demo.

CREATE TABLE users (
  id          TEXT PRIMARY KEY,
  email       TEXT NOT NULL UNIQUE,
  created_at  INTEGER NOT NULL,
  is_demo     INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
  -- Lower case, exactly one "@", and it is the one in "@usc.edu" at the end.
  CHECK (email = lower(email)),
  CHECK (length(email) > 8 AND substr(email, -8) = '@usc.edu'),
  CHECK (instr(email, '@') = length(email) - 7)
);

-- One-time sign-in codes. Only a hash of the code is stored.
CREATE TABLE signin_challenges (
  id           TEXT PRIMARY KEY,
  email        TEXT NOT NULL,
  code_hash    TEXT NOT NULL,
  created_at   INTEGER NOT NULL,
  expires_at   INTEGER NOT NULL,
  attempts     INTEGER NOT NULL DEFAULT 0,
  consumed_at  INTEGER
);
CREATE INDEX signin_challenges_email ON signin_challenges (email, created_at);

-- Session tokens. Only a SHA-256 hash of the bearer token is stored.
CREATE TABLE sessions (
  token_hash  TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  created_at  INTEGER NOT NULL,
  expires_at  INTEGER NOT NULL
);
CREATE INDEX sessions_user ON sessions (user_id);

-- A week. starts_at / ends_at are copied from the winning option when the
-- vote is decided; until then they are NULL.
CREATE TABLE weeks (
  id                 TEXT PRIMARY KEY,
  vote_opens_at      INTEGER NOT NULL,
  vote_closes_at     INTEGER NOT NULL,
  starts_at          INTEGER,
  ends_at            INTEGER,
  told_at            INTEGER NOT NULL,
  winning_option_id  TEXT REFERENCES options (id),
  created_at         INTEGER NOT NULL,
  is_demo            INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
  CHECK (vote_opens_at < vote_closes_at),
  CHECK (vote_closes_at < told_at),
  CHECK ((starts_at IS NULL) = (ends_at IS NULL)),
  CHECK ((starts_at IS NULL) = (winning_option_id IS NULL)),
  CHECK (starts_at IS NULL OR (vote_closes_at <= starts_at AND starts_at < ends_at AND ends_at <= told_at))
);
CREATE UNIQUE INDEX weeks_vote_opens_at ON weeks (vote_opens_at);

-- A proposed window. The vote count is not stored here; it is counted from
-- the votes table every time it is read.
CREATE TABLE options (
  id         TEXT PRIMARY KEY,
  week_id    TEXT NOT NULL REFERENCES weeks (id) ON DELETE CASCADE,
  position   INTEGER NOT NULL,
  starts_at  INTEGER NOT NULL,
  ends_at    INTEGER NOT NULL,
  reason     TEXT NOT NULL,
  source     TEXT NOT NULL CHECK (source IN ('admin', 'ai', 'demo')),
  is_demo    INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
  CHECK (starts_at < ends_at),
  UNIQUE (week_id, position)
);

-- One vote per user per week (the primary key enforces it).
CREATE TABLE votes (
  user_id     TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  week_id     TEXT NOT NULL REFERENCES weeks (id) ON DELETE CASCADE,
  option_id   TEXT NOT NULL REFERENCES options (id) ON DELETE CASCADE,
  updated_at  INTEGER NOT NULL,
  is_demo     INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
  PRIMARY KEY (user_id, week_id)
);
CREATE INDEX votes_week_option ON votes (week_id, option_id);

-- A person's part in a week. Created the first time their app touches the
-- week, with status 'in' (in by default).
--   joined_at   when this row was created (when their app first saw the week)
--   wrote_line  1 once they have submitted their line; deliberately has no
--               time and no reference to the line (see lines below)
CREATE TABLE participation (
  user_id     TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  week_id     TEXT NOT NULL REFERENCES weeks (id) ON DELETE CASCADE,
  status      TEXT NOT NULL CHECK (status IN ('in', 'skipped', 'left')),
  joined_at   INTEGER NOT NULL,
  left_at     INTEGER,
  reaches     INTEGER NOT NULL DEFAULT 0 CHECK (reaches >= 0),
  wrote_line  INTEGER NOT NULL DEFAULT 0 CHECK (wrote_line IN (0, 1)),
  is_demo     INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1)),
  PRIMARY KEY (user_id, week_id),
  CHECK ((status = 'left') = (left_at IS NOT NULL))
);
CREATE INDEX participation_week_status ON participation (week_id, status);

-- Board posts: one line and a place. user_id is kept for abuse handling and
-- the per-person post limit; it is never returned by the API.
-- moderation: 'pending' (not checked yet, not shown), 'ok' (shown),
--             'hidden' (failed the check on a later pass, not shown).
CREATE TABLE board_posts (
  id               TEXT PRIMARY KEY,
  week_id          TEXT NOT NULL REFERENCES weeks (id) ON DELETE CASCADE,
  user_id          TEXT REFERENCES users (id) ON DELETE SET NULL,
  text             TEXT NOT NULL,
  place            TEXT NOT NULL,
  created_at       INTEGER NOT NULL,
  moderation       TEXT NOT NULL CHECK (moderation IN ('pending', 'ok', 'hidden')),
  moderation_note  TEXT,
  is_demo          INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1))
);
CREATE INDEX board_posts_week_created ON board_posts (week_id, created_at);

-- Lines: what someone did. ANONYMOUS BY CONSTRUCTION:
--   * no user column and no foreign key to anything but the week
--   * no timestamp of any kind (a time could be matched to other activity)
--   * WITHOUT ROWID with a random primary key, so rows are stored in random
--     order and there is no hidden insertion counter
--   * no other table references this one
CREATE TABLE lines (
  id          TEXT PRIMARY KEY,
  week_id     TEXT NOT NULL REFERENCES weeks (id) ON DELETE CASCADE,
  text        TEXT NOT NULL,
  moderation  TEXT NOT NULL CHECK (moderation IN ('pending', 'ok', 'hidden')),
  is_demo     INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1))
) WITHOUT ROWID;
CREATE INDEX lines_week ON lines (week_id);

-- The hour told back. highlights_json carries line ids for every highlight.
CREATE TABLE recaps (
  week_id          TEXT PRIMARY KEY REFERENCES weeks (id) ON DELETE CASCADE,
  highlights_json  TEXT NOT NULL,
  stats_json       TEXT NOT NULL,
  generator        TEXT NOT NULL,
  generated_at     INTEGER NOT NULL,
  attempts         INTEGER NOT NULL,
  dropped_json     TEXT NOT NULL,
  is_demo          INTEGER NOT NULL DEFAULT 0 CHECK (is_demo IN (0, 1))
);
