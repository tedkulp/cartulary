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

/**
 * Where a Document is in processing: the seven statuses the backend stores, and the
 * same vocabulary as `ProcessingStatus` in `app/processing/stages.py`. Anything that
 * renders a status switches on this rather than on bare strings.
 */
export type ProcessingStatus =
  | 'pending'
  | 'processing'
  | 'ocr_complete'
  | 'ocr_failed'
  | 'embedding_complete'
  | 'llm_complete'
  | 'failed'

export interface Document {
  id: string
  title: string
  description?: string
  original_filename: string
  file_size: number
  mime_type: string
  file_extension: string
  checksum: string
  processing_status: ProcessingStatus
  ocr_text?: string
  ocr_text_manually_edited: boolean
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

export interface DocumentOCRTextUpdate {
  ocr_text: string
}
