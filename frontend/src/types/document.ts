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
  extracted_title?: string
  extracted_date?: string
  extracted_sender?: string
  extracted_recipient?: string
}

export interface DocumentUploadData {
  file: File
  title?: string
}
