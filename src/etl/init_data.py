#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# @author by wangcw @ 2025
# @generate at 2025-4-10 14:23:19
# comment: 根据时间范围初始化工单数据到ElasticSearch

import sys
import os
import argparse
import datetime
import configparser
import json
import pymysql
from loguru import logger
from elasticsearch import Elasticsearch

# 添加项目根目录到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入事件处理器
from event_processor import EventProcessor
from utils import dict_to_json

# 配置文件读取
config = configparser.ConfigParser()
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
config_path = os.path.join(project_root, "conf", "db.cnf")
config.read(config_path)

# 数据库连接配置
src_host = config.get("source", "host")
src_database = config.get("source", "database")
src_user = config.get("source", "user")
src_password = config.get("source", "password")
src_port = int(config.get("source", "port"))
src_charset = config.get("source", "charset")

# 目标ElasticSearch配置
tar_host = config.get("target", "host")
tar_port = int(config.get("target", "port"))
tar_user = config.get("target", "user")
tar_password = config.get("target", "password")

DB_SETTINGS = {
    "host": src_host,
    "port": src_port,
    "user": src_user,
    "password": src_password,
    "database": src_database,
    "charset": src_charset,
}

ES_SETTINGS = {
    "hosts": [f"http://{tar_host}:{tar_port}"],
    "http_auth": (tar_user, tar_password) if tar_user and tar_password else None,
    "timeout": 30
}


def process_table(conn, cursor, processor, table_name, sql_query, order_ids, batch_size=1000):
    """
    处理单个表数据
    
    Args:
        conn: 数据库连接
        cursor: 数据库游标
        processor: 事件处理器
        table_name: 表名
        sql_query: SQL查询语句
        order_ids: 订单ID列表
        batch_size: 批处理大小
    
    Returns:
        int: 处理的记录数
    """
    processed_count = 0
    
    if '{id_placeholder}' in sql_query:
        # 分批处理
        total_orders = len(order_ids)
        logger.info(f"表 {table_name} 开始批量处理，总订单数: {total_orders}")
        
        batches = [order_ids[i:i + batch_size] for i in range(0, total_orders, batch_size)]
        batch_num = 1
        
        for batch in batches:
            logger.info(f"表 {table_name} 处理批次 {batch_num}/{len(batches)}")
            # 构建SQL中的IN查询字符串
            ids_str = ','.join(['%s'] * len(batch))
            query = sql_query.format(id_placeholder=ids_str)
            
            try:
                cursor.execute(query, batch)
                records = cursor.fetchall()
                
                for record in records:
                    event = {
                        "schema": src_database,
                        "table": table_name,
                        "action": "update"
                    }
                    event.update(record)
                    
                    # 处理字节类型键
                    event_processed = {}
                    for key, value in event.items():
                        # 处理字节类型的键
                        if isinstance(key, bytes):
                            try:
                                str_key = key.decode('utf-8')
                            except UnicodeDecodeError:
                                str_key = key.hex()
                        else:
                            str_key = str(key)
                        
                        # 处理字典类型的值中的字节类型键
                        if isinstance(value, dict):
                            new_value = {}
                            for k, v in value.items():
                                if isinstance(k, bytes):
                                    try:
                                        new_k = k.decode('utf-8')
                                    except UnicodeDecodeError:
                                        new_k = k.hex()
                                else:
                                    new_k = str(k)
                                new_value[new_k] = v
                            event_processed[str_key] = new_value
                        else:
                            event_processed[str_key] = value
                    
                    json_data = json.loads(dict_to_json(event_processed))
                    
                    result = processor.handle_event(
                        action="update",
                        data=json_data
                    )
                    
                    if result:
                        processed_count += 1
                        if processed_count % 50 == 0:
                            logger.info(f"表 {table_name} 已处理 {processed_count} 条记录")
                
                batch_num += 1
                
            except Exception as e:
                logger.error(f"处理表 {table_name} 批次 {batch_num} 时发生错误: {str(e)}")
    
    else:
        # 全量查询处理
        logger.info(f"开始处理表 {table_name} 的全量数据")
        try:
            cursor.execute(sql_query)
            records = cursor.fetchall()
            total_records = len(records)
            logger.info(f"表 {table_name} 查询到 {total_records} 条记录")
            
            for record in records:
                event = {
                    "schema": src_database,
                    "table": table_name,
                    "action": "update"
                }
                event.update(record)
                
                # 处理字节类型键
                event_processed = {}
                for key, value in event.items():
                    # 处理字节类型的键
                    if isinstance(key, bytes):
                        try:
                            str_key = key.decode('utf-8')
                        except UnicodeDecodeError:
                            str_key = key.hex()
                    else:
                        str_key = str(key)
                    
                    # 处理字典类型的值中的字节类型键
                    if isinstance(value, dict):
                        new_value = {}
                        for k, v in value.items():
                            if isinstance(k, bytes):
                                try:
                                    new_k = k.decode('utf-8')
                                except UnicodeDecodeError:
                                    new_k = k.hex()
                            else:
                                new_k = str(k)
                            new_value[new_k] = v
                        event_processed[str_key] = new_value
                    else:
                        event_processed[str_key] = value
                
                json_data = json.loads(dict_to_json(event_processed))
                
                result = processor.handle_event(
                    action="update",
                    data=json_data
                )
                
                if result:
                    processed_count += 1
                    if processed_count % 50 == 0:
                        logger.info(f"表 {table_name} 已处理 {processed_count} 条记录")
        
        except Exception as e:
            logger.error(f"处理表 {table_name} 全量数据时发生错误: {str(e)}")
    
    logger.success(f"表 {table_name} 处理完成，共处理 {processed_count} 条记录")
    return processed_count


def init_data(start_time, end_time=None, batch_size=1000):
    """
    根据时间范围初始化工单数据到ElasticSearch
    
    Args:
        start_time: 开始时间，格式为 YYYY-MM-DD HH:MM:SS
        end_time: 结束时间，格式为 YYYY-MM-DD HH:MM:SS
        batch_size: 每批处理的记录数，默认为100
    """
    if end_time is None:
        end_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
    logger.info(f"开始初始化数据，时间范围: {start_time} 至 {end_time}")
    
    try:
        conn = pymysql.connect(**DB_SETTINGS)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        logger.info("数据库连接成功")
    except Exception as e:
        logger.error(f"数据库连接失败: {str(e)}")
        return None, None
    
    try:
        es_client = Elasticsearch(**ES_SETTINGS)
        logger.info("ElasticSearch连接成功")
    except Exception as e:
        logger.error(f"ElasticSearch连接失败: {str(e)}")
        cursor.close()
        conn.close()
        return
    
    processor = EventProcessor(es_client)
    
    try:
        id_sql = """
        SELECT Id 
        FROM py_test 
        WHERE MySQLInsertTime BETWEEN %s AND %s
        ORDER BY Id
        """
        cursor.execute(id_sql, (start_time, end_time))
        id_records = cursor.fetchall()
        
        if not id_records:
            logger.warning("没有找到符合条件的工单数据")
            return
        
        order_ids = [str(record['Id']) for record in id_records]
        total_count = len(order_ids)
        logger.info(f"找到符合条件的工单数: {total_count}")
        
        tables_to_process = {
            "py_test": """
            SELECT * 
            FROM py_test 
            WHERE Id IN ({id_placeholder})
            """,
            "py_test_detail": """
            SELECT * 
            FROM py_test_detail 
            WHERE Id IN ({id_placeholder})
            """
        }
        
        total_processed = 0
        for table_name, sql_query in tables_to_process.items():
            processed = process_table(
                conn, cursor, processor, 
                table_name, sql_query, 
                order_ids, batch_size
            )
            total_processed += processed
        
        logger.success(f"数据初始化完成，共处理 {total_processed} 条记录")
        
        try:
            cursor.execute("SHOW MASTER STATUS")
            binlog_status = cursor.fetchone()
            if binlog_status and len(binlog_status) >= 2:
                log_file = binlog_status['File']
                log_pos = binlog_status['Position']
                logger.info(f"当前binlog位置: {log_file}:{log_pos}")
                return log_file, log_pos
            else:
                logger.warning("无法获取当前binlog位置")
                return None, None
        except Exception as e:
            logger.error(f"获取binlog位置时发生错误: {str(e)}")
            return None, None
    
    except Exception as e:
        logger.error(f"数据初始化过程中发生错误: {str(e)}")
        return None, None
    finally:
        cursor.close()
        conn.close()
        es_client.close()


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="根据时间范围初始化工单数据到ElasticSearch")
    parser.add_argument("--start", required=True, help="开始时间，格式为 YYYY-MM-DD HH:MM:SS")
    parser.add_argument("--end", help="结束时间，格式为 YYYY-MM-DD HH:MM:SS，默认为当前时间")
    parser.add_argument("--batch", type=int, default=100, help="每批处理的记录数，默认为100")
    
    args = parser.parse_args()
    
    try:
        datetime.datetime.strptime(args.start, "%Y-%m-%d %H:%M:%S")
        if args.end:
            datetime.datetime.strptime(args.end, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        logger.error("时间格式错误，请使用 YYYY-MM-DD HH:MM:SS 格式")
        return
    
    log_file, log_pos = init_data(args.start, args.end, args.batch)
    
    if log_file and log_pos:
        logger.info(f"初始化完成，当前binlog位置: {log_file}:{log_pos}")
        
        try:
            config = configparser.ConfigParser()
            config.read(config_path)
            config.set("binlog", "log_file", log_file)
            config.set("binlog", "log_pos", str(log_pos))
            config.set("binlog", "init_time", "")  # 清空init_time字段
            with open(config_path, 'w') as f:
                config.write(f)
            logger.info("已更新配置文件中的binlog位置并清空init_time")
        except Exception as e:
            logger.error(f"更新配置文件时发生错误: {str(e)}")


if __name__ == "__main__":
    main()