from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from app.models.schemas import QuestionRequest, AnswerResponse
from app.services.qa_service import QAService
from app.services.vision_service import VisionService
import logging
import json
import io

logger = logging.getLogger(__name__)

router = APIRouter()
qa_service = QAService()
vision_service = VisionService()

@router.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """回答用户问题"""
    try:
        result = await qa_service.answer_question(request.question)
        
        return AnswerResponse(
            answer=result["answer"],
            sources=result["sources"],
            query_time=result["query_time"],
            conversation_id=request.conversation_id
        )
    except Exception as e:
        logger.error(f"API 处理失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.post("/ask/stream")
async def ask_question_stream(request: QuestionRequest):
    """流式回答用户问题"""
    try:
        async def event_generator():
            try:
                # 获取流式响应
                stream = qa_service.answer_question_stream(request.question)
                
                # 逐块生成响应
                async for chunk in stream:
                    if chunk:
                        # 将每个文本块包装成SSE格式
                        yield f"data: {json.dumps({'content': chunk})}\n\n"
                
                # 结束标记
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"流式输出错误: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"
        
        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 若有 Nginx，关闭缓冲
        }
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers=headers
        )
    except Exception as e:
        logger.error(f"流式API处理失败: {e}")
        raise HTTPException(status_code=500, detail="内部服务器错误")

@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "Insurance KG QA System"}

@router.get("/products")
async def search_products(query: str = None):
    """搜索保险产品"""
    if not query:
        return {"products": []}
    
    keywords = qa_service.llm_service.extract_keywords(query)
    products = qa_service.graph_service.search_insurance_products(keywords)
    return {"products": products}

@router.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    prompt: str = Form(default="")
):
    """
    分析上传的图片（专用于视觉模型）
    
    Args:
        file: 上传的图片文件
        prompt: 可选的自定义分析提示词
    """
    try:
        # 检查文件类型
        if not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件类型: {file.content_type}，请上传图片文件"
            )
        
        # 读取图片数据
        image_data = await file.read()
        
        if not image_data:
            raise HTTPException(status_code=400, detail="图片文件为空")
        
        # 检查文件大小（限制 10MB）
        max_size = 10 * 1024 * 1024  # 10MB
        if len(image_data) > max_size:
            raise HTTPException(
                status_code=400, 
                detail=f"图片文件过大（{len(image_data)//1024//1024}MB），请上传小于 10MB 的图片"
            )
        
        logger.info(f"收到图片上传请求，文件名: {file.filename}，大小: {len(image_data)} bytes")
        
        # 调用视觉服务分析图片
        result = vision_service.analyze_image(
            image_data=image_data,
            user_prompt=prompt if prompt else None
        )
        
        return {
            "success": True,
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(image_data),
            "analysis": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("图片分析失败")
        raise HTTPException(
            status_code=500, 
            detail=f"图片分析失败: {str(e)}"
        )

@router.post("/analyze-image-url")
async def analyze_image_url(request: dict):
    """
    分析网络图片 URL
    
    Args:
        request: {"image_url": "...", "prompt": "..."}
    """
    try:
        image_url = request.get("image_url")
        prompt = request.get("prompt", "")
        
        if not image_url:
            raise HTTPException(status_code=400, detail="图片 URL 不能为空")
        
        logger.info(f"收到图片 URL 分析请求: {image_url}")
        
        # 调用视觉服务分析图片
        result = vision_service.analyze_image_url(
            image_url=image_url,
            user_prompt=prompt if prompt else None
        )
        
        return {
            "success": True,
            "image_url": image_url,
            "analysis": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("网络图片分析失败")
        raise HTTPException(
            status_code=500, 
            detail=f"网络图片分析失败: {str(e)}"
        )

@router.post("/extract-insurance-info")
async def extract_insurance_info(file: UploadFile = File(...)):
    """
    从保险文档图片中提取结构化信息
    """
    try:
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="请上传图片文件")
        
        image_data = await file.read()
        
        if not image_data:
            raise HTTPException(status_code=400, detail="图片文件为空")
        
        logger.info(f"提取保险信息，文件名: {file.filename}")
        
        # 调用视觉服务提取结构化信息
        result = vision_service.extract_insurance_info(image_data)
        
        return {
            "success": True,
            "filename": file.filename,
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("保险信息提取失败")
        raise HTTPException(
            status_code=500, 
            detail=f"保险信息提取失败: {str(e)}"
        )
