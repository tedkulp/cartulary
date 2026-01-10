import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  FileText,
  Search,
  Tags,
  Brain,
  Share2,
  FolderInput,
  Mail,
  Shield,
  Zap,
  Database,
  Cloud,
  Info,
} from 'lucide-react'

interface FeatureCardProps {
  icon: React.ReactNode
  title: string
  description: string
}

function FeatureCard({ icon, title, description }: FeatureCardProps) {
  return (
    <Card className="h-full">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <div className="text-primary">{icon}</div>
          <CardTitle className="text-lg">{title}</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  )
}

export default function AboutPage() {
  const version = '0.7.0'

  const features = [
    {
      icon: <FileText className="h-5 w-5" />,
      title: 'Document Management',
      description:
        'Upload, organize, and manage PDF files and images with automatic duplicate detection and secure storage.',
    },
    {
      icon: <Search className="h-5 w-5" />,
      title: 'Semantic Search',
      description:
        'Find documents using natural language with RAG-powered search that understands context and meaning.',
    },
    {
      icon: <Brain className="h-5 w-5" />,
      title: 'AI Metadata Extraction',
      description:
        'Automatically extract titles, dates, correspondents, and summaries using OpenAI, Gemini, or Ollama.',
    },
    {
      icon: <Tags className="h-5 w-5" />,
      title: 'Smart Tagging',
      description:
        'Organize documents with tags, including AI-suggested tags based on document content analysis.',
    },
    {
      icon: <Zap className="h-5 w-5" />,
      title: 'OCR Processing',
      description:
        'Automatic text extraction from scanned documents and images using advanced OCR technology.',
    },
    {
      icon: <Share2 className="h-5 w-5" />,
      title: 'Document Sharing',
      description:
        'Share documents with other users and control access permissions with role-based security.',
    },
    {
      icon: <FolderInput className="h-5 w-5" />,
      title: 'Directory Import',
      description:
        'Automatically import documents from watched directories with configurable move/delete options.',
    },
    {
      icon: <Mail className="h-5 w-5" />,
      title: 'Email Import',
      description:
        'Monitor IMAP mailboxes and automatically import email attachments as documents.',
    },
    {
      icon: <Shield className="h-5 w-5" />,
      title: 'Enterprise SSO',
      description:
        'Optional OIDC authentication support for enterprise single sign-on integration.',
    },
  ]

  const techStack = [
    { name: 'FastAPI', category: 'Backend' },
    { name: 'PostgreSQL', category: 'Database' },
    { name: 'pgvector', category: 'Vector Search' },
    { name: 'Redis', category: 'Cache & Queue' },
    { name: 'Celery', category: 'Task Queue' },
    { name: 'React', category: 'Frontend' },
    { name: 'TypeScript', category: 'Language' },
    { name: 'Tailwind CSS', category: 'Styling' },
    { name: 'Docker', category: 'Deployment' },
  ]

  return (
    <div className="container mx-auto py-6 space-y-8">
      {/* Header Section */}
      <div className="text-center space-y-4">
        <div className="flex items-center justify-center gap-2">
          <Database className="h-10 w-10 text-primary" />
          <h1 className="text-4xl font-bold">Cartulary</h1>
        </div>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          A modern digital archive system for organizing, searching, and managing your documents
          with AI-powered intelligence.
        </p>
        <Badge variant="secondary" className="text-sm">
          Version {version}
        </Badge>
      </div>

      {/* About Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Info className="h-5 w-5 text-primary" />
            <CardTitle>About Cartulary</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="prose prose-sm dark:prose-invert max-w-none">
          <p className="text-muted-foreground leading-relaxed">
            Cartulary is a comprehensive digital archive system designed to help individuals and
            organizations manage their documents efficiently. Inspired by systems like paperless-ngx,
            Cartulary goes further by integrating advanced AI capabilities for semantic search,
            automatic metadata extraction, and intelligent tagging.
          </p>
          <p className="text-muted-foreground leading-relaxed">
            Whether you're digitizing paper documents, organizing existing files, or processing
            email attachments, Cartulary provides a powerful, unified platform for document
            management with enterprise-grade security and modern search capabilities.
          </p>
        </CardContent>
      </Card>

      {/* Features Grid */}
      <div className="space-y-4">
        <h2 className="text-2xl font-semibold text-center">Features</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {features.map((feature, index) => (
            <FeatureCard
              key={index}
              icon={feature.icon}
              title={feature.title}
              description={feature.description}
            />
          ))}
        </div>
      </div>

      {/* Technology Stack */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Cloud className="h-5 w-5 text-primary" />
            <CardTitle>Technology Stack</CardTitle>
          </div>
          <CardDescription>
            Built with modern, reliable open-source technologies
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {techStack.map((tech, index) => (
              <Badge key={index} variant="outline" className="text-sm py-1 px-3">
                {tech.name}
                <span className="ml-1 text-muted-foreground">({tech.category})</span>
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Footer Info */}
      <div className="text-center text-sm text-muted-foreground space-y-2">
        <p>
          Cartulary is open source software. Contributions and feedback are welcome.
        </p>
        <p>
          Built with FastAPI, React, and PostgreSQL with pgvector for semantic search.
        </p>
      </div>
    </div>
  )
}
