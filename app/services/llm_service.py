import json
from typing import List, Dict, Any, Optional, AsyncIterator
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import asyncio
import yaml

from app.core.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        """初始化Langchain LLM服务"""
        self.llm = ChatOpenAI(
            model="qwen-long",
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_BASE_URL,
            temperature=0.3,
            max_tokens=2000
        )
        self.model_configs = {
            'medical_specialist': {
                'model': 'qwen-long',
                'temperature': 0.3,
                'max_tokens': 2000
            },
            'insurance_consultant': {
                'model': 'qwen-long',
                'temperature': 0.3,
                'max_tokens': 2000
            },
            'legal_expert': {
                'model': 'qwen-long',
                'temperature': 0.3,
                'max_tokens': 2000
            }
        }
        # 创建每个专家的LLM实例
        self.expert_llms = {}
        for role, config in self.model_configs.items():
            self.expert_llms[role] = ChatOpenAI(
                model=config['model'],
                openai_api_key=settings.OPENAI_API_KEY,
                openai_api_base=settings.OPENAI_BASE_URL,
                temperature=config['temperature'],
                max_tokens=config['max_tokens']
            )
        self.prompts = self._load_prompts()
        # 定义系统提示词
        self.system_prompt = self.prompts['system_prompt']
        
        # 关键词提取提示词
        self.keyword_extraction_prompt = self.prompts['keyword_extraction_prompt']
            
        # 各类专家角色提示词定义
        self.expert_prompts = self.prompts['expert_prompts']

    def _load_prompts(self) -> dict:
        """加载提示词配置文件"""
        try:
            with open('app/core/prompts.yaml', 'r', encoding='utf-8') as file:
                prompts = yaml.safe_load(file)
            return prompts
        except Exception as e:
            logger.error(f"加载提示词配置文件失败: {e}")
    
    def generate_response(self, 
                         prompt: str, 
                         context: List[Dict[str, Any]] = None,
                         temperature: float = 0.3) -> str:
        """使用Langchain生成回答"""
        try:
            # 构建消息历史
            messages = [SystemMessage(content=self.system_prompt)]
            
            user_content = prompt
            if context:
                context_str = "\n".join([str(item) for item in context])
                user_content = f"基于以下信息回答问题：\n{context_str}\n\n问题：{prompt}"
            
            messages.append(HumanMessage(content=user_content))
            
            # 更新温度设置（如果需要）
            if temperature != self.llm.temperature:
                self.llm.temperature = temperature
                
            # 调用模型
            response = self.llm.invoke(messages)
            return response.content
            
        except Exception as e:
            logger.error(f"Langchain LLM 调用失败: {e}")
            return "抱歉，我现在无法回答这个问题，请稍后再试。"

    async def generate_response_stream(self, 
                                     prompt: str, 
                                     context: List[Dict[str, Any]] = None,
                                     temperature: float = 0.3) -> AsyncIterator[str]:
        """使用Langchain生成流式回答"""
        try:
            # 构建消息历史
            messages = [SystemMessage(content=self.system_prompt)]
            
            user_content = prompt
            if context:
                context_str = "\n".join([str(item) for item in context])
                user_content = f"基于以下信息回答问题：\n{context_str}\n\n问题：{prompt}"
            
            messages.append(HumanMessage(content=user_content))
            
            # 更新温度设置（如果需要）
            if temperature != self.llm.temperature:
                self.llm.temperature = temperature
                
            # 调用模型并生成流式响应
            async for chunk in self.llm.astream(messages):
                yield chunk.content
                
        except Exception as e:
            logger.error(f"Langchain LLM 流式调用失败: {e}")
            yield "抱歉，我现在无法回答这个问题，请稍后再试。"

    def extract_keywords(self, question: str) -> List[str]:
        """使用Langchain从问题中提取关键词"""
        try:
            # 创建关键词提取提示模板
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "你是一个专业的信息提取助手。"),
                ("human", self.keyword_extraction_prompt)
            ])
            
            # 创建处理链
            chain = prompt_template | self.llm | StrOutputParser()
            
            # 调用链并获取结果
            response = chain.invoke({"question": question})
            keywords = [kw.strip() for kw in response.split(",") if kw.strip()]
            return keywords
            
        except Exception as e:
            logger.error(f"关键词提取失败: {e}")
            return None
        
            
    async def consult_experts(self, question: str, context: List[Dict[str, Any]]) -> Dict[str, str]:
        """召集多位专家分别就问题发表见解"""
        expert_opinions = {}
        
        tasks = []
        for role, prompt in self.expert_prompts.items():
            task = asyncio.create_task(self._get_expert_opinion(role, prompt, question, context))
            tasks.append(task)
            
        results = await asyncio.gather(*tasks)
        
        for i, (role, _) in enumerate(self.expert_prompts.items()):
            expert_opinions[role] = results[i]
            
        return expert_opinions

    async def _get_expert_opinion(self, 
                                  role: str,
                                  system_prompt: str,
                                  question: str,
                                  context: List[Dict[str, Any]]) -> str:
        """获取单个专家的意见"""
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"请基于以下背景信息回答问题：\n{json.dumps(context, ensure_ascii=False)}\n\n问题：{question}")
            ]
            
            response = await self.expert_llms[role].ainvoke(messages)
            return response.content
            
        except Exception as e:
            logger.error(f"{role}专家响应失败: {e}")
            return "暂时无法提供该领域的专业建议"

    def synthesize_final_answer(self, 
                               original_question: str,
                               expert_opinions: Dict[str, str]) -> str:
        """综合所有专家意见生成最终答复"""
        synthesis_prompt = f"""
            你是总顾问，请汇总以下来自各个领域专家的观点，并向用户做出全面而易懂的回答。
            
            用户原始问题：{original_question}
            
            各专家反馈如下：
            1. 医疗专家意见：{expert_opinions.get('medical_specialist', '无')}
            2. 保险专家意见：{expert_opinions.get('insurance_consultant', '无')}
            3. 法律专家意见：{expert_opinions.get('legal_expert', '无')}

            最终回复应满足：
            - 条理清晰地组织信息结构
            - 保留重要技术术语但需适当解释
            - 若存在冲突观点需要标明并给出判断依据
            - 总结核心要点方便用户快速掌握
        """

        try:
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=synthesis_prompt)
            ]
            
            response = self.llm.invoke(messages)
            return response.content
            
        except Exception as e:
            logger.error(f"合成最终答案时发生错误: {e}")
            return "抱歉，在整理专家意见过程中出现问题，请重试"
            
    async def generate_multi_expert_response(self,
                                           question: str,
                                           context: List[Dict[str, Any]] = None) -> str:
        """使用多专家系统生成回答"""
        try:
            if not context:
                context = []
                
            # 召集专家意见
            expert_opinions = await self.consult_experts(question, context)
            
            # 综合专家意见生成最终答案
            final_answer = self.synthesize_final_answer(question, expert_opinions)
            
            return final_answer
            
        except Exception as e:
            logger.error(f"多专家系统调用失败: {e}")
            return "抱歉，我现在无法回答这个问题，请稍后再试。"