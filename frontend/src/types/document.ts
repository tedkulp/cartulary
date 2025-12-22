export interface Tag {
  id: string
  name: string
  color?: string
  description?: string
  created_at: string
}

export interface Document {
  id: string
  title: string
  original_filename: string
  file_size: number
  mime_type: string
  file_extension: string
  checksum: string
  processing_status: string
  ocr_text?: string
  created_at: string
  updated_at: string
  tags: Tag[]
  extracted_title?: string
  extracted_date?: string
  extracted_sender?: string
  extracted_recipient?: string
}

export interface DocumentUploadData {
  file: File
  title?: string
}
