from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from pipeline import load_and_reconcile, analyze, sql_quality_check


def test_source_counts_and_linkage():
    data, audit = load_and_reconcile()
    assert len(data) == 20190
    assert audit['record_id_unique']
    assert audit['linkage']['both'] == len(data)
    assert audit['linkage']['left_only'] == 0
    assert audit['linkage']['right_only'] == 0


def test_audit_constraints_and_sql():
    data, audit = load_and_reconcile()
    checks = sql_quality_check(data)
    assert checks['records'] == 20190
    assert checks['negative_visit_counts'] == 0
    assert audit['overlapping_health_categories'] == 0


def test_analysis_and_group_denominators():
    data, _ = load_and_reconcile()
    metrics, groups, by_band = analyze(data)
    assert groups['records'].sum() == metrics['analyzed_records']
    assert by_band['records'].sum() == metrics['analyzed_records']
    assert 0 <= metrics['zero_visit_percent'] <= 100
    assert metrics['model_comparison']['negative_binomial_alpha'] > 0
