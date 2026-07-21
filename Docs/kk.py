import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# ==========================================
# 1. 基础配置
# ==========================================
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

base_dir = r"G:\WorkSpace-Yangjunjie\Data\2026-04-14_21-49-52"
print(f"🚀 启动批量下钻生成引擎，目标路径: {base_dir}")

# 我们关心的四个核心状态
core_statuses = ['待分配商家', '处理中', '已回复', '投诉已完成']
colors = ['#e74c3c', '#f1c40f', '#3498db', '#2ecc71']  # 红黄蓝绿

# ==========================================
# 2. 按行业独立处理大循环
# ==========================================
# 遍历根目录下的每一个行业文件夹
for industry_folder in os.listdir(base_dir):
    industry_path = os.path.join(base_dir, industry_folder)

    # 确保是文件夹（排除可能生成出来的 png 或 csv 文件）
    if not os.path.isdir(industry_path):
        continue

    print(f"\n📂 正在深入剖析行业: 【{industry_folder}】...")

    industry_records = []

    # 遍历该行业下的状态文件夹
    for status_folder in os.listdir(industry_path):
        status_path = os.path.join(industry_path, status_folder)

        if os.path.isdir(status_path):
            # 遍历状态文件夹下的 JSON
            for file_name in os.listdir(status_path):
                if file_name.endswith('.json'):
                    file_path = os.path.join(status_path, file_name)

                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            complaints = json.load(f)
                            for comp in complaints:
                                info = comp.get('complaint_info', {})
                                problems = info.get('投诉问题', '')

                                if pd.isna(problems) or not problems:
                                    continue

                                # 拆分词条
                                for p in str(problems).split(','):
                                    p = p.strip()
                                    if p:
                                        industry_records.append({
                                            '具体投诉问题': p,
                                            '所处状态': status_folder
                                        })
                    except Exception as e:
                        print(f"  ⚠️ 读取文件出错 {file_path}: {e}")

    # 将当前行业的所有底层数据转为 DataFrame
    df = pd.DataFrame(industry_records)

    # 如果这个行业有数据，就开始专门为它画图
    if len(df) > 0:
        print(f"  -> 提取到 {len(df)} 个问题标签，开始绘制专属诊断图...")

        # 交叉统计当前行业的问题和状态
        cross_tab = pd.crosstab(df['具体投诉问题'], df['所处状态'])

        # 补全可能缺失的列
        for col in core_statuses:
            if col not in cross_tab.columns:
                cross_tab[col] = 0
#下面是TF-IDF的变体，总频次-TF，怠慢率-IDF
        # 计算总频次，取该行业特有的 Top 10 或 12 高频问题（避免条目太多图太挤）
        cross_tab['总频次'] = cross_tab.sum(axis=1)
        top_problems = cross_tab.sort_values(by='总频次', ascending=False).head(12)

        # 计算该行业特有问题的“怠慢率”并降序
        top_problems['怠慢率'] = top_problems['待分配商家'] / top_problems['总频次']
        top_problems_sorted = top_problems.sort_values(by='怠慢率', ascending=False)
#综合排序 (TF * IDF)
        # 转为百分比数据
        plot_data = top_problems_sorted[core_statuses]
        plot_data_pct = plot_data.div(plot_data.sum(axis=1), axis=0) * 100

        # ==========================================
        # 3. 独立渲染并保存该行业的图表
        # ==========================================
        fig, ax = plt.subplots(figsize=(10, 7), dpi=200)

        plot_data_pct.plot(
            kind='bar',
            stacked=True,
            color=colors,
            ax=ax,
            width=0.7,
            edgecolor='white'
        )

        plt.title(f'【{industry_folder}】行业专属高频痛点与处理态度诊断图', fontsize=14, fontweight='bold', pad=15)
        plt.xlabel('该行业特有的投诉痛点 (Top 12)', fontsize=12, fontweight='bold')
        plt.ylabel('处理进度占比 (%)', fontsize=12, fontweight='bold')

        ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        plt.xticks(rotation=45, ha='right', fontsize=11)
        plt.legend(title='处理进度', bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=10)

        # 加数字标签
        for n, row in enumerate(plot_data_pct.index):
            y_bottom = 0
            for col in plot_data.columns:
                y_val = plot_data_pct.loc[row, col]
                if y_val > 5:  # 只显示占比 > 5% 的
                    ax.text(n, y_bottom + y_val / 2, f"{y_val:.1f}%", ha='center', va='center', color='white',
                            fontweight='bold', fontsize=8)
                y_bottom += y_val

        plt.tight_layout()

        # 动态命名并保存到根目录
        output_img = os.path.join(base_dir, f"[{industry_folder}]_专属痛点分析图.png")
        plt.savefig(output_img)

        # ⚠️极其重要：清空并关闭当前画布，准备画下一个行业的图！
        plt.close(fig)

        print(f"  ✅ [{industry_folder}] 图表生成完毕！")
    else:
        print(f"  ❌ [{industry_folder}] 未抓取到有效数据，跳过绘图。")

print(f"\n🎉 所有行业批量分析完成！请前往 {base_dir} 查看您的 12 张专属分析图。")