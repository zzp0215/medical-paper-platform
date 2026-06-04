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

-- ============================================
-- LiteLLM 专用数据库 (Phase 1.1.5)
-- ============================================
-- 单独库避免与主应用 schema 冲突; LiteLLM 启动时自动建表
-- 注意: 需在 postgres 容器第一次启动时执行 (用 CREATE DATABASE)
-- ============================================
-- 注: PostgreSQL init 脚本不支持 CREATE DATABASE 在 IF NOT EXISTS 形式,
--      用 DO 块做幂等
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'medpaper_litellm') THEN
        CREATE DATABASE medpaper_litellm;
    END IF;
END
$$;
