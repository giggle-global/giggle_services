
import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI", "mongodb://keydraft:deepak123@35.154.97.163:27017/")
DB_NAME = os.getenv("DB_NAME", "giggle")

# AWS setup
BUCKET = os.getenv("AWS_BUCKET", "giggle-files")

def run_fix():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    portfolio = db.portfolio
    
    # Find projects with PDF but no cover_image
    # Also include those with status != deleted
    query = {
        "portfolio_pdf": {"$exists": True, "$ne": None, "$ne": ""},
        "cover_image": {"$in": [None, ""]},
        "status": {"$ne": "deleted"}
    }
    
    projects = list(portfolio.find(query))
    logger.info(f"Found {len(projects)} projects needing thumbnails")
    
    if not projects:
        return

    # Importing the service and utility from the app structure
    import sys
    sys.path.append(os.getcwd())
    
    from app.services.portfolio import PortfolioService
    from app.repositories.portfolio import PortfolioRepository
    
    service = PortfolioService(repo=PortfolioRepository())
    
    for project in projects:
        project_id = str(project.get("_id"))
        # We need to convert bson Id to string for the repository methods
        project["id"] = project_id
        
        logger.info(f"Generating thumbnail for project: {project_id} - {project.get('title')}")
        try:
            service._generate_thumbnail_if_needed(project)
            logger.info(f"Successfully processed project {project_id}")
        except Exception as e:
            logger.error(f"Failed to process project {project_id}: {e}")

if __name__ == "__main__":
    run_fix()
