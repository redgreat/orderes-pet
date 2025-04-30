#!/usr/bin/env python3
# -*- coding:utf-8 -*-
# @author by wangcw @ 2025
# @generate at 2025/4/15 15:26
# comment: binlog延时监控模块

import time
import requests
import json
from loguru import logger
import configparser
import os

class BinlogMonitor:
    def __init__(self):
        # 读取配置文件
        config = configparser.ConfigParser()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        config_path = os.path.join(project_root, "conf", "db.cnf")
        config.read(config_path)
        
        # 获取企业微信配置
        self.to_group_key = config.get("wechat", "to_group_key")
        self.to_user = config.get("wechat", "to_user")
        self.to_user = self.to_user.split(',')
        self.to_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={self.to_group_key}"
        # 获取监控配置
        self.delay_threshold = int(config.get("monitor", "delay_threshold", fallback="300"))  # 默认5分钟
        self.check_interval = int(config.get("monitor", "check_interval", fallback="60"))  # 默认1分钟
        
        
        # 记录上次binlog事件时间
        self.last_event_time = time.time()  
    
    
    def send_wechat_alert(self, message):
        """发送企业微信告警"""
        try:
            response = requests.post(self.to_url, 
                json={"msgtype": "text",
                      "text": {"content": message,
                               "mentioned_mobile_list": self.to_user
                              }
                     }, 
                headers = {'Content-Type':'application/json'}
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    logger.info("企业微信告警发送成功")
                    return True
                else:
                    logger.error(f"企业微信告警发送失败: {result.get('errmsg')}")
            return False
        except Exception as e:
            logger.error(f"发送企业微信告警时发生错误: {str(e)}")
            return False
    
    def update_event_time(self):
        """更新最后事件时间"""
        self.last_event_time = time.time()
    
    def check_delay(self):
        """检查binlog延时"""
        current_time = time.time()
        delay = current_time - self.last_event_time
        
        if delay > self.delay_threshold:
            message = f"【Binlog延时告警】\n当前binlog接收延时: {int(delay)}秒\n超过阈值: {self.delay_threshold}秒"
            self.send_wechat_alert(message)
            logger.warning(message)
    
    def start_monitoring(self):
        """启动监控"""
        logger.info("启动binlog延时监控")
        while True:
            try:
                self.check_delay()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"监控过程中发生错误: {str(e)}")
                time.sleep(self.check_interval)
