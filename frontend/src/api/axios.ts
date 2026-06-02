import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8001/api',
});

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    

    const authPaths = ['/auth/login/', '/auth/register/'];
    const isAuthPath = authPaths.some(path => config.url?.endsWith(path));

    if (token && !isAuthPath) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    
    if (error.response && error.response.status === 401) {
      const isLoginRequest = error.config?.url?.includes('/auth/login/');

      if (!isLoginRequest) {

        localStorage.clear(); 
        
        
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
    }

    return Promise.reject(error);
  }
);

export default api;