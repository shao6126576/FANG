import pandas as pd
from py2neo import Graph, Node, Relationship
import re
from typing import List, Dict
from tqdm import tqdm

class InsuranceKGImporter:
    def __init__(self, uri, user, password):
        self.graph = Graph(uri, auth=(user, password))
        # self.clear_database()  # 清空现有数据库

    def clear_database(self):
        self.graph.run("MATCH (n) DETACH DELETE n")

    def _parse_exception_cell(self, text: str) -> List[Dict]:
        """解析"责任免除例外"单元格，返回结构化数据"""
        if not text:
            return []
        s = str(text).strip()
        # 统一换行
        s = s.replace("\r\n", "\n").replace("<br/>", "\n").replace("<br>", "\n")
        # 按 1. / 2. / 3. 这样的编号切段
        pattern = re.compile(r"^\s*(\d+)\.\s*(.+?)(?=^\s*\d+\.|\Z)", re.M | re.S)
        sections = pattern.findall(s)
        results: List[Dict] = []
        for _, content in sections:
            content = content.strip()
            if not content:
                continue
            # 头部：标题（含可选的（条款 x.x）），后接 "：" 描述
            if "：" in content:
                header, body = content.split("：", 1)
            else:
                header, body = content, ""

            header = header.strip()
            body = body.strip()

            # 抽取条款号（例如：不可抗辩例外（条款 7.2））
            article = None
            m = re.search(r"（\s*条款\s*([0-9.]+)\s*）", header)
            if m:
                article = m.group(1)
                exc_type = re.sub(r"（\s*条款\s*[0-9.]+\s*）", "", header).strip()
            else:
                exc_type = header

            # 抽取每一行的子条件（以 - 或 • 开头）
            lines = [ln.strip() for ln in body.split("\n")]
            conditions: List[str] = []
            diseases: List[str] = []
            for ln in lines:
                if not ln:
                    continue
                # 以 - 开头的是条件
                if re.match(r"^[-•—]\s*", ln):
                    item = re.sub(r"^[-•—]\s*", "", ln).strip()
                    conditions.append(item)

            # 如果是"遗传 / 先天疾病免责例外"，从条件行中提取疾病名（按中文顿号/逗号/斜杠分割）
            if "遗传" in exc_type or "先天" in exc_type or "疾病" in exc_type:
                for c in conditions or [body]:
                    # 常见分隔：顿号、逗号、斜杠、空格
                    parts = re.split(r"[、，,/；;]\s*", c)
                    for p in parts:
                        name = p.strip("：:。,.、；;（）() ").strip()
                        if name:
                            diseases.append(name)
                # 避免把整句条件都当成疾病；仅保留明显是"列表"的条目
                diseases = [d for d in diseases if len(d) <= 20]  # 简单裁剪避免整句
                diseases = list(dict.fromkeys(diseases))  # 去重

            results.append({
                "type": exc_type,
                "article": article,
                "desc": body if body else None,
                "conditions": conditions,
                "diseases": diseases
            })
        return results

    def _parse_disease_cell(self, text: str) -> List[str]:
        """解析"疾病"单元格，支持 1、2、3、 或 1. 2. 3. 的编号格式"""
        if not text:
            return []
        s = str(text).strip()
        s = s.replace("\r\n", "\n").replace("<br/>", "\n").replace("<br>", "\n")
        items: List[str] = []
        for line in s.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^\s*\d+[、\.．]\s*(.+?)\s*$", line)
            name = m.group(1).strip() if m else line
            # 规范清理左右空白/多余标点
            name = name.strip("：:。,.、；;（）() ").strip()
            if name:
                items.append(name)
        # 去重，保持顺序
        return list(dict.fromkeys(items))

    def import_insurance_data(self, excel_file):
        df = pd.read_excel(excel_file, sheet_name="RapidMiner Data")

        for _, row in tqdm(df.iterrows(), total=len(df), desc="导入保险数据", unit="条"):
            # 创建保险公司节点
            if pd.notna(row["公司名称"]):
                company_node = Node("公司名称", 名称=row["公司名称"])
                self.graph.merge(company_node, "公司名称", "名称")

            # 创建保险产品节点
            product_node = None
            if pd.notna(row["产品名称"]):
                product_node = Node("产品名称", 名称=row["产品名称"])
                self.graph.merge(product_node, "产品名称", "名称")

            # 创建关系：公司推出产品
            if pd.notna(row["公司名称"]) and product_node is not None:
                rel_company = Relationship(company_node, "提供产品", product_node)
                self.graph.merge(rel_company)

            # 处理备案名
            if pd.notna(row.get("备案名")) and product_node is not None:
                filing_name_node = Node("备案名称", 名称=row["备案名"])
                self.graph.merge(filing_name_node, "备案名称", "名称")
                rel_filing = Relationship(company_node, "发布产品备案", filing_name_node)
                self.graph.merge(rel_filing)
                rel_alias = Relationship(product_node, "别称为", filing_name_node)
                self.graph.merge(rel_alias)

            # 处理产品类别
            if pd.notna(row.get("产品类别")) and product_node is not None:
                category_node = Node("产品类别", 名称=row["产品类别"])
                self.graph.merge(category_node, "产品类别", "名称")
                rel_category = Relationship(company_node, "产品分类为", category_node)
                self.graph.merge(rel_category)

            # 处理销售状态
            if pd.notna(row.get("销售状态")) and product_node is not None:
                status_node = Node("销售状态", 状态=row["销售状态"])
                self.graph.merge(status_node, "销售状态", "状态")
                rel_status = Relationship(product_node, "标记为", status_node)
                self.graph.merge(rel_status)

            # 处理等待期
            if pd.notna(row.get("等待期")) and product_node is not None:
                waiting_period_node = Node("等待期", 期限=row["等待期"])
                self.graph.merge(waiting_period_node, "等待期", "期限")
                rel_waiting = Relationship(product_node, "设定等待期为", waiting_period_node)
                self.graph.merge(rel_waiting)

            # 处理犹豫期
            if pd.notna(row.get("犹豫期")) and product_node is not None:
                hesitation_period_node = Node("犹豫期", 期限=row["犹豫期"])
                self.graph.merge(hesitation_period_node, "犹豫期", "期限")
                rel_hesitation = Relationship(product_node, "规定犹豫期为", hesitation_period_node)
                self.graph.merge(rel_hesitation)

            # 处理保险期间
            if pd.notna(row.get("保险期间")) and product_node is not None:
                insurance_period_node = Node("保险期间", 期间=row["保险期间"])
                self.graph.merge(insurance_period_node, "保险期间", "期间")
                rel_period = Relationship(product_node, "约定保险期间为", insurance_period_node)
                self.graph.merge(rel_period)

            # 处理保证续保
            if pd.notna(row.get("保证续保")) and product_node is not None:
                renewable_node = Node("保证续保", 保证=row["保证续保"])
                self.graph.merge(renewable_node, "保证续保", "保证")
                rel_renewable = Relationship(product_node, "规定保证续保", renewable_node)
                self.graph.merge(rel_renewable)
                # 保证续保延长保险期间
                if pd.notna(row.get("保险期间")):
                    rel_extend = Relationship(renewable_node, "延长保险期间", insurance_period_node)
                    self.graph.merge(rel_extend)

            # 处理现金价值
            if pd.notna(row.get("现金价值")) and product_node is not None:
                cash_value_node = Node("现金价值", 价值=row["现金价值"])
                self.graph.merge(cash_value_node, "现金价值", "价值")
                rel_cash = Relationship(product_node, "根据规则计算", cash_value_node)
                self.graph.merge(rel_cash)

            # 处理保险责任
            if pd.notna(row.get("保险责任")) and product_node is not None:
                duties = str(row["保险责任"]).split("；")
                for duty in duties:
                    duty = duty.strip()
                    if duty:
                        duty_node = Node("保险责任", 责任=duty)
                        self.graph.merge(duty_node, "保险责任", "责任")
                        rel_duty = Relationship(product_node, "包含保险责任为", duty_node)
                        self.graph.merge(rel_duty)

            # 处理保险金计算方法
            if pd.notna(row.get("保险金计算方法")) and product_node is not None:
                calculation_node = Node("保险金计算方法", 方法=row["保险金计算方法"])
                self.graph.merge(calculation_node, "保险金计算方法", "方法")
                rel_calculation = Relationship(product_node, "规定保险金计算方法为", calculation_node)
                self.graph.merge(rel_calculation)
                # 保险责任决定保险金计算方法
                if pd.notna(row.get("保险责任")):
                    duties = str(row["保险责任"]).split("；")
                    for duty in duties:
                        duty = duty.strip()
                        if duty:
                            duty_node = Node("保险责任", 责任=duty)
                            self.graph.merge(duty_node, "保险责任", "责任")
                            rel_duty_calc = Relationship(duty_node, "决定保险金计算方法为", calculation_node)
                            self.graph.merge(rel_duty_calc)

            # 处理投保范围
            if pd.notna(row.get("投保范围")) and product_node is not None:
                scope_node = Node("投保范围", 范围=row["投保范围"])
                self.graph.merge(scope_node, "投保范围", "范围")
                rel_scope = Relationship(product_node, "规定投保范围为", scope_node)
                self.graph.merge(rel_scope)

            # 处理责任免除
            if pd.notna(row.get("责任免除")) and product_node is not None:
                exclusions = str(row["责任免除"]).split("<br>")
                for excl in exclusions:
                    excl = excl.strip()
                    if excl:
                        excl_node = Node("责任免除", 内容=excl)
                        self.graph.merge(excl_node, "责任免除", "内容")
                        rel_excl = Relationship(product_node, "规定责任免除为", excl_node)
                        self.graph.merge(rel_excl)

            # 处理疾病列表（从"疾病"列提取）
            if pd.notna(row.get("疾病")) and product_node is not None:
                diseases = self._parse_disease_cell(row["疾病"])
                for disease in diseases:
                    disease = disease.strip()
                    if disease:
                        disease_node = Node("疾病", 名称=disease)
                        self.graph.merge(disease_node, "疾病", "名称")
                        rel_disease = Relationship(product_node, "赔付疾病为", disease_node)
                        self.graph.merge(rel_disease)
                        # 保险责任覆盖疾病
                        if pd.notna(row.get("保险责任")):
                            duties = str(row["保险责任"]).split("；")
                            for duty in duties:
                                duty = duty.strip()
                                if duty:
                                    duty_node = Node("保险责任", 责任=duty)
                                    self.graph.merge(duty_node, "保险责任", "责任")
                                    rel_coverage = Relationship(duty_node, "覆盖疾病为", disease_node)
                                    self.graph.merge(rel_coverage)

            # 处理责任免除例外
            if pd.notna(row.get("责任免除例外")) and product_node is not None:
                exceptions = self._parse_exception_cell(row["责任免除例外"])
                for ex in exceptions:
                    exc_node = Node("责任免除例外", 类型=ex["type"])
                    if ex.get("article"):
                        exc_node["条款"] = ex["article"]
                    if ex.get("desc"):
                        exc_node["描述"] = ex["desc"]
                    # 使用类型+条款作为唯一键
                    unique_key = f"{ex['type']}"
                    if ex.get("article"):
                        unique_key += f"_{ex['article']}"
                    exc_node["类型_条款"] = unique_key
                    self.graph.merge(exc_node, "责任免除例外", "类型_条款")
                    self.graph.merge(Relationship(product_node, "存在例外", exc_node))

                    # 子条件
                    for cond in ex.get("conditions", []):
                        cond = cond.strip()
                        if not cond:
                            continue
                        cond_node = Node("例外条件", 名称=cond)
                        self.graph.merge(cond_node, "例外条件", "名称")
                        self.graph.merge(Relationship(exc_node, "适用条件", cond_node))

                    # 例外关联疾病
                    for dis in ex.get("diseases", []):
                        if not dis:
                            continue
                        disease_node = Node("疾病", 名称=dis)
                        self.graph.merge(disease_node, "疾病", "名称")
                        self.graph.merge(Relationship(exc_node, "例外适用疾病", disease_node))

    def import_drug_data_nation(self, excel_file):
        """导入药品数据并建立关系"""
        df = pd.read_excel(excel_file)
        
        for _, row in tqdm(df.iterrows(), total=len(df), desc="导入药品数据", unit="条"):
            # 创建药品节点
            drug_node = Node("药品名称", 名称=row["药品名称"])
            self.graph.merge(drug_node, "药品名称", "名称")
            
            # 创建批准文号节点并建立关系
            if pd.notna(row["批准文号"]):
                approval_node = Node("批准文号", 文号=row["批准文号"])
                self.graph.merge(approval_node, "批准文号", "文号")
                rel_approval = Relationship(drug_node, "具有批准文号", approval_node)
                self.graph.merge(rel_approval)
            
            # 创建剂型节点并建立关系
            if pd.notna(row["剂型"]):
                dosage_form_node = Node("剂型", 名称=row["剂型"])
                self.graph.merge(dosage_form_node, "剂型", "名称")
                rel_dosage = Relationship(drug_node, "剂型为", dosage_form_node)
                self.graph.merge(rel_dosage)
            
            # 创建规格节点并建立关系
            if pd.notna(row["规格"]):
                specification_node = Node("规格", 名称=row["规格"])
                self.graph.merge(specification_node, "规格", "名称")
                rel_spec = Relationship(drug_node, "规格为", specification_node)
                self.graph.merge(rel_spec)

            # 创建药品类型节点并建立关系
            if pd.notna(row["药品类型"]):
                drug_type_node = Node("药品类型", 类型=row["药品类型"])
                self.graph.merge(drug_type_node, "药品类型", "类型")
                rel_type = Relationship(drug_node, "属于药品类型", drug_type_node)
                self.graph.merge(rel_type)
            
            # 创建药品来源节点并建立关系
            if pd.notna(row["药品来源"]):
                source_node = Node("药品来源", 来源=row["药品来源"])
                self.graph.merge(source_node, "药品来源", "来源")
                rel_source = Relationship(drug_node, "来源于", source_node)
                self.graph.merge(rel_source)
            
            # 创建ATC分类节点并建立关系
            if pd.notna(row["ATC分类"]):
                atc_node = Node("ATC分类", 分类=row["ATC分类"])
                self.graph.merge(atc_node, "ATC分类", "分类")
                rel_atc = Relationship(drug_node, "治疗分类为", atc_node)
                self.graph.merge(rel_atc)

    
    def import_hospital_data(self, excel_file):
        """导入医院数据并建立关系"""
        df = pd.read_excel(excel_file)
        
        for _, row in tqdm(df.iterrows(), total=len(df), desc="导入医院数据", unit="条"):
            # 创建医院节点
            if pd.notna(row["医院名称"]):  # 添加检查确保医院名称不为空或NaN
                hospital_node = Node("医院名称", 名称=row["医院名称"])
                self.graph.merge(hospital_node, "医院名称", "名称")
            else:
                continue  # 如果没有有效的医院名称，则跳过该记录
            
            # 创建医院别名节点并建立关系
            if pd.notna(row["医院别名"]):
                alias_node = Node("医院别名", 别名=row["医院别名"])
                self.graph.merge(alias_node, "医院别名", "别名")
                rel_alias = Relationship(hospital_node, "别称", alias_node)
                self.graph.merge(rel_alias)
            
            # 创建医院等级节点并建立关系
            if pd.notna(row["医院等级"]):
                level_node = Node("医院等级", 等级=row["医院等级"])
                self.graph.merge(level_node, "医院等级", "等级")
                rel_level = Relationship(hospital_node, "等级为", level_node)
                self.graph.merge(rel_level)
            
            # 创建医院类型节点并建立关系
            if pd.notna(row["医院类型"]):
                type_node = Node("医院类型", 类型=row["医院类型"])
                self.graph.merge(type_node, "医院类型", "类型")
                rel_type = Relationship(hospital_node, "类型为", type_node)
                self.graph.merge(rel_type)
            
            # 创建经营方式节点并建立关系
            if pd.notna(row["产权性质"]):
                operation_node = Node("产权性质", 性质=row["产权性质"])
                self.graph.merge(operation_node, "产权性质", "性质")
                rel_operation = Relationship(hospital_node, "产权性质为", operation_node)
                self.graph.merge(rel_operation)
            
            # 创建电话节点并建立关系
            if pd.notna(row["电话"]):
                phone_node = Node("电话", 号码=row["电话"])
                self.graph.merge(phone_node, "电话", "号码")
                rel_phone = Relationship(hospital_node, "联系方式为", phone_node)
                self.graph.merge(rel_phone)
            
            # 创建医院地址节点并建立关系
            if pd.notna(row["医院地址"]):
                address_node = Node("医院地址", 地址=row["医院地址"])
                self.graph.merge(address_node, "医院地址", "地址")
                rel_address = Relationship(hospital_node, "地址为", address_node)
                self.graph.merge(rel_address)
            
            # 创建省份节点并建立关系
            if pd.notna(row["省"]):
                province_node = Node("省", 名称=row["省"])
                self.graph.merge(province_node, "省", "名称")
                rel_province = Relationship(hospital_node, "隶属于省", province_node)
                self.graph.merge(rel_province)
            
            # 创建城市节点并建立关系
            if pd.notna(row["市"]):
                city_node = Node("市", 名称=row["市"])
                self.graph.merge(city_node, "市", "名称")
                rel_city = Relationship(hospital_node, "隶属于市", city_node)
                self.graph.merge(rel_city)
            
            # 创建区县节点并建立关系
            if pd.notna(row["区县"]):
                district_node = Node("区县", 名称=row["区县"])
                self.graph.merge(district_node, "区县", "名称")
                rel_district = Relationship(hospital_node, "隶属于区县", district_node)
                self.graph.merge(rel_district)

    def import_court_data(self, excel_file):
        """导入法院数据并建立关系"""
        df = pd.read_excel(excel_file)
        
        for _, row in tqdm(df.iterrows(), total=len(df), desc="导入法院数据", unit="条"):
            # 创建案件节点
            case_node = Node("案件名称", 名称=row["案件名称"])
            self.graph.merge(case_node, "案件名称", "名称")
            
            # 创建案号节点并建立关系
            if pd.notna(row.get("案号")):
                case_number_node = Node("案号", 编号=row["案号"])
                self.graph.merge(case_number_node, "案号", "编号")
                rel_number = Relationship(case_node, "编号为", case_number_node)
                self.graph.merge(rel_number)
            
            # 创建案件类型节点并建立关系
            if pd.notna(row.get("案件类型")):
                case_type_node = Node("案件类型", 类型=row["案件类型"])
                self.graph.merge(case_type_node, "案件类型", "类型")
                rel_type = Relationship(case_node, "属于", case_type_node)
                self.graph.merge(rel_type)
            
            # 创建审理程序节点并建立关系
            if pd.notna(row.get("审理程序")):
                procedure_node = Node("审理程序", 程序=row["审理程序"])
                self.graph.merge(procedure_node, "审理程序", "程序")
                rel_procedure = Relationship(case_node, "处于程序", procedure_node)
                self.graph.merge(rel_procedure)
            
            # 创建裁判日期节点并建立关系
            if pd.notna(row.get("裁判日期")):
                judgment_date_node = Node("裁判日期", 日期=row["裁判日期"])
                self.graph.merge(judgment_date_node, "裁判日期", "日期")
                rel_date = Relationship(case_node, "裁判日期为", judgment_date_node)
                self.graph.merge(rel_date)
            
            # 创建险种节点并建立关系
            if pd.notna(row.get("险种")):
                insurance_type_node = Node("险种", 类型=row["险种"])
                self.graph.merge(insurance_type_node, "险种", "类型")
                rel_insurance = Relationship(case_node, "涉及险种", insurance_type_node)
                self.graph.merge(rel_insurance)
            
            # 创建法律依据节点并建立关系
            if pd.notna(row.get("法律依据")):
                legal_basis_node = Node("法律依据", 依据=row["法律依据"])
                self.graph.merge(legal_basis_node, "法律依据", "依据")
                rel_legal = Relationship(case_node, "依据法律条文", legal_basis_node)
                self.graph.merge(rel_legal)
            
            # 创建当事人节点并建立关系
            if pd.notna(row.get("当事人")):
                parties = str(row["当事人"]).split(";")
                for party in parties:
                    party = party.strip()
                    if party:
                        party_node = Node("当事人", 名称=party)
                        self.graph.merge(party_node, "当事人", "名称")
                        rel_party = Relationship(case_node, "包括当事人", party_node)
                        self.graph.merge(rel_party)
            
            # 创建上诉摘要节点并建立关系
            if pd.notna(row.get("上诉摘要")):
                appeal_node = Node("上诉摘要", 摘要=row["上诉摘要"])
                self.graph.merge(appeal_node, "上诉摘要", "摘要")
                rel_appeal = Relationship(case_node, "包括上诉摘要", appeal_node)
                self.graph.merge(rel_appeal)
                
                # 上诉摘要反映争议类型
                if pd.notna(row.get("案件类型")):
                    rel_reflect = Relationship(appeal_node, "反映争议类型", case_type_node)
                    self.graph.merge(rel_reflect)
            
            # 创建判决摘要节点并建立关系
            if pd.notna(row.get("判决摘要")):
                judgment_node = Node("判决摘要", 摘要=row["判决摘要"])
                self.graph.merge(judgment_node, "判决摘要", "摘要")
                rel_judgment = Relationship(case_node, "包含判决摘要", judgment_node)
                self.graph.merge(rel_judgment)
                
                # 上诉摘要针对判决摘要
                if pd.notna(row.get("上诉摘要")):
                    appeal_node = Node("上诉摘要", 摘要=row["上诉摘要"])
                    self.graph.merge(appeal_node, "上诉摘要", "摘要")
                    rel_target = Relationship(appeal_node, "针对判决摘要", judgment_node)
                    self.graph.merge(rel_target)
            
            # 创建法院节点并建立关系
            if pd.notna(row.get("法院")):
                court_node = Node("法院", 名称=row["法院"])
                self.graph.merge(court_node, "法院", "名称")
                rel_court = Relationship(court_node, "审理", case_node)
                self.graph.merge(rel_court)
                
                # 法院作出裁判日期
                if pd.notna(row.get("裁判日期")):
                    rel_court_date = Relationship(court_node, "作出裁判日期", judgment_date_node)
                    self.graph.merge(rel_court_date)
                
                # 法院作出判决摘要
                if pd.notna(row.get("判决摘要")):
                    rel_court_judgment = Relationship(court_node, "作出判决摘要", judgment_node)
                    self.graph.merge(rel_court_judgment)

class KnowledgeGraphVisualizer:
    
    def __init__(self, uri, user, password):
        self.graph = Graph(uri, auth=(user, password))
        
    def get_node_labels(self) -> List[str]:
        """
        获取图数据库中所有节点标签
        
        Returns:
            节点标签列表
        """
        query = "CALL db.labels()"
        result = self.graph.run(query)
        return [record["label"] for record in result]
    
    def get_relationship_types(self) -> List[str]:
        """
        获取图数据库中所有关系类型
        
        Returns:
            关系类型列表
        """
        query = "CALL db.relationshipTypes()"
        result = self.graph.run(query)
        return [record["relationshipType"] for record in result]
        
    def get_statistics(self):
        """
        获取图数据库统计信息
        
        Returns:
            统计信息字典
        """
        stats = {}
        
        # 获取节点标签统计
        node_stats_query = """
        MATCH (n)
        RETURN labels(n) AS label, count(*) AS count
        ORDER BY count DESC
        """
        node_stats_result = self.graph.run(node_stats_query)
        stats["node_labels"] = [(record["label"][0], record["count"]) for record in node_stats_result]
        
        # 获取关系类型统计
        rel_stats_query = """
        MATCH ()-[r]->()
        RETURN type(r) AS relationshipType, count(*) AS count
        ORDER BY count DESC
        """
        rel_stats_result = self.graph.run(rel_stats_query)
        stats["relationship_types"] = [(record["relationshipType"], record["count"]) for record in rel_stats_result]
        
        # 获取节点总数
        node_count_query = "MATCH (n) RETURN count(n) AS count"
        node_count_result = self.graph.run(node_count_query)
        stats["total_nodes"] = node_count_result.evaluate()
        
        # 获取关系总数
        rel_count_query = "MATCH ()-[r]->() RETURN count(r) AS count"
        rel_count_result = self.graph.run(rel_count_query)
        stats["total_relationships"] = rel_count_result.evaluate()
        
        return stats
    
    def print_statistics(self):
        """
        打印图数据库统计信息
        """
        stats = self.get_statistics()
        
        print("=" * 50)
        print("医疗保险知识图谱统计信息")
        print("=" * 50)
        print(f"总节点数: {stats['total_nodes']}")
        print(f"总关系数: {stats['total_relationships']}")
        print("\n节点标签统计:")
        for label, count in stats["node_labels"]:
            print(f"  {label}: {count}")
        print("\n关系类型统计:")
        for rel_type, count in stats["relationship_types"]:
            print(f"  {rel_type}: {count}")
        print("=" * 50)


if __name__ == "__main__":
    
    NEO4J_URI: str = "NEO4J_URI"
    NEO4J_USERNAME: str = "NEO4J_USERNAME"
    NEO4J_PASSWORD: str = "NEO4J_PASSWORD"

    importer = InsuranceKGImporter(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    importer.import_insurance_data("重疾与健康保险产品.xls")
    importer.import_drug_data_nation("处方药目录.xlsx")
    importer.import_hospital_data("全国二级以上医院数据库.xlsx")
    importer.import_court_data("保险纠纷-健康险.xlsx")
    print("医疗保险知识图谱构建完成")

    visualizer = KnowledgeGraphVisualizer(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    visualizer.print_statistics()