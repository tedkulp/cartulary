#!/usr/bin/env python3
"""Test just the database query."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

print("Step 1: Import database")
from app.database import SessionLocal
from sqlalchemy import text
print("✓ Imports successful\n")

print("Step 2: Create session")
db = SessionLocal()
print("✓ Session created\n")

print("Step 3: Execute query")
result = db.execute(text("SELECT id, length(ocr_text), substring(ocr_text, 1, 100) FROM documents WHERE id = '3c78c4c1-7820-479e-b9dd-3d77acd60ba7'"))
print("✓ Query executed\n")

print("Step 4: Fetch result")
row = result.fetchone()
print(f"✓ Got row: {row}\n")

print("Step 5: Close session")
db.close()
print("✓ Session closed\n")

print("SUCCESS!")
