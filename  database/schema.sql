-- database/schema.sql

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Main invoice table
CREATE TABLE invoices (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    invoice_number VARCHAR(255) UNIQUE,
    invoice_date DATE,
    due_date DATE,
    invoice_type VARCHAR(100),
    status VARCHAR(50) DEFAULT 'PENDING',
    total_amount DECIMAL(15, 2),
    currency VARCHAR(10) DEFAULT 'USD',
    ocr_confidence_score DECIMAL(5, 2),
    source_file_url TEXT,
    processed_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Seller/Vendor information
CREATE TABLE sellers (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    name VARCHAR(500),
    address TEXT,
    contact_information TEXT,
    tax_id VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Buyer/Customer information
CREATE TABLE buyers (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    name VARCHAR(500),
    address TEXT,
    contact_information TEXT,
    tax_id VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Invoice line items
CREATE TABLE invoice_items (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    item_description TEXT,
    item_code VARCHAR(100),
    quantity DECIMAL(10, 3),
    unit_price DECIMAL(15, 4),
    discount_percentage DECIMAL(5, 2),
    discount_amount DECIMAL(15, 2),
    tax_rate DECIMAL(5, 2),
    tax_amount DECIMAL(15, 2),
    line_total DECIMAL(15, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Payment information
CREATE TABLE payment_information (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    payment_terms VARCHAR(255),
    payment_method VARCHAR(100),
    bank_account_details TEXT,
    payment_status VARCHAR(50) DEFAULT 'UNPAID',
    paid_amount DECIMAL(15, 2),
    payment_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Invoice summary/totals
CREATE TABLE invoice_summary (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    subtotal DECIMAL(15, 2),
    total_discount DECIMAL(15, 2),
    total_tax DECIMAL(15, 2),
    shipping_cost DECIMAL(15, 2),
    total_amount_due DECIMAL(15, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Additional metadata
CREATE TABLE invoice_metadata (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    po_number VARCHAR(255),
    terms_and_conditions TEXT,
    notes TEXT,
    custom_fields JSONB,
    ocr_raw_data JSONB,
    processing_logs JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Processing history for audit
CREATE TABLE processing_history (
    id UUID DEFAULT uuid_generate_v4() PRIMARY KEY,
    invoice_id UUID REFERENCES invoices(id) ON DELETE CASCADE,
    action VARCHAR(100),
    status VARCHAR(50),
    details JSONB,
    performed_by VARCHAR(255),
    performed_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX idx_invoices_invoice_number ON invoices(invoice_number);
CREATE INDEX idx_invoices_invoice_date ON invoices(invoice_date);
CREATE INDEX idx_invoices_status ON invoices(status);
CREATE INDEX idx_sellers_invoice_id ON sellers(invoice_id);
CREATE INDEX idx_buyers_invoice_id ON buyers(invoice_id);
CREATE INDEX idx_invoice_items_invoice_id ON invoice_items(invoice_id);
CREATE INDEX idx_payment_information_invoice_id ON payment_information(invoice_id);