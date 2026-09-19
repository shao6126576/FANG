// API基础配置
const API_BASE_URL = '/api/v1';

// 统一的API请求函数
async function apiRequest(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    
    const config = {
        headers: {
            'Content-Type': 'application/json',
        },
        ...options
    };
    
    if (options.body) {
        config.body = JSON.stringify(options.body);
    }
    
    try {
        console.log('发送请求到:', url, config);
        const response = await fetch(url, config);
        
        console.log('收到响应:', response.status, response.statusText);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('API错误响应:', errorText);
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
        }
        
        const responseData = await response.json();
        console.log('响应数据:', responseData);
        return responseData;
    } catch (error) {
        console.error('API请求失败:', error);
        throw error;
    }
}

// 问答API
const chatAPI = {
    // 发送问题（非流式）
    askQuestion: async (question) => {
        return await apiRequest('/ask', {
            method: 'POST',
            body: { question }
        });
    },

    // 流式发送问题
    askQuestionStream: async (question, onChunk, onComplete, onError) => {
        try {
            const response = await fetch(`${API_BASE_URL}/ask/stream`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question: question })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    if (onComplete) onComplete();
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || '';

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.substring(6);
                        if (data === '[DONE]') {
                            if (onComplete) onComplete();
                            return;
                        }
                        
                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.error) {
                                if (onError) onError(parsed.error);
                            } else if (parsed.content) {
                                if (onChunk) onChunk(parsed.content);
                            }
                        } catch (e) {
                            console.error('解析流式数据失败:', e);
                        }
                    }
                }
            }
        } catch (error) {
            if (onError) onError(error.message);
        }
    },
    
    // 搜索产品
    searchProducts: async (query = '') => {
        return await apiRequest(`/products?query=${encodeURIComponent(query)}`);
    },
    
    // 搜索疾病
    searchDiseases: async (keyword) => {
        return await apiRequest(`/diseases?keyword=${encodeURIComponent(keyword)}`);
    },
    
    // 分析图片
    analyzeImage: async (file, prompt) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('prompt', prompt || '');
        
        const response = await fetch(`${API_BASE_URL}/analyze-image`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    }
};

// 产品API
const productAPI = {
    // 获取产品列表
    getProducts: async (page = 1, limit = 20) => {
        return await apiRequest(`/products?page=${page}&limit=${limit}`);
    },
    
    // 获取产品详情
    getProductDetail: async (productId) => {
        return await apiRequest(`/products/${productId}`);
    },
    
    // 对比产品
    compareProducts: async (productIds) => {
        return await apiRequest('/products/compare', {
            method: 'POST',
            body: { productIds }
        });
    }
};

// 案例API
const caseAPI = {
    // 获取案例列表
    getCases: async (page = 1, limit = 10, category = '') => {
        let url = `/cases?page=${page}&limit=${limit}`;
        if (category) {
            url += `&category=${encodeURIComponent(category)}`;
        }
        return await apiRequest(url);
    },
    
    // 获取案例详情
    getCaseDetail: async (caseId) => {
        return await apiRequest(`/cases/${caseId}`);
    },
    
    // 搜索案例
    searchCases: async (keyword) => {
        return await apiRequest(`/cases/search?keyword=${encodeURIComponent(keyword)}`);
    }
};

// 反馈API
const feedbackAPI = {
    // 提交反馈
    submitFeedback: async (feedbackData) => {
        return await apiRequest('/feedback', {
            method: 'POST',
            body: feedbackData
        });
    },
    
    // 获取反馈列表
    getFeedbacks: async (page = 1, limit = 10) => {
        return await apiRequest(`/feedback?page=${page}&limit=${limit}`);
    }
};

// 将API设置为全局变量
window.chatAPI = chatAPI;
window.productAPI = productAPI;
window.caseAPI = caseAPI;
window.feedbackAPI = feedbackAPI;