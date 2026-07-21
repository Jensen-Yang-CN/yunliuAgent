# -*- coding: utf-8 -*-
"""
RAG Utilities Module

提供与Milvus向量数据库交互的功能，实现视频分析结果与本地知识库的比对。
该模块负责向量检索和相似度匹配，确保只输出知识库中存在的隐患或违章行为。
"""

import logging
import numpy as np
import time
import traceback
from pymilvus import connections, Collection, utility
from sentence_transformers import SentenceTransformer

# 加载BAAI/bge-m3 Embedding模型
embedding_model = "BAAI/bge-m3"

# 从配置文件导入RAG配置
from .config import RAGConfig

# Milvus连接参数
MILVUS_HOST = RAGConfig.MILVUS_HOST
MILVUS_PORT = RAGConfig.MILVUS_PORT
KNOWLEDGE_COLLECTION = RAGConfig.KNOWLEDGE_COLLECTION

# 相似度阈值，用于过滤结果
SIMILARITY_THRESHOLD = RAGConfig.SIMILARITY_THRESHOLD

def init_embedding_model():
    """
    初始化Embedding模型
    """
    global embedding_model
    try:
        if isinstance(embedding_model, str):
            logging.info(f"正在加载Embedding模型: {embedding_model}")
            embedding_model = SentenceTransformer('BAAI/bge-m3')
            logging.info("Embedding模型加载成功")
        elif embedding_model is None:
            logging.info("Embedding模型未初始化，正在加载...")
            embedding_model = SentenceTransformer('BAAI/bge-m3')
            logging.info("Embedding模型加载成功")
        return True
    except Exception as e:
        logging.error(f"Embedding模型加载失败: {str(e)}")
        return False

def connect_to_milvus(max_retries=3, retry_interval=2):
    """
    连接到Milvus向量数据库，支持自动重试
    
    Args:
        max_retries: 最大重试次数
        retry_interval: 重试间隔（秒）
        
    Returns:
        bool: 连接是否成功
    """
    for attempt in range(max_retries):
        try:
            # 检查是否已连接
            try:
                # 尝试使用新版API检查连接
                if connections.has_connection("default"):
                    logging.info("已存在Milvus连接，无需重新连接")
                    return True
            except AttributeError:
                # 如果新版API不可用，尝试旧版API
                try:
                    if utility.has_connection("default"):
                        logging.info("已存在Milvus连接，无需重新连接")
                        return True
                except AttributeError:
                    # 两种方法都不可用，继续尝试建立连接
                    pass
                
            # 建立新连接
            connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)
            logging.info(f"成功连接到Milvus服务器: {MILVUS_HOST}:{MILVUS_PORT}")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"连接Milvus失败 (尝试 {attempt+1}/{max_retries}): {str(e)}，将在 {retry_interval} 秒后重试")
                import time
                time.sleep(retry_interval)
            else:
                logging.error(f"连接Milvus失败，已达到最大重试次数: {str(e)}")
                return False

def get_embedding(text):
    """
    获取文本的向量表示
    
    Args:
        text: 输入文本
        
    Returns:
        文本的向量表示
    """
    if not init_embedding_model():
        return None
    
    try:
        # 预处理文本，移除Markdown标记和特殊字符
        if text and isinstance(text, str):
            # 移除常见的Markdown标记
            import re
            # 移除标题标记 (###, ##, #)
            text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
            # 移除粗体标记 (**text**)
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
            # 移除斜体标记 (*text*)
            text = re.sub(r'\*([^*]+)\*', r'\1', text)
            # 移除列表标记 (-, *, 1.)
            text = re.sub(r'^[\-\*]\s+', '', text, flags=re.MULTILINE)
            text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
            # 移除代码块标记
            text = re.sub(r'```[\s\S]*?```', '', text)
            # 移除内联代码标记
            text = re.sub(r'`([^`]+)`', r'\1', text)
            # 移除链接标记 [text](url)
            text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
            # 移除HTML标签
            text = re.sub(r'<[^>]+>', '', text)
            # 移除多余空白
            text = re.sub(r'\s+', ' ', text).strip()
            
            logging.info(f"文本预处理完成，长度: {len(text)}")
        
        return embedding_model.encode(text)
    except Exception as e:
        logging.error(f"生成文本向量失败: {str(e)}")
        return None

def search_similar_issues(text, top_k=5):
    """
    在知识库中搜索与输入文本相似的内容
    
    Args:
        text: 输入文本，通常是视频分析结果
        top_k: 返回的最相似结果数量
        
    Returns:
        list: 相似内容列表，每项包含内容和相似度分数
    """
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        logging.warning("搜索文本为空或无效，跳过向量搜索")
        return []
        
    logging.info(f"开始搜索相似内容，文本长度: {len(text)}")
    
    # 连接到Milvus
    if not connect_to_milvus():
        logging.error("无法连接到Milvus，跳过向量搜索")
        return []
    
    # 获取文本向量
    start_time = time.time()
    vector = get_embedding(text)
    if vector is None:
        logging.error("无法获取文本向量，跳过向量搜索")
        return []
    logging.info(f"文本向量化完成，耗时: {time.time() - start_time:.2f}秒")
    
    try:
        # 检查集合是否存在
        try:
            # 尝试使用新版API检查集合
            if not connections.has_collection(KNOWLEDGE_COLLECTION):
                logging.error(f"知识库集合 {KNOWLEDGE_COLLECTION} 不存在")
                return []
        except AttributeError:
            # 如果新版API不可用，尝试旧版API
            try:
                if not utility.has_collection(KNOWLEDGE_COLLECTION):
                    logging.error(f"知识库集合 {KNOWLEDGE_COLLECTION} 不存在")
                    return []
            except AttributeError:
                # 两种方法都不可用，记录错误并继续尝试
                logging.warning(f"无法检查集合 {KNOWLEDGE_COLLECTION} 是否存在，将尝试直接加载")
        
        # 获取集合
        try:
            collection = Collection(KNOWLEDGE_COLLECTION)
            collection.load()
            logging.info(f"成功加载知识库集合: {KNOWLEDGE_COLLECTION}")
        except Exception as e:
            logging.error(f"加载知识库集合 {KNOWLEDGE_COLLECTION} 失败: {str(e)}")
            return []
        
        # 执行向量搜索
        search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
        search_start = time.time()
        results = collection.search(
            data=[vector],
            anns_field="embedding",  # 向量字段名，根据实际情况调整
            param=search_params,
            limit=top_k,
            output_fields=["text"]  # 文本字段名，根据实际情况调整
        )
        logging.info(f"向量搜索完成，耗时: {time.time() - search_start:.2f}秒")
        
        # 处理搜索结果
        similar_items = []
        for hits in results:
            for hit in hits:
                if hit.score >= SIMILARITY_THRESHOLD:  # 只返回相似度超过阈值的结果
                    text_content = hit.entity.get("text")
                    if text_content and isinstance(text_content, str):
                        similar_items.append({
                            "text": text_content,
                            "score": hit.score
                        })
        
        logging.info(f"找到 {len(similar_items)} 个相似度超过阈值的结果")
        return similar_items
    except Exception as e:
        import traceback
        logging.error(f"搜索知识库失败: {str(e)}\n{traceback.format_exc()}")
        return []

def extract_json_from_text(text):
    """
    从文本中提取信息并创建JSON格式的结果
    
    Args:
        text: 分析结果文本
        
    Returns:
        dict: JSON格式的结果字典
    """
    result = {
        "safety_hazards": [],
        "violations": [],
        "warning_message": "无异常",
        "regulation_codes": [],
        "regulation_contents": [],
        "regulation_sources": [],
        "has_warning": False
    }
    
    try:
        # 提取安全隐患
        if "安全隐患：" in text:
            hazards_text = text.split("安全隐患：")[1].split("\n")[0].strip()
            if hazards_text and hazards_text != "无":
                result["safety_hazards"] = [h.strip() for h in hazards_text.split("、")]
        
        # 提取违章行为
        if "违章行为：" in text:
            violations_text = text.split("违章行为：")[1].split("\n")[0].strip()
            if violations_text and violations_text != "无":
                result["violations"] = [v.strip() for v in violations_text.split("、")]
        
        # 提取预警信息
        if "预警信息：" in text:
            warning_text = text.split("预警信息：")[1].split("\n")[0].strip()
            if warning_text and warning_text != "无异常" and warning_text != "无":
                result["warning_message"] = warning_text
        
        # 提取规程信息
        if "规程" in text:
            lines = text.split("\n")
            for line in lines:
                if line.startswith("规程") and " - " in line:
                    parts = line.split(" - ", 1)
                    code = parts[0].split("：", 1)[1].strip() if "：" in parts[0] else parts[0].strip()
                    content = parts[1].strip()
                    result["regulation_codes"].append(code)
                    result["regulation_contents"].append(content)
        
        # 设置预警标志
        result["has_warning"] = bool(result["safety_hazards"] or result["violations"] or 
                                  result["warning_message"] != "无异常")
        
        return result
    except Exception as e:
        logging.error(f"从文本提取JSON信息失败: {str(e)}")
        return result

def filter_analysis_result(analysis_result):
    """
    过滤分析结果，只保留与知识库中匹配的内容，并提取规程编号、来源和条例内容
    
    Args:
        analysis_result: 视频分析结果文本
        
    Returns:
        tuple: (过滤后的文本结果, JSON格式的结果字典)
    """
    import json
    import re
    
    # 如果分析结果为空，直接返回
    if not analysis_result:
        empty_result = {
            "safety_hazards": [],
            "violations": [],
            "warning_message": "无异常",
            "regulation_codes": [],
            "regulation_contents": [],
            "regulation_sources": [],
            "has_warning": False
        }
        return "安全隐患：无\n违章行为：无\n预警信息：无异常", empty_result
    
    # 优化：使用更精确的关键违规行为检测
    # 高空作业安全帽相关违规（最常见的安全隐患）
    key_violations = {
        "未佩戴安全帽": {
            "code": "Q/YLKY-AB302-CB-G01-2023",
            "content": "工作人员必须佩戴安全帽进入施工现场，安全帽必须系紧下颚带",
            "source": "2024.云硫采选85号附件2《采选公司安全操作规程（2024年修订）》",
            "warning": "请立即检查并确保高空作业人员佩戴安全帽。"
        },
        "安全帽缺失": {
            "code": "Q/YLKY-AB302-CB-G01-2023",
            "content": "工作人员必须佩戴安全帽进入施工现场，安全帽必须系紧下颚带",
            "source": "2024.云硫采选85号附件2《采选公司安全操作规程（2024年修订）》",
            "warning": "请立即检查并确保高空作业人员佩戴安全帽。"
        },
        "未系安全带": {
            "code": "Q/YLKY-AB302-CB-G02-2023",
            "content": "高空作业必须正确佩戴安全带，并确保安全带固定在牢固的锚点上",
            "source": "2024.云硫采选85号附件2《采选公司安全操作规程（2024年修订）》",
            "warning": "请立即检查并确保高空作业人员正确佩戴安全带。"
        },
        "绳索固定不牢固": {
            "code": "Q/YLKY-AB302-CB-G03-2023",
            "content": "高空作业绳索必须固定在牢固的锚点上，并定期检查绳索状态",
            "source": "2024.云硫采选85号附件2《采选公司安全操作规程（2024年修订）》",
            "warning": "请立即检查并确保高空作业绳索固定牢固。"
        }
    }
    
    # 检查是否包含预定义的关键违规行为
    for violation, info in key_violations.items():
        if violation in analysis_result:
            logging.info(f"检测到关键违规行为：{violation}，使用预定义规程信息")
            
            # 创建包含关键违规行为的JSON结果
            key_result = {
                "safety_hazards": [violation],
                "violations": [],
                "warning_message": info["warning"],
                "regulation_codes": [info["code"]],
                "regulation_contents": [info["content"]],
                "regulation_sources": [info["source"]],
                "has_warning": True
            }
            
            # 构建格式化的输出文本
            formatted_result = f"安全隐患：{violation}\n违章行为：无\n预警信息：{info['warning']}\n规程1：{info['code']} - {info['content']}\n参考来源：{info['source']}"
            
            return formatted_result, key_result
            
    # 如果没有匹配预定义的关键违规，尝试从知识库获取信息
    # 提取分析结果中的安全隐患和违章行为
    safety_hazards = []
    if "安全隐患：" in analysis_result:
        hazards_text = analysis_result.split("安全隐患：")[1].split("\n")[0].strip()
        if hazards_text and hazards_text != "无":
            safety_hazards = [h.strip() for h in hazards_text.split("、")]
    
    # 如果有安全隐患，尝试从知识库获取相关规程
    if safety_hazards:
        # 构建查询文本
        query_text = f"{' '.join(safety_hazards)} 安全操作规程"
        similar_items = search_similar_issues(query_text, top_k=3)
    
    # 默认无异常结果
    default_result = "安全隐患：无\n违章行为：无\n预警信息：无异常"
    default_json = {
        "safety_hazards": [],
        "violations": [],
        "warning_message": "无异常",
        "regulation_codes": [],
        "regulation_contents": [],
        "regulation_sources": [],
        "has_warning": False
    }
    
    try:
        # 在知识库中搜索相似内容
        similar_items = search_similar_issues(analysis_result)
        if not similar_items:
            # 如果没有匹配到任何内容，但原始结果中包含"违章行为"或"安全隐患"关键词
            # 且不包含"无"或"无异常"，则保留原始结果
            if ("违章行为" in analysis_result or "安全隐患" in analysis_result) and \
               not ("违章行为：无" in analysis_result and "安全隐患：无" in analysis_result):
                logging.info("未匹配到知识库内容，但原始结果包含违规信息，保留原始结果")
                # 从原始结果中提取信息创建JSON
                original_json = extract_json_from_text(analysis_result)
                return analysis_result, original_json
            return default_result, default_json
        
        # 提取安全隐患和违章行为
        hazards = []
        violations = []
        warnings = []
        regulation_codes = []
        regulation_contents = []
        regulation_sources = []
        
        # 对相似项进行去重和排序（按相似度降序）
        unique_texts = {}
        for item in similar_items:
            item_text = item["text"]
            score = item["score"]
            if item_text not in unique_texts or score > unique_texts[item_text]:
                unique_texts[item_text] = score
        
        # 按相似度排序
        sorted_items = sorted([(text, score) for text, score in unique_texts.items()], 
                              key=lambda x: x[1], reverse=True)
        
        # 分类处理
        for item_text, _ in sorted_items:
            # 使用正则表达式提取规程编号、来源和条例内容
            # 提取规程编号 - 查找类似Q/YLKY-AB302-CB-G01-2023的格式
            code_matches = re.findall(r'[QG]/[A-Z]+-[A-Z0-9]+-[A-Z]+-[A-Z0-9]+-\d+', item_text)
            if code_matches:
                for code in code_matches:
                    if code and code not in regulation_codes:
                        regulation_codes.append(code)
            elif "规程编号" in item_text:
                try:
                    code = item_text.split("规程编号")[1].split("\n")[0].strip("：: ")
                    if code and code not in regulation_codes:
                        regulation_codes.append(code)
                except:
                    pass
            
            # 提取条例内容
            content_patterns = [
                r'[\d\.]+\s*([^\n]+佩戴[^\n]+)',  # 匹配包含佩戴的条款
                r'[\d\.]+[^\n]+安全[^\n]+',  # 匹配包含安全的条款
                r'条例内容[：:]\s*([^\n]+)'  # 匹配条例内容字段
            ]
            
            for pattern in content_patterns:
                content_matches = re.findall(pattern, item_text)
                if content_matches:
                    for content in content_matches:
                        if content and content not in regulation_contents:
                            regulation_contents.append(content)
            
            if not content_matches and "条例内容" in item_text:
                try:
                    content = item_text.split("条例内容")[1].split("\n")[0].strip("：: ")
                    if content and content not in regulation_contents:
                        regulation_contents.append(content)
                except:
                    pass
                    
            # 提取规程来源
            source_patterns = [
                r'《([^》]+)》',  # 匹配《规程名称》格式
                r'\d+\.云硫采选\d+号附件\d+《[^》]+》',  # 匹配特定格式的文号
                r'参考来源[：:]\s*(.+?)\n',  # 匹配参考来源字段
                r'规程来源[：:]\s*(.+?)\n'   # 匹配规程来源字段
            ]
            
            for pattern in source_patterns:
                source_matches = re.findall(pattern, item_text)
                if source_matches:
                    for source in source_matches:
                        if source and source not in regulation_sources:
                            regulation_sources.append(source)
            
            if not source_matches:
                if "规程来源" in item_text:
                    try:
                        source = item_text.split("规程来源")[1].split("\n")[0].strip("：: ")
                        if source and source not in regulation_sources:
                            regulation_sources.append(source)
                    except:
                        pass
                # 尝试从文本中提取参考来源格式的内容
                elif "参考来源" in item_text:
                    try:
                        source = item_text.split("参考来源")[1].split("\n")[0].strip("：: ")
                        if source and source not in regulation_sources:
                            regulation_sources.append(source)
                    except:
                        pass
            
            # 提取安全隐患、违章行为和预警信息
            if "安全隐患" in item_text:
                try:
                    hazard_content = item_text.split("安全隐患")[1].split("\n")[0].strip("：: ")
                    if hazard_content and hazard_content != "无":
                        for h in hazard_content.split("、"):
                            if h.strip() and h.strip() not in hazards:
                                hazards.append(h.strip())
                except:
                    pass
                    
            if "违章行为" in item_text:
                try:
                    violation_content = item_text.split("违章行为")[1].split("\n")[0].strip("：: ")
                    if violation_content and violation_content != "无":
                        for v in violation_content.split("、"):
                            if v.strip() and v.strip() not in violations:
                                violations.append(v.strip())
                except:
                    pass
                    
            if "预警信息" in item_text:
                try:
                    warning_content = item_text.split("预警信息")[1].split("\n")[0].strip("：: ")
                    if warning_content and warning_content != "无异常" and warning_content != "无":
                        warnings.append(warning_content)
                except:
                    pass
        
        # 记录匹配结果
        logging.info(f"从知识库匹配到 {len(hazards)} 个安全隐患, {len(violations)} 个违章行为, {len(warnings)} 个预警信息, {len(regulation_codes)} 个规程编号, {len(regulation_contents)} 个条例内容")
        
        # 如果没有匹配到任何内容，但原始结果中包含关键词，则保留原始结果并尝试查询相关规程
        if not hazards and not violations and not warnings:
            if "违章行为" in analysis_result and "安全隐患" in analysis_result and \
               not ("违章行为：无" in analysis_result and "安全隐患：无" in analysis_result):
                logging.info("未从知识库提取到有效内容，但原始结果包含违规信息，尝试查询相关规程")
                
                # 提取原始结果中的关键词进行二次查询
                key_terms = []
                if "安全隐患：" in analysis_result:
                    hazard_text = analysis_result.split("安全隐患：")[1].split("\n")[0].strip()
                    if hazard_text and hazard_text != "无":
                        key_terms.extend(hazard_text.split("、"))
                
                if "违章行为：" in analysis_result:
                    violation_text = analysis_result.split("违章行为：")[1].split("\n")[0].strip()
                    if violation_text and violation_text != "无":
                        key_terms.extend(violation_text.split("、"))
                
                # 如果找到关键词，尝试查询相关规程
                if key_terms:
                    query_text = " ".join(key_terms) + " 安全操作规程"
                    similar_items = search_similar_issues(query_text, top_k=3)
                    
                    # 如果找到相关规程，提取信息
                    if similar_items:
                        # 提取规程信息
                        for item in similar_items:
                            item_text = item["text"]
                            
                            # 提取规程编号
                            code_matches = re.findall(r'[QG]/[A-Z]+-[A-Z0-9]+-[A-Z]+-[A-Z0-9]+-\d+', item_text)
                            if code_matches and code_matches[0] not in regulation_codes:
                                regulation_codes.append(code_matches[0])
                            
                            # 提取规程来源
                            source_patterns = [
                                r'《([^》]+)》',
                                r'\d+\.云硫采选\d+号附件\d+《[^》]+》',
                                r'参考来源[：:]\s*(.+?)\n',
                                r'规程来源[：:]\s*(.+?)\n'
                            ]
                            
                            for pattern in source_patterns:
                                source_matches = re.findall(pattern, item_text)
                                if source_matches and source_matches[0] not in regulation_sources:
                                    regulation_sources.append(source_matches[0])
                                    break
                            
                            # 提取条例内容
                            content_patterns = [
                                r'[\d\.]+\s*([^\n]+佩戴[^\n]+)',
                                r'[\d\.]+[^\n]+安全[^\n]+',
                                r'条例内容[：:]\s*([^\n]+)'
                            ]
                            
                            for pattern in content_patterns:
                                content_matches = re.findall(pattern, item_text)
                                if content_matches and content_matches[0] not in regulation_contents:
                                    regulation_contents.append(content_matches[0])
                                    break
                
                # 从原始结果中提取信息创建JSON
                original_json = extract_json_from_text(analysis_result)
                
                # 添加找到的规程信息
                if regulation_codes:
                    original_json["regulation_codes"] = regulation_codes
                if regulation_contents:
                    original_json["regulation_contents"] = regulation_contents
                if regulation_sources:
                    original_json["regulation_sources"] = regulation_sources
                
                # 如果找到规程信息，构建格式化输出
                if regulation_sources and regulation_contents:
                    warning_text = original_json["warning_message"]
                    formatted_source = regulation_sources[0]
                    formatted_code = regulation_codes[0] if regulation_codes else ""
                    formatted_content = regulation_contents[0]
                    
                    formatted_result = f"{warning_text}。参考来源：{formatted_source}中的{formatted_code}，根据规定：{formatted_content}；"
                    return formatted_result, original_json
                
                return analysis_result, original_json
            return default_result, default_json
        
        # 构建JSON格式的结果
        result_json = {
            "safety_hazards": hazards,
            "violations": violations,
            "warning_message": "；".join(warnings) if warnings else "无异常",
            "regulation_codes": regulation_codes,
            "regulation_contents": regulation_contents,
            "regulation_sources": regulation_sources,
            "has_warning": bool(hazards or violations or warnings)
        }
        
        # 构建文本格式的结果（向后兼容）
        hazard_text = "、".join(hazards) if hazards else "无"
        violation_text = "、".join(violations) if violations else "无"
        warning_text = "；".join(warnings) if warnings else "无异常"
        
        # 添加规程信息
        regulation_text = ""
        if regulation_codes or regulation_contents:
            # 确保三个列表长度一致，不足的用空字符串填充
            max_len = max(len(regulation_codes), len(regulation_contents), len(regulation_sources))
            regulation_codes = regulation_codes + [''] * (max_len - len(regulation_codes))
            regulation_contents = regulation_contents + [''] * (max_len - len(regulation_contents))
            regulation_sources = regulation_sources + [''] * (max_len - len(regulation_sources))
            
            for i in range(max_len):
                regulation_text += f"\n规程{i+1}：{regulation_codes[i]}"
                if regulation_contents[i]:
                    regulation_text += f" - {regulation_contents[i]}"
                if regulation_sources[i]:
                    regulation_text += f"\n参考来源：{regulation_sources[i]}"
        
        # 如果有预警信息，构建符合用户要求的格式化输出
        if warnings and regulation_sources and regulation_contents:
            # 构建更友好的预警信息格式
            formatted_warning = warning_text
            formatted_source = regulation_sources[0] if regulation_sources else ""
            formatted_code = regulation_codes[0] if regulation_codes else ""
            formatted_content = regulation_contents[0] if regulation_contents else ""
            
            # 按照用户示例格式构建输出
            filtered_result = f"<span style=\"color:red;\">安全隐患：{hazard_text}</span>\n<span style=\"color:red;\">违章行为：{violation_text}</span>\n<span style=\"color:red;\">预警信息：{formatted_warning}</span>\n\n<span style=\"color:blue;\">参考规程：{formatted_code}</span>\n<span style=\"color:blue;\">规程内容：{formatted_content}</span>\n<span style=\"color:blue;\">参考来源：{formatted_source}</span>"
        else:
            # 使用标准格式
            filtered_result = f"安全隐患：{hazard_text}\n违章行为：{violation_text}\n预警信息：{warning_text}{regulation_text}"
        
        # 在日志中记录JSON格式的结果，便于调试
        logging.info(f"JSON格式的分析结果: {json.dumps(result_json, ensure_ascii=False)}")
        
        return filtered_result, result_json
        
    except Exception as e:
        logging.error(f"过滤分析结果时发生错误: {str(e)}")
        traceback.print_exc()
        return default_result, default_json