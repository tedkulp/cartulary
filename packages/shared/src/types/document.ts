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

/**
 * What a status means to a reader: the seven statuses grouped by the distinctions
 * anything rendering one actually draws. `stage_complete` and `complete` are apart
 * because a Document that has only been read is not one that has been described —
 * a surface that says "ready" may only say it of `complete`. This is the decision
 * each app was making for itself; the app maps the group to its own vocabulary —
 * Tailwind classes on web, `StyleSheet` entries on mobile — and no app repeats the
 * cascade.
 */
export type ProcessingStatusGroup =
  | 'queued'
  | 'in_flight'
  | 'stage_complete'
  | 'complete'
  | 'failed'

/**
 * The group a status belongs to. Exhaustive over `ProcessingStatus`, so adding a
 * status is a compile error here and nowhere else.
 */
export function processingStatusGroup(status: ProcessingStatus): ProcessingStatusGroup {
  switch (status) {
    case 'pending':
      return 'queued'
    case 'processing':
      return 'in_flight'
    case 'ocr_complete':
    case 'embedding_complete':
      return 'stage_complete'
    case 'llm_complete':
      return 'complete'
    case 'ocr_failed':
    case 'failed':
      return 'failed'
  }
}

/**
 * How a status reads on screen: underscores to spaces, upper case, with OCR and LLM
 * kept as the acronyms they are.
 */
export function formatProcessingStatus(status: ProcessingStatus): string {
  return status
    .replace(/_/g, ' ')
    .replace(/ocr/gi, 'OCR')
    .replace(/llm/gi, 'LLM')
    .toUpperCase()
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
