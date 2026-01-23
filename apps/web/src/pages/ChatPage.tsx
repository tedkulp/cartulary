import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { chatService } from '../services'
import type { ChatMessage, DocumentSource } from '@cartulary/shared'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Send, Loader2, MessageSquare, FileText, ExternalLink } from 'lucide-react'
import { toast } from 'sonner'

interface MessageWithSources extends ChatMessage {
  sources?: DocumentSource[]
}

export default function ChatPage() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState<MessageWithSources[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')

    // Add user message to chat
    const newUserMessage: MessageWithSources = {
      role: 'user',
      content: userMessage,
    }
    setMessages((prev) => [...prev, newUserMessage])

    setIsLoading(true)
    try {
      // Send to backend
      const response = await chatService.sendMessage(
        userMessage,
        messages.map((m) => ({ role: m.role, content: m.content }))
      )

      // Add assistant response
      const assistantMessage: MessageWithSources = {
        role: 'assistant',
        content: response.answer,
        sources: response.sources,
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (error) {
      console.error('Chat error:', error)
      toast.error('Failed to get response. Please try again.')
      
      // Add error message
      const errorMessage: MessageWithSources = {
        role: 'assistant',
        content: 'I encountered an error processing your question. Please try again.',
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const clearChat = () => {
    setMessages([])
    setInput('')
    inputRef.current?.focus()
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-3xl font-bold">Chat with Documents</h1>
          <p className="text-muted-foreground">Ask questions about your documents</p>
        </div>
        {messages.length > 0 && (
          <Button variant="outline" onClick={clearChat}>
            Clear Chat
          </Button>
        )}
      </div>

      {/* Messages Area */}
      <Card className="flex-1 flex flex-col overflow-hidden">
        <CardContent className="flex-1 overflow-y-auto p-6 space-y-4">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
              <MessageSquare className="h-16 w-16 text-muted-foreground" />
              <div>
                <h3 className="text-lg font-medium mb-2">Start a conversation</h3>
                <p className="text-muted-foreground max-w-md">
                  Ask questions about your documents. I'll search through them and provide answers based on their content.
                </p>
              </div>
              <div className="text-sm text-muted-foreground space-y-1">
                <p className="font-medium">Try asking:</p>
                <p>"What documents do I have about taxes?"</p>
                <p>"Summarize the contract from ABC Corp"</p>
                <p>"When was the invoice from XYZ dated?"</p>
              </div>
            </div>
          ) : (
            <>
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-lg p-4 ${
                      message.role === 'user'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted'
                    }`}
                  >
                    <div className="whitespace-pre-wrap break-words">{message.content}</div>
                    
                    {/* Sources */}
                    {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-border/50 space-y-2">
                        <div className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                          <FileText className="h-3 w-3" />
                          Sources:
                        </div>
                        <div className="space-y-1">
                          {message.sources.map((source) => (
                            <button
                              key={source.id}
                              onClick={() => navigate(`/documents/${source.id}`)}
                              className="flex items-center gap-2 text-xs hover:underline text-left w-full group"
                            >
                              <Badge variant="secondary" className="text-xs">
                                {(source.score * 100).toFixed(0)}%
                              </Badge>
                              <span className="flex-1 truncate">{source.title}</span>
                              <ExternalLink className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              
              {isLoading && (
                <div className="flex justify-start">
                  <div className="bg-muted rounded-lg p-4">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </>
          )}
        </CardContent>

        {/* Input Area */}
        <div className="border-t p-4">
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask a question about your documents..."
              disabled={isLoading}
              className="flex-1"
            />
            <Button onClick={handleSend} disabled={!input.trim() || isLoading}>
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}
