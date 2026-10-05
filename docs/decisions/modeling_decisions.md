# Data Modeling Decisions

This document documents the key data modeling decisions for the StreamFlix project.

---

## 🗄️ Two-Layer Architecture

### Decision
Separate the database into two conceptual layers: Raw Layer and Data Warehouse Layer.

### Rationale
- **Separation of concerns**: Raw events are immutable, DW is optimized for analytics
- **Audit trail**: Raw layer preserves original events for debugging
- **Flexibility**: Can reprocess raw events if business rules change
- **Performance**: DW layer is optimized for query performance
- **Industry pattern**: Lambda/Kappa architecture commonly used in production

### Trade-offs
- **Storage**: Raw layer duplicates data
- **ETL complexity**: Requires transformation step

### Alternatives Considered
- **Single layer**: Simpler, but less flexible
- **Three layers** (Raw, Staging, DW): More complex, not needed for this scale

---

## 📊 Star Schema for Data Warehouse

### Decision
Use Star Schema for the Data Warehouse layer.

### Rationale
- **Query performance**: Fewer joins than snowflake schema
- **Simplicity**: Easy to understand and maintain
- **BI-friendly**: Works well with Power BI, Tableau
- **Denormalized dimensions**: Faster dimension table queries
- **Industry standard**: Widely used in data warehousing

### Trade-offs
- **Data redundancy**: Dimension tables may have duplicate data
- **Storage**: Slightly more storage than fully normalized schemas

### Alternatives Considered
- **Snowflake schema**: More normalized, but more joins
- **Data Vault**: Better for auditing, but more complex
- **Flat wide tables**: Simpler, but less flexible

---

## 🔑 Surrogate Keys

### Decision
Use surrogate keys (auto-increment integers) for all dimension tables.

### Rationale
- **Stability**: Surrogate keys don't change when natural keys change
- **Performance**: Integer joins are faster than string joins
- **Consistency**: Uniform key types across all tables
- **Size**: Smaller than natural keys (UUIDs, composite keys)

### Trade-offs
- **Indirection**: Requires joins to get natural keys
- **Complexity**: Additional mapping to maintain

### Alternatives Considered
- **Natural keys**: Simpler, but less stable
- **UUIDs**: Globally unique, but larger and slower

---

## 📅 Date Dimension

### Decision
Create a separate `dim_date` table with pre-populated dates.

### Rationale
- **Time-based analysis**: Enables filtering by day, month, quarter, year
- **Performance**: Faster than extracting date parts from timestamps
- **Flexibility**: Can add custom attributes (holidays, fiscal periods)
- **BI-friendly**: Power BI and Tableau work well with date dimensions
- **Industry standard**: Common in data warehousing

### Trade-offs
- **Maintenance**: Need to populate dates periodically
- **Storage**: Additional table

### Alternatives Considered
- **Date functions**: Simpler, but slower for complex queries
- **Calendar table as view**: Less storage, but slower

---

## 🎭 Content-Genre Bridge Table

### Decision
Use a bridge table (`dim_content_genre`) for many-to-many relationship between content and genres.

### Rationale
- **Flexibility**: Content can belong to multiple genres
- **Normalization**: Avoids repeating genre names in content table
- **Query performance**: Can filter by any genre efficiently
- **Industry standard**: Standard pattern for many-to-many relationships

### Trade-offs
- **Complexity**: Requires additional join for genre queries
- **Storage**: Additional table

### Alternatives Considered
- **Comma-separated genres**: Simpler, but harder to query
- **JSON array**: Flexible, but less performant for filtering

---

## 📦 JSONB for Metadata

### Decision
Use PostgreSQL JSONB for flexible metadata in `raw_events`.

### Rationale
- **Flexibility**: Can store varying event attributes without schema changes
- **Queryability**: JSONB supports indexing and querying
- **NoSQL-like**: Combines relational and NoSQL benefits
- **Event data**: Events often have varying structures
- **Performance**: JSONB is binary-encoded and faster than JSON

### Trade-offs
- **Schema enforcement**: Less strict than relational columns
- **Query complexity**: JSON queries are more verbose

### Alternatives Considered
- **EAV model**: More relational, but complex queries
- **Separate tables per event type**: More structured, but many tables
- **Plain JSON**: Slower, no indexing

---

## 🔗 Foreign Key Constraints

### Decision
Enforce foreign key constraints in the Data Warehouse layer.

### Rationale
- **Data integrity**: Prevents orphan records
- **Documentation**: Explicitly defines relationships
- **Query optimization**: Helps planner optimize joins
- **Quality**: Catches data quality issues at database level

### Trade-offs
- **ETL complexity**: Requires loading dimensions before facts
- **Performance**: Slight overhead on inserts/updates

### Alternatives Considered
- **No FKs**: Simpler ETL, but risk of orphan records
- **Application-level validation**: More flexible, but less reliable

---

## 📈 Fact Table Granularity

### Decision
Set fact table granularity at the event level (one row per event).

### Rationale
- **Maximum detail**: Preserves all information
- **Flexibility**: Can aggregate to any level later
- **Debugging**: Can drill down to individual events
- **Event sourcing**: Aligns with event-driven architecture

### Trade-offs
- **Volume**: More rows than aggregated facts
- **Query performance**: Slower for high-level aggregations

### Alternatives Considered
- **Session-level facts**: Fewer rows, but lose event detail
- **Daily aggregates**: Smallest volume, but lose granularity

---

## 🔄 Idempotent ETL

### Decision
Design ETL to be idempotent using upserts (INSERT ... ON CONFLICT).

### Rationale
- **Re-run safety**: Can re-run ETL without side effects
- **Incremental updates**: Can process new events without reprocessing all
- **Error recovery**: Can resume from failures
- **Production pattern**: Common in real ETL systems

### Trade-offs
- **Complexity**: Requires natural keys and conflict handling
- **Performance**: Upserts can be slower than inserts

### Alternatives Considered
- **Append-only**: Simpler, but creates duplicates
- **Truncate and reload**: Simpler, but loses history

---

## 📊 Separate Playback Events

### Decision
Create a separate `raw_playback_events` table for playback-specific events.

### Rationale
- **Different schema**: Playback events have timing fields (position, duration)
- **Query optimization**: Can optimize indexes differently
- **Access patterns**: Playback events queried differently from general events
- **Separation of concerns**: Clear domain separation

### Trade-offs
- **Complexity**: Additional table to manage
- **Joins**: Requires joins for combined analysis

### Alternatives Considered
- **Single events table**: Simpler, but mixed schemas
- **JSON fields for timing**: Flexible, but less performant

---

## 🎯 Recommendation Fact Tables

### Decision
Separate recommendations into two tables: `fact_recommendations` (generated) and `fact_recommendation_feedback` (interactions).

### Rationale
- **Different purposes**: One for serving, one for analytics
- **Volume**: Feedback events are fewer than generated recommendations
- **Time alignment**: Generated at serving time, feedback over time
- **Analytics**: Easier to calculate CTR with separate tables

### Trade-offs
- **Complexity**: Additional table and joins
- **Consistency**: Need to ensure recommendations have feedback

### Alternatives Considered
- **Single table**: Simpler, but mixed concerns
- **Feedback in recommendations table**: Simpler, but sparse data

---

## 🗂️ Indexing Strategy

### Decision
Create indexes on foreign keys, timestamps, and frequently queried columns.

### Rationale
- **Query performance**: Critical for analytics queries
- **Join performance**: FK indexes speed up joins
- **Time-based queries**: Timestamp indexes for date ranges
- **Filtering**: Indexes on commonly filtered columns

### Trade-offs
- **Storage**: Indexes consume additional storage
- **Write performance**: Slower inserts/updates due to index maintenance
- **Maintenance**: Need to manage index bloat

### Alternatives Considered
- **No indexes**: Faster writes, but much slower reads
- **Materialized views**: Faster reads, but manual refresh

---

## 📍 Location Dimension

### Decision
Create `dim_location` with composite key (country, region).

### Rationale
- **Geographic analysis**: Enables analysis by country and region
- **Hierarchy**: Natural hierarchy (country → region)
- **Performance**: Integer keys faster than string joins
- **Normalization**: Avoids repeating country/region names

### Trade-offs
- **Granularity**: Limited to country/region (no city-level)
- **Privacy**: Coarse location protects user privacy

### Alternatives Considered
- **Lat/Long coordinates**: More precise, but privacy concerns
- **String fields in fact tables**: Simpler, but slower

---

## 📱 Device Dimension

### Decision
Create `dim_location` with standardized device types.

### Rationale
- **Device analysis**: Enables analysis by device type
- **Standardization**: Consistent device naming across events
- **Performance**: Integer keys faster than string joins
- **Extensibility**: Easy to add new device types

### Trade-offs
- **Granularity**: High-level device types (no OS, browser)
- **Complexity**: Additional table and join

### Alternatives Considered
- **String fields in fact tables**: Simpler, but inconsistent
- **User-agent strings**: More detailed, but complex parsing

---

## 🎯 Summary

All modeling decisions prioritize:
1. **Query performance**: Optimized for analytics queries
2. **Data integrity**: Constraints and validation
3. **Flexibility**: Can adapt to changing requirements
4. **Industry patterns**: Common patterns in data warehousing
5. **Scalability**: Can handle growth in data volume
6. **Privacy**: Coarse location, no PII

These decisions ensure the data model supports both analytical queries and ML feature extraction while maintaining data quality and performance.

---

*Document updated: 2025-01-05*
