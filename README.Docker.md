壹好车服车电主列表页数据同步至ElasticSearch数据库

## 运行
```shell
docker run -itd \
-m 1G \
--memory-reservation 2G \
--memory-swappiness=0 \
-oom-kill-disable \
--cpu-shares=0 \
--restart=always \
-v ./conf/:/app/conf
-v ./log/:/app/log
--name orderes registry.cn-hangzhou.aliyuncs.com/redgreat/orderes
```
或者dockercompose
```shell
docker-compose up -d
```