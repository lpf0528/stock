```
# 启动docker
colima start
```

```
# 创建docker镜像
docker run -d \
  --name instockdb \
  -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=root \
  mariadb:latest
```