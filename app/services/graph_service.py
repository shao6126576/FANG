from py2neo import Graph, NodeMatcher, RelationshipMatcher
from app.core.config import settings
from typing import List, Dict, Any, Optional
import logging
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

class GraphService:
    def __init__(self):
        self.graph = Graph(
            settings.NEO4J_URI, 
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
        )
        self.node_matcher = NodeMatcher(self.graph)
        self.rel_matcher = RelationshipMatcher(self.graph)
        self.llm_service = LLMService()

    def ai_query_graph(self, question, context) -> List[Dict]:
        """使用AI生成Cypher查询并执行，增强知识图谱检索能力"""
        try:
            # 1. 提取关键词
            keywords = self.llm_service.extract_keywords(question)
            
            # 2. 生成Cypher查询语句
            cypher_query = self._generate_cypher_with_llm(question, keywords, context)
            
            # 3. 执行查询
            if cypher_query:
                result = self.graph.run(cypher_query, 
                                      keywords=keywords if keywords else [],
                                      question=question)
                return [dict(record) for record in result]
            else:
                return []
                
        except Exception as e:
            logger.error(f"AI图谱查询执行失败: {e}")
            return []
    
    def _generate_cypher_with_llm(self, question, keywords, context) -> str:
        """使用LLM将自然语言问题转换为Cypher查询语句"""  
        prompt = '''你是一个专业的Neo4j Cypher查询语句生成器。根据用户提供的自然语言查询，生成准确的Cypher语句。
  
  图数据库模式包括以下节点和关系：
  节点类型：
  - 保险产品(名称, 产品类别, 赔付限额, 免赔额, 赔付比例)
  - 保险公司(名称)
  - 保险责任(名称)
  - 疾病(名称, 分类)
  - 责任免除(内容)
  - 投保范围(描述)
  - 药品(产品名称, 剂型, 规格)
  - 医院(名称, 医院等级, 医院类型)
  - 省份(名称)
  - 城市(名称)
  - 区县(名称)
  
  关系类型：
  - 保险产品-[:包含责任]->保险责任
  - 保险产品-[:保障疾病]->疾病
  - 保险产品-[:免除责任]->责任免除
  - 保险产品-[:适用人群]->投保范围
  - 保险公司-[:推出产品]->保险产品
  - 药品-[:具有名称]->产品名称
  - 药品-[:具有剂型]->剂型
  - 药品-[:具有规格]->规格
  - 医院<-[:包含医院]-区县
  - 区县<-[:包含区县]-城市
  - 城市<-[:包含城市]-省份
  
  注意事项：
  1. 只返回Cypher查询语句，不包含其他说明文字
  2. 使用参数化查询，关键词使用$keywords参数，问题使用$question参数
  3. 查询应返回有意义的结果列，避免返回整个节点对象
  4. 对于模糊匹配使用CONTAINS操作符
  5. 如果查询涉及多个条件，使用WHERE子句组合
  6. 限制返回结果数量（LIMIT 50）
  7. 不要包含任何修改数据的操作（CREATE, DELETE, SET等）
  
  示例：
  用户查询："查找包含'癌症'保障的保险产品"
  Cypher查询：MATCH (p:保险产品)-[:保障疾病]->(d:疾病) WHERE any(k in $keywords WHERE d.名称 CONTAINS k) RETURN p.名称 as product_name, d.名称 as disease_name LIMIT 50
'''

        try:
            cypher_query = self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1  # 使用较低温度确保准确性
            )
            
            # 简单验证生成的查询是否合理
            if "MATCH" in cypher_query.upper() and "RETURN" in cypher_query.upper():
                logger.info(f"生成的Cypher查询: {cypher_query}")
                return cypher_query
            else:
                logger.warning("生成的Cypher查询不符合要求")
                return ""
                
        except Exception as e:
            logger.error(f"生成Cypher查询失败: {e}")
            return ""
    
    
    def search_insurance_products(self, keywords: List[str]) -> List[Dict]:
        """搜索保险产品"""
        query = """
        MATCH (product:保险产品)
        WHERE any(keyword IN $keywords WHERE product.名称 CONTAINS keyword 
               OR product.产品类别 CONTAINS keyword)
        OPTIONAL MATCH (product)-[:包含责任]->(duty:保险责任)
        OPTIONAL MATCH (product)-[:保障疾病]->(disease:疾病)
        OPTIONAL MATCH (product)-[:免除责任]->(exclusion:责任免除)
        OPTIONAL MATCH (product)-[:适用人群]->(scope:投保范围)
        OPTIONAL MATCH (company:保险公司)-[:推出产品]->(product)
        RETURN product.名称 as product_name,
           product.产品类别 as category,
           product.赔付限额 as limit,
           product.免赔额 as deductible,
           product.赔付比例 as ratio,
           company.名称 as company_name,
           collect(DISTINCT duty.名称) as duties,
           collect(DISTINCT disease.名称) as diseases,
           collect(DISTINCT exclusion.内容) as exclusions,
           collect(DISTINCT scope.描述) as scopes
    """
        result = self.graph.run(query, keywords=keywords)
        return [dict(record) for record in result]
    
    def search_diseases(self, disease_names: List[str]) -> List[Dict]:
        """搜索疾病保障信息"""
        query = """
        MATCH (disease:疾病)<-[:保障疾病]-(product:保险产品)
        WHERE any(name IN $disease_names WHERE disease.名称 CONTAINS name)
        OPTIONAL MATCH (company:保险公司)-[:推出产品]->(product)
        RETURN disease.名称 as disease_name,
               collect(DISTINCT {
                   product_name: product.名称,
                   company: company.名称,
                   category: product.产品类别
               }) as covered_products
        """
        result = self.graph.run(query, disease_names=disease_names)
        return [dict(record) for record in result]
    
    def search_companies(self, company_names: List[str]) -> List[Dict]:
        """搜索保险公司产品"""
        query = """
        MATCH (company:保险公司)-[:推出产品]->(product:保险产品)
        WHERE any(name IN $company_names WHERE company.名称 CONTAINS name)
        OPTIONAL MATCH (product)-[:包含责任]->(duty:保险责任)
        OPTIONAL MATCH (product)-[:保障疾病]->(disease:疾病)
        WITH company, product, collect(DISTINCT duty.名称) as duties, collect(DISTINCT disease.名称) as diseases
        RETURN company.名称 as company_name,
               collect(DISTINCT {
                   product_name: product.名称,
                   category: product.产品类别,
                   duties: duties,
                   diseases: diseases
               }) as products
        """
        result = self.graph.run(query, company_names=company_names)
        return [dict(record) for record in result]
    
    def get_product_details(self, product_name: str) -> Optional[Dict]:
        """获取产品详细信息"""
        query = """
        MATCH (product:保险产品 {名称: $product_name})
        OPTIONAL MATCH (company:保险公司)-[:推出产品]->(product)
        OPTIONAL MATCH (product)-[:包含责任]->(duty:保险责任)
        OPTIONAL MATCH (product)-[:保障疾病]->(disease:疾病)
        OPTIONAL MATCH (product)-[:免除责任]->(exclusion:责任免除)
        OPTIONAL MATCH (product)-[:适用人群]->(scope:投保范围)
        RETURN product,
               company.名称 as company_name,
               collect(DISTINCT duty.名称) as duties,
               collect(DISTINCT disease.名称) as diseases,
               collect(DISTINCT exclusion.内容) as exclusions,
               collect(DISTINCT scope.描述) as scopes
        """
        result = self.graph.run(query, product_name=product_name)
        record = result.data()
        return record[0] if record else None
    
    def compare_products(self, product_names: List[str]) -> List[Dict]:
        """比较多个保险产品"""
        query = """
        MATCH (product:保险产品)
        WHERE product.名称 IN $product_names
        OPTIONAL MATCH (company:保险公司)-[:推出产品]->(product)
        OPTIONAL MATCH (product)-[:包含责任]->(duty:保险责任)
        OPTIONAL MATCH (product)-[:保障疾病]->(disease:疾病)
        RETURN product.名称 as product_name,
               company.名称 as company_name,
               product.产品类别 as category,
               product.赔付限额 as limit,
               product.免赔额 as deductible,
               product.赔付比例 as ratio,
               collect(DISTINCT duty.名称) as duties,
               collect(DISTINCT disease.名称) as diseases
        ORDER BY product_name
        """
        result = self.graph.run(query, product_names=product_names)
        return [dict(record) for record in result]
    
    def search_drugs(self, drug_names: List[str]) -> List[Dict]:
        """搜索药品信息"""
        query = """
        MATCH (drug:药品)
        WHERE any(name IN $drug_names WHERE drug.产品名称 CONTAINS name)
        OPTIONAL MATCH (drug)-[:具有名称]->(name:产品名称)
        OPTIONAL MATCH (drug)-[:具有剂型]->(form:剂型)
        OPTIONAL MATCH (drug)-[:具有规格]->(spec:规格)
        RETURN drug.批准文号 as approval_number,
            drug.产品名称 as product_name,
            drug.剂型 as dosage_form,
            drug.规格 as specification,
            name.注册证号 as registration_number,
            name.上市许可持有人英文 as holder_english,
            name.药品编码 as drug_code,
            form.名称 as form_name,
            spec.名称 as spec_name
        """
        result = self.graph.run(query, drug_names=drug_names)
        return [dict(record) for record in result]

    def get_drug_details(self, drug_name: str) -> Optional[Dict]:
        """获取药品详细信息"""
        query = """
        MATCH (drug:药品 {产品名称: $drug_name})
        OPTIONAL MATCH (drug)-[:具有名称]->(name:产品名称)
        OPTIONAL MATCH (drug)-[:具有剂型]->(form:剂型)
        OPTIONAL MATCH (drug)-[:具有规格]->(spec:规格)
        RETURN drug,
            name.注册证号 as registration_number,
            name.上市许可持有人英文 as holder_english,
            name.药品编码 as drug_code,
            form.名称 as form_name,
            spec.名称 as spec_name
        """
        result = self.graph.run(query, drug_name=drug_name)
        record = result.data()
        return record[0] if record else None
    
    def search_hospitals(self, keywords: List[str]) -> List[Dict]:
        """搜索医院信息"""
        query = """
        MATCH (hospital:医院)
        WHERE any(keyword IN $keywords WHERE hospital.名称 CONTAINS keyword 
                OR hospital.医院别名 CONTAINS keyword)
        OPTIONAL MATCH (hospital)<-[:包含医院]-(district:区县)
        OPTIONAL MATCH (district)<-[:包含区县]-(city:城市)
        OPTIONAL MATCH (city)<-[:包含城市]-(province:省份)
        RETURN hospital.名称 as hospital_name,
            hospital.医院别名 as hospital_alias,
            hospital.医院等级 as hospital_level,
            hospital.医院类型 as hospital_type,
            hospital.经营方式 as management_type,
            hospital.是否医保 as is_medical_insurance,
            hospital.电话 as phone,
            hospital.医院地址 as address,
            province.名称 as province,
            city.名称 as city,
            district.名称 as district
        """
        result = self.graph.run(query, keywords=keywords)
        return [dict(record) for record in result]

    def get_hospital_details(self, hospital_name: str) -> Optional[Dict]:
        """获取医院详细信息"""
        query = """
        MATCH (hospital:医院 {名称: $hospital_name})
        OPTIONAL MATCH (hospital)<-[:包含医院]-(district:区县)
        OPTIONAL MATCH (district)<-[:包含区县]-(city:城市)
        OPTIONAL MATCH (city)<-[:包含城市]-(province:省份)
        RETURN hospital,
            province.名称 as province,
            city.名称 as city,
            district.名称 as district
        """
        result = self.graph.run(query, hospital_name=hospital_name)
        record = result.data()
        return record[0] if record else None
    
    def get_product_disease_coverage(self, product_name: str) -> List[Dict]:
        """获取产品保障的疾病列表"""
        query = """
        MATCH (product:保险产品 {名称: $product_name})
        -[:保障疾病]->(disease:疾病)
        RETURN disease.名称 as disease_name,
            disease.分类 as disease_category
        ORDER BY disease_name
        """
        result = self.graph.run(query, product_name=product_name)
        return [dict(record) for record in result]

    def get_company_products(self, company_name: str) -> List[Dict]:
        """获取公司所有产品"""
        query = """
        MATCH (company:保险公司 {名称: $company_name})
        -[:推出产品]->(product:保险产品)
        OPTIONAL MATCH (product)-[:包含责任]->(duty:保险责任)
        OPTIONAL MATCH (product)-[:保障疾病]->(disease:疾病)
        RETURN product.名称 as product_name,
            product.产品类别 as category,
            collect(DISTINCT duty.名称) as duties,
            collect(DISTINCT disease.名称) as diseases
        """
        result = self.graph.run(query, company_name=company_name)
        return [dict(record) for record in result]