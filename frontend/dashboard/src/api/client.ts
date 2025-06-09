import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Invoice {
  id: number;
  stripe_invoice_id: string;
  provider: string;
  status: string;
  invoice_number?: string;
  customer_name?: string;
  customer_email?: string;
  customer_tax_id?: string;
  amount: number;
  currency: string;
  created_at: string;
  updated_at: string;
  error_message?: string;
  pdf_url?: string;
  xml_content?: string;
}

export interface ProcessingHistory {
  id: number;
  invoice_id: number;
  action: string;
  status: string;
  error_message?: string;
  created_at: string;
}

export interface RetryQueueItem {
  id: number;
  invoice_id: number;
  retry_count: number;
  next_retry_at: string;
  max_retries: number;
  error_message?: string;
  created_at: string;
}

export interface ProviderStats {
  provider: string;
  total_invoices: number;
  successful: number;
  failed: number;
  pending: number;
  success_rate: number;
}

export interface DashboardStats {
  total_invoices: number;
  total_amount: number;
  providers: ProviderStats[];
  recent_activity: ProcessingHistory[];
}

export const api = {
  invoices: {
    getAll: async (params?: { 
      provider?: string; 
      status?: string; 
      start_date?: string; 
      end_date?: string;
      search?: string;
    }) => {
      const response = await apiClient.get<Invoice[]>('/api/dashboard/invoices', { params });
      return response.data;
    },
    
    getById: async (id: number) => {
      const response = await apiClient.get<Invoice>(`/api/dashboard/invoices/${id}`);
      return response.data;
    },
    
    retry: async (id: number) => {
      const response = await apiClient.post(`/api/dashboard/invoices/${id}/retry`);
      return response.data;
    },
    
    getHistory: async (id: number) => {
      const response = await apiClient.get<ProcessingHistory[]>(`/api/dashboard/invoices/${id}/history`);
      return response.data;
    }
  },
  
  retryQueue: {
    getAll: async () => {
      const response = await apiClient.get<RetryQueueItem[]>('/api/dashboard/retry-queue');
      return response.data;
    },
    
    remove: async (id: number) => {
      const response = await apiClient.delete(`/api/dashboard/retry-queue/${id}`);
      return response.data;
    }
  },
  
  dashboard: {
    getStats: async () => {
      const response = await apiClient.get<DashboardStats>('/api/dashboard/stats');
      return response.data;
    }
  },
  
  providers: {
    getAll: async () => {
      const response = await apiClient.get<string[]>('/api/providers/names');
      return response.data;
    },
    
    validate: async (provider: string) => {
      const response = await apiClient.post(`/api/providers/${provider}/validate`);
      return response.data;
    }
  }
};

export default apiClient;