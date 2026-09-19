// 页面切换功能
function switchPage(pageId) {
    // 隐藏所有页面
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    // 显示目标页面
    const targetPage = document.getElementById(pageId);
    if (targetPage) {
        targetPage.classList.add('active');
    }
    
    // 更新导航激活状态
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('data-page') === pageId) {
            link.classList.add('active');
        }
    });
    
    // 滚动到顶部
    window.scrollTo(0, 0);
    
    // 根据页面类型执行相应初始化
    switch(pageId) {
        case 'dispute':
            loadDisputeCases();
            break;
        case 'products':
            loadProducts();
            break;
        case 'feedback':
            loadUserComments();
            break;
        case 'chat':
            // 检查是否已有消息，如果没有则显示欢迎消息
            const messagesContainer = document.getElementById('chatMessages');
            if (messagesContainer && messagesContainer.children.length === 0) {
                clearChat();
            }
            break;
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化聊天功能
    initChat();
    
    // 初始化产品搜索
    initProductSearch();
    
    // 初始化页面
    initializePage();
    
    // 为导航链接添加点击事件
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const pageId = this.getAttribute('data-page');
            if (pageId) {
                switchPage(pageId);
            }
        });
    });
    
    // 也为href属性中的hash变化添加监听
    window.addEventListener('hashchange', function(e) {
        const hash = window.location.hash.substring(1); // 移除 #
        if (hash) {
            switchPage(hash);
        }
    });
    
    // 页面加载时检查URL hash
    const initialHash = window.location.hash.substring(1);
    if (initialHash) {
        switchPage(initialHash);
    }
    
    // 为反馈按钮添加点击事件
    const showFeedbackBtn = document.getElementById('show-feedback-btn');
    if (showFeedbackBtn) {
        showFeedbackBtn.addEventListener('click', openFeedbackModal);
    }
    
    // 点击模态框外部关闭
    const modal = document.getElementById('feedback-modal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeFeedbackModal();
            }
        });
    }
    
    // ESC键关闭模态框
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeFeedbackModal();
        }
    });
});

// 登录处理函数
function handleLogin() {
    showLoading();
    setTimeout(() => {
        hideLoading();
        showMessage('登录功能开发中，敬请期待！', 'info');
    }, 1500);
}

// 显示加载遮罩
function showLoading() {
    document.getElementById('loadingOverlay').classList.remove('hidden');
}

// 隐藏加载遮罩
function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

// 聊天功能
let chatMessages = [];

// Markdown渲染配置
function renderMarkdown(text) {
    marked.setOptions({
        gfm: true,
        breaks: true,
        headerIds: false,
        mangle: false,
        tables: true,
        smartLists: true,
        langPrefix: 'language-'
    });
    return marked.parse(String(text || ''));
}

function setMessageContentAsMarkdown(el, text) {
    el.classList.add('markdown');
    el.innerHTML = renderMarkdown(text);
}

// 触发文件选择
function triggerImageUpload() {
    const input = document.getElementById('imageFileInput');
    if (input) input.click();
}

// 处理图片上传
async function handleImageUpload(event) {
    const file = event.target.files?.[0];
    event.target.value = ''; // 重置选择
    if (!file) return;
    
    if (!file.type.startsWith('image/')) {
        addMessage({ 
            role: 'assistant', 
            content: '请上传图片文件。', 
            timestamp: new Date().toISOString() 
        });
        return;
    }
    
    const reader = new FileReader();
    reader.onload = async () => {
        addMessage({
            role: 'user',
            content: `📷 正在分析中：${file.name}`,
            imageUrl: reader.result,
            timestamp: new Date().toISOString()
        });
        
        await analyzeImage(file, '请从图片中提取与保险相关的关键信息，并用要点列出。');
    };
    reader.readAsDataURL(file);
}

// 分析图片
async function analyzeImage(file, prompt) {
    showLoading();
    const analyzingMsgId = Date.now();
    addMessage({ 
        role: 'assistant', 
        content: '🔍 正在分析图片，请稍候...', 
        id: analyzingMsgId, 
        timestamp: new Date().toISOString() 
    });

    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('prompt', prompt || '');

        const res = await fetch('http://127.0.0.1:8000/api/v1/analyze-image', { 
            method: 'POST', 
            body: formData 
        });
        const raw = await res.text();
        if (!res.ok) throw new Error(`HTTP ${res.status} ${raw}`);

        const result = JSON.parse(raw);
        removeMessage(analyzingMsgId);
        addMessage({ 
            role: 'assistant', 
            content: result.analysis || '分析完成。', 
            timestamp: new Date().toISOString() 
        });
    } catch (error) {
        console.error('图片分析失败:', error);
        removeMessage(analyzingMsgId);
        addMessage({
            role: 'assistant',
            content: `抱歉，图片分析失败：${error.message}`,
            timestamp: new Date().toISOString()
        });

    } finally {
        hideLoading();
    }
}


// 移除消息
function removeMessage(messageId) {
    const messages = document.querySelectorAll('.message');
    messages.forEach(msg => {
        if (msg.dataset.id == messageId) {
            msg.remove();
        }
    });
}

// 添加消息到聊天界面
function addMessage(message) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${message.role} chat-bubble`;
    if (message.id) messageDiv.dataset.id = message.id;

    let avatarHtml = '';
    if (message.role === 'user') {
        avatarHtml = `
            <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
                <i class="fas fa-user text-white"></i>
            </div>
        `;
    } else {
        avatarHtml = `
            <div class="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-full flex items-center justify-center flex-shrink-0">
                <i class="fas fa-robot text-white"></i>
            </div>
        `;
    }

    let contentHtml = '';
    if (message.imageUrl) {
        contentHtml += `
            <div class="mb-3">
                <img src="${message.imageUrl}" alt="上传的图片" class="max-w-xs rounded-lg shadow-md">
            </div>
        `;
    }

    const messageClass = message.role === 'user' ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white' : 'bg-white text-gray-800';
    
    contentHtml += `
        <div class="${messageClass} rounded-xl p-4 shadow-sm border border-gray-100">
    `;

    if (message.role === 'assistant') {
        const contentDiv = document.createElement('div');
        setMessageContentAsMarkdown(contentDiv, message.content || '');
        contentHtml += contentDiv.innerHTML;
    } else {
        contentHtml += `<p class="leading-relaxed">${message.content || ''}</p>`;
    }
    
    contentHtml += '</div>';

    messageDiv.innerHTML = `
        <div class="flex items-start space-x-3 ${message.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''}">
            ${avatarHtml}
            <div class="flex-1 ${message.role === 'user' ? 'text-right' : ''}">
                ${contentHtml}
                <div class="text-xs text-gray-500 mt-2">${formatTime(message.timestamp || new Date().toISOString())}</div>
            </div>
        </div>
    `;

    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    // 保存消息
    chatMessages.push(message);
}

// 发送消息
async function sendMessage() {
    const input = document.getElementById('messageInput');
    const button = document.getElementById('sendButton');
    const message = input.value.trim();
    
    if (!message) return;
    
    // 禁用输入和按钮
    input.disabled = true;
    button.disabled = true;
    
    // 添加用户消息
    addMessage({
        role: 'user',
        content: message,
        timestamp: new Date().toISOString()
    });
    
    // 清空输入
    input.value = '';
    
    
    // 显示加载状态
    showLoading();

    // 创建临时的AI消息元素用于流式更新
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant chat-bubble';
    
    messageDiv.innerHTML = `
        <div class="flex items-start space-x-3">
            <div class="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-full flex items-center justify-center flex-shrink-0">
                <i class="fas fa-robot text-white"></i>
            </div>
            <div class="flex-1">
                <div class="bg-white rounded-xl p-4 shadow-sm border border-gray-100">
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <span class="text-gray-500 ml-2">正在思考中...</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    messagesContainer.appendChild(messageDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    let fullContent = '';
    
    try {
        await chatAPI.askQuestionStream(
            message,
            (chunk) => {
                fullContent += chunk;
                // 更新消息内容
                const contentDiv = messageDiv.querySelector('.bg-white');
                if (contentDiv) {
                    contentDiv.innerHTML = `<div class="markdown">${renderMarkdown(fullContent)}</div>`;
                }
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            },
            () => {
                // 完成时的处理
                console.log('流式传输完成');
                
                // 移除临时消息元素
                if (messageDiv.parentNode === messagesContainer) {
                    messagesContainer.removeChild(messageDiv);
                }
                
                // 添加完整的消息
                addMessage({
                    role: 'assistant',
                    content: fullContent,
                    timestamp: new Date().toISOString()
                });
                
                // 隐藏加载状态
                hideLoading();
                
                // 恢复输入和按钮
                input.disabled = false;
                button.disabled = false;
                input.focus();
            },
            (error) => {
                // 错误处理
                console.error('流式传输错误:', error);
                
                // 移除临时消息元素
                if (messageDiv.parentNode === messagesContainer) {
                    messagesContainer.removeChild(messageDiv);
                }
                
                addMessage({
                    role: 'assistant',
                    content: '抱歉，网络出现问题了，请稍后重试。',
                    timestamp: new Date().toISOString()
                });
                
                // 隐藏加载状态
                hideLoading();
                
                // 恢复输入和按钮
                input.disabled = false;
                button.disabled = false;
                input.focus();
            }
        );
    } catch (error) {
        console.error('发送消息失败:', error);
        
        // 移除临时消息元素
        if (messageDiv.parentNode === messagesContainer) {
            messagesContainer.removeChild(messageDiv);
        }
        
        addMessage({
            role: 'assistant',
            content: '抱歉，网络出现问题了，请稍后重试。',
            timestamp: new Date().toISOString()
        });
        
        // 隐藏加载状态
        hideLoading();
        
        // 恢复输入和按钮
        input.disabled = false;
        button.disabled = false;
        input.focus();
    }
}

// 清空对话
function clearChat() {
    const messagesContainer = document.getElementById('chatMessages');
    messagesContainer.innerHTML = '';
    chatMessages = [];
    
    // 添加欢迎消息
    addMessage({
        role: 'assistant',
        content: '您好！我是智保灵枢智能助手，可以为您解答关于健康险的各种问题，包括保障范围、理赔流程、产品对比等。请问有什么可以帮您的？',
        timestamp: new Date().toISOString()
    });
}

// 加载纠纷案例
function loadDisputeCases() {
    const disputeGrid = document.getElementById('disputeGrid');
    if (!disputeGrid) return;
    
    const cases = [
        {
            title: '保险责任范围认定纠纷',
            date: '2025-06-27',
            type: '重疾险',
            content: '张某某投保重大疾病保险后被诊断为多发性大肠息肉（腺瘤），接受了CSP术治疗。保险公司以未进行肠段切除手术为由拒赔。法院认定保险条款中明确约定需进行肠段切除手术才符合理赔条件，CSP术不符合合同约定，保险公司无需承担保险责任。',
            tags: ['保险责任', '重疾险', '条款解释']
        },
        {
            title: '未履行如实告知义务纠纷',
            date: '2025-03-06',
            type: '医疗险',
            content: '张某某投保医疗险后因急性心肌梗死住院治疗，保险公司以其2019年脑梗死住院未告知为由拒赔。法院认为保险人未提供证据证明其进行了具体询问，且未在法定期限内行使合同解除权，判决保险公司败诉，需支付保险金5万余元。',
            tags: ['如实告知', '医疗险', '合同解除权']
        },
        {
            title: '遗传性疾病免责纠纷',
            date: '2024-08-08',
            type: '医疗险',
            content: '吴某磊投保医疗险和重疾险后被诊断为家族性息肉病并接受全结肠切除术，保险公司以该病属于遗传性疾病为由拒赔。法院认定该病属于保险合同约定的遗传性疾病免责范围，且保险公司已履行提示说明义务，判决驳回原告诉请。',
            tags: ['遗传性疾病', '医疗险', '免责条款']
        },
        {
            title: '短期健康险续保纠纷',
            date: '2024-05-31',
            type: '医疗险',
            content: '丁某之子为孙子投保某超e保2021医疗保险，保险合同特别约定可续保至100岁。投保人去世后丁某申请变更投保人并续保，保险公司以短期健康险不保证续保为由拒绝。法院认定特别约定违反监管规定无效，驳回原告诉请。',
            tags: ['短期健康险', '保证续保', '监管规定']
        },
        {
            title: '重复投保未告知纠纷',
            date: '2024-04-29',
            type: '重疾险',
            content: '何某某投保重疾险时未告知在其他保险公司投保情况，保险公司以违反如实告知义务为由拒赔30万元。法院认定保险人询问不明确，投保人主观无故意，且未告知事项不影响承保决定，判决保险公司败诉，需支付保险金。',
            tags: ['如实告知', '重疾险', '重复投保']
        },
        {
            title: '保险责任范围争议案例',
            date: '2024-01-31',
            type: '重疾险',
            content: '常某某投保一年期重大疾病保险后被诊断为重度阻塞性睡眠呼吸暂停低通气综合征，认为属于保险条款释义的47种疾病范围要求理赔。法院认定保险条款释义系对术语的解释说明，不属于免责条款，且所患疾病不在保险合同约定的20种轻度疾病范围内，判决驳回诉请。',
            tags: ['保险责任', '重疾险', '条款释义']
        }
    ];
    
    disputeGrid.innerHTML = '';
    
    cases.forEach(caseItem => {
        const caseCard = document.createElement('div');
        caseCard.className = 'case-card bg-white rounded-2xl p-6 shadow-lg hover-lift';
        
        const tagsHtml = caseItem.tags.map(tag => 
            `<span class="inline-block bg-primary-100 text-primary-800 text-xs px-3 py-1 rounded-full mr-2 mb-2">${tag}</span>`
        ).join('');
        
        caseCard.innerHTML = `
            <div class="flex items-start justify-between mb-4">
                <h3 class="text-xl font-bold text-gray-900 leading-tight">${caseItem.title}</h3>
                <span class="text-sm text-gray-500 bg-gray-100 px-3 py-1 rounded-full">${caseItem.type}</span>
            </div>
            <div class="flex items-center text-sm text-gray-500 mb-4">
                <i class="fas fa-calendar mr-2"></i>
                ${caseItem.date}
            </div>
            <p class="text-gray-700 leading-relaxed mb-4">${caseItem.content}</p>
            <div class="flex flex-wrap">
                ${tagsHtml}
            </div>
        `;
        
        disputeGrid.appendChild(caseCard);
    });
}

// 加载产品数据
async function loadProducts(query = '') {
    const tbody = document.getElementById('productsTableBody');
    const loadingEl = document.getElementById('productsLoading');
    
    if (!tbody) return;
    
    // 显示加载状态
    if (loadingEl) {
        loadingEl.classList.remove('hidden');
    }
    
    try {
        // 模拟API调用延迟
        await new Promise(resolve => setTimeout(resolve, 500));
        
        const products = [
            {
                name: '康宁终身重大疾病保险',
                company: '中国人寿',
                type: '重疾险',
                coverage: '120种重大疾病，50种轻症',
                premium: '¥3,200/年'
            },
            {
                name: '平安e生保医疗保险',
                company: '平安保险',
                type: '医疗险',
                coverage: '住院医疗、特殊门诊、住院前后门急诊',
                premium: '¥1,850/年'
            },
            {
                name: '好医保长期医疗',
                company: '众安保险',
                type: '医疗险',
                coverage: '一般医疗、100种重疾医疗、特殊门诊',
                premium: '¥1,290/年'
            },
            {
                name: '国寿福终身重大疾病保险',
                company: '中国人寿',
                type: '重疾险',
                coverage: '120种重疾、20种中症、40种轻症',
                premium: '¥4,500/年'
            },
            {
                name: '平安福终身重大疾病保险',
                company: '平安保险',
                type: '重疾险',
                coverage: '100种重疾、20种中症、40种轻症',
                premium: '¥4,200/年'
            },
            {
                name: '尊享e生医疗保险',
                company: '众安保险',
                type: '医疗险',
                coverage: '一般医疗、重疾医疗、质子重离子医疗',
                premium: '¥2,100/年'
            },
            {
                name: '好医保门诊险',
                company: '众安保险',
                type: '医疗险',
                coverage: '门诊医疗、药品费用、体检费用',
                premium: '¥580/年'
            },
            {
                name: '健康福重疾险',
                company: '中国人保',
                type: '重疾险',
                coverage: '100种重疾、30种轻症、身故保障',
                premium: '¥3,800/年'
            },
            {
                name: '复星联合和睦医疗保险',
                company: '复星联合健康',
                type: '医疗险',
                coverage: '门诊医疗、住院医疗、生育责任',
                premium: '¥3,500/年'
            },
            {
                name: '泰康在线百万医疗险',
                company: '泰康在线',
                type: '医疗险',
                coverage: '住院医疗、特殊门诊、门诊手术',
                premium: '¥1,350/年'
            }
        ];
        
        // 过滤产品（如果有关键词）
        let filteredProducts = products;
        if (query) {
            filteredProducts = products.filter(product => 
                product.name.toLowerCase().includes(query.toLowerCase()) ||
                product.company.toLowerCase().includes(query.toLowerCase()) ||
                product.type.toLowerCase().includes(query.toLowerCase())
            );
        }
        
        tbody.innerHTML = '';
        
        filteredProducts.forEach(product => {
            const row = document.createElement('tr');
            row.className = 'product-card hover:bg-gray-50 transition-all duration-300';
            
            row.innerHTML = `
                <td class="px-6 py-4">
                    <div class="font-semibold text-gray-900">${product.name}</div>
                </td>
                <td class="px-6 py-4 text-gray-700">${product.company}</td>
                <td class="px-6 py-4">
                    <span class="inline-block bg-blue-100 text-blue-800 text-xs px-3 py-1 rounded-full">
                        ${product.type}
                    </span>
                </td>
                <td class="px-6 py-4 text-gray-700 max-w-xs">${product.coverage}</td>
                <td class="px-6 py-4">
                    <span class="font-semibold text-primary-600">${product.premium}</span>
                </td>
                <td class="px-6 py-4">
                    <button class="bg-gradient-to-r from-primary-500 to-primary-600 text-white px-4 py-2 rounded-lg hover:from-primary-600 hover:to-primary-700 transition-all duration-300 text-sm font-medium">
                        查看详情
                    </button>
                </td>
            `;
            
            tbody.appendChild(row);
        });
        
        if (filteredProducts.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="6" class="px-6 py-8 text-center text-gray-500">
                        <i class="fas fa-search text-4xl mb-4 text-gray-300"></i>
                        <p class="text-lg">未找到相关产品</p>
                    </td>
                </tr>
            `;
        }
        
    } catch (error) {
        console.error('加载产品数据失败:', error);
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="px-6 py-8 text-center text-red-500">
                    <i class="fas fa-exclamation-triangle text-4xl mb-4"></i>
                    <p class="text-lg">加载失败，请稍后重试</p>
                </td>
            </tr>
        `;
    } finally {
        // 隐藏加载状态
        if (loadingEl) {
            loadingEl.classList.add('hidden');
        }
    }
}

// 搜索产品
function searchProducts() {
    const searchInput = document.getElementById('productSearch');
    const query = searchInput.value.trim();
    loadProducts(query);
}

// 加载用户评论
function loadUserComments() {
    const commentsList = document.getElementById('comments-list');
    if (!commentsList) return;
    
    const comments = [
        { name: '保险小白君', comment: '作为一个保险小白，这个平台真的帮了我大忙！之前对重疾险完全不了解，通过智保灵枢的智能问答，不仅搞懂了各种条款，还帮我选到了合适的保险产品。整个过程只花了不到半小时，太高效了！', rating: 5 },
        { name: '职场奋斗鸭', comment: '昨晚突发奇想查了一下医疗险和重疾险的区别，AI助手回答得超级详细，还有图表解释，一目了然。比之前看的那些长篇大论好懂多了，给我的选购提供了很大帮助。', rating: 5 },
        { name: '宝妈小雨', comment: '平台上真实的理赔纠纷案例对我帮助特别大，让我在买保险时知道哪些条款是坑，应该如何避险。已经推荐给身边好几个朋友了！', rating: 4 },
        { name: '理财规划师Ken', comment: '作为金融从业者，我对这类平台要求比较高。智保灵枢的专业度确实不错，知识库比较全面，问答准确率也挺高。对于普通消费者来说绝对够用了。', rating: 5 },
        { name: '数码萌新', comment: '界面设计得很清爽，操作逻辑也很清晰，没有那些复杂的套路。特别是产品对比功能，几个维度一筛选就知道哪个更适合，省了不少事。', rating: 4 },
        { name: '夕阳红粉丝团', comment: '给我爸妈选保险的时候纠结了很久，后来在这上面咨询了专业AI助手，把防癌险和医疗险的区别讲得明明白白的。老人家也能听懂，很不错！', rating: 5 },
        { name: '程序猿小王', comment: '24小时在线这一点太赞了！晚上研究保险产品时有问题随时问，回复速度很快，内容也专业。比人工客服效率高多了，不用等回复。', rating: 5 },
        { name: '健身达人阿强', comment: '本来以为保险平台就是推销产品，没想到这里这么多干货。尤其是健康告知部分的解读，让我避免了带病投保的风险，真是良心平台。', rating: 4 },
        { name: '学生党小林', comment: '大学生一枚，预算有限但又想买保险。平台上的产品按价格和保障范围排序，很容易就找到了性价比高的产品，还有详细的投保教程，真的很贴心。', rating: 5 },
        { name: '家庭主妇莉莉', comment: '平台上保险产品信息很全，每个产品的优缺点都列出来了，对比起来很方便。最后我选了一款适合全家的医疗险，保费比代理人推荐的便宜不少。', rating: 4 }
    ];
    
    commentsList.innerHTML = '';
    
    comments.forEach(commentItem => {
        const commentDiv = document.createElement('div');
        commentDiv.className = 'bg-gray-50 rounded-xl p-4 hover:bg-gray-100 transition-all duration-300';
        
        const starsHtml = Array.from({length: 5}, (_, i) => 
            `<i class="fas fa-star ${i < commentItem.rating ? 'text-yellow-400' : 'text-gray-300'}"></i>`
        ).join('');
        
        commentDiv.innerHTML = `
            <div class="flex items-start justify-between mb-2">
                <h4 class="font-semibold text-gray-900">${commentItem.name}</h4>
                <div class="flex items-center space-x-1">
                    ${starsHtml}
                </div>
            </div>
            <p class="text-gray-700 leading-relaxed">${commentItem.comment}</p>
        `;
        
        commentsList.appendChild(commentDiv);
    });
}

// 打开反馈弹窗
function openFeedbackModal() {
    const modal = document.getElementById('feedback-modal');
    if (modal) {
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
}

// 关闭反馈弹窗
function closeFeedbackModal() {
    const modal = document.getElementById('feedback-modal');
    if (modal) {
        modal.classList.add('hidden');
        document.body.style.overflow = 'auto';
        
        // 重置表单
        const form = document.getElementById('feedbackForm');
        if (form) form.reset();
        
        // 隐藏成功提示
        const response = document.getElementById('feedbackResponse');
        if (response) response.classList.add('hidden');
        
        // 显示表单
        const formContainer = form?.parentElement;
        if (formContainer) formContainer.classList.remove('hidden');
    }
}

// 提交反馈
function submitFeedback() {
    const name = document.getElementById('feedbackName').value.trim();
    const contact = document.getElementById('feedbackContact').value.trim();
    const type = document.getElementById('feedbackType').value;
    const content = document.getElementById('feedbackContent').value.trim();
    
    if (!name || !content) {
        showMessage('请填写姓名和反馈内容', 'warning');
        return;
    }
    
    // 隐藏表单，显示成功提示
    const form = document.getElementById('feedbackForm');
    const response = document.getElementById('feedbackResponse');
    
    if (form && response) {
        form.parentElement.classList.add('hidden');
        response.classList.remove('hidden');
        
        // 3秒后关闭弹窗
        setTimeout(() => {
            closeFeedbackModal();
        }, 3000);
    }
}

// 初始化聊天功能
function initChat() {
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    
    if (!messageInput || !sendButton) return;
    
    // 发送消息事件
    sendButton.addEventListener('click', sendMessage);
    
    // 回车发送消息
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // 自动调整输入框高度
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
}

// 初始化产品搜索
function initProductSearch() {
    const searchInput = document.getElementById('productSearch');
    if (!searchInput) return;
    
    // 防抖搜索
    let searchTimeout;
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            searchProducts();
        }, 300);
    });
    
    // 回车搜索
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchProducts();
        }
    });
}


// 显示消息提示
function showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `fixed top-20 right-4 z-50 p-4 rounded-lg shadow-lg max-w-sm transform translate-x-full transition-transform duration-300`;
    
    const bgColor = {
        'info': 'bg-blue-500',
        'success': 'bg-green-500',
        'warning': 'bg-yellow-500',
        'error': 'bg-red-500'
    }[type] || 'bg-blue-500';
    
    messageDiv.className += ` ${bgColor} text-white`;
    messageDiv.innerHTML = `
        <div class="flex items-center space-x-2">
            <i class="fas ${{
                'info': 'fa-info-circle',
                'success': 'fa-check-circle',
                'warning': 'fa-exclamation-triangle',
                'error': 'fa-times-circle'
            }[type] || 'fa-info-circle'}"></i>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(messageDiv);
    
    // 显示动画
    setTimeout(() => {
        messageDiv.classList.remove('translate-x-full');
    }, 100);
    
    // 自动隐藏
    setTimeout(() => {
        messageDiv.classList.add('translate-x-full');
        setTimeout(() => {
            document.body.removeChild(messageDiv);
        }, 300);
    }, 3000);
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化聊天功能
    initChat();
    
    // 初始化产品搜索
    initProductSearch();
    
    // 初始化页面
    initializePage();
    
    // 为导航链接添加点击事件
    document.querySelectorAll('.nav-link').forEach(link => {
        if (link.getAttribute('data-page')) {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                const pageId = this.getAttribute('data-page');
                switchPage(pageId);
            });
        }
    });
    
    // 为反馈按钮添加点击事件
    const showFeedbackBtn = document.getElementById('show-feedback-btn');
    if (showFeedbackBtn) {
        showFeedbackBtn.addEventListener('click', openFeedbackModal);
    }
    
    // 点击模态框外部关闭
    const modal = document.getElementById('feedback-modal');
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                closeFeedbackModal();
            }
        });
    }
    
    // ESC键关闭模态框
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeFeedbackModal();
        }
    });
});