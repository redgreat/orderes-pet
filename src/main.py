#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# @author by wangcw @ 2025
# @generate at 2025/3/21 15:26
# comment: 监听mysql binglog，监听变化量后写入宽表

import sys
import os
import configparser
from loguru import logger
import json
import pymysql
import time
import argparse
from elasticsearch import Elasticsearch
from utils import dict_to_str, dict_to_json
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import (
    DeleteRowsEvent,
    UpdateRowsEvent,
    WriteRowsEvent,
)

from event_processor import EventProcessor
from monitor import BinlogMonitor

# 数据库连接定义
config = configparser.ConfigParser()
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
config_path = os.path.join(project_root, "conf", "db.cnf")
config.read(config_path)

src_host = config.get("source", "host")
src_database = config.get("source", "database").split(',')
src_tables = config.get("source", "tables").split(',')
src_user = config.get("source", "user")
src_password = config.get("source", "password")
src_port = int(config.get("source", "port"))
src_charset = config.get("source", "charset")

# 目标ElasticSearch配置
tar_host = config.get("target", "host")
tar_port = int(config.get("target", "port"))
tar_user = config.get("target", "user")
tar_password = config.get("target", "password")

# binlog起始位点
bin_log_file = config.get("binlog", "log_file")
bin_log_pos = int(config.get("binlog", "log_pos"))

# 日志级别
log_level = config.get("log", "level")

# 日志配置
logDir = os.path.join(project_root, "log")
if not os.path.exists(logDir):
    os.makedirs(logDir, exist_ok=True)
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
    level=log_level,
)

SRC_MYSQL_SETTINGS = {
    "host": src_host,
    "port": src_port,
    "user": src_user,
    "passwd": src_password,
    "charset": src_charset,
}

# ElasticSearch连接配置
ES_SETTINGS = {
    "hosts": [f"http://{tar_host}:{tar_port}"],
    "http_auth": (tar_user, tar_password) if tar_user and tar_password else None,
    "timeout": 30
}


def get_current_binlog_position(conn):
    """获取当前binlog位置
    
    Args:
        conn: 数据库连接
        
    Returns:
        tuple: (log_file, log_pos) 或者在出错时返回 (None, None)
    """
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SHOW MASTER STATUS")
        binlog_status = cursor.fetchone()
        cursor.close()
        
        if binlog_status and 'File' in binlog_status and 'Position' in binlog_status:
            log_file = binlog_status['File']
            log_pos = binlog_status['Position']
            return log_file, log_pos
        else:
            logger.warning("无法获取当前binlog位置")
            return None, None
    except Exception as e:
        logger.error(f"获取binlog位置时发生错误: {str(e)}")
        return None, None


def update_binlog_config(log_file, log_pos):
    """更新配置文件中的binlog位置
    
    Args:
        log_file: binlog文件名
        log_pos: binlog位置
        
    Returns:
        bool: 更新是否成功
    """
    try:
        config = configparser.ConfigParser()
        config.read(config_path)
        config.set("binlog", "log_file", log_file)
        config.set("binlog", "log_pos", str(log_pos))
        with open(config_path, 'w') as f:
            config.write(f)
        logger.info(f"已更新配置文件中的binlog位置: {log_file}:{log_pos}")
        return True
    except Exception as e:
        logger.error(f"更新配置文件时发生错误: {str(e)}")
        return False


def start_binlog_listener(log_file, log_pos):
    """启动binlog监听
    
    Args:
        log_file: binlog文件名
        log_pos: binlog位置
    """
    logger.info(f"开始监听binlog，起始位置: {log_file}:{log_pos}")
    
    # 创建binlog流读取器
    stream = BinLogStreamReader(
        connection_settings=SRC_MYSQL_SETTINGS,
        server_id=3,
        blocking=True,  # 持续监听
        only_events=[DeleteRowsEvent, WriteRowsEvent, UpdateRowsEvent],  # 指定只监听某些事件
        only_schemas=src_database,  # 指定只监听某些库（但binlog还是要读取全部）
        only_tables=src_tables,  # 指定监听某些表
        log_file=log_file,  # 指定起始binlog文件
        log_pos=log_pos  # 指定起始位点
    )

    # 创建ElasticSearch连接
    es_client = Elasticsearch(**ES_SETTINGS)
    
    # 创建统一的事件处理器
    processor = EventProcessor(es_client)
    
    # 创建监控实例
    monitor = BinlogMonitor()
    
    # 启动监控线程
    monitor_thread = threading.Thread(target=monitor.start_monitoring)
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # 记录上次记录binlog位置的时间
    last_log_time = time.time()
    # 记录binlog位置的间隔（秒）
    log_interval = 300  # 5分钟记录一次
    
    # 创建数据库连接用于获取binlog位置
    conn = pymysql.connect(
        host=src_host,
        port=src_port,
        user=src_user,
        password=src_password,
        charset=src_charset
    )
    
    try:
        with processor:
            for binlog_event in stream:
                # 更新监控时间
                monitor.update_event_time()
                
                current_time = time.time()
                if current_time - last_log_time >= log_interval:
                    current_log_file = stream.log_file
                    current_log_pos = stream.log_pos
                    
                    logger.info(f"当前binlog位置: {current_log_file}:{current_log_pos}")
                    update_binlog_config(current_log_file, current_log_pos)
                    
                    last_log_time = current_time
                
                for row in binlog_event.rows:
                    event = {"schema": binlog_event.schema, "table": binlog_event.table}
                    
                    if isinstance(binlog_event, WriteRowsEvent):
                        event["action"] = "insert"
                        event.update(row["values"])
                    elif isinstance(binlog_event, UpdateRowsEvent):
                        event["action"] = "update"
                        event.update(row["after_values"])
                    elif isinstance(binlog_event, DeleteRowsEvent):
                        event["action"] = "delete"
                        event.update(row["values"])
                    
                    json_data = json.loads(dict_to_json(event))
                    processor.handle_event(
                        action=event["action"],
                        data=json_data
                    )
    except KeyboardInterrupt:
        logger.info("收到中断信号，程序退出")
    except Exception as e:
        logger.error(f"监听binlog过程中发生错误: {str(e)}, event: {event}")
    finally:
        stream.close()
        es_client.close()
        conn.close()
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="工单数据同步工具")
    args = parser.parse_args()
    
    init_time = None
    try:
        init_time = config.get("binlog", "init_time")
        logger.info(f"从配置文件获取到初始化时间: {init_time}")
    except (configparser.NoSectionError, configparser.NoOptionError):
        logger.info("配置文件中未找到初始化时间配置，将直接使用binlog位点")
    
    if init_time:
        try:
            logger.info("尝试导入init_data模块...")
            import traceback
            try:
                from etl.init_data import init_data
                logger.info("成功导入init_data模块")
                
                logger.info(f"开始初始化历史数据，起始时间: {init_time}")
                log_file, log_pos = init_data(init_time)
                
                if log_file and log_pos:
                    logger.info(f"初始化完成，使用最新binlog位置启动监听: {log_file}:{log_pos}")
                    update_binlog_config(log_file, log_pos)
                    start_binlog_listener(log_file, log_pos)
                else:
                    logger.error("初始化数据后无法获取binlog位置，使用配置文件中的位置启动监听")
                    start_binlog_listener(bin_log_file, bin_log_pos)
            except ImportError as ie:
                logger.error(f"导入init_data时出错: {str(ie)}")
                logger.error(f"导入错误详情: {traceback.format_exc()}")
                return
        except Exception as e:
            logger.error(f"初始化过程中出现其他错误: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            return
    else:
        logger.info(f"使用配置文件中的binlog位置启动监听: {bin_log_file}:{bin_log_pos}")
        start_binlog_listener(bin_log_file, bin_log_pos)


if __name__ == "__main__":
    main()
