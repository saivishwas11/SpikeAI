from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import asyncio
from dotenv import load_dotenv
import logging

from models import QueryRequest, QueryResponse
from orchestrator import handle_query
from agents.seo_agent import seo_agent
from utils.sheets import load_seo_data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize SEO Agent with data on startup
async def initialize_seo_agent() -> bool:
    """
    Initialize the SEO Agent with data from Google Sheets.
    
    Returns:
        bool: True if initialization was successful, False otherwise
    """
    try:
        logger.info("Initializing SEO Agent...")
        df, error = load_seo_data()
        
        if error:
            logger.error(f"Failed to load SEO data: {error}")
            return False
            
        if df.empty:
            logger.error("No SEO data loaded - empty DataFrame")
            return False
            
        # Update the global seo_agent with the loaded data
        global seo_agent
        seo_agent = SEOAgent(df)
        logger.info(f"SEO Agent initialized successfully with {len(df)} rows of data")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize SEO Agent: {e}", exc_info=True)
        return False

# Initialize FastAPI app
app = FastAPI(
    title="Spike AI Analytics & SEO API",
    description="API for querying GA4 analytics and SEO data using natural language",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Handle natural language queries for analytics and SEO data.
    For GA4 analytics queries, include the propertyId parameter.
    """
    try:
        # Pass the propertyId (if present) to the orchestrator
        result = await handle_query(
            query=request.query,
            property_id=request.propertyId
        )
        return QueryResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        # Log the error (in a real app) and return 500
        print(f"Server Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "services": {
            "seo_agent_initialized": seo_agent.df is not None
        },
        "version": "1.0.0"
    }

if __name__ == "__main__":
    # Initialize SEO Agent before starting the server
    seo_initialized = asyncio.run(initialize_seo_agent())
    if not seo_initialized:
        logger.warning("SEO Agent initialization failed. SEO features will not be available.")
    else:
        logger.info("SEO Agent is ready")

    # STRICT REQUIREMENT: Port 8080
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)