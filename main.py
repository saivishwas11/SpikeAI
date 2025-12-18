from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv

from models import QueryRequest, QueryResponse
from orchestrator import handle_query

# Load environment variables
load_dotenv()

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
    return {"status": "ok", "version": "1.0.0"}

if __name__ == "__main__":
    # STRICT REQUIREMENT: Port 8080
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)