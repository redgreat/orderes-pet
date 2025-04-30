#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# @author by wangcw @ 2025
# comment: 车辆信息处理器

from elasticsearch import Elasticsearch
from loguru import logger
from typing import Dict, Any
from src.base_processor import BaseProcessor, index_name

class TestDetailHandler(BaseProcessor):
    """处理py_test_detail表的事件，存入details嵌套字段"""
    def handle(self, action: str, data: Dict) -> bool:
        test_id = data.get('testId')

        doc_id = str(test_id)
        detail_data = {
            'Id': str(data.get('Id')),
            'testId': test_id,
            'Name': data.get('Name'),
            'mysqlInsertTime': data.get('MySQLInsertTime')
        }
        
        if action == "insert":
            doc_body = {
                'details': [detail_data]
            }
            return self._execute_es("index", doc_id, doc_body)
        elif action == "update":
            script = {
                "source": """
                    if (ctx._source.details == null) {
                        ctx._source.details = new ArrayList();
                    }
                    def found = false;
                    for (int i=0; i<ctx._source.details.size(); i++) {
                        if (ctx._source.details[i].Id == params.detail.Id) {
                            ctx._source.details.set(i, params.detail);
                            found = true;
                            break;
                        }
                    }
                    if (!found) {
                        ctx._source.details.add(params.detail);
                    }
                """,
                "lang": "painless",
                "params": {
                    "detail": detail_data
                }
            }
            try:
                self.es_client.update(
                    index=index_name,
                    id=doc_id,
                    body={"script": script}
                )
                # logger.success(f"ES更新details成功: 索引={index_name}, ID={doc_id}, DetailID={detail_data['Id']}")
                return True
            except Exception as e:
                if "document_missing_exception" in str(e) or "404" in str(e):
                    # logger.success(f"ES更新details时，原信息不存在，自动转为插入操作: 索引={index_name}, ID={doc_id}")
                    doc_body = {
                        'details': [detail_data]
                    }
                    return self._execute_es("index", doc_id, doc_body)
                else:
                    logger.error(f"ES更新details失败: 索引={index_name}, ID={doc_id}, {str(e)}")
                    return False
        elif action == "delete":
            script = {
                "source": """
                    if (ctx._source.details != null) {
                        def iterator = ctx._source.details.iterator();
                        while (iterator.hasNext()) {
                            if (iterator.next().Id == params.detailId) {
                                iterator.remove();
                            }
                        }
                    }
                """,
                "lang": "painless",
                "params": {
                    "detailId": str(data.get('Id'))
                }
            }
            try:
                self.es_client.update(
                    index=index_name,
                    id=doc_id,
                    body={"script": script}
                )
                # logger.success(f"ES删除details成功: 索引={index_name}, ID={doc_id}, DetailID={str(data.get('Id'))}")
                return True
            except Exception as e:
                if "document_missing_exception" in str(e) or "404" in str(e):
                    # logger.success(f"ES删除details时文档不存在，视为成功: 索引={index_name}, ID={doc_id}, DetailID={str(data.get('Id'))}")
                    return True
                else:
                    logger.error(f"ES删除details失败: 索引={index_name}, ID={doc_id}, {str(e)}")
                    return False
        else:
            logger.warning(f"未定义的操作类型: {action}")
            return False