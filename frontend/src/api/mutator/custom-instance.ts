import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type AxiosResponse,
} from 'axios';

const BASE_URL = import.meta.env.PROD ? 'https://api.letatec.com' : 'http://localhost:8000';

export const AXIOS_INSTANCE = axios.create({ baseURL: BASE_URL });

export function customInstance<T>(
  config: AxiosRequestConfig,
  options?: AxiosRequestConfig,
): Promise<T> {
  return AXIOS_INSTANCE({
    ...config,
    ...options,
    headers: { ...config.headers, ...options?.headers },
  }).then((response: AxiosResponse<T>) => response.data);
}

export type ErrorType<TError> = AxiosError<TError>;
