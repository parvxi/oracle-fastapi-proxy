# proxy.py - Enhanced Oracle Integration Proxy
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import requests
import logging
from typing import Optional, Dict, Any
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Oracle Integration Proxy",
    description="Secure proxy for Oracle database operations",
    version="1.0.0"
)

# CRITICAL: CORS middleware to enable browser access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Oracle configuration
ORACLE_URL = "https://gp8wf9ag.adb.me-jeddah-1.oraclecloud.com/ords/petrolube_staging/table1_11/"

# Helper function for Oracle API calls
async def make_oracle_request(
    method: str, 
    url: str, 
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Make request to Oracle API with proper error handling"""
    try:
        response = requests.request(
            method=method,
            url=url,
            json=data,
            timeout=30,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
        
        # Log request details
        logger.info(f"{method} {url} - Status: {response.status_code}")
        
        # Handle different response codes
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 201:
            return {"success": True, "data": response.json()}
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Record not found")
        else:
            # Try to get error details from Oracle
            try:
                error_data = response.json()
                error_message = error_data.get("message", f"Oracle API error: {response.status_code}")
            except:
                error_message = f"Oracle API returned status {response.status_code}"
            
            raise HTTPException(status_code=response.status_code, detail=error_message)
            
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Oracle database timeout")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Cannot connect to Oracle database")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Check proxy and Oracle connectivity"""
    try:
        response = requests.get(ORACLE_URL, timeout=10)
        oracle_status = "connected" if response.status_code == 200 else "error"
    except:
        oracle_status = "disconnected"
    
    return {
        "status": "healthy",
        "oracle_connection": oracle_status,
        "timestamp": requests.get("http://worldtimeapi.org/api/timezone/Asia/Riyadh").json()["datetime"]
    }

# READ: Get all records
@app.get("/oracle/table1_11/")
async def read_data():
    """Fetch all records from Oracle database"""
    logger.info("Fetching all records from Oracle")
    return await make_oracle_request("GET", ORACLE_URL)

# CREATE: Add new record
@app.post("/oracle/table1_11/")
async def create_data(request: Request):
    """Create new record in Oracle database"""
    body = await request.json()
    logger.info(f"Creating new record: {body.get('customer_name', 'Unknown')}")
    return await make_oracle_request("POST", ORACLE_URL, body)

# READ: Get specific record by ID
@app.get("/oracle/table1_11/{record_id}")
async def read_record(record_id: str):
    """Fetch specific record by ID"""
    logger.info(f"Fetching record ID: {record_id}")
    url = f"{ORACLE_URL}{record_id}"
    return await make_oracle_request("GET", url)

# UPDATE: Modify existing record
@app.put("/oracle/table1_11/{record_id}")
async def update_data(record_id: str, request: Request):
    """Update existing record in Oracle database"""
    body = await request.json()
    logger.info(f"Updating record ID: {record_id}")
    url = f"{ORACLE_URL}{record_id}"
    return await make_oracle_request("PUT", url, body)

# DELETE: Remove record
@app.delete("/oracle/table1_11/{record_id}")
async def delete_data(record_id: str):
    """Delete record from Oracle database"""
    logger.info(f"Deleting record ID: {record_id}")
    url = f"{ORACLE_URL}{record_id}"
    return await make_oracle_request("DELETE", url)

# Bulk operations for dashboard
@app.get("/oracle/table1_11/stats/summary")
async def get_summary_stats():
    """Get summary statistics for dashboard"""
    try:
        data = await make_oracle_request("GET", ORACLE_URL)
        records = data.get("items", [])
        
        # Calculate statistics
        total_records = len(records)
        pending_orders = len([r for r in records if r.get("status") == "Pending"])
        total_revenue = sum(float(r.get("total_amount", 0)) for r in records)
        
        # Find top product
        products = {}
        for record in records:
            product = record.get("product_name")
            if product:
                products[product] = products.get(product, 0) + 1
        
        top_product = max(products.items(), key=lambda x: x[1])[0] if products else "None"
        
        return {
            "total_records": total_records,
            "pending_orders": pending_orders,
            "total_revenue": total_revenue,
            "top_product": top_product,
            "last_updated": requests.get("http://worldtimeapi.org/api/timezone/Asia/Riyadh").json()["datetime"]
        }
    except Exception as e:
        logger.error(f"Stats calculation error: {str(e)}")
        return {
            "total_records": 0,
            "pending_orders": 0,
            "total_revenue": 0,
            "top_product": "Error",
            "error": str(e)
        }

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "details": str(exc)}
    )

# Development server configuration
if __name__ == "__main__":
    # For development - use uvicorn with SSL
    uvicorn.run(
        "proxy:app",
        host="0.0.0.0",
        port=3000,
        reload=True,
        log_level="info",
        # For HTTPS (production):
        # ssl_keyfile="path/to/private.key",
        # ssl_certfile="path/to/certificate.crt"
    )