#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# @author by wangcw @ 2025
# @generate at 2025-4-9 14:14:09
# comment: 创建ElasticSearch索引结构

from elasticsearch import Elasticsearch
from loguru import logger
import configparser
import os

# 数据库连接定义
config = configparser.ConfigParser()
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
config_path = os.path.join(project_root, "conf", "db.cnf")
config.read(config_path)

# 目标ElasticSearch配置
tar_host = config.get("target", "host")
tar_port = int(config.get("target", "port"))
tar_user = config.get("target", "user")
tar_password = config.get("target", "password")
index_name = config.get("target", "index_name")

# 日志配置
logDir = os.path.join(project_root, "log")
if not os.path.exists(logDir):
    os.mkdir(logDir)
logFile = os.path.join(logDir, "repl.log")
# logger.remove(handler_id=None)

logger.add(
    logFile,
    colorize=True,
    rotation="1 days",
    retention="3 days",
    format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}",
    backtrace=True,
    diagnose=True,
    level="INFO",
)

# ElasticSearch连接配置
ES_SETTINGS = {
    "hosts": [f"http://{tar_host}:{tar_port}"],
    "http_auth": (tar_user, tar_password) if tar_user and tar_password else None,
    "timeout": 30
}

# 所有字段通用的日期格式定义
DATE_FORMAT = "strict_date_optional_time||yyyy-MM-dd'T'HH:mm:ssxxx||yyyy-MM-dd HH:mm:ss||yyyy-MM-dd||epoch_millis"

def create_order_index():
    """创建工单索引结构"""
    es = Elasticsearch(**ES_SETTINGS)
    
    # 索引映射定义
    mapping = {
  "mappings": {
      "properties": {
        "createTime": {
          "type": "date",
          "format": "yyyy-MM-dd HH:mm:ss",
          "ignore_malformed": False
        },
        "details": {
          "properties": {
            "id": {
              "type": "long"
            },
            "mysqlInsertTime": {
              "type": "date",
          "format": "yyyy-MM-dd HH:mm:ss",
          "ignore_malformed": False
            },
            "name": {
              "type": "text",
              "fields": {
                "keyword": {
                  "type": "keyword",
                  "ignore_above": 256
                }
              }
            },
            "testId": {
              "type": "long"
            }
          }
        },
        "id": {
          "type": "long"
        },
        "mysqlInsertTime": {
         "type": "date",
          "format": "yyyy-MM-dd HH:mm:ss",
          "ignore_malformed": False
        },
        "name": {
          "type": "text",
          "fields": {
            "keyword": {
              "type": "keyword",
              "ignore_above": 256
            }
          }
        }
      }
  }
}
    
    try:
        # 删除已存在的索引（如果存在）
        if es.indices.exists(index=index_name):
            es.indices.delete(index=index_name)
            logger.info(f"已删除现有索引: {index_name}")
            
        # 创建新索引
        es.indices.create(index=index_name, mappings=mapping["mappings"])
        logger.success(f"成功创建索引: {index_name}")
        return True
    except Exception as e:
        logger.error(f"创建索引失败: {str(e)}")
        return False

if __name__ == "__main__":
    # 创建主工单索引
    create_order_index()
