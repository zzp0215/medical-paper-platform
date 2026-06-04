-- ============================================
-- PostgreSQL 初始化脚本 (容器首次启动自动执行)
-- ============================================
-- 文件名必须以数字前缀 (01-, 02-...), 按字母序执行
-- 这里放: 扩展创建 + 默认 schema + 基础健康表
-- 业务表由 Alembic (Phase 1.1.4) 创建, 不在此处声明
-- ============================================

-- 必要扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";     -- UUID 生成
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- 文本相似度 (Phase 3 检索兜底)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- 加密函数
CREATE EXTENSION IF NOT EXISTS "vector";         -- pgvector (备用, 主向量用 Milvus)

-- 应用专用 schema
CREATE SCHEMA IF NOT EXISTS medpaper;

-- 健康检查表 (供 /health/db 验证连通性)
CREATE TABLE IF NOT EXISTS medpaper._healthcheck (
    id            SERIAL PRIMARY KEY,
    checked_at    TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO medpaper._healthcheck DEFAULT VALUES;

-- 输出 schema
\dn medpaper
