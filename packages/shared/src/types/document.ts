export interface Tag {
  id: string
  name: string
  color?: string
  description?: string
  created_at: string
}

export interface TagCreate {
  name: string
  color?: string
  description?: string
}

export interface TagUpdate {
  name?: string
  color?: string
  description?: string
}

export interface Document {
  id: string
  title: string
  description?: string
  original_filename: string
  file_size: number
  mime_type: string
  file_extension: string
  checksum: string
  processing_status: string
  ocr_text?: string
  created_at: string
  updated_at: string
  uploaded_by?: string
  tags: Tag[]
  // LLM-extracted metadata
  extracted_title?: string
  extracted_correspondent?: string
  extracted_date?: string
  extracted_document_type?: string
  extracted_summary?: string
}

export interface DocumentUploadData {
  file: File
  title?: string
}
