#修改之后论文地址是对的了

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import json

# 1. 配置浏览器（启用无头模式+优化资源）
chrome_options = Options()
chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})  # 禁用图片
chrome_options.add_argument("--headless=new")  # 无头模式：不打开浏览器窗口，更稳定
chrome_options.add_argument("--disable-gpu")  # 配合无头模式
chrome_options.add_argument("--window-size=1920,1080")  # 模拟窗口大小，避免元素定位异常
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)
wait = WebDriverWait(driver, 20)  # 延长等待到20秒，适配慢加载

all_papers = []
max_pages = 200   # 目标页数
current_page = 1

try:
    target_url = "https://joss.theoj.org/papers/published"
    driver.get(target_url)
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "paper-card")))  # 等待列表页加载完成

    # ========== 外层：翻页循环 ==========
    while current_page <= max_pages:
        print(f"\n==================== 正在爬取第 {current_page} 页 ====================")
        
        # 滚动加载当前页所有内容（用显式等待替代部分sleep）
        driver.execute_script("window.scrollTo(0, 0);")
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)  # 缩短sleep
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # 获取当前页论文总数
        paper_cards = driver.find_elements(By.CLASS_NAME, "paper-card")
        current_page_paper_count = len(paper_cards)
        print(f"✅ 第 {current_page} 页找到 {current_page_paper_count} 篇论文，爬取全部{min(20, current_page_paper_count)}篇")

        # ========== 内层：爬取当前页最多20篇 ==========
        for idx in range(min(20 , current_page_paper_count)):
            # 修复总序号计算
            total_idx = (current_page - 1) * 20 + (idx + 1)
            print(f"\n=== 总第 {total_idx} 篇（第{current_page}页第{idx+1}篇）===")
            
            # 重新定位card，避免元素失效
            driver.execute_script("window.scrollTo(0, 0);")
            current_cards = driver.find_elements(By.CLASS_NAME, "paper-card")
            if idx >= len(current_cards):
                print("❌ 当前card不存在，跳过")
                continue
            card = current_cards[idx]

            # 点击进入详情页
            try:
                click_elem = card.find_element(By.CLASS_NAME, "paper-title").find_element(By.TAG_NAME, "a")
                driver.execute_script("arguments[0].scrollIntoView({block: 'top'});", click_elem)
                driver.execute_script("arguments[0].click();", click_elem)
                print("✅ 跳转到详情页")
                # 等待详情页标题加载（替代固定sleep）
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))

                # ========== 提取数据 ==========
                detail_title = "无标题"
                github_link = "无github链接"
                submit_time = "无上传时间"
                published_time = "无发表时间"
                time.sleep(2)  # 强制等待2秒，给JavaScript足够的时间去更新URL
                paper_link = driver.current_url.strip()  # 详情页URL即论文地址
                paper_tags = ["无论文标签"]
                # 修复初始类型为列表
                language_of_paper = ["无论文语言"]

                # 提取标题
                try:
                    detail_title = driver.find_element(By.TAG_NAME, "h1").text.strip()
                    print(f"✅ 标题提取成功：{detail_title[:50]}...")
                except Exception as e:
                    print(f"❌ 标题提取失败：{str(e)[:80]}")

                # 提取github链接
                try:
                    github_link_elem = wait.until(EC.presence_of_element_located(
                        (By.XPATH, "//div[@class='btn-group-vertical']/a[@class='btn paper-btn']")
                    ))
                    github_link = github_link_elem.get_attribute("href").strip()
                    print(f"✅ github链接：{github_link}")
                except Exception as e:
                    print(f"❌ github链接提取失败：{str(e)[:80]}")

                # 提取上传时间
                try:
                    time1_elem = wait.until(EC.presence_of_element_located(
                        (By.XPATH, "//span[@class='small' and contains(text(), 'Submitted')]")
                    ))
                    submit_time = time1_elem.text.strip().replace("Submitted ", "")
                    print(f"✅ 上传时间：{submit_time}")
                except Exception as e:
                    print(f"❌ 上传时间提取失败：{str(e)[:80]}")

                # 提取发表时间
                try:
                    time2_elem = wait.until(EC.presence_of_element_located(
                        (By.XPATH, "//span[contains(@class, 'small') and contains(text(), 'Published')]")
                    ))
                    published_time = time2_elem.text.strip().replace("Published ", "")
                    print(f"✅ 发表时间：{published_time}")
                except Exception as e:
                    print(f"❌ 发表时间提取失败：{str(e)[:80]}")

                # 提取论文标签
                try:
                    paper_tag_elems = wait.until(EC.presence_of_all_elements_located(
                        (By.XPATH, "//span[@class='badge-lang']/a")
                    ))
                    paper_tags = [elem.text.strip() for elem in paper_tag_elems if elem.text.strip()]
                    print(f"✅ 论文标签：{paper_tags}")
                except Exception as e:
                    print(f"❌ 标签提取失败：{str(e)[:80]}")

                # 提取论文语言
                try:
                    language_elems = wait.until(EC.presence_of_all_elements_located(
                        (By.XPATH, "//div[@class='paper-meta']/h1/following-sibling::span[@class='badge-lang']/a")
                    ))
                    language_of_paper = [a.text.strip() for a in language_elems if a.text.strip()]
                    print(f"✅ 论文语言：{language_of_paper}")
                except Exception as e:
                    print(f"❌ 论文语言提取失败：{str(e)[:100]}")

                # 保存数据
                all_papers.append({
                    "总序号": total_idx,
                    "页码": current_page,
                    "页内序号": idx+1,
                    "标题": detail_title,
                    "github链接": github_link,
                    "上传时间": submit_time,
                    "发表时间": published_time,
                    "论文地址": paper_link,
                    "论文标签": paper_tags,
                    "论文语言": language_of_paper
                })

                # 返回列表页
                driver.back()
                # 等待列表页加载完成
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "paper-card")))

            except Exception as e:
                print(f"❌ 单篇论文提取失败：{str(e)[:100]}")
                driver.back()
                time.sleep(1)
                continue

        # ========== 翻页逻辑 ==========
        if current_page < max_pages:
            try:
                print(f"\n🔍 准备翻到第 {current_page+1} 页...")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                # 等待Next按钮可点击
                next_btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//div[@class='pagination']/a[contains(@aria-label, 'next')]")
                ))
                driver.execute_script("arguments[0].click();", next_btn)
                # 等待下一页加载
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "paper-card")))
                current_page += 1
                print(f"✅ 成功翻到第 {current_page} 页")
            except Exception as e:
                print(f"❌ 翻页失败（可能已到最后一页）：{str(e)[:80]}")
                break
        else:
            print(f"\n✅ 已爬完指定的 {max_pages} 页")
            break

# ========== 保存数据（边爬边保存，避免丢失） ==========
finally:
    if all_papers:
        # 保存JSONL（推荐后续处理）
        with open("论文详情_批量爬取.jsonl", "w", encoding="utf-8") as f_json:
            for paper in all_papers:
                json.dump(paper, f_json, ensure_ascii=False)
                f_json.write("\n")
        
        # # 保存TXT
        # with open("论文详情_批量爬取.txt", "w", encoding="utf-8") as f_txt:
        #     for p in all_papers:
        #         f_txt.write("="*50 + "\n")
        #         f_txt.write(f"总序号：{p['总序号']}\n")
        #         f_txt.write(f"页码：{p['页码']} | 页内序号：{p['页内序号']}\n")
        #         f_txt.write(f"标题：{p['标题']}\n")
        #         f_txt.write(f"github链接：{p['github链接']}\n")
        #         f_txt.write(f"上传时间：{p['上传时间']}\n")
        #         f_txt.write(f"发表时间：{p['发表时间']}\n")
        #         f_txt.write(f"论文地址：{p['论文地址']}\n")
        #         f_txt.write(f"论文标签：{','.join(p['论文标签'])}\n")
        #         f_txt.write(f"论文语言：{','.join(p['论文语言'])}\n")
        #         f_txt.write("="*50 + "\n\n")
        
        print(f"\n✅ 数据保存完成！共爬取 {len(all_papers)} 篇论文")
    else:
        print("\n❌ 未爬取到任何论文数据")
    
    driver.quit()
    print("\n🔚 程序结束")