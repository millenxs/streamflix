# Technology Choices and Decisions

This document documents the key technology choices made for the StreamFlix project, along with the rationale and trade-offs.

---

## 🐍 Python 3.11–3.12

### Decision
Use Python 3.11 or 3.12 as the primary programming language.

### Rationale
- **Rich ecosystem**: Unmatched libraries for data science (pandas, numpy, scikit-learn)
- **Industry standard**: Widely used in data engineering, ML, and backend development
- **Type hints**: Python 3.11+ has mature type hinting support for better code quality
- **Dependency compatibility**: Python 3.11–3.12 aligns with the current PyArrow and data-science dependency pins
- **Developer experience**: Large community, excellent documentation

### Trade-offs
- **Slower than compiled languages**: Not a concern for this project's scale
- **GIL**: Limits true parallelism, but not an issue for I/O-bound tasks

### Alternatives Considered
- **Scala**: Better for streaming, but steeper learning curve
- **Java**: More performant, but more verbose
- **Go**: Great for microservices, but fewer data science libraries

---

## 📦 pip + pyproject.toml for Dependency Management

### Decision
Use `pip` with `requirements.txt`, `requirements-dev.txt`, and a standards-based `pyproject.toml`.

### Rationale
- **Simple local setup**: Recruiters and reviewers can run the project with standard Python tooling.
- **Low onboarding friction**: No Poetry installation is required before the first run.
- **Separation of dependencies**: Runtime dependencies live in `requirements.txt`; development and notebook tooling live in `requirements-dev.txt`.
- **Modern project metadata**: `pyproject.toml` still centralizes package metadata and tool configuration for Black, Ruff, Mypy, and Pytest.
- **Portfolio-friendly**: The setup is transparent and easy to reproduce in CI or Docker later.

### Trade-offs
- **No committed lock file yet**: Fully reproducible dependency locking can be added later with `pip-tools` if needed.
- **Manual virtual environment management**: Contributors must create and activate a `.venv` themselves.

### Alternatives Considered
- **Poetry**: More complete dependency management, but adds an extra tool and was intentionally removed to simplify setup.
- **Conda**: Good for data science, but heavier and less aligned with Docker-based deployment.

---

## 🗄️ PostgreSQL 16

### Decision
Use PostgreSQL 16 as the primary database.

### Rationale
- **ACID compliance**: Reliable transactional integrity
- **Advanced SQL**: Window functions, CTEs, JSONB support
- **Mature**: Battle-tested, reliable, well-documented
- **Open source**: No licensing costs
- **JSONB**: Flexible metadata storage without NoSQL
- **Industry standard**: Widely used in data warehousing

### Trade-offs
- **Not as fast as specialized OLAP**: Not optimized for analytics queries at scale
- **Scaling**: Requires read replicas for high throughput

### Alternatives Considered
- **MySQL**: Good, but less advanced SQL features
- **MongoDB**: Better for unstructured data, but less SQL capabilities
- **ClickHouse**: Excellent for analytics, but less transactional support
- **Snowflake/BigQuery**: Cloud data warehouses, but overkill for local project

---

## 🚀 Apache Kafka-compatible broker via Confluent Platform 7.5.0

### Decision
Use a Kafka-compatible broker from Confluent Platform for local event streaming.

### Rationale
- **Industry standard**: Used by Netflix, Uber, LinkedIn, etc.
- **Scalable**: Horizontal scaling with partitions
- **Durable**: Log-based storage with configurable retention
- **Fault-tolerant**: Replication across brokers
- **Mature**: Large ecosystem, well-documented
- **Pattern match**: Real-world streaming architecture

### Trade-offs
- **Complexity**: Requires Zookeeper (though recent versions support KRaft)
- **Resource intensive**: Requires more memory and CPU than alternatives
- **Windows support**: Challenging on Windows native, requires WSL2

### Alternatives Considered
- **Redpanda**: Kafka-compatible, simpler, faster, but less mature
- **RabbitMQ**: Simpler, but not designed for streaming analytics
- **Apache Pulsar**: More features, but more complex
- **Redis Streams**: Simpler, but less durable and scalable

---

## 🐳 Docker & Docker Compose

### Decision
Use Docker and Docker Compose for infrastructure orchestration.

### Rationale
- **Reproducibility**: Same environment across machines
- **Isolation**: No conflicts with local system
- **Simplicity**: Single command to start all services
- **Production-like**: Closer to real deployment than local installs
- **Documentation**: docker-compose.yml documents infrastructure
- **WSL2 support**: Works well on Windows via WSL2

### Trade-offs
- **Resource overhead**: Containers consume more memory
- **Learning curve**: Requires understanding of Docker concepts
- **Windows complexity**: Requires WSL2 for best experience

### Alternatives Considered
- **Local installs**: Simpler, but less reproducible
- **Vagrant**: Similar benefits, but heavier
- **Kubernetes**: Overkill for local development

---

## 📊 Pandas, NumPy, PyArrow

### Decision
Use Pandas, NumPy, and PyArrow for data processing.

### Rationale
- **Pandas**: Industry standard for data manipulation in Python
- **NumPy**: High-performance numerical computing
- **PyArrow**: Fast columnar data format, interoperability
- **Ecosystem**: Extensive documentation and community support
- **Integration**: Works well with scikit-learn, PostgreSQL

### Trade-offs
- **Memory**: Pandas can be memory-intensive for large datasets
- **Single-machine**: Not distributed like Spark

### Alternatives Considered
- **Apache Spark**: Distributed processing, but overkill for this scale
- **Polars**: Faster than Pandas, but less mature ecosystem
- **Dask**: Distributed Pandas, but adds complexity

---

## 🤖 Scikit-learn

### Decision
Use Scikit-learn for machine learning.

### Rationale
- **Comprehensive**: Covers clustering, classification, regression
- **Well-documented**: Excellent tutorials and examples
- **Industry standard**: Widely used in production
- **Consistent API**: Similar patterns across algorithms
- **Performance**: Optimized C/Cython backend

### Trade-offs
- **Not deep learning**: Limited for neural networks
- **Single-machine**: Not distributed

### Alternatives Considered
- **TensorFlow/PyTorch**: Overkill for this project's ML needs
- **XGBoost/LightGBM**: Better for gradient boosting, but scikit-learn is sufficient
- **MLflow**: Added complexity, simplified to Joblib + JSON

---

## 🌐 FastAPI

### Decision
Use FastAPI for the API layer.

### Rationale
- **Modern**: Built on Python 3.6+ type hints
- **Fast**: Performance comparable to NodeJS and Go
- **Automatic docs**: OpenAPI/Swagger documentation generated automatically
- **Validation**: Pydantic for request/response validation
- **Async support**: Native async/await for I/O-bound tasks
- **Developer experience**: Easy to use, excellent editor support

### Trade-offs
- **Younger**: Not as mature as Django or Flask
- **Smaller ecosystem**: Fewer third-party extensions

### Alternatives Considered
- **Flask**: Simpler, but requires more boilerplate
- **Django**: More features, but heavier
- **Express.js (Node)**: Fast, but would introduce JavaScript

---

## 📈 Power BI

### Decision
Use Power BI as the primary BI tool.

### Rationale
- **Industry standard**: Widely used in enterprise
- **Rich visualizations**: Extensive chart types
- **DAX**: Powerful formula language for calculations
- **Windows integration**: Native on Windows
- **Sharing**: Easy to share via Power BI Service
- **Learning value**: Marketable skill

### Trade-offs
- **Windows-only**: Not available on Linux/Mac
- **Cost**: Desktop free, but Service requires subscription
- **Driver**: Requires ODBC driver for PostgreSQL

### Alternatives Considered
- **Tableau**: More powerful, but expensive
- **Metabase**: Open source, but less sophisticated
- **Looker Studio**: Free, but less powerful DAX
- **Superset**: Open source, but steeper learning curve

---

## 🔍 MLflow → Simplified Tracking

### Decision
Use Joblib + JSON for model persistence instead of MLflow.

### Rationale
- **Simplicity**: Less infrastructure to manage
- **No server**: No need to run MLflow server
- **Sufficient**: For portfolio project, simple persistence is adequate
- **Focus**: More time on ML code, less on tracking infrastructure
- **Future-proof**: Can be replaced by MLflow if needed

### Trade-offs
- **No UI**: No visual tracking of experiments
- **No comparison**: Harder to compare multiple runs
- **No deployment**: No built-in model serving

### Alternatives Considered
- **MLflow**: Full-featured, but adds significant complexity
- **Weights & Biases**: Cloud-based, but requires account
- **Comet**: Similar to W&B, but overkill

---

## 🧪 Pytest

### Decision
Use Pytest for testing.

### Rationale
- **Simple**: Easy to write and read tests
- **Powerful**: Fixtures, parametrization, plugins
- **Industry standard**: Widely used in Python projects
- **Async support**: pytest-asyncio for FastAPI testing
- **Coverage**: pytest-cov for coverage reports

### Trade-offs
- **None significant**: Pytest is excellent for this use case

### Alternatives Considered
- **unittest**: Built-in, but more verbose
- **nose2**: Similar to pytest, but less popular

---

## 🖥️ WSL2 for Docker on Windows

### Decision
Use WSL2 as the primary environment for Docker and infrastructure.

### Rationale
- **Better performance**: Native Linux kernel for Docker
- **Stability**: More stable than Docker Desktop on Windows
- **Compatibility**: Works well with Kafka and PostgreSQL
- **Development**: VS Code Remote WSL provides seamless experience
- **Future-proof**: Closer to production Linux environments

### Trade-offs
- **Setup**: Requires WSL2 installation and configuration
- **File system**: Some performance issues with Windows file system from WSL
- **Learning**: Familiarity with Linux commands required

### Alternatives Considered
- **Docker Desktop on Windows**: Easier setup, but less stable
- **Windows native containers**: Not as mature as Linux containers

---

## 📝 Black, Ruff, MyPy

### Decision
Use Black for formatting, Ruff for linting, MyPy for type checking.

### Rationale
- **Black**: Opinionated formatter, no configuration needed, consistent code
- **Ruff**: Fast linter (written in Rust), replaces multiple tools (flake8, isort, etc.)
- **MyPy**: Static type checking, catches bugs before runtime
- **Professional**: These tools are used in production codebases
- **Automated**: Can be integrated into CI/CD

### Trade-offs
- **Setup time**: Initial configuration required
- **Strictness**: MyPy can be strict, requires discipline

### Alternatives Considered
- **Pylint**: More features, but slower
- **autopep8**: Alternative formatter, but Black is more opinionated
- **No type checking**: Faster development, but more runtime errors

---

## 🗂️ Star Schema for Data Warehouse

### Decision
Use Star Schema for dimensional modeling.

### Rationale
- **Simplicity**: Easy to understand and query
- **Performance**: Fewer joins than snowflake schema
- **Industry standard**: Widely used in data warehousing
- **BI-friendly**: Works well with Power BI, Tableau
- **Denormalized dimensions**: Faster dimension queries

### Trade-offs
- **Data redundancy**: Denormalized dimensions store duplicate data
- **Storage**: Slightly more storage than normalized schemas

### Alternatives Considered
- **Snowflake schema**: More normalized, but more joins
- **Data Vault**: More complex, but better for auditing
- **Wide tables**: Simpler, but less flexible

---

## 🎯 Summary

All technology choices prioritize:
1. **Industry relevance**: Technologies used in real companies
2. **Learning value**: Marketable skills for portfolio
3. **Simplicity**: Avoid overengineering for portfolio project
4. **Reproducibility**: Docker, virtual environments, requirements files
5. **Performance**: Sufficient for project scale
6. **Future-proof**: Technologies with active communities

These choices ensure the project demonstrates competence in technologies that hiring managers recognize and value.

---

*Document updated: 2025-01-05*
