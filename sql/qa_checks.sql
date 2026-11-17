-- Live validation query executed against a SQLite analytical extract.
-- Note: record_id is a surrogate row key, not an actual RAND HIE subject ID.
SELECT
  COUNT(*) AS records,
  COUNT(DISTINCT record_id) AS distinct_record_ids,
  COALESCE(SUM(CASE WHEN mdvis < 0 THEN 1 ELSE 0 END),0) AS negative_visit_counts,
  COALESCE(SUM(CASE WHEN COALESCE(hlthg,0) + COALESCE(hlthf,0) + COALESCE(hlthp,0) > 1 THEN 1 ELSE 0 END),0) AS health_flag_conflicts,
  COALESCE(SUM(CASE WHEN lncoins IS NULL THEN 1 ELSE 0 END),0) AS missing_coinsurance,
  COALESCE(SUM(CASE WHEN mdvis IS NULL THEN 1 ELSE 0 END),0) AS missing_visit_counts
FROM study_records;
