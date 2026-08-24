export interface KnowledgeDocument {
  document_id: string;
  title: string;
  filename: string;
  category: string;
  document_type: string;
  tags: string[];
  uploader: string;
  uploaded_at: string;
  effective_date: string;
  version: number;
  status: string;
  chunk_count: number;
  is_active: boolean;
  sha256: string;
  file_path: string;
  error_message?: string;
  last_modified?: string;
}

export interface AuditLog {
  timestamp: string;
  user_id: string;
  action: string;
  document_id?: string;
  details: string;
}

export interface CategoryInfo {
  folder: string;
  files: number;
  exists?: boolean;
}

export interface SystemStatus {
  faiss_index: {
    total_vectors: number;
    dimension: number;
    status: string;
    error?: string;
  };
  chunks_in_corpus: number;
  categories: Record<string, CategoryInfo>;
  admin?: string;
}

export interface IngestionJob {
  job_id: string;
  status: string;
  files: string[];
  category: string;
  started_at: string;
  results: Array<{ file: string; status: string; chunks_added?: number; error?: string }>;
  uploaded_by: string;
  total_chunks_added?: number;
  finished_at?: string;
}
