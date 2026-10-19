CREATE DATABASE IF NOT EXISTS sql_dialect_converter;

USE sql_dialect_converter;

CREATE TABLE IF NOT EXISTS dialect (
    dialect_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    dialect_name VARCHAR(64) NOT NULL,
    version VARCHAR(32) NULL,
    supported_options JSON NOT NULL,
    PRIMARY KEY (dialect_id),
    UNIQUE KEY uq_dialect_name (dialect_name)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS ast_snapshot (
    snapshot_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    request_id CHAR(36) NOT NULL,
    source_dialect_id BIGINT UNSIGNED NOT NULL,
    target_dialect_id BIGINT UNSIGNED NOT NULL,
    snapshot_stage VARCHAR(32) NOT NULL,
    stage_number INT UNSIGNED NOT NULL,
    raw_sql LONGTEXT NOT NULL,
    generated_sql LONGTEXT NULL,
    ast_json JSON NOT NULL,
    node_count INT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (snapshot_id),
    UNIQUE KEY uq_snapshot_request_stage (request_id, stage_number),
    KEY ix_snapshot_request (request_id),
    CONSTRAINT fk_snapshot_source_dialect
        FOREIGN KEY (source_dialect_id) REFERENCES dialect (dialect_id),
    CONSTRAINT fk_snapshot_target_dialect
        FOREIGN KEY (target_dialect_id) REFERENCES dialect (dialect_id)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS optimization_rule (
    rule_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    rule_name VARCHAR(128) NOT NULL,
    pass_number INT UNSIGNED NOT NULL,
    description TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (rule_id),
    UNIQUE KEY uq_optimization_rule_name (rule_name)
) ENGINE = InnoDB;

CREATE TABLE IF NOT EXISTS transformation (
    snapshot_id BIGINT UNSIGNED NOT NULL,
    step_number INT UNSIGNED NOT NULL,
    rule_id BIGINT UNSIGNED NOT NULL,
    output_snapshot_id BIGINT UNSIGNED NOT NULL,
    ast_delta JSON NOT NULL,
    exec_time_us BIGINT UNSIGNED NOT NULL,
    PRIMARY KEY (snapshot_id, step_number),
    CONSTRAINT fk_transformation_input_snapshot
        FOREIGN KEY (snapshot_id) REFERENCES ast_snapshot (snapshot_id),
    CONSTRAINT fk_transformation_output_snapshot
        FOREIGN KEY (output_snapshot_id) REFERENCES ast_snapshot (snapshot_id),
    CONSTRAINT fk_transformation_rule
        FOREIGN KEY (rule_id) REFERENCES optimization_rule (rule_id)
) ENGINE = InnoDB;
