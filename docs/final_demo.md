# StreamFlix Final Demonstration

Run this sequence from the repository root to demonstrate the full platform locally.

```powershell
python scripts/init_db.py
python src/ingestion/load_movielens.py
python -m src.generation.users
python -m src.streaming.producer --days 1 --users 50 --limit 5000 --events-per-second 0
python -m src.streaming.consumer --limit 5000 --idle-timeout 10
python -m src.etl.pipeline
python -m src.analytics.quality
python -m src.analytics.views
python -m src.analytics.eda
python -m src.features.user_features
python -m src.ml.clustering.train
python -m src.ml.churn.train
python -m src.ml.recommendation.generate
uvicorn src.api.main:app --reload
streamlit run app/streamlit_app.py
```

Run the API and Streamlit commands in separate terminals. Then open:

- Recommendation API: `http://localhost:8000/recommendations/1`
- API health: `http://localhost:8000/health`
- Streamlit demo: `http://localhost:8501`
- Kafka UI: `http://localhost:8080`
- Power BI preparation: connect to PostgreSQL and import the `vw_*` analytics views. The repository includes setup guidance and starter DAX measures, but no completed `.pbix` report.

The demo covers ingestion, raw persistence, ETL, quality checks, analytics views, feature engineering, ML training, recommendation serving, in-memory API feedback capture, A/B assignment, and thumbnail variant assignment. TMDB metadata enrichment is optional and requires TMDB access to be configured.
