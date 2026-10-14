# Performance Optimization Notes

StreamFlix uses database-first optimizations for the current local portfolio scale.

## Implemented choices

- Primary keys on all raw, dimension, and fact tables.
- Indexes on high-selectivity filters: user, content, event type, timestamp, device, recommendation, and session IDs.
- Idempotent `ON CONFLICT` writes for replay-safe ingestion and ETL.
- Set-based PostgreSQL ETL instead of Python row loops.
- Kafka message keys based on `user_id` for stable partition locality.
- Analytics views aggregate from warehouse facts rather than raw JSON.
- Parquet artifacts for feature engineering and model training.

## Scaling path

- Partition `raw_events` and large fact tables by event date.
- Materialize `vw_executive_kpis` if dashboard refresh time grows.
- Add batch inserts to the Kafka consumer if event volume exceeds local demo scale.
- Move model artifacts to object storage for multi-service deployment.
- Add query plans to CI for the top dashboard views.
