# src/tools/supabase_tool.py
from supabase import create_client, Client
import asyncpg
import asyncio
from typing import Dict, Any, List, Optional
import os
from datetime import datetime
from decimal import Decimal
import uuid
import json
from urllib.parse import urlparse

class SupabaseTool:
    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        
        # Parse database URL for asyncpg
        parsed = urlparse(self.database_url)
        self.db_config = {
            'host': parsed.hostname,
            'port': parsed.port,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path[1:]  # Remove leading '/'
        }
        
        # Initialize Supabase client if credentials available
        if self.supabase_url and self.supabase_key:
            self.client: Client = create_client(self.supabase_url, self.supabase_key)
        else:
            self.client = None
            
        self.pool = None
    
    async def init_pool(self):
        """Initialize connection pool"""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                host=self.db_config['host'],
                port=self.db_config['port'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                database=self.db_config['database'],
                min_size=1,
                max_size=10
            )
    
    async def close_pool(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
    
    async def save_invoice(self, invoice_data: Dict[str, Any]) -> str:
        """Save complete invoice data to Supabase using direct PostgreSQL"""
        
        await self.init_pool()
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    invoice_id = str(uuid.uuid4())
                    
                    # 1. Insert main invoice record
                    await conn.execute("""
                        INSERT INTO invoices (
                            id, invoice_number, invoice_date, due_date, 
                            invoice_type, total_amount, currency, 
                            ocr_confidence_score, status, source_file_url
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """, 
                        invoice_id,
                        invoice_data["invoice_info"]["invoice_number"],
                        datetime.strptime(invoice_data["invoice_info"]["invoice_date"], "%Y-%m-%d").date() if invoice_data["invoice_info"].get("invoice_date") else None,
                        datetime.strptime(invoice_data["invoice_info"]["due_date"], "%Y-%m-%d").date() if invoice_data["invoice_info"].get("due_date") else None,
                        invoice_data["invoice_info"].get("invoice_type", "STANDARD"),
                        float(invoice_data["summary"]["total_amount_due"]),
                        "USD",
                        float(invoice_data["confidence_scores"]["overall"]),
                        "PROCESSED",
                        invoice_data.get("source_file_url")
                    )
                    
                    # 2. Insert seller information
                    if invoice_data.get("seller"):
                        await conn.execute("""
                            INSERT INTO sellers (
                                invoice_id, name, address, contact_information, 
                                tax_id, email, phone
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                            invoice_id,
                            invoice_data["seller"].get("name"),
                            invoice_data["seller"].get("address"),
                            invoice_data["seller"].get("contact_information"),
                            invoice_data["seller"].get("tax_id"),
                            invoice_data["seller"].get("email"),
                            invoice_data["seller"].get("phone")
                        )
                    
                    # 3. Insert buyer information
                    if invoice_data.get("buyer"):
                        await conn.execute("""
                            INSERT INTO buyers (
                                invoice_id, name, address, contact_information,
                                tax_id, email, phone
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """,
                            invoice_id,
                            invoice_data["buyer"].get("name"),
                            invoice_data["buyer"].get("address"),
                            invoice_data["buyer"].get("contact_information"),
                            invoice_data["buyer"].get("tax_id"),
                            invoice_data["buyer"].get("email"),
                            invoice_data["buyer"].get("phone")
                        )
                    
                    # 4. Insert line items
                    for item in invoice_data.get("items", []):
                        await conn.execute("""
                            INSERT INTO invoice_items (
                                invoice_id, item_description, item_code,
                                quantity, unit_price, discount_percentage,
                                discount_amount, tax_rate, tax_amount, line_total
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        """,
                            invoice_id,
                            item.get("description"),
                            item.get("code"),
                            float(item.get("quantity", 0)),
                            float(item.get("unit_price", 0)),
                            float(item.get("discount_percentage", 0)),
                            float(item.get("discount_amount", 0)),
                            float(item.get("tax_rate", 0)),
                            float(item.get("tax_amount", 0)),
                            float(item.get("line_total", 0))
                        )
                    
                    # 5. Insert summary
                    await conn.execute("""
                        INSERT INTO invoice_summary (
                            invoice_id, subtotal, total_discount, total_tax,
                            shipping_cost, total_amount_due
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                        invoice_id,
                        float(invoice_data["summary"].get("subtotal", 0)),
                        float(invoice_data["summary"].get("total_discount", 0)),
                        float(invoice_data["summary"].get("total_tax", 0)),
                        float(invoice_data["summary"].get("shipping_cost", 0)),
                        float(invoice_data["summary"].get("total_amount_due", 0))
                    )
                    
                    # 6. Insert payment information
                    if invoice_data.get("payment"):
                        await conn.execute("""
                            INSERT INTO payment_information (
                                invoice_id, payment_terms, payment_method,
                                bank_account_details, payment_status
                            ) VALUES ($1, $2, $3, $4, $5)
                        """,
                            invoice_id,
                            invoice_data["payment"].get("terms"),
                            invoice_data["payment"].get("method"),
                            invoice_data["payment"].get("bank_details"),
                            "UNPAID"
                        )
                    
                    # 7. Insert metadata
                    await conn.execute("""
                        INSERT INTO invoice_metadata (
                            invoice_id, po_number, notes, terms_and_conditions,
                            ocr_raw_data, custom_fields
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                        invoice_id,
                        invoice_data["invoice_info"].get("po_number"),
                        invoice_data.get("additional", {}).get("notes"),
                        invoice_data.get("additional", {}).get("terms_and_conditions"),
                        json.dumps(invoice_data),
                        json.dumps({})
                    )
                    
                    # 8. Log processing history
                    await conn.execute("""
                        INSERT INTO processing_history (
                            invoice_id, action, status, details, performed_by
                        ) VALUES ($1, $2, $3, $4, $5)
                    """,
                        invoice_id,
                        "INVOICE_CREATED",
                        "SUCCESS",
                        json.dumps({"source": "OCR_PROCESSING"}),
                        "system"
                    )
                    
                    return invoice_id
                    
                except Exception as e:
                    raise Exception(f"Failed to save invoice: {str(e)}")
    
    async def get_invoice(self, invoice_id: str = None, invoice_number: str = None) -> Optional[Dict]:
        """Retrieve invoice by ID or invoice number"""
        
        await self.init_pool()
        
        async with self.pool.acquire() as conn:
            try:
                # Build query
                if invoice_id:
                    query = """
                        SELECT * FROM invoices WHERE id = $1
                    """
                    param = invoice_id
                elif invoice_number:
                    query = """
                        SELECT * FROM invoices WHERE invoice_number = $1
                    """
                    param = invoice_number
                else:
                    return None
                
                # Fetch invoice
                invoice_row = await conn.fetchrow(query, param)
                
                if not invoice_row:
                    return None
                
                invoice_data = dict(invoice_row)
                invoice_id = invoice_data["id"]
                
                # Fetch related data
                seller_row = await conn.fetchrow(
                    "SELECT * FROM sellers WHERE invoice_id = $1", invoice_id
                )
                invoice_data["seller"] = dict(seller_row) if seller_row else None
                
                buyer_row = await conn.fetchrow(
                    "SELECT * FROM buyers WHERE invoice_id = $1", invoice_id
                )
                invoice_data["buyer"] = dict(buyer_row) if buyer_row else None
                
                items_rows = await conn.fetch(
                    "SELECT * FROM invoice_items WHERE invoice_id = $1", invoice_id
                )
                invoice_data["items"] = [dict(row) for row in items_rows]
                
                summary_row = await conn.fetchrow(
                    "SELECT * FROM invoice_summary WHERE invoice_id = $1", invoice_id
                )
                invoice_data["summary"] = dict(summary_row) if summary_row else None
                
                payment_row = await conn.fetchrow(
                    "SELECT * FROM payment_information WHERE invoice_id = $1", invoice_id
                )
                invoice_data["payment"] = dict(payment_row) if payment_row else None
                
                return invoice_data
                
            except Exception as e:
                print(f"Error fetching invoice: {str(e)}")
                return None
    
    async def execute_query(self, query: str, params: List = None) -> Dict[str, Any]:
        """Execute a raw SQL query"""
        
        await self.init_pool()
        
        async with self.pool.acquire() as conn:
            try:
                if query.strip().upper().startswith("SELECT"):
                    rows = await conn.fetch(query, *(params or []))
                    return {
                        "success": True,
                        "data": [dict(row) for row in rows],
                        "row_count": len(rows)
                    }
                else:
                    result = await conn.execute(query, *(params or []))
                    return {
                        "success": True,
                        "data": None,
                        "row_count": int(result.split()[-1]) if result else 0
                    }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "data": None
                }