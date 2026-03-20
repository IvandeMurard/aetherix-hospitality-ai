/**
 * API client for F&B Operations Agent backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Make a fetch request to the API
 */
async function apiRequest<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  // Ensure endpoint starts with /
  const path = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  const url = `${API_BASE_URL}${path}`;

  // Validate URL scheme
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    throw new Error(
      `Invalid API URL: ${url}. URL scheme must be "http" or "https" for CORS request.`
    );
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `API request failed: ${response.status} ${response.statusText}. ${errorText}`
      );
    }

    return response.json();
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error(
        `Failed to fetch from ${url}. Possible reasons: CORS, Network Failure, or invalid URL scheme.`
      );
    }
    throw error;
  }
}

/**
 * API methods
 */
export const api = {
  /**
   * Health check
   */
  async health() {
    return apiRequest<{ status: string }>('/health');
  },

  /**
   * Get root endpoint info
   */
  async root() {
    return apiRequest<{
      name: string;
      version: string;
      status: string;
      docs: string;
    }>('/');
  },

  /**
   * Test Claude connection
   */
  async testClaude() {
    return apiRequest<{ status: string; message?: string }>('/test/claude');
  },

  /**
   * Test Qdrant connection
   */
  async testQdrant() {
    return apiRequest<{ status: string; message?: string }>('/test/qdrant');
  },
};

export default api;
