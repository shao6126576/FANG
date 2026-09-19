import base64
import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings

logger = logging.getLogger(__name__)

class VisionService:
    """视觉模型服务 - 专门处理图片分析"""
    
    def __init__(self):
        """初始化 qwen3-vl-plus 视觉模型"""
        self.vision_llm = ChatOpenAI(
            model="qwen3-vl-plus",
            openai_api_key=settings.OPENAI_API_KEY_SF,
            openai_api_base=settings.OPENAI_BASE_URL,
            temperature=0.2,
            max_tokens=2000
        )
        
        # 默认系统提示词
        self.system_prompt = """你是一个专业的保险文档分析助手，擅长从保单、医疗报告、理赔单据等图片中提取关键信息。

请注意：
1. 准确识别图片中的文字和表格内容
2. 提取保险产品名称、保障内容、理赔条款等关键信息
3. 用清晰的 Markdown 格式组织输出
4. 对模糊或不确定的信息标注说明
5. 如果图片质量差或无法识别，请如实告知"""

    def _encode_image_to_base64(self, image_data: bytes) -> str:
        """将图片字节数据转为 base64 编码"""
        return base64.b64encode(image_data).decode('utf-8')

    def analyze_image(self, 
                     image_data: bytes, 
                     user_prompt: Optional[str] = None) -> str:
        """
        分析图片内容
        
        Args:
            image_data: 图片的字节数据
            user_prompt: 用户自定义提示词，如果为空则使用默认提示
            
        Returns:
            分析结果文本
        """
        try:
            # 将字节数据转为 base64
            image_b64 = self._encode_image_to_base64(image_data)
            image_url = f"data:image/jpeg;base64,{image_b64}"
            
            # 构建提示词
            if not user_prompt:
                user_prompt = "请详细分析这张图片，提取所有保险相关的关键信息，包括但不限于：产品名称、保障内容、保额、等待期、免责条款等。"
            
            # 构建消息
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=[
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ])
            ]
            
            logger.info("开始调用视觉模型分析图片")
            response = self.vision_llm.invoke(messages)
            logger.info("视觉模型分析完成")
            
            return response.content
            
        except Exception as e:
            logger.error(f"视觉模型处理失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return "抱歉，图片分析失败。可能的原因：\n1. 图片格式不支持\n2. 图片过大或损坏\n3. 网络连接问题\n\n请检查后重试。"

    def analyze_image_url(self, 
                         image_url: str, 
                         user_prompt: Optional[str] = None) -> str:
        """
        分析网络图片 URL
        
        Args:
            image_url: 图片的网络地址
            user_prompt: 用户自定义提示词
            
        Returns:
            分析结果文本
        """
        try:
            # 构建提示词
            if not user_prompt:
                user_prompt = "请详细分析这张图片，提取所有保险相关的关键信息。"
            
            # 构建消息
            messages = [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=[
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ])
            ]
            
            logger.info(f"开始分析网络图片: {image_url}")
            response = self.vision_llm.invoke(messages)
            logger.info("网络图片分析完成")
            
            return response.content
            
        except Exception as e:
            logger.error(f"网络图片分析失败: {e}")
            return "抱歉，无法访问或分析该图片链接。请检查：\n1. URL 是否有效\n2. 图片是否公开可访问\n3. 图片格式是否支持"

    def extract_insurance_info(self, image_data: bytes) -> dict:
        """
        专门提取保险文档的结构化信息
        
        Returns:
            结构化的保险信息字典
        """
        try:
            prompt = """请从这张保险文档中提取以下信息，并以 JSON 格式输出：
            
{
  "product_name": "产品名称",
  "company": "保险公司",
  "coverage": ["保障项目1", "保障项目2"],
  "sum_insured": "保额",
  "waiting_period": "等待期",
  "exclusions": ["免责条款1", "免责条款2"],
  "premium": "保费",
  "other_info": "其他重要信息"
}

如果某项信息在图片中找不到，请标注为 "未找到"。"""

            result = self.analyze_image(image_data, prompt)
            
            # 尝试解析 JSON（如果模型返回了 JSON）
            import json
            try:
                return json.loads(result)
            except:
                # 如果不是 JSON 格式，返回原始文本
                return {"raw_text": result}
                
        except Exception as e:
            logger.error(f"提取保险信息失败: {e}")
            return {"error": str(e)}
