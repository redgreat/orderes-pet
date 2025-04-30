#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# @author by wangcw @ 2025
# @generate at 2025-4-10 15:58:28
# comment: 事件处理器基类

from elasticsearch import Elasticsearch
from loguru import logger
from typing import Dict, Any
import os
import configparser

config = configparser.ConfigParser()
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
config_path = os.path.join(project_root, "conf", "db.cnf")
config.read(config_path)
index_name = config.get("target", "index_name")

class BaseProcessor:
    """事件处理器基类，提供基础的ES操作方法"""
    def __init__(self, es_client: Elasticsearch):
        self.es_client = es_client
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def _execute_es(self, operation: str, doc_id: str, doc_body: Dict) -> bool:
        """执行ES操作"""
        try:
            if operation == "index":
                # 使用upsert操作，如果文档不存在则创建，存在则更新
                self.es_client.update(
                    index=index_name,
                    id=doc_id,
                    body={"doc": doc_body, "doc_as_upsert": True}
                )
                # logger.success(f"ES索引成功: 索引={index_name}, ID={doc_id}")
                return True
            else:
                logger.warning(f"未定义的ES操作: {operation}")
                return False
        except Exception as e:
            logger.error(f"ES操作失败: 索引={index_name}, ID={doc_id}, {str(e)}")
            return False