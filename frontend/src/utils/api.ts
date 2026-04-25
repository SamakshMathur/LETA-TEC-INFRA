import axios from 'axios';

export const AXIOS_INSTANCE = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

// Custom instance to be used by generated services
export const customInstance = <T>(config: any): Promise<T> => {
  return AXIOS_INSTANCE(config).then((response) => response.data);
};
