#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# @author by wangcw @ 2025
# comment: 测试表信息处理器

from elasticsearch import Elasticsearch
from loguru import logger
from typing import Dict, Any
from src.base_processor import BaseProcessor, index_name
import datetime

class TestHandler(BaseProcessor):
    """处理py_test表的事件"""
    def handle(self, action: str, data: Dict) -> bool:
        doc_id = str(data.get('Id'))      
        LastUpdateTimeStamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doc_body = {
                'Id': doc_id,
                'Name': data.get('Name'),
                'mysqlInsertTime': data.get('MySQLInsertTime'),
                'createTime': LastUpdateTimeStamp
            }
        if action == "insert":         
            return self._execute_es("index", doc_id, doc_body)
        elif action == "update":
            try:
                self.es_client.update(
                    index=index_name,
                    id=doc_id,
                    body={"doc": doc_body}
                )
                # logger.success(f"ES更新测试信息成功: 索引={index_name}, ID={doc_id}")
                return True
            except Exception as e:
                if "document_missing_exception" in str(e) or "404" in str(e):
                    # logger.success(f"ES测试信息不存在，自动转为插入操作: 索引={index_name}, ID={doc_id}")
                    return self._execute_es("index", doc_id, doc_body)
                else:
                    logger.error(f"ES更新测试信息失败: 索引={index_name}, ID={doc_id}, {str(e)}")
                    return False
        elif action == "delete":
            try:
                self.es_client.delete(
                    index=index_name,
                    id=doc_id
                )
                # logger.success(f"ES删除测试信息成功: 索引={index_name}, ID={doc_id}")
                return True
            except Exception as e:
                if "document_missing_exception" in str(e) or "404" in str(e):
                    # logger.success(f"ES删除测试信息时文档不存在，视为成功: 索引={index_name}, ID={doc_id}")
                    return True
                else:
                    logger.error(f"ES删除工单信息失败: 索引={index_name}, ID={doc_id}, {str(e)}")
                    return False
        else:
            logger.warning(f"未定义的操作类型: {action}")
            return False