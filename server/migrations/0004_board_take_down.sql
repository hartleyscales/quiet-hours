-- Quiet Hours schema, version 4.
--
-- A writer can take down their own board post (DELETE /v1/board/:id) while
-- the board is open. The row is kept, marked taken_down = 1, and is never
-- shown again to anyone. It still counts toward the writer's posts for the
-- week (MAX_POSTS_PER_WEEK), so taking a post down does not free a slot:
-- otherwise post, take down, post again would have no limit.
ALTER TABLE board_posts ADD COLUMN taken_down INTEGER NOT NULL DEFAULT 0 CHECK (taken_down IN (0, 1));
