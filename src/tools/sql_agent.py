import os
import json
import asyncio
import google.generativeai as genai
from typing import Dict, Any
class InvoiceSQLAgent:
    """
    An intelligent SQL generation and execution agent for an invoice database.
    Uses Google Gemini API to convert natural language questions into PostgreSQL queries
    and summarize the results in human-readable form.
    """

    def __init__(self, supabase_tool):
        # Configure Gemini API using environment variable
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("Missing GOOGLE_API_KEY in environment variables.")

        genai.configure(api_key=api_key)
        self.supabase_tool = supabase_tool
        self.llm = genai.GenerativeModel("gemini-1.5-pro")

        # System-level schema context for the model
        self.system_prompt = """
        You are an SQL expert for a PostgreSQL invoice database. The database has these tables:

        1. invoices: Main invoice information
           - id (UUID), invoice_number (VARCHAR), invoice_date (DATE), due_date (DATE),
             invoice_type (VARCHAR), status (VARCHAR), total_amount (DECIMAL), currency (VARCHAR),
             ocr_confidence_score (DECIMAL), created_at (TIMESTAMP), updated_at (TIMESTAMP)

        2. sellers: Seller/vendor information
           - id (UUID), invoice_id (UUID), name (VARCHAR), address (TEXT),
             contact_information (TEXT), tax_id (VARCHAR), email (VARCHAR), phone (VARCHAR)

        3. buyers: Customer information
           - id (UUID), invoice_id (UUID), name (VARCHAR), address (TEXT),
             contact_information (TEXT), tax_id (VARCHAR), email (VARCHAR), phone (VARCHAR)

        4. invoice_items: Line items
           - id (UUID), invoice_id (UUID), item_description (TEXT), item_code (VARCHAR),
             quantity (DECIMAL), unit_price (DECIMAL), discount_percentage (DECIMAL),
             tax_rate (DECIMAL), line_total (DECIMAL)

        5. invoice_summary: Totals and summary
           - id (UUID), invoice_id (UUID), subtotal (DECIMAL), total_discount (DECIMAL),
             total_tax (DECIMAL), shipping_cost (DECIMAL), total_amount_due (DECIMAL)

        6. payment_information: Payment details
           - id (UUID), invoice_id (UUID), payment_terms (VARCHAR), payment_method (VARCHAR),
             payment_status (VARCHAR), paid_amount (DECIMAL), payment_date (DATE)

        Generate PostgreSQL queries for user questions.

        Rules:
        - Return ONLY the SQL query (no explanation, no markdown).
        - Use JOINs when pulling from multiple tables.
        - Use PostgreSQL syntax (ILIKE for case-insensitive search, :: for casting).
        - Always limit results to 100 rows unless specified otherwise.
        - Format dates using TO_CHAR for readability.
        - Use table aliases for clarity when necessary.
        """

    # --------------------------------------------------------------------------------
    async def generate_query(self, user_question: str) -> str:
        """
        Generate a SQL query from a natural language question using Gemini.
        Returns the clean SQL string.
        """
        prompt = f"{self.system_prompt}\n\nUser Question: {user_question}\nSQL Query:"

        response = await asyncio.to_thread(self.llm.generate_content, prompt)
        sql_query = response.text.strip()

        # Remove markdown or fenced code blocks
        if "```" in sql_query:
            sql_query = sql_query.split("```")[1].replace("sql", "").strip()

        # Start from first SELECT statement
        lines = sql_query.split("\n")
        for i, line in enumerate(lines):
            if line.strip().upper().startswith("SELECT"):
                sql_query = "\n".join(lines[i:])
                break

        return sql_query.strip()

    # --------------------------------------------------------------------------------
    async def execute_query(self, query: str) -> Dict[str, Any]:
        """
        Execute a SQL query via the Supabase tool.
        The Supabase tool must have an async `execute_query(query)` method.
        """
        return await self.supabase_tool.execute_query(query)

    # --------------------------------------------------------------------------------
    async def answer_question(self, question: str) -> str:
        """
        End-to-end process:
        1. Generate SQL query from natural language.
        2. Execute the query via Supabase.
        3. Use Gemini to summarize the results in natural language.
        """
        try:
            # Step 1: Generate SQL
            query = await self.generate_query(question)
            print(f"[SQL_AGENT] Generated Query:\n{query}")

            # Step 2: Execute SQL
            result = await self.execute_query(query)

            if not result.get("success"):
                return f"❌ Error executing query: {result.get('error')}"

            data = result.get("data", [])
            if not data:
                return "No data found for your query."

            # Step 3: Summarize with Gemini
            summary_prompt = f"""
            You are an expert data summarizer.
            Provide a concise, clear answer based on the SQL query result below.

            Question: {question}
            SQL Result (first 10 rows): {json.dumps(data[:10], indent=2)}

            Guidelines:
            - Use bullet points for multiple items.
            - Format monetary values with currency symbols (e.g., $123.45).
            - Format dates as "Jan 15, 2024".
            - If it's a summary (totals, averages), mention key metrics clearly.
            - If it's a list, summarize common trends or counts.
            """

            response = await asyncio.to_thread(self.llm.generate_content, summary_prompt)
            return response.text.strip()

        except Exception as e:
            return f"⚠️ Error processing query: {str(e)}"

