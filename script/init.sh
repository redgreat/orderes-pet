#!/bin/bash
# -*- coding:utf-8 -*-
# @author by wangcw @ 2025
# @generate at 2025-4-10 15:57:41
# comment: 初始化语句

python d:\github\orderes\src\etl\init_data.py --start "2025-04-09 00:00:00" --end "2025-04-10 00:00:00"

# git发布标签，打包镜像
git tag v0.0.3
git push origin v0.0.3

# 删除打包失败的标签
git tag -d v0.0.1
git push origin :refs/tags/v0.0.1

# 重新打标签并推送，上面操作