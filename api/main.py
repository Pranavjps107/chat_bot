# api/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import uuid
from pathlib import Path
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

load_dotenv()  # <-- loads the .env file

# Import our modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.graph import InvoiceProcessingWorkflow
from src.tools.supabase_tool import SupabaseTool
from src.tools.sql_agent import InvoiceSQLAgent

# Global instances
workflow = None
supabase_tool = None
sql_agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global workflow, supabase_tool, sql_agent
    
    # Startup
    print("Starting up application...")
    workflow = InvoiceProcessingWorkflow()
    supabase_tool = SupabaseTool()
    await supabase_tool.init_pool()
    sql_agent = InvoiceSQLAgent(supabase_tool)
    
    yield
    
    # Shutdown
    print("Shutting down application...")
    if supabase_tool:
        await supabase_tool.close_pool()

# Initialize FastAPI with lifespan
app = FastAPI(
    title="Invoice Processing API",
    version="1.0.0",
    description="AI-powered invoice processing with OCR and SQL query capabilities",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Request/Response models (same as before)
class ProcessInvoiceRequest(BaseModel):
    query: Optional[str] = None

class ProcessInvoiceResponse(BaseModel):
    invoice_id: str
    status: str
    invoice_number: Optional[str]
    total_amount: Optional[float]
    confidence_score: Optional[float]
    errors: List[str]
    warnings: List[str]
    processing_time: float

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    query: str
    answer: str
    sql_generated: Optional[str]
    execution_time: float
    success: bool
    error: Optional[str]

# Endpoints
@app.get("/")
async def root():
    return {
        "message": "Invoice Processing API",
        "version": "1.0.0",
        "database": "PostgreSQL (Supabase)",
        "endpoints": {
            "POST /process-invoice": "Upload and process an invoice image",
            "POST /query": "Query invoice data using natural language",
            "GET /invoice/{invoice_id}": "Get invoice details by ID",
            "POST /search": "Search invoices with filters",
            "GET /stats": "Get invoice statistics",
            "GET /health": "Health check"
        }
    }

@app.post("/process-invoice", response_model=ProcessInvoiceResponse)
async def process_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    query: Optional[str] = None
):
    """Process an uploaded invoice image"""
    start_time = datetime.now()
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Save uploaded file
    file_id = str(uuid.uuid4())
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "png"
    file_path = UPLOAD_DIR / f"{file_id}.{file_extension}"
    
    try:
        # Save file
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Process invoice
        result = await workflow.process_invoice(
            image_path=str(file_path),
            user_query=query
        )
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Extract key information for response
        processed_invoice = result.get("processed_invoice", {})
        validation_result = result.get("validation_result", {})
        
        response = ProcessInvoiceResponse(
            invoice_id=result.get("invoice_id", ""),
            status="SUCCESS" if result.get("db_status") == "saved" else "FAILED",
            invoice_number=processed_invoice.get("invoice_number") if processed_invoice else None,
            total_amount=float(processed_invoice.get("summary", {}).get("total_amount_due", 0)) if processed_invoice else None,
            confidence_score=result.get("ocr_result", {}).get("confidence_scores", {}).get("overall") if result.get("ocr_result") else None,
            errors=result.get("errors", []),
            warnings=validation_result.get("warnings", []) if validation_result else [],
            processing_time=processing_time
        )
        
        # Clean up file in background
        background_tasks.add_task(cleanup_file, file_path)
        
        return response
        
    except Exception as e:
        # Clean up on error
        if file_path.exists():
            os.remove(file_path)
        
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query", response_model=QueryResponse)
async def query_invoices(request: QueryRequest):
    """Query invoice data using natural language"""
    start_time = datetime.now()
    
    try:
        # Generate SQL query
        sql_query = await sql_agent.generate_query(request.query)
        
        # Get answer
        answer = await sql_agent.answer_question(request.query)
        
        response = QueryResponse(
            query=request.query,
            answer=answer,
            sql_generated=sql_query,
            execution_time=(datetime.now() - start_time).total_seconds(),
            success=True,
            error=None
        )
        
        return response
        
    except Exception as e:
        return QueryResponse(
            query=request.query,
            answer="",
            sql_generated=None,
            execution_time=(datetime.now() - start_time).total_seconds(),
            success=False,
            error=str(e)
        )

@app.get("/stats")
async def get_statistics():
    """Get invoice statistics"""
    try:
        queries = {
            "total_invoices": "SELECT COUNT(*) as count FROM invoices",
            "total_amount": "SELECT SUM(total_amount) as total FROM invoices",
            "avg_confidence": "SELECT AVG(ocr_confidence_score) as avg FROM invoices WHERE ocr_confidence_score IS NOT NULL",
            "status_distribution": """
                SELECT status, COUNT(*) as count 
                FROM invoices 
                GROUP BY status
            """,
            "recent_invoices": """
                SELECT invoice_number, total_amount, invoice_date, status 
                FROM invoices 
                ORDER BY created_at DESC 
                LIMIT 5
            """,
            "top_buyers": """
                SELECT b.name, COUNT(*) as invoice_count, SUM(i.total_amount) as total_amount
                FROM buyers b
                JOIN invoices i ON b.invoice_id = i.id
                GROUP BY b.name
                ORDER BY total_amount DESC
                LIMIT 5
            """
        }
        
        stats = {}
        for key, query in queries.items():
            result = await supabase_tool.execute_query(query)
            if result["success"]:
                stats[key] = result["data"]
        
        return {
            "statistics": stats,
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        result = await supabase_tool.execute_query("SELECT 1")
        db_status = "healthy" if result["success"] else "unhealthy"
        
        return {
            "status": "healthy",
            "database": db_status,
            "timestamp": datetime.now().isoformat()
        }
    except:
        return {
            "status": "unhealthy",
            "database": "error",
            "timestamp": datetime.now().isoformat()
        }

# Helper functions
async def cleanup_file(file_path: Path):
    """Clean up uploaded file after processing"""
    try:
        if file_path.exists():
            os.remove(file_path)
    except Exception:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)