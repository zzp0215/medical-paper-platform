# 基础服务 Docker 编排

> 关联: [项目 TODO](../TODO.md) Phase 1.1.3 | [架构文档](../README.md)

## 服务清单

| 服务 | 版本 | 端口 | 用途 | 内存上限 |
|------|------|------|------|----------|
| PostgreSQL | 16-alpine | 5432 | 关系数据库 (用户/文献元数据/任务状态) | 1G |
| Redis | 7-alpine | 6379 | 缓存 + Celery Broker/Backend | 768M |
| MinIO | 2024-09-13 | 9000/9001 | 对象存储 (PDF/图表/Word) | 1G |
| Milvus | v2.4.10 | 19530/9091 | 向量数据库 (BGE-M3 embeddings) | 4G |
| Milvus etcd | v3.5.16 | - | Milvus 元数据 | 512M |
| Milvus MinIO | 2024-09-13 | - | Milvus 内部对象存储 (与主 MinIO 隔离) | 1G |
| Elasticsearch | 8.15.0 | 9200 | 全文检索 + 倒排索引 | 1.5G |

**总内存峰值**: ~10G (CPU 服务器推荐 16G 内存)

## 快速开始

```bash
# 1. 复制环境变量 (可选, 已有 .env.docker 默认值)
cp .env.docker .env.docker.local   # 修改后再用 --env-file 引用

# 2. 启动所有基础服务
make up

# 3. 查看状态
make ps
make health

# 4. 初始化 MinIO buckets + ES 索引
make minio-init
make es-init ES_PASSWORD=es_dev_pwd

# 5. 启动管理面板 (可选, 单独 compose 文件)
make pgadmin       # http://localhost:5050  (admin@medpaper.local / admin)
make redis-insight # http://localhost:8001
make kibana        # http://localhost:5601
make admin-up      # 一次性全开
make admin-down    # 全部关闭

# 6. 关闭
make down          # 保留数据卷
make reset         # ⚠️ 删除所有数据卷
```

## 端口规划

```
主机端口   容器服务              用途
───────   ────────              ────
5432      postgres:5432         FastAPI 业务读写
6379      redis:6379            缓存 + Celery (db 0/1/2)
9000      minio:9000            S3 兼容 API
9001      minio:9001            Web Console
19530     milvus:19530          SDK gRPC
9091      milvus:9091           metrics (Prometheus)
9200      elasticsearch:9200    ES REST API
```

## 网络 & 存储

- **网络**: `medpaper-net` (bridge, 172.28.0.0/16)
  - 容器间通过服务名互访, 例如 FastAPI 连 `postgres:5432`
- **数据卷**: 全部命名卷 (`docker volume ls | grep medpaper`)
  - 备份: `docker run --rm -v medpaper_postgres_data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/pg-$(date +%F).tgz /data`
  - 恢复: 反向操作

## 凭据管理

**开发环境** (`.env.docker`): 使用 `*_dev_pwd` 等弱密码, 方便本地快速启动

**生产部署** (Phase 9):
- 必须修改所有 `*_dev_pwd` 为强密码
- 通过环境变量注入, 切勿提交到 Git
- ES 启用 `xpack.security.http.ssl.enabled: true`
- MinIO 启用 TLS

## 验证清单

- [x] `docker compose config` 无语法错误
- [x] `make up` 后所有服务 `healthy` (约 60s)
- [x] `psql -h localhost -U medpaper -d medpaper` 可登录
- [x] `redis-cli -h localhost ping` 返回 PONG
- [x] `curl http://localhost:9000/minio/health/live` 返回 200
- [x] `curl -u elastic:xxx http://localhost:9200/_cluster/health` 返回 green/yellow
- [x] `python3 -c "from pymilvus import connections; connections.connect(host='localhost', port='19530')"` 成功

## 故障排查

| 现象 | 排查 |
|------|------|
| `port already in use` | `lsof -i :<port>` 找占用进程, 或改 `.env.docker` 端口 |
| Milvus 反复重启 | 检查 `milvus-etcd` / `milvus-minio` 是否 healthy, 依赖顺序错会起不来 |
| ES 启动失败 OOM | 调小 `ES_JAVA_OPTS` 到 `-Xms256m -Xmx256m` (CPU 服务器) |
| MinIO bucket 创建失败 | 确认 `make minio-init` 用的密码与 `.env.docker` 一致 |
| 网络不通 | `docker network inspect medpaper-net` 看容器 IP, 容器间必须用服务名 |

## 下一步 (Phase 1.1.4+)

```bash
# 基础服务起来后, 回到项目根目录:
cd ..
# 搭建 FastAPI 骨架 (backend/...), 通过 docker compose 启动的 PostgreSQL/Redis
# DATABASE_URL=postgresql+asyncpg://medpaper:medpaper_dev_pwd@localhost:5432/medpaper
# REDIS_URL=redis://:redis_dev_pwd@localhost:6379/0
```
