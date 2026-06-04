# ============================================
# Docker Compose 便捷管理脚本
# ============================================
# 用法:  cd docker && make <target>
# 注意:  默认读取 .env.docker; 想用自定义环境变量用 make CMD=... ARGS=...
# ============================================

COMPOSE = docker-compose --env-file .env.docker
PROJECT = medpaper
ADMIN_FILE = docker-compose.admin.yml

.PHONY: help up down restart ps logs status health reset \
        pgadmin redis-insight kibana \
        minio-init es-init

help:  ## 显示帮助
	@awk 'BEGIN {FS = ":.*##"; printf "\n用法:  make \033[36m<target>\033[0m\n\n可用目标:\n"} \
	/^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

up:  ## 启动所有基础服务
	$(COMPOSE) up -d
	@echo "✅ 基础服务启动中, 等待健康检查..."
	@$(MAKE) --no-print-directory health

down:  ## 停止所有服务 (保留数据卷)
	$(COMPOSE) down

restart:  ## 重启所有服务
	$(COMPOSE) restart

ps:  ## 查看服务状态
	$(COMPOSE) ps

logs:  ## 跟踪所有服务日志 (用法: make logs S=postgres)
	$(COMPOSE) logs -f $(S)

status:  ## 显示资源占用
	docker stats $(PROJECT)-* --no-stream

health:  ## 健康检查
	@echo "🔍 检查服务健康状态..."
	@for svc in postgres redis minio milvus elasticsearch; do \
		state=$$($(COMPOSE) ps --format json $$svc 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0].get('Health','unknown')) if d else print('missing')" 2>/dev/null || echo "unknown"); \
		printf "  %-15s %s\n" $$svc $$state; \
	done

reset:  ## ⚠️ 销毁并重建 (会删除所有数据卷)
	@echo "⚠️  这会删除所有数据卷! 5 秒后继续, Ctrl+C 取消..."
	@sleep 5
	$(COMPOSE) down -v
	$(COMPOSE) up -d

# ---------- 管理工具 (叠加 admin 文件) ----------
pgadmin:  ## 启动 pgAdmin (http://localhost:5050)
	$(COMPOSE) -f docker-compose.yml -f $(ADMIN_FILE) up -d pgadmin

redis-insight:  ## 启动 RedisInsight (http://localhost:8001)
	$(COMPOSE) -f docker-compose.yml -f $(ADMIN_FILE) up -d redis-insight

kibana:  ## 启动 Kibana (http://localhost:5601)
	$(COMPOSE) -f docker-compose.yml -f $(ADMIN_FILE) up -d kibana

admin-up:  ## 一次性启动所有管理工具
	$(COMPOSE) -f docker-compose.yml -f $(ADMIN_FILE) up -d

admin-down:  ## 关闭所有管理工具
	$(COMPOSE) -f $(ADMIN_FILE) down

# ---------- 初始化 ----------
minio-init:  ## 创建 MinIO 默认 buckets
	@echo "🪣 创建 MinIO buckets: medpaper-pdfs, medpaper-figures, medpaper-exports"
	@docker run --rm --network $(PROJECT)-net \
		-e MC_HOST_minio=http://$(MINIO_ROOT_USER:-medpaper}:$(MINIO_ROOT_PASSWORD:-medpaper_dev_pwd)@minio:9000 \
		minio/mc:latest \
		sh -c "mc mb --ignore-existing minio/medpaper-pdfs && \
		       mc mb --ignore-existing minio/medpaper-figures && \
		       mc mb --ignore-existing minio/medpaper-exports && \
		       mc anonymous set download minio/medpaper-pdfs"
	@echo "✅ Buckets 创建完成"

es-init:  ## 初始化 ES 索引 (medpaper_papers, medpaper_chunks)
	@echo "📑 创建 ES 索引..."
	@curl -s -u elastic:$(ES_PASSWORD) -X PUT "http://localhost:9200/medpaper_papers" \
		-H "Content-Type: application/json" \
		-d '{"settings":{"number_of_shards":1,"number_of_replicas":0},"mappings":{"properties":{"title":{"type":"text","analyzer":"standard"},"abstract":{"type":"text"},"authors":{"type":"keyword"},"year":{"type":"integer"}}}}' \
		| python3 -m json.tool
	@curl -s -u elastic:$(ES_PASSWORD) -X PUT "http://localhost:9200/medpaper_chunks" \
		-H "Content-Type: application/json" \
		-d '{"settings":{"number_of_shards":1,"number_of_replicas":0},"mappings":{"properties":{"content":{"type":"text","analyzer":"standard"},"doc_id":{"type":"keyword"},"section":{"type":"keyword"}}}}' \
		| python3 -m json.tool
	@echo "✅ ES 索引创建完成"
