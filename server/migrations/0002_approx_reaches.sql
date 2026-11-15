-- Quiet Hours schema, version 2.
--
-- The reach count is what each phone reports, and the phone can only
-- approximate it (docs/LOCK-NOTES.md, "Reach counter"): iOS never says "the
-- shield was shown", so the phone counts shield draws, merged within 3
-- seconds. The column is renamed so nothing downstream reads it as exact.
ALTER TABLE participation RENAME COLUMN reaches TO approx_reaches;
