# process_data.py

import pandas as pd
import json
from datetime import datetime, timezone

# --- 1. 定义文件路径 ---
# 使用 r"" 来避免 Windows 路径中的反斜杠问题
INPUT_FILE = "../data/crawled_data.jsonl"
OUTPUT_FILE = "scored_data.jsonl"

# --- 2. 定义评分函数 ---
def calculate_scores(row):
    """
    根据单行数据计算贡献度和活跃度得分
    """
    score_contribution = 0
    score_activity = 0
    
    # --- A. 贡献度评估 (满分 50) ---
    max_commits = 10000
    commits_score = min(row.get('total_commits_count', 0) / max_commits * 15, 15)
    score_contribution += commits_score

    max_contributors = 200
    # 使用 .get('key', []) or [] 来安全地处理 None 值
    contributors_list = row.get('contributor_list', []) or []
    contributors_score = min(len(contributors_list) / max_contributors * 20, 20)
    score_contribution += contributors_score

    total_commits = row.get('total_commits_count', 0)
    if total_commits > 0 and len(contributors_list) >= 10:
        top10_commits = sum([c[1] for c in contributors_list[:10]])
        top10_ratio = top10_commits / total_commits
        if top10_ratio <= 0.2:
            distribution_score = 15
        elif top10_ratio >= 0.8:
            distribution_score = 0
        else:
            distribution_score = 15 - (top10_ratio - 0.2) / (0.8 - 0.2) * 15
        score_contribution += distribution_score

    # --- B. 活跃度评估 (满分 50) ---
    max_recent_commits = 50
    recent_commits_score = min(row.get('recent_commits_count', 0) / max_recent_commits * 25, 25)
    score_activity += recent_commits_score

    pushed_at_str = row.get('pushed_at')
    if pushed_at_str:
        try:
            # 处理带 'Z' 后缀的 ISO 字符串
            pushed_at = datetime.fromisoformat(pushed_at_str.replace('Z', '+00:00'))
            days_since_pushed = (datetime.now(timezone.utc) - pushed_at).days
            if days_since_pushed <= 1:
                update_score = 15
            elif days_since_pushed >= 180:
                update_score = 0
            else:
                update_score = 15 - days_since_pushed / 180 * 15
            score_activity += update_score
        except (ValueError, TypeError):
            # 如果日期格式不正确或为 None，则跳过
            pass
            
    max_stars = 50000
    stars_score = min(row.get('stargazers_count', 0) / max_stars * 10, 10)
    score_activity += stars_score
    
    return score_contribution, score_activity, score_contribution + score_activity

# --- 3. 主处理流程 ---
def main():
    print(f"开始处理数据，输入文件: {INPUT_FILE}")
    
    try:
        df = pd.read_json(INPUT_FILE, lines=True)
        print(f"成功加载 {len(df)} 条记录。")
    except FileNotFoundError:
        print(f"错误：输入文件 '{INPUT_FILE}' 未找到。请检查文件路径是否正确。")
        return
    except Exception as e:
        print(f"读取文件时发生错误: {e}")
        return

    scored_records = []
    print("正在计算分数...")
    for index, row in df.iterrows():
        record = row.to_dict()
        
        # --- 关键修改：同时处理 Timestamp 和 NaT ---
        # 检查 'created_at'
        if pd.notna(record.get('created_at')):
            record['created_at'] = record['created_at'].isoformat()
        else:
            # 如果是 NaT 或 None, 都设为 None，json.dump 会将其转为 null
            record['created_at'] = None
            
        # 检查 'pushed_at'
        if pd.notna(record.get('pushed_at')):
            record['pushed_at'] = record['pushed_at'].isoformat()
        else:
            record['pushed_at'] = None

        # 计算分数
        contrib_score, activ_score, total_score = calculate_scores(record)
        
        # 将计算出的分数添加到字典中
        record['贡献度得分'] = round(contrib_score, 2)
        record['活跃度得分'] = round(activ_score, 2)
        record['总分'] = round(total_score, 2)
        
        scored_records.append(record)
        
        # 每处理100条打印一次进度
        if (index + 1) % 100 == 0:
            print(f"  已处理 {index + 1}/{len(df)} 条记录...")

    print("分数计算完成！")

    # 将带有分数的记录写入新的 JSONL 文件
    print(f"正在将结果写入输出文件: {OUTPUT_FILE}")
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for record in scored_records:
                json.dump(record, f, ensure_ascii=False)
                f.write('\n')
    except Exception as e:
        print(f"写入文件时发生错误: {e}")
        return
            
    print(f"\n处理完成！已生成包含分数的文件: {OUTPUT_FILE}")
    print("现在可以运行 `visualize_data.py` 进行可视化分析。")

if __name__ == "__main__":
    main()