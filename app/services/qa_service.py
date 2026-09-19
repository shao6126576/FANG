from app.services.graph_service import GraphService
from app.services.llm_service import LLMService
from typing import List, Dict, Any, Tuple
import time
import logging
import traceback
import json
import asyncio

logger = logging.getLogger(__name__)

class QAService:
    def __init__(self):
        try:
            self.graph_service = GraphService()
            self.llm_service = LLMService()
        except Exception as e:
            logger.error(f"初始化服务失败: {e}")
            logger.error(traceback.format_exc())
            raise
    
    async def answer_question(self, question: str) -> Dict[str, Any]:
        """处理用户问题并生成回答"""
        start_time = time.time()
        
        try:

            logger.info(f"开始处理用户问题: {question}")

            # 1. 提取关键词
            keywords = self.llm_service.extract_keywords(question)
            logger.info(f"提取的关键词: {keywords}")
            
            # 2. 从知识图谱检索相关信息
            context_data = self._retrieve_context(keywords, question)
            logger.info(f"检索到的上下文数据: {context_data}")
            
            # 3. 生成回答
            answer = await self.llm_service.generate_multi_expert_response(question, context_data)
            logger.info(f"生成的回答: {answer}")
            
            # 4. 构建响应
            response_time = time.time() - start_time
            
            result = {
                "answer": answer,
                "sources": self._format_sources(context_data),
                "query_time": response_time,
                "keywords": keywords
            }
            logger.info(f"返回的答案结果: {result}")

            return result
            
        except Exception as e:
            logger.error(f"问答处理失败: {e}")
            logger.error(traceback.format_exc())
            return {
                "answer": "抱歉，处理您的问题时出现了错误。请稍后重试或联系客服。",
                "sources": [],
                "query_time": time.time() - start_time,
                "keywords": [],
                "error": str(e)
            }
        
    async def answer_question_stream(self, question: str):
        """处理用户问题并生成流式回答"""
        try:
            # 1. 提取关键词（失败不阻断）
            try:
                keywords = self.llm_service.extract_keywords(question)
                logger.info(f"提取的关键词: {keywords}")
            except Exception as e:
                logger.warning(f"关键词提取失败: {e}")
                keywords = []
            
            # 2. 从知识图谱检索相关信息（失败不阻断）
            context_data = []
            try:
                context_data = self._retrieve_context(keywords, question)
                logger.info(f"检索到 {len(context_data)} 条上下文")
            except Exception as e:
                logger.warning(f"图检索失败，降级纯 LLM: {e}")
            
            # 3. 直接 yield 流式内容，不要 return 生成器
            async for chunk in self.llm_service.generate_response_stream(question, context_data):
                yield chunk

            # 3. 使用多专家系统生成完整回答
            # full_response = await self.llm_service.generate_multi_expert_response(question, context_data)
            
            # # 4. 将完整回答转换为流式输出
            # for i in range(0, len(full_response), 10):  # 每次输出10个字符
            #     yield full_response[i:i+10]
            #     await asyncio.sleep(0.01)  # 短暂延迟以模拟流式效果


        except Exception as e:
            logger.error(f"流式问答处理失败: {e}")
            logger.error(traceback.format_exc())
            yield "抱歉，处理您的问题时出现了错误。"
    
    def _retrieve_context(self, keywords: List[str], question: str) -> List[Dict[str, Any]]:
        """从知识图谱检索相关信息"""
        context = []
        
        # 根据问题类型选择检索策略
        if any(word in question for word in ["产品", "保险", "保障"]):
            # 保险产品相关查询
            products = self.graph_service.search_insurance_products(keywords)
            context.extend(products)
        
        if any(word in question for word in ["疾病", "病", "医疗"]):
            # 疾病保障相关查询
            diseases = self.graph_service.search_diseases(keywords)
            context.extend(diseases)
        
        if any(word in question for word in ["公司", "人寿", "保险"]):
            # 保险公司相关查询
            companies = self.graph_service.search_companies(keywords)
            context.extend(companies)
        
        if any(word in question for word in ["药品", "药", "处方"]):
            # 药品相关查询
            drugs = self.graph_service.search_drugs(keywords)
            context.extend(drugs)
        
        if any(word in question for word in ["医院", "诊所", "医疗机构"]):
            # 医院相关查询
            hospitals = self.graph_service.search_hospitals(keywords)
            context.extend(hospitals)
        
        # 如果关键词匹配到具体产品名称，获取详细信息
        for keyword in keywords:
            product_detail = self.graph_service.get_product_details(keyword)
            if product_detail:
                context.append(product_detail)
            
            drug_detail = self.graph_service.get_drug_details(keyword)
            if drug_detail:
                context.append(drug_detail)
            
            hospital_detail = self.graph_service.get_hospital_details(keyword)
            if hospital_detail:
                context.append(hospital_detail)
        
        return context
    
    def _format_sources(self, context_data: List[Dict]) -> List[Dict]:
        """格式化来源信息"""
        sources = []
        for data in context_data:
            if 'product' in data:
                sources.append({
                    "type": "保险产品",
                    "name": data.get('product', {}).get('名称', ''),
                    "company": data.get('company_name', '')
                })
            elif 'disease_name' in data:
                sources.append({
                    "type": "疾病保障",
                    "disease": data.get('disease_name', ''),
                    "products": len(data.get('covered_products', []))
                })
        return sources