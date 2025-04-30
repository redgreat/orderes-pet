from datetime import datetime
from elasticsearch import Elasticsearch
import sys
import os
import configparser

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 数据库连接定义
config = configparser.ConfigParser()
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
config_path = os.path.join(project_root, "conf", "db.cnf")
config.read(config_path)

# 目标ElasticSearch配置
tar_host = config.get("target_press", "host")
tar_port = int(config.get("target_press", "port"))
tar_user = config.get("target_press", "user")
tar_password = config.get("target_press", "password")

# ElasticSearch连接配置
ES_SETTINGS = {
    "hosts": [f"http://{tar_host}:{tar_port}"],
    "http_auth": (tar_user, tar_password) if tar_user and tar_password else None,
    "timeout": 30
}

es = Elasticsearch(**ES_SETTINGS)

# 查询并按时差倒序排序，查询 100 条
response = es.search(
    index="test_index",
    size=100,
    _source=["mysqlInsertTime", "createTime"],
    query={"match_all": {}},
    sort=[
        {
            "_script": {
                "type": "number",
                "script": {
                    "lang": "painless",
                    "source": "def fmt = java.time.format.DateTimeFormatter.ofPattern('yyyy-MM-dd HH:mm:ss'); def t1 = java.time.LocalDateTime.parse(params._source.createTime, fmt).atZone(java.time.ZoneOffset.UTC).toInstant().toEpochMilli(); def t2 = java.time.LocalDateTime.parse(params._source.mysqlInsertTime, fmt).atZone(java.time.ZoneOffset.UTC).toInstant().toEpochMilli(); (t1 - t2) / 1000;"
                },
                "order": "desc"
            }
        }
    ],
    script_fields={
        "time_diff_seconds": {
            "script": {
                "lang": "painless",
                "source": "def fmt = java.time.format.DateTimeFormatter.ofPattern('yyyy-MM-dd HH:mm:ss'); def t1 = java.time.LocalDateTime.parse(params._source.createTime, fmt).atZone(java.time.ZoneOffset.UTC).toInstant().toEpochMilli(); def t2 = java.time.LocalDateTime.parse(params._source.mysqlInsertTime, fmt).atZone(java.time.ZoneOffset.UTC).toInstant().toEpochMilli(); return (t1 - t2) / 1000;"
            }
        }
    },
)
for hit in response['hits']['hits']:
    diff = hit['fields']['time_diff_seconds'][0]
    print(
        f"id={hit['_id']}，mysqlInsertTime={hit['_source']['mysqlInsertTime']}，createTime={hit['_source']['createTime']}，时差：{diff} 秒"
    )
