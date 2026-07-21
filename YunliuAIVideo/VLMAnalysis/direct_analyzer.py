# -*- coding: utf-8 -*-
"""
Direct Analyzer Module

优化的视频分析模块，直接使用视觉大模型的识别结果，省去大语言模型的二次分析。
实现实时检测视频中是否存在安全隐患和违章行为，若存在则立即输出异常情况并报警。
集成RAG功能，与本地知识库进行比对，只输出知识库中存在的隐患或违章行为。
"""

import base64
import cv2
import time
import numpy as np
import os
import asyncio
import logging
import json
from datetime import datetime
from .utility import video_chat_async_limit_frame
from .config import RAGConfig, VideoConfig, VIDEO_WARNING_DIR, VLM_ANALYSIS_DIR # Added VIDEO_WARNING_DIR and VLM_ANALYSIS_DIR
from .rag_utils import filter_analysis_result

# 优化的提示词，直接要求视觉大模型识别安全隐患和违章行为并输出规范的预警信息
prompt_direct_detection = """
你是智慧工地安全监控专家，请仔细识别画面中的安全隐患和违章行为，严格按以下格式输出：

安全隐患：[如发现安全隐患，请列出具体关键词，例如：未佩戴安全帽、高空作业无防护、脚手架不稳固等；确认无安全隐患时才填写"无"]
违章行为：[如发现违章行为，请列出具体关键词，例如：违规操作设备、无证上岗、超载作业等；确认无违章行为时才填写"无"]
预警信息：[如发现任何安全隐患或违章行为，请给出简短明确的预警信息；确认现场完全安全时才填写"无异常"]

注意事项：
1. 重点关注高空作业安全，特别是安全帽、安全带、绳索固定等关键防护措施
2. 认真检查画面中的每个工人，确保所有人都符合安全规范
3. 不要轻易判断为"无"或"无异常"，安全隐患可能不明显但很危险
4. 预警信息必须简洁明了，直接指出问题和应对措施
"""

class DirectAnalyzer:
    """直接分析器类
    
    优化的分析器，直接使用视觉大模型识别安全隐患和违章行为，
    省去大语言模型的二次分析，提高效率和准确性。
    """
    
    def __init__(self):
        self.last_warning_time = 0  # 上次预警时间戳
        self.warning_cooldown = 30  # 预警冷却时间（秒），避免频繁报警
        
    def trans_date(self, date_str):
        """转换日期格式"""
        year, month, day, hour, minute, second = date_str.split('-')
        
        am_pm = "上午" if int(hour) < 12 else "下午"
        hour_12 = hour if hour == '12' else str(int(hour) % 12)
        
        return f"{year}年{int(month)}月{int(day)}日{am_pm}{hour_12}点（{hour}时）{int(minute)}分{int(second)}秒"
    
    async def analyze(self, frames, fps=20, timestamps=None):
        """分析视频帧
        
        Args:
            frames: 视频帧列表
            fps: 帧率
            timestamps: 时间戳元组 (开始时间, 结束时间)
            
        Returns:
            分析结果字典，JSON格式的预警信息
        """
        start_time = time.time()
        
        # 如果没有时间戳，直接返回空结果
        if timestamps is None:
            return {"alert": "无异常"}
        
        # 保存视频片段用于可能的预警
        self._save_video_clip(frames, fps)
        
        # 优化：只选取关键帧进行分析，减少处理时间
        key_frames = self._extract_key_frames(frames)
        
        # 直接使用视觉大模型分析视频帧
        analysis_result = await video_chat_async_limit_frame(prompt_direct_detection, key_frames, timestamps, fps=fps)
        
        # 记录分析时间
        analysis_time = time.time() - start_time
        print(f"视频分析耗时: {analysis_time:.2f}秒")
        
        # 保存原始分析结果，用于后续可能的恢复
        original_result = analysis_result
        
        # 优化关键词列表，聚焦于高频安全隐患
        safety_keywords = [
            # 高优先级关键词（常见严重隐患）
            "未佩戴安全帽", "无安全帽", "安全帽缺失", 
            "未系安全带", "无安全带", "安全带松动",
            "高空作业", "坠落风险", "绳索固定不牢固",
            
            # 中优先级关键词
            "脚手架", "固定点", "锚固", "防坠落装置",
            "电气安全", "漏电", "火灾隐患",
            "防护栏", "护栏缺失", "警示标志"
        ]
        
        violation_keywords = [
            # 高优先级违章行为
            "违规操作", "无证操作", "违反规定",
            "设备超载", "未经检查",
            "无监护", "未经培训", "违反操作规程"
        ]
        
        # 检查是否包含关键违规行为
        contains_key_violation = any(keyword in analysis_result.lower() for keyword in safety_keywords + violation_keywords)
        
        # 初始化JSON格式的预警信息
        warning_json = {
            "safety_hazards": [],       # 安全隐患列表
            "violations": [],          # 违章行为列表
            "warning_message": "",    # 预警信息
            "regulation_codes": [],    # 规程编号列表
            "regulation_contents": [], # 规程内容列表
            "has_warning": False       # 是否有预警
        }
        
        # 如果启用RAG，使用知识库过滤分析结果
        if RAGConfig.ENABLE_RAG:
            print("RAG已启用，正在与知识库进行比对...")
            
            # 获取过滤后的文本结果和JSON格式的结果
            filtered_result, rag_json_result = filter_analysis_result(analysis_result)
            
            # 更新warning_json
            if rag_json_result and isinstance(rag_json_result, dict):
                warning_json.update(rag_json_result)
                print(f"成功获取JSON格式的分析结果: {json.dumps(rag_json_result, ensure_ascii=False)}")
            else:
                logging.warning("未能获取有效的JSON格式分析结果")
                
            analysis_result = filtered_result
            print("知识库比对完成")
            
            # 如果过滤后结果表示无异常，但原始结果包含关键违规行为，则使用原始结果
            if ("预警信息：无异常" in analysis_result or "预警信息：无" in analysis_result) and contains_key_violation:
                print("RAG过滤可能丢失关键信息，使用原始分析结果")
                analysis_result = original_result
        
        # 保存分析结果到本地文件（不存入向量数据库）
        date_flag = self.trans_date(timestamps[0]) + "："
        self._save_history(date_flag + analysis_result)
        
        # 解析分析结果，提取安全隐患、违章行为和预警信息
        safety_hazards = []
        violations = []
        warning_message = ""
        
        # 提取安全隐患
        if "安全隐患：" in analysis_result:
            hazards_text = analysis_result.split("安全隐患：")[1].split("\n")[0].strip()
            if hazards_text and hazards_text != "无":
                safety_hazards = [hazard.strip() for hazard in hazards_text.split("、")]
                warning_json["safety_hazards"] = safety_hazards
        
        # 提取违章行为
        if "违章行为：" in analysis_result:
            violations_text = analysis_result.split("违章行为：")[1].split("\n")[0].strip()
            if violations_text and violations_text != "无":
                violations = [violation.strip() for violation in violations_text.split("、")]
                warning_json["violations"] = violations
        
        # 提取预警信息
        if "预警信息：" in analysis_result:
            warning_text = analysis_result.split("预警信息：")[1].split("\n")[0].strip()
            if warning_text and warning_text != "无异常" and warning_text != "无":
                warning_message = warning_text
                warning_json["warning_message"] = warning_message
        
        # 处理规程编号和内容
        if RAGConfig.ENABLE_RAG:
            # RAG已启用。 warning_json 已通过 rag_json_result 更新。
            # 我们只需记录RAG是否提供了规程信息。
            if warning_json.get("regulation_codes") and warning_json.get("regulation_contents"):
                print("RAG已提供规程信息。")
            else:
                print("RAG已启用，但未从知识库找到匹配规程。")
        else:  # RAGConfig.ENABLE_RAG is False
            # RAG未启用。如果存在安全隐患或违章行为，则执行模拟查找。
            if safety_hazards or violations:
                print("RAG未启用，执行模拟查找规程信息。")
                regulation_codes_simulated = []
                regulation_contents_simulated = []
                
                # 模拟从知识库中获取规程信息
                for hazard in safety_hazards:
                    # 根据安全隐患类型查找对应的规程编号和内容
                    if "安全帽" in hazard:
                        regulation_codes_simulated.append("安规-01-003")
                        regulation_contents_simulated.append("工作人员必须佩戴安全帽进入施工现场，安全帽必须系紧下颚带")
                    elif "安全带" in hazard:
                        regulation_codes_simulated.append("安规-02-005")
                        regulation_contents_simulated.append("高空作业必须正确佩戴安全带，并确保安全带固定在牢固的锚点上")
                    elif "脚手架" in hazard:
                        regulation_codes_simulated.append("安规-03-012")
                        regulation_contents_simulated.append("脚手架必须搭设牢固，并设置防护栏杆，严禁在不稳固的脚手架上作业")
                
                for violation in violations:
                    # 根据违章行为类型查找对应的规程编号和内容
                    if "违规操作" in violation:
                        regulation_codes_simulated.append("操规-05-008")
                        regulation_contents_simulated.append("严禁违规操作设备，必须按照操作规程进行操作")
                    elif "无证" in violation:
                        regulation_codes_simulated.append("人规-02-003")
                        regulation_contents_simulated.append("特种作业人员必须持证上岗，严禁无证操作")
                
                warning_json["regulation_codes"] = regulation_codes_simulated
                warning_json["regulation_contents"] = regulation_contents_simulated
        
        # 判断是否有预警
        has_safety_issue = len(safety_hazards) > 0
        has_violation = len(violations) > 0
        has_warning = warning_message != ""
        
        # 如果既没有安全隐患也没有违章行为，且预警信息也表明无异常，则返回无异常
        if not has_safety_issue and not has_violation and not has_warning:
            print("分析结果未检测到异常情况")
            return {"alert": "无异常"}
        
        # 设置预警标志
        warning_json["has_warning"] = True
            
        # 打印检测到的异常情况，便于调试
        if has_safety_issue or has_violation or has_warning:
            print(f"检测到异常情况 - 安全隐患: {has_safety_issue}, 违章行为: {has_violation}, 预警信息: {has_warning}")
            print(f"原始分析结果: {analysis_result}")
            print(f"JSON格式预警信息: {json.dumps(warning_json, ensure_ascii=False)}")
        
        # 检查预警冷却时间
        current_time = time.time()
        if current_time - self.last_warning_time < self.warning_cooldown:
            print(f"预警冷却中，跳过此次预警 ({current_time - self.last_warning_time:.1f}秒 < {self.warning_cooldown}秒)")
            return {"alert": "无异常"}
        
        # 更新预警时间
        self.last_warning_time = current_time
        
        # 生成预警文件名
        file_str = f"warning_{timestamps[0].replace('-', '_')}"
        # Use VIDEO_WARNING_DIR from config
        new_file_name = os.path.join(VIDEO_WARNING_DIR, f"{file_str}.mp4")
        
        # 确保目录存在
        os.makedirs(VIDEO_WARNING_DIR, exist_ok=True) # Use VIDEO_WARNING_DIR
        
        # 重命名临时视频文件
        # Construct path using VIDEO_WARNING_DIR
        temp_video_path = os.path.join(VIDEO_WARNING_DIR, "output.mp4")
        if os.path.exists(temp_video_path):
            os.rename(temp_video_path, new_file_name)
        else:
            logging.warning("警告视频文件不存在")
        
        # 保存预警截图
        frame = frames[0]
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        # Construct path using VIDEO_WARNING_DIR
        cv2.imwrite(os.path.join(VIDEO_WARNING_DIR, f"{file_str}.jpg"), frame)
        
        # 构建HTML格式的预警信息显示
        html_warning = f"<span style=\"color:red;\">"  
        
        # 添加安全隐患信息
        if safety_hazards:
            html_warning += f"安全隐患：{', '.join(safety_hazards)}<br>"
        
        # 添加违章行为信息
        if violations:
            html_warning += f"违章行为：{', '.join(violations)}<br>"
        
        # 添加预警信息
        if warning_message:
            html_warning += f"预警信息：{warning_message}<br>"
        
        # 添加规程信息
        if warning_json["regulation_codes"]:
            for i, (code, content) in enumerate(zip(warning_json["regulation_codes"], warning_json["regulation_contents"])):
                html_warning += f"规程{i+1}：{code} - {content}<br>"
        
        html_warning += "</span>"
        
        # 返回预警信息，包含JSON格式的数据和HTML格式的显示
        return {
            "alert": html_warning,
            "description": f"当前监控时间: {date_flag}",
            "video_file_name": f"{file_str}.mp4",
            "picture_file_name": f"{file_str}.jpg",
            "warning_json": json.dumps(warning_json, ensure_ascii=False)  # 添加JSON格式的预警信息
        }
    
    def _save_video_clip(self, frames, fps):
        """保存视频片段"""
        try:
            # 确保目录存在
            os.makedirs(VIDEO_WARNING_DIR, exist_ok=True) # Use VIDEO_WARNING_DIR
            
            # 获取视频尺寸
            height, width = frames[0].shape[:2]
            
            # 创建视频写入器
            fourcc = cv2.VideoWriter_fourcc(*'avc1')
            # Construct path using VIDEO_WARNING_DIR
            video_writer = cv2.VideoWriter(os.path.join(VIDEO_WARNING_DIR, 'output.mp4'), fourcc, fps, (width, height))
            
            # 写入帧
            for frame in frames:
                # 确保帧是正确的数据类型和形状
                if frame.dtype != np.uint8:
                    frame = frame.astype(np.uint8)
                if len(frame.shape) == 2:
                    frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
                video_writer.write(frame)
            
            # 释放视频写入器
            video_writer.release()
        except Exception as e:
            logging.error(f"保存视频片段失败: {str(e)}")
    
    def _extract_key_frames(self, frames, max_frames=5):
        """提取关键帧进行分析
        
        Args:
            frames: 原始视频帧列表
            max_frames: 最大提取帧数
            
        Returns:
            关键帧列表
        """
        if len(frames) <= max_frames:
            return frames
        
        # 计算帧间差异以找出场景变化较大的帧
        frame_diffs = []
        prev_frame = cv2.cvtColor(frames[0], cv2.COLOR_BGR2GRAY)
        
        for i in range(1, len(frames)):
            curr_frame = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
            # 计算帧间差异
            diff = cv2.absdiff(prev_frame, curr_frame)
            diff_sum = np.sum(diff)
            frame_diffs.append((i, diff_sum))
            prev_frame = curr_frame
        
        # 按差异大小排序并选择top N帧
        frame_diffs.sort(key=lambda x: x[1], reverse=True)
        key_indices = [0]  # 始终包含第一帧
        key_indices.extend([idx for idx, _ in frame_diffs[:max_frames-1]])
        key_indices.sort()  # 按时间顺序排序
        
        # 确保最后一帧也被包含
        if len(frames) - 1 not in key_indices and len(key_indices) < max_frames:
            key_indices.append(len(frames) - 1)
        
        return [frames[i] for i in key_indices]
    
    def _save_history(self, content):
        """保存历史记录到本地文件（不存入向量数据库）"""
        try:
            # 始终保存所有分析结果，无论是否有预警
            # RAGConfig.HISTORY_FILE will be updated in config.py to be an absolute path
            with open(RAGConfig.HISTORY_FILE, 'a', encoding='utf-8') as file:
                file.write(content + '\n')
            
            # 根据内容类型记录不同的日志
            if "预警信息：无异常" in content or "预警信息：无" in content:
                logging.info(f"保存正常记录: {content[:50]}...")
            else:
                logging.info(f"保存预警记录: {content[:50]}...")
        except Exception as e:
            logging.error(f"保存历史记录失败: {str(e)}")