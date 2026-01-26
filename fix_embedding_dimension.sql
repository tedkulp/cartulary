-- Fix embedding dimension from 384 to 768 for nomic-embed-text model
-- This will drop existing embeddings and recreate the column with correct dimensions

-- Drop the old embedding column (384 dimensions)
ALTER TABLE document_embeddings DROP COLUMN IF EXISTS embedding;

-- Add new embedding column with 768 dimensions
ALTER TABLE document_embeddings ADD COLUMN embedding vector(768);

-- Optional: Clear the embeddings table to regenerate all embeddings
-- TRUNCATE TABLE document_embeddings;

SELECT 'Embedding dimension updated to 768. Existing embeddings have been removed.' AS status;
