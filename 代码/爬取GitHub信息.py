
#能正常运行
import json
import time
from github import Github, GithubException
from datetime import datetime, timezone, timedelta
import os
import sys

# --- 1. 配置 ---

# 你的 GitHub Personal Access Token
GITHUB_TOKEN = "  "        #此处填写Token

# 输入和输出文件路径
INPUT_FILE = "../data/论文详情_批量爬取.jsonl"
OUTPUT_FILE = "crawled_data.jsonl"
STATE_FILE = "last_processed_id.txt"

# --- 2. 初始化 ---

print("--- 初始化爬虫 ---")
# 初始化 GitHub 连接
try:
    g = Github(GITHUB_TOKEN)
    # 测试连接
    g.get_user().login
    print(f"成功连接到 GitHub API，当前用户: {g.get_user().login}")
except Exception as e:
    print(f"错误：无法连接到 GitHub API。请检查你的网络和 Token。错误信息: {e}")
    sys.exit()

# --- 3. 加载仓库列表和检查续爬状态 ---

repos_to_crawl = []
try:
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                repos_to_crawl.append(data)
            except json.JSONDecodeError:
                print(f"警告：跳过无法解析的行: {line.strip()}")
    print(f"成功从 '{INPUT_FILE}' 加载了 {len(repos_to_crawl)} 个仓库。")
except FileNotFoundError:
    print(f"错误：输入文件 '{INPUT_FILE}' 未找到。请确保文件在脚本目录中。")
    sys.exit()

start_index = 0
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE, 'r') as f:
            last_id = int(f.read().strip())
            # 找到这个 ID 在列表中的索引
            for i, repo_info in enumerate(repos_to_crawl):
                if repo_info["总序号"] == last_id:
                    start_index = i + 1  # 从下一个开始
                    break
        print(f"检测到断点，将从序号 {last_id + 1} 开始继续爬取。")
    except Exception as e:
        print(f"警告：状态文件 '{STATE_FILE}' 存在但读取失败，将从头开始。错误: {e}")
else:
    print("未检测到断点，将从头开始爬取。")

# --- 4. 开始爬取 ---

print("\n--- 开始爬取数据 ---")
processed_count = 0
for i in range(start_index, len(repos_to_crawl)):
    repo_info = repos_to_crawl[i]
    repo_id = repo_info["总序号"]
    repo_url = repo_info["github链接"]

    print(f"\n[{i+1}/{len(repos_to_crawl)}] 正在处理序号 {repo_id}: {repo_url}")

    # 解析 owner 和 repo name
    if 'github.com' not in repo_url:
        print(f"  -> 警告：非 GitHub 链接，已跳过。")
        continue

    parts = repo_url.strip('/').split('/')
    if len(parts) < 2:
        print(f"  -> 警告：无法解析的 GitHub 链接，已跳过。")
        continue
    owner_name = parts[-2]
    repo_name = parts[-1]
    repo_full_name = f"{owner_name}/{repo_name}"

    # 准备要保存的数据
    result_data = {
        "总序号": repo_id,
        "github链接": repo_url,
        "owner": owner_name,
        "repo_name": repo_name,
        "stargazers_count": None,
        "forks_count": None,
        "open_issues_count": None,
        "created_at": None,
        "pushed_at": None,
        "contributor_list": [],
        "recent_commits_count": None,
        "total_commits_count": None,
        "error": None # 用于记录错误信息
    }

    try:
        # 获取仓库对象
        repo = g.get_repo(repo_full_name)
        print(f"  -> 成功获取仓库对象: {repo.full_name}")

        # --- 爬取数据 ---

        # 1. 基本信息
        result_data["stargazers_count"] = repo.stargazers_count
        result_data["forks_count"] = repo.forks_count
        result_data["open_issues_count"] = repo.open_issues_count
        result_data["created_at"] = repo.created_at.isoformat() if repo.created_at else None
        result_data["pushed_at"] = repo.pushed_at.isoformat() if repo.pushed_at else None
        time.sleep(1)

        # 2. 贡献者信息
        contributors = repo.get_contributors()
        result_data["contributor_list"] = [(c.login, c.contributions) for c in contributors]
        time.sleep(1)

        # 3. 提交历史
        last_month_date = datetime.now(timezone.utc) - timedelta(days=30)
        recent_commits = repo.get_commits(since=last_month_date)
        result_data["recent_commits_count"] = recent_commits.totalCount
        time.sleep(1)

        total_commits = repo.get_commits()
        result_data["total_commits_count"] = total_commits.totalCount
        time.sleep(1)
        
        print(f"  -> 数据爬取成功。星标: {result_data['stargazers_count']}, 贡献者: {len(result_data['contributor_list'])}")

    except GithubException as e:
        error_msg = f"GitHub API 错误: {e.status} - {e.data.get('message', 'No message')}"
        result_data["error"] = error_msg
        print(f"  -> {error_msg}")
    except Exception as e:
        error_msg = f"未知错误: {e}"
        result_data["error"] = error_msg
        print(f"  -> {error_msg}")

    # --- 5. 保存数据和更新状态 ---

    # 将结果追加到 JSONL 文件
    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False)
        f.write('\n')

    # 更新状态文件
    with open(STATE_FILE, 'w') as f:
        f.write(str(repo_id))
        
    processed_count += 1

# --- 6. 完成 ---

print("\n--- 爬取完成 ---")
print(f"总共处理了 {processed_count} 个仓库。")
print(f"数据已保存到 '{OUTPUT_FILE}'。")
print(f"最后处理的仓库序号 {repo_id} 已记录在 '{STATE_FILE}'。")

# 清理状态文件（可选）
if start_index + processed_count >= len(repos_to_crawl):
    os.remove(STATE_FILE)
    print(f"所有仓库已处理完毕，状态文件 '{STATE_FILE}' 已删除。")