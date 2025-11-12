# Rixly - Reddit Lead Extraction API

**Simplified Reddit lead extraction API without agent orchestration**

Extract **any type of business opportunity** from Reddit posts and comments using keyword-based searches with AI-powered analysis. Find leads for hiring, consulting, partnerships, sales, marketing, security, investments, and more.

---

## 🎯 Features

- ✅ **Flexible Lead Discovery** - Find ANY type of business opportunity (hiring, consulting, partnerships, sales, marketing, security, investments, etc.)
- ✅ **Reddit Scraping** - Posts and comments from multiple subreddits
- ✅ **Keyword Search Management** - Scheduled and one-time scraping
- ✅ **AI-Powered Analysis** - Opportunity classification, contact extraction, lead scoring
- ✅ **Platform-Agnostic Design** - Ready for LinkedIn/Twitter expansion
- ✅ **Simple REST API** - No agent, direct processing
- ✅ **PostgreSQL Database** - Production-ready with Alembic migrations
- ✅ **Duplicate Prevention** - Automatic tracking prevents re-scraping same URLs/posts
- ✅ **Webhook Notifications** - Optional webhooks for lead creation and job completion
- ✅ **Enhanced Pagination** - Full pagination metadata with filtering

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 12+ (running locally or remote)
- Reddit API credentials (client_id, client_secret)
- LLM API key (Groq or OpenAI)

### Installation

```bash
# Clone and navigate
cd rixly

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and database credentials
# Required: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and at least one LLM API key

# Setup PostgreSQL database
# Option 1: Use setup script (Linux/Mac)
./scripts/setup_db.sh

# Option 2: Manual setup
psql -U postgres
CREATE DATABASE rixly;
CREATE USER rixly WITH PASSWORD 'rixly';
GRANT ALL PRIVILEGES ON DATABASE rixly TO rixly;
\q

    # Initialize database schema (Alembic migrations)
    alembic upgrade head

    # Validate environment variables (optional but recommended)
    python scripts/validate_env.py

    # Run API server
    python run_api.py
```

The API will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

See `EXAMPLE_USAGE.md` for detailed usage examples.

---

## 📡 API Endpoints

### Keyword Searches

- `POST /api/v1/keyword-searches` - Create keyword search
  - **Validation**: `scraping_interval` required for `scheduled`, must be omitted for `one_time`
- `GET /api/v1/keyword-searches` - List searches
- `GET /api/v1/keyword-searches/{id}` - Get search
- `PUT /api/v1/keyword-searches/{id}` - Update search
  - **Validation**: Same rules as create
- `DELETE /api/v1/keyword-searches/{id}` - Delete search
- `POST /api/v1/keyword-searches/{id}/scrape` - Trigger one-time scrape
- `GET /api/v1/keyword-searches/{id}/status` - Get scraping status and job info

### Leads

- `GET /api/v1/leads` - List leads (with filters and pagination)
- `GET /api/v1/leads/{id}` - Get lead
- `PATCH /api/v1/leads/{id}` - Update lead status
- `GET /api/v1/leads/statistics/summary` - Get statistics

### Utilities

- `POST /api/v1/generate-keywords` - Generate keywords from product description
- `POST /api/v1/website-summary` - Generate website summary (50 words default)

See `md/API_REFERENCE.md` for complete API documentation with examples.

---

## 📚 Documentation

- `md/IMPLEMENTATION_PLAN.md` - Complete implementation plan and architecture
- `md/PROGRESS.md` - Implementation progress tracking
- `md/STATUS.md` - Current project status
- `md/COMPREHENSIVE_STATUS.md` - Detailed status report (what's done, missing, incomplete)
- `USE_CASES.md` - Examples of different lead types you can find
- `EXAMPLE_USAGE.md` - Quick start guide and API examples
- `DOCKER.md` - Docker setup and deployment guide

---

## 🏗️ Project Structure

```
rixly/
├── core/           # Configuration, logging, LLM
├── modules/        # Reddit, analyzer, database, scheduler
├── api/            # FastAPI routes and middleware
├── scripts/        # Run scripts
├── alembic/        # Database migrations
├── data/           # Data files (if any)
├── md/             # Documentation
└── logs/           # Log files
```

---

## 🗄️ Database

Rixly uses **PostgreSQL** with **Alembic** for migrations.

### Migration Commands

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current revision
alembic current
```

### Database Configuration

Configure via `.env` file:
```env
DATABASE_URL=postgresql://rixly:rixly@localhost:5432/rixly
```

Or use individual parts:
```env
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=rixly
DATABASE_USER=rixly
DATABASE_PASSWORD=rixly
```

---

**Status**: ✅ Core Implementation Complete

Ready for testing and deployment. See `md/STATUS.md` for details.
