import type { AxiosInstance } from 'axios'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface DocumentSource {
  id: string
  title: string
  score: number
}

export interface ChatResponse {
  answer: string
  sources: DocumentSource[]
  chunks_used: string[]
}

export interface ChatRequest {
  question: string
  conversation_history?: ChatMessage[]
  num_chunks?: number
}

/**
 * Chat service for RAG-based document Q&A
 */
export class ChatService {
  constructor(private api: AxiosInstance) {}

  async sendMessage(
    question: string,
    conversationHistory: ChatMessage[] = [],
    numChunks: number = 5
  ): Promise<ChatResponse> {
    const { data } = await this.api.post<ChatResponse>('/api/v1/chat/', {
      question,
      conversation_history: conversationHistory,
      num_chunks: numChunks,
    } as ChatRequest)
    return data
  }
}
