import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import numpy as np
import sys
import plotly.io as pio
from jinja2 import Template
import warnings
import traceback
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List, Any, Optional

# 忽略警告
warnings.filterwarnings('ignore')

# --- 1. 配置与常量定义 ---
class Config:
    """配置类，集中管理所有配置参数"""
    PAPER_FILE_PATH = "../data/论文详情_批量爬取.jsonl"
    SCORED_FILE_PATH = "../data/scored_data.jsonl"
    OUTPUT_HTML = "academic_open_source_analysis_report.html"
    OUTPUT_DATA_JSON = "analysis_summary.json"
    
    # 图表参数
    CHART_HEIGHT = 350
    CHART_WIDTH = None  # None表示自适应
    COLOR_SCALE = 'Viridis'
    OPACITY = 0.8
    BUBBLE_SCALE_FACTOR = 3
    
    # 筛选阈值
    HIGH_SCORE_THRESHOLD = 30
    HIGH_CONTRIB_THRESHOLD = 5
    HIGH_ACTIVE_RATIO_THRESHOLD = 0.6
    
    # 页面样式
    PRIMARY_COLOR = "#3498db"
    SECONDARY_COLOR = "#2c3e50"
    SUCCESS_COLOR = "#27ae60"
    WARNING_COLOR = "#f39c12"
    DANGER_COLOR = "#e74c3c"

class Logger:
    """日志记录类"""
    def __init__(self):
        self.start_time = datetime.now()
        
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")
    
    def section(self, title: str):
        print("\n" + "="*60)
        print(f" {title}")
        print("="*60)
    
    def performance(self, operation: str):
        """记录性能信息"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return f"{operation}: {elapsed:.2f}s"

class JSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理Timestamp等特殊类型"""
    def default(self, obj):
        if isinstance(obj, (datetime, pd.Timestamp)):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        elif pd.isna(obj):
            return None
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super().default(obj)

# --- 2. 数据加载与预处理 ---
class DataProcessor:
    """数据处理类，封装所有数据处理逻辑"""
    
    @staticmethod
    def safe_read_jsonl(file_path: str, encoding_list: List[str] = ['utf-8', 'gbk', 'utf-8-sig']) -> Optional[pd.DataFrame]:
        """安全读取JSONL文件，尝试多种编码"""
        logger = Logger()
        for encoding in encoding_list:
            try:
                df = pd.read_json(file_path, lines=True, encoding=encoding)
                logger.log(f"成功以 {encoding} 编码加载文件: {os.path.basename(file_path)}")
                return df
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.log(f"读取文件 {file_path} 失败: {str(e)}", "ERROR")
                raise
        
        logger.log(f"无法以任何编码读取文件: {file_path}", "ERROR")
        return None
    
    @staticmethod
    def validate_data(df: pd.DataFrame, required_columns: List[str]) -> pd.DataFrame:
        """验证数据完整性"""
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            raise ValueError(f"缺少必要的列: {missing_cols}")
        
        null_counts = df[required_columns].isnull().sum()
        if null_counts.sum() > 0:
            print("数据缺失情况:")
            for col in required_columns:
                if null_counts[col] > 0:
                    print(f"  {col}: {null_counts[col]} 个空值")
        
        return df.dropna(subset=required_columns)
    
    @staticmethod
    def calculate_derived_features(df: pd.DataFrame) -> pd.DataFrame:
        """计算衍生特征"""
        df_clean = df.copy()
        
        # 日期处理
        df_clean['发表时间'] = pd.to_datetime(df_clean['发表时间'], errors='coerce')
        df_clean['发表周'] = df_clean['发表时间'].dt.to_period('W').dt.start_time
        df_clean['发表月份'] = df_clean['发表时间'].dt.to_period('M').dt.start_time
        df_clean['发表年份'] = df_clean['发表时间'].dt.year
        
        # 得分计算
        df_clean['活跃度占比'] = df_clean['活跃度得分'] / df_clean['总分'].replace(0, np.nan)
        
        # 气泡大小（基于总分，使用对数缩放避免极端值）
        df_clean['size_scaled'] = np.sqrt(df_clean['总分']) * Config.BUBBLE_SCALE_FACTOR
        
        # 同周内排序
        df_clean = df_clean.sort_values('发表周').reset_index(drop=True)
        df_clean['同周内顺序'] = df_clean.groupby('发表周').cumcount()
        
        return df_clean

# --- 3. 统计分析类 ---
class StatisticsAnalyzer:
    """统计分析类，计算各种统计指标"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.stats = {}
        
    def calculate_basic_stats(self) -> Dict[str, Any]:
        """计算基础统计量"""
        # 基础统计
        stats = {
            'total_projects': len(self.df),
            'time_range': {
                'start': self.df['发表时间'].min().strftime('%Y-%m-%d') if not self.df['发表时间'].empty else None,
                'end': self.df['发表时间'].max().strftime('%Y-%m-%d') if not self.df['发表时间'].empty else None,
                'days': int((self.df['发表时间'].max() - self.df['发表时间'].min()).days) if not self.df['发表时间'].empty else 0
            },
            'score_stats': {
                'total': {
                    'mean': float(self.df['总分'].mean()) if not self.df['总分'].empty else 0,
                    'median': float(self.df['总分'].median()) if not self.df['总分'].empty else 0,
                    'std': float(self.df['总分'].std()) if not self.df['总分'].empty else 0,
                    'min': float(self.df['总分'].min()) if not self.df['总分'].empty else 0,
                    'max': float(self.df['总分'].max()) if not self.df['总分'].empty else 0,
                    'q1': float(self.df['总分'].quantile(0.25)) if not self.df['总分'].empty else 0,
                    'q3': float(self.df['总分'].quantile(0.75)) if not self.df['总分'].empty else 0
                },
                'contribution': {
                    'mean': float(self.df['贡献度得分'].mean()) if not self.df['贡献度得分'].empty else 0,
                    'max': float(self.df['贡献度得分'].max()) if not self.df['贡献度得分'].empty else 0
                },
                'activity': {
                    'mean': float(self.df['活跃度得分'].mean()) if not self.df['活跃度得分'].empty else 0,
                    'max': float(self.df['活跃度得分'].max()) if not self.df['活跃度得分'].empty else 0
                }
            }
        }
        
        # 项目分类统计
        high_score_count = len(self.df[self.df['总分'] > Config.HIGH_SCORE_THRESHOLD])
        high_contrib_count = len(self.df[self.df['贡献度得分'] > Config.HIGH_CONTRIB_THRESHOLD])
        high_active_count = len(self.df[self.df['活跃度占比'] > Config.HIGH_ACTIVE_RATIO_THRESHOLD])
        
        stats['categories'] = {
            'high_score': int(high_score_count),
            'high_contrib': int(high_contrib_count),
            'high_active': int(high_active_count)
        }
        
        # 时间分布统计
        if not self.df['发表时间'].empty:
            monthly_counts = self.df.groupby(self.df['发表时间'].dt.strftime('%Y-%m')).size()
            if not monthly_counts.empty:
                peak_month = monthly_counts.idxmax()
                peak_count = int(monthly_counts.max())
            else:
                peak_month = None
                peak_count = 0
        else:
            peak_month = None
            peak_count = 0
            
        stats['time_distribution'] = {
            'weeks': int(self.df['发表周'].nunique()) if '发表周' in self.df.columns else 0,
            'months': int(self.df['发表月份'].nunique()) if '发表月份' in self.df.columns else 0,
            'years': int(self.df['发表年份'].nunique()) if '发表年份' in self.df.columns else 0,
            'peak_month': peak_month,
            'peak_count': peak_count
        }
        
        self.stats.update(stats)
        return stats
    
    def get_top_projects(self, n: int = 10) -> pd.DataFrame:
        """获取Top N项目"""
        if len(self.df) == 0:
            return pd.DataFrame()
        
        top_df = self.df.nlargest(n, '总分')[['repo_name', '总分', '贡献度得分', '活跃度得分', '发表时间']].copy()
        # 转换日期为字符串格式
        top_df['发表时间'] = top_df['发表时间'].dt.strftime('%Y-%m-%d')
        return top_df
    
    def get_summary_for_json(self) -> Dict[str, Any]:
        """获取适合JSON序列化的摘要数据"""
        stats = self.calculate_basic_stats()
        top_projects = self.get_top_projects(10)
        
        return {
            'stats': stats,
            'top_projects': top_projects.to_dict('records'),
            'generated_at': datetime.now().isoformat(),
            'data_version': '1.0.0',
            'total_records': len(self.df)
        }
    
    def search_projects(self, search_term: str) -> pd.DataFrame:
        """搜索项目"""
        if not search_term or len(search_term.strip()) == 0:
            return pd.DataFrame()
        
        search_lower = search_term.lower().strip()
        mask = (
            self.df['repo_name'].str.lower().str.contains(search_lower, na=False) |
            self.df['github链接'].str.lower().str.contains(search_lower, na=False) |
            self.df['论文地址'].str.lower().str.contains(search_lower, na=False)
        )
        
        return self.df[mask].copy()

# --- 4. 图表生成类 ---
class ChartGenerator:
    """图表生成类，封装所有图表生成逻辑"""
    
    @staticmethod
    def create_timeline_chart(df: pd.DataFrame, stats: Dict[str, Any]) -> go.Figure:
        """创建主时间轴图表 - 恢复原来的样式"""
        fig = go.Figure()
        
        if len(df) == 0:
            # 如果没有数据，显示空图表
            fig.add_annotation(
                text="暂无数据",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20)
            )
            return fig
        
        # 准备 customdata 用于点击跳转
        customdata = np.column_stack([
            df['repo_name'],
            df['github链接'],
            df['发表时间'].dt.strftime('%Y-%m-%d'),
            df['总分'].round(2),
            df['贡献度得分'].round(2),
            df['活跃度得分'].round(2),
            df['论文地址']
        ])
        
        # 创建四个数据集
        all_data = df.copy()
        high_score = df[df['总分'] > Config.HIGH_SCORE_THRESHOLD]
        high_contrib = df[df['贡献度得分'] > Config.HIGH_CONTRIB_THRESHOLD]
        high_active = df[df['活跃度占比'] > Config.HIGH_ACTIVE_RATIO_THRESHOLD]
        
        # 准备各个数据集的customdata
        custom_all = np.column_stack([
            all_data['repo_name'],
            all_data['github链接'],
            all_data['发表时间'].dt.strftime('%Y-%m-%d'),
            all_data['总分'].round(2),
            all_data['贡献度得分'].round(2),
            all_data['活跃度得分'].round(2),
            all_data['论文地址']
        ])
        
        custom_high_score = np.column_stack([
            high_score['repo_name'],
            high_score['github链接'],
            high_score['发表时间'].dt.strftime('%Y-%m-%d'),
            high_score['总分'].round(2),
            high_score['贡献度得分'].round(2),
            high_score['活跃度得分'].round(2),
            high_score['论文地址']
        ]) if len(high_score) > 0 else None
        
        custom_high_contrib = np.column_stack([
            high_contrib['repo_name'],
            high_contrib['github链接'],
            high_contrib['发表时间'].dt.strftime('%Y-%m-%d'),
            high_contrib['总分'].round(2),
            high_contrib['贡献度得分'].round(2),
            high_contrib['活跃度得分'].round(2),
            high_contrib['论文地址']
        ]) if len(high_contrib) > 0 else None
        
        custom_high_active = np.column_stack([
            high_active['repo_name'],
            high_active['github链接'],
            high_active['发表时间'].dt.strftime('%Y-%m-%d'),
            high_active['总分'].round(2),
            high_active['贡献度得分'].round(2),
            high_active['活跃度得分'].round(2),
            high_active['论文地址']
        ]) if len(high_active) > 0 else None
        
        # 四个 trace（全部关联 coloraxis1，实现色阶统一）
        fig.add_trace(go.Scatter(
            x=all_data['发表周'], y=all_data['同周内顺序'],
            mode='markers',
            marker=dict(
                size=all_data['size_scaled'], 
                color=all_data['总分'],
                colorscale='Viridis',
                opacity=Config.OPACITY,
                coloraxis="coloraxis1"
            ),
            hoverlabel=dict(
                bgcolor="white",
                bordercolor="black",
                font=dict(color="#333333")
            ),
            name='全部项目',
            hovertemplate="""
<br>
<b>仓库:</b> %{customdata[0]}<br>
<b>Github:</b> <a href='%{customdata[1]}'>%{customdata[1]}</a><br>
<b>发表:</b> %{customdata[2]}<br>
<b>总分:</b> %{customdata[3]}<br>
<b>贡献度:</b> %{customdata[4]} | <b>活跃度:</b> %{customdata[5]}<br>
<b>论文:</b> <a href='%{customdata[6]}'>%{customdata[6]}</a><br>
<extra></extra>
""",
            customdata=custom_all,
            visible=True
        ))
        
        if len(high_score) > 0:
            fig.add_trace(go.Scatter(
                x=high_score['发表周'], y=high_score['同周内顺序'],
                mode='markers',
                marker=dict(
                    size=high_score['size_scaled'], 
                    color=high_score['总分'],
                    colorscale='Viridis',
                    opacity=Config.OPACITY,
                    coloraxis="coloraxis1"
                ),
                hoverlabel=dict(
                    bgcolor="white",
                    bordercolor="black",
                    font=dict(color="#333333")
                ),
                name='高分项目 (>30)',
                hovertemplate=fig.data[0].hovertemplate,
                customdata=custom_high_score,
                visible=False
            ))
        
        if len(high_contrib) > 0:
            fig.add_trace(go.Scatter(
                x=high_contrib['发表周'], y=high_contrib['同周内顺序'],
                mode='markers',
                marker=dict(
                    size=high_contrib['size_scaled'], 
                    color=high_contrib['总分'],
                    colorscale='Viridis',
                    opacity=Config.OPACITY,
                    coloraxis="coloraxis1"
                ),
                hoverlabel=dict(
                    bgcolor="white",
                    bordercolor="black",
                    font=dict(color="#333333")
                ),
                name='高贡献度 (>5)',
                hovertemplate=fig.data[0].hovertemplate,
                customdata=custom_high_contrib,
                visible=False
            ))
        
        if len(high_active) > 0:
            fig.add_trace(go.Scatter(
                x=high_active['发表周'], y=high_active['同周内顺序'],
                mode='markers',
                marker=dict(
                    size=high_active['size_scaled'], 
                    color=high_active['总分'],
                    colorscale='Viridis',
                    opacity=Config.OPACITY,
                    coloraxis="coloraxis1"
                ),
                hoverlabel=dict(
                    bgcolor="white",
                    bordercolor="black",
                    font=dict(color="#333333")
                ),
                name='高活跃度 (>60%)',
                hovertemplate=fig.data[0].hovertemplate,
                customdata=custom_high_active,
                visible=False
            ))
        
        # 计算按钮显示状态
        button_visible = [True]
        if len(high_score) > 0:
            button_visible.append(True)
        else:
            button_visible.append(False)
            
        if len(high_contrib) > 0:
            button_visible.append(True)
        else:
            button_visible.append(False)
            
        if len(high_active) > 0:
            button_visible.append(True)
        else:
            button_visible.append(False)
        
        # 创建按钮列表
        buttons = [
            dict(
                label="全部项目",
                method="update",
                args=[
                    {"visible": [True] + [False] * (len(fig.data) - 1)},
                    {}
                ]
            )
        ]
        
        if len(high_score) > 0:
            visible_list = [False] * len(fig.data)
            visible_list[1] = True  # 高分项目是第二个trace
            buttons.append(
                dict(
                    label="高分项目(>30)",
                    method="update",
                    args=[
                        {"visible": visible_list},
                        {}
                    ]
                )
            )
        
        if len(high_contrib) > 0:
            visible_list = [False] * len(fig.data)
            visible_list[2] = True  # 高贡献项目是第三个trace
            buttons.append(
                dict(
                    label="高贡献度项目",
                    method="update",
                    args=[
                        {"visible": visible_list},
                        {}
                    ]
                )
            )
        
        if len(high_active) > 0:
            visible_list = [False] * len(fig.data)
            visible_list[3] = True  # 高活跃项目是第四个trace
            buttons.append(
                dict(
                    label="高活跃度项目",
                    method="update",
                    args=[
                        {"visible": visible_list},
                        {}
                    ]
                )
            )
        
        fig.update_layout(
            title=dict(
                text="<b>📅 学术开源项目时间轴</b><br><sup>上方按钮筛选项目</sup>",
                font=dict(size=16),
                x=0.5
            ),
            xaxis=dict(
                title="论文发表周 (周一为起点)",
                showgrid=True,
                gridcolor='LightGray',
                rangeslider=dict(
                    visible=True,
                    bgcolor='#f8f9fa',
                    bordercolor='#dee2e6',
                    borderwidth=1,
                    thickness=0.1
                )
            ),
            yaxis=dict(
                title="同周内顺序",
                showgrid=False,
                showticklabels=False
            ),
            coloraxis=dict(
                colorscale='Viridis',
                colorbar=dict(
                    title=dict(text="总分", font=dict(size=12)),
                    tickfont=dict(size=10),
                    x=1.05,
                    y=0.5,
                    len=0.8
                ),
                cmin=df['总分'].min(),
                cmax=df['总分'].max()
            ),
            template='plotly_white',
            height=Config.CHART_HEIGHT + 100,
            hovermode='closest',
            updatemenus=[
                dict(
                    type="buttons",
                    direction="right",
                    x=0.5, y=1.15,
                    xanchor="center", yanchor="top",
                    buttons=buttons
                )
            ]
        )
        
        return fig
    
    @staticmethod
    def create_score_distribution_chart(df: pd.DataFrame) -> go.Figure:
        """创建得分分布图表"""
        fig = go.Figure()
        
        if len(df) == 0:
            fig.add_annotation(
                text="暂无数据",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20)
            )
            return fig
        
        # 总分分布
        fig.add_trace(go.Histogram(
            x=df['总分'],
            nbinsx=30,
            name='总分分布',
            marker_color=Config.PRIMARY_COLOR,
            opacity=0.7
        ))
        
        fig.update_layout(
            title="<b>📊 项目总分分布</b>",
            xaxis_title="总分",
            yaxis_title="项目数量",
            height=Config.CHART_HEIGHT,
            template='plotly_white',
            bargap=0.1
        )
        
        return fig
    
    @staticmethod
    def create_scatter_matrix(df: pd.DataFrame) -> go.Figure:
        """创建散点矩阵图"""
        fig = go.Figure()
        
        if len(df) == 0:
            fig.add_annotation(
                text="暂无数据",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20)
            )
            return fig
        
        fig.add_trace(go.Scatter(
            x=df['贡献度得分'],
            y=df['活跃度得分'],
            mode='markers',
            marker=dict(
                size=8,
                color=df['总分'],
                colorscale=Config.COLOR_SCALE,
                showscale=True,
                colorbar=dict(title="总分")
            ),
            text=df['repo_name'],
            customdata=np.column_stack([
                df['repo_name'],
                df['总分'].round(2)
            ]),
            hovertemplate="<b>%{text}</b><br>贡献度: %{x:.2f}<br>活跃度: %{y:.2f}<br>总分: %{customdata[1]}<extra></extra>"
        ))
        
        # 添加趋势线（至少需要2个点）
        if len(df) >= 2:
            try:
                z = np.polyfit(df['贡献度得分'], df['活跃度得分'], 1)
                p = np.poly1d(z)
                x_line = np.linspace(df['贡献度得分'].min(), df['贡献度得分'].max(), 100)
                y_line = p(x_line)
                
                fig.add_trace(go.Scatter(
                    x=x_line, y=y_line,
                    mode='lines',
                    line=dict(color='red', width=2, dash='dash'),
                    name='趋势线'
                ))
            except:
                pass
        
        fig.update_layout(
            title="<b>🔗 贡献度 vs 活跃度关系</b>",
            xaxis_title="贡献度得分",
            yaxis_title="活跃度得分",
            height=Config.CHART_HEIGHT,
            template='plotly_white'
        )
        
        return fig
    
    @staticmethod
    def create_trend_chart(df: pd.DataFrame) -> go.Figure:
        """创建趋势图"""
        fig = go.Figure()
        
        if len(df) == 0 or df['发表时间'].isnull().all():
            fig.add_annotation(
                text="暂无数据",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20)
            )
            return fig
        
        # 按月度聚合
        try:
            monthly_data = df.set_index('发表时间').resample('M').agg({
                '总分': ['count', 'mean', 'sum']
            })
            monthly_data.columns = ['项目数量', '平均总分', '总分合计']
            monthly_data = monthly_data.reset_index()
            
            if len(monthly_data) == 0:
                raise ValueError("月度数据为空")
                
            # 项目数量（柱状图）
            fig.add_trace(go.Bar(
                x=monthly_data['发表时间'],
                y=monthly_data['项目数量'],
                name='项目数量',
                marker_color=Config.SECONDARY_COLOR,
                opacity=0.6
            ))
            
            # 平均总分（折线图，次y轴）
            fig.add_trace(go.Scatter(
                x=monthly_data['发表时间'],
                y=monthly_data['平均总分'],
                name='平均总分',
                mode='lines+markers',
                yaxis='y2',
                line=dict(color=Config.SUCCESS_COLOR, width=2)
            ))
            
            fig.update_layout(
                title="<b>📈 月度发表趋势</b>",
                xaxis_title="时间",
                yaxis_title="项目数量",
                yaxis2=dict(
                    title="平均总分",
                    overlaying='y',
                    side='right'
                ),
                height=Config.CHART_HEIGHT,
                template='plotly_white',
                hovermode='x unified'
            )
        except Exception as e:
            fig.add_annotation(
                text=f"数据聚合失败: {str(e)}",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14)
            )
        
        return fig
    
    @staticmethod
    def create_category_pie_chart(df: pd.DataFrame, stats: Dict[str, Any]) -> go.Figure:
        """创建分类饼图"""
        fig = go.Figure()
        
        if len(df) == 0:
            fig.add_annotation(
                text="暂无数据",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=20)
            )
            return fig
        
        # 分类数据
        categories = ['高分项目', '高贡献项目', '高活跃项目']
        values = [
            stats['categories']['high_score'],
            stats['categories']['high_contrib'],
            stats['categories']['high_active']
        ]
        
        # 过滤掉值为0的类别
        filtered_categories = []
        filtered_values = []
        for cat, val in zip(categories, values):
            if val > 0:
                filtered_categories.append(cat)
                filtered_values.append(val)
        
        if not filtered_categories:
            fig.add_annotation(
                text="无分类数据",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14)
            )
            return fig
        
        colors = [Config.SUCCESS_COLOR, Config.WARNING_COLOR, Config.PRIMARY_COLOR]
        
        fig.add_trace(go.Pie(
            labels=filtered_categories,
            values=filtered_values,
            hole=0.4,
            marker=dict(colors=colors[:len(filtered_categories)]),
            textinfo='label+percent+value',
            hovertemplate='<b>%{label}</b><br>数量: %{value}<br>占比: %{percent}<extra></extra>'
        ))
        
        fig.update_layout(
            title="<b>🥧 项目分类分布</b>",
            height=Config.CHART_HEIGHT,
            template='plotly_white',
            showlegend=True
        )
        
        return fig

# --- 5. HTML生成类 ---
class HTMLGenerator:
    """HTML页面生成类"""
    
    @staticmethod
    def generate_html(timeline_chart: go.Figure, stat_charts: Dict[str, go.Figure], 
                     stats: Dict[str, Any], data_summary: Dict[str, Any],
                     project_data: List[Dict]) -> str:
        """生成完整的HTML页面"""
        
        template = Template('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    
    <!-- 图标库 -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
        :root {
            --primary-color: {{ primary_color }};
            --secondary-color: {{ secondary_color }};
            --success-color: {{ success_color }};
            --warning-color: {{ warning_color }};
            --danger-color: {{ danger_color }};
            --light-bg: #f8f9fa;
            --border-color: #dee2e6;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f7fa;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 5px 30px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        
        /* 头部样式 */
        .header {
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 40px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: radial-gradient(circle, rgba(255,255,255,0.1) 1px, transparent 1px);
            background-size: 20px 20px;
            opacity: 0.1;
        }
        
        .header h1 {
            font-size: 2.8rem;
            margin-bottom: 15px;
            font-weight: 700;
            position: relative;
        }
        
        .header .subtitle {
            font-size: 1.2rem;
            opacity: 0.9;
            max-width: 800px;
            margin: 0 auto;
        }
        
        /* 搜索框 */
        .search-container {
            background: var(--light-bg);
            padding: 20px;
            border-bottom: 1px solid var(--border-color);
        }
        
        .search-box {
            display: flex;
            gap: 10px;
            max-width: 800px;
            margin: 0 auto;
        }
        
        .search-input {
            flex: 1;
            padding: 12px 20px;
            border: 2px solid var(--border-color);
            border-radius: 8px;
            font-size: 1rem;
            transition: all 0.3s;
        }
        
        .search-input:focus {
            outline: none;
            border-color: var(--primary-color);
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.2);
        }
        
        .search-button {
            padding: 12px 24px;
            background: var(--primary-color);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .search-button:hover {
            background: #2980b9;
            transform: translateY(-2px);
        }
        
        .clear-button {
            padding: 12px 24px;
            background: var(--secondary-color);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .clear-button:hover {
            background: #1c2833;
            transform: translateY(-2px);
        }
        
        .search-tips {
            margin-top: 10px;
            font-size: 0.9rem;
            color: #666;
            text-align: center;
        }
        
        /* 搜索结果 */
        .search-results {
            background: white;
            border-radius: 8px;
            margin: 20px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            border: 1px solid var(--border-color);
            max-height: 400px;
            overflow-y: auto;
            display: none;
        }
        
        .search-results.active {
            display: block;
        }
        
        .search-result-header {
            padding: 15px 20px;
            background: var(--light-bg);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .search-result-count {
            font-weight: 600;
            color: var(--secondary-color);
        }
        
        .search-result-list {
            padding: 0;
        }
        
        .search-result-item {
            padding: 15px 20px;
            border-bottom: 1px solid var(--border-color);
            transition: background-color 0.3s;
        }
        
        .search-result-item:hover {
            background-color: rgba(0, 123, 255, 0.05);
        }
        
        .search-result-item:last-child {
            border-bottom: none;
        }
        
        .result-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 5px;
            color: var(--secondary-color);
        }
        
        .result-links {
            display: flex;
            gap: 15px;
            margin-top: 8px;
        }
        
        .result-link {
            color: var(--primary-color);
            text-decoration: none;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .result-link:hover {
            text-decoration: underline;
        }
        
        .result-stats {
            display: flex;
            gap: 15px;
            margin-top: 8px;
            font-size: 0.9rem;
            color: #666;
        }
        
        .stat-item {
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        /* 控制面板 */
        .control-panel {
            background: var(--light-bg);
            padding: 20px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .info-badge {
            background: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .info-badge:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }
        
        .info-badge i {
            font-size: 1.1rem;
        }
        
        /* 统计卡片 */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 30px;
        }
        
        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 3px 15px rgba(0,0,0,0.08);
            transition: transform 0.3s, box-shadow 0.3s;
            border-top: 4px solid var(--primary-color);
            display: flex;
            align-items: center;
            gap: 20px;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 20px rgba(0,0,0,0.12);
        }
        
        .stat-card.highlight {
            border-top-color: var(--success-color);
        }
        
        .stat-icon {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.8rem;
            color: white;
        }
        
        .stat-content {
            flex: 1;
        }
        
        .stat-value {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 1rem;
            color: #666;
        }
        
        /* 图表区域 */
        .chart-section {
            padding: 0 30px 30px;
        }
        
        .section-title {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--secondary-color);
            margin: 30px 0 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .section-title i {
            color: var(--primary-color);
        }
        
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 25px;
            margin-bottom: 30px;
        }
        
        @media (max-width: 1300px) {
            .charts-grid {
                grid-template-columns: 1fr;
            }
        }
        
        .chart-container {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            border: 1px solid var(--border-color);
            min-height: {{ chart_height }}px;
        }
        
        .chart-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 15px;
            color: var(--secondary-color);
        }
        
        /* 数据表格 */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            font-size: 0.95rem;
        }
        
        .data-table th,
        .data-table td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }
        
        .data-table th {
            background-color: var(--light-bg);
            font-weight: 600;
            color: var(--secondary-color);
            position: sticky;
            top: 0;
        }
        
        .data-table tr:hover {
            background-color: rgba(0, 123, 255, 0.05);
        }
        
        /* 页脚 */
        .footer {
            background: var(--secondary-color);
            color: white;
            padding: 25px;
            text-align: center;
            margin-top: 40px;
        }
        
        .footer-links {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-top: 15px;
        }
        
        .footer a {
            color: white;
            text-decoration: none;
            opacity: 0.8;
            transition: opacity 0.3s;
        }
        
        .footer a:hover {
            opacity: 1;
            text-decoration: underline;
        }
        
        /* 响应式设计 */
        @media (max-width: 768px) {
            .header h1 {
                font-size: 2rem;
            }
            
            .header {
                padding: 25px;
            }
            
            .charts-grid {
                grid-template-columns: 1fr;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .control-panel {
                flex-direction: column;
                align-items: stretch;
            }
            
            .stat-card {
                flex-direction: column;
                text-align: center;
                gap: 15px;
            }
            
            .data-table {
                display: block;
                overflow-x: auto;
            }
            
            .search-box {
                flex-direction: column;
            }
        }
        
        /* 动画效果 */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .fade-in {
            animation: fadeIn 0.6s ease-out;
        }
        
        /* 工具提示 */
        .tooltip {
            position: relative;
            cursor: help;
            border-bottom: 1px dotted #666;
        }
        
        .tooltip-text {
            visibility: hidden;
            width: 200px;
            background-color: #333;
            color: #fff;
            text-align: center;
            border-radius: 6px;
            padding: 10px;
            position: absolute;
            z-index: 1000;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 0.9rem;
        }
        
        .tooltip:hover .tooltip-text {
            visibility: visible;
            opacity: 1;
        }
        
        /* 加载动画 */
        .loader {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(255,255,255,0.95);
            z-index: 9999;
            justify-content: center;
            align-items: center;
            flex-direction: column;
        }
        
        .loader.active {
            display: flex;
        }
        
        .spinner {
            width: 50px;
            height: 50px;
            border: 5px solid #f3f3f3;
            border-top: 5px solid var(--primary-color);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        /* 消息通知 */
        .notification {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            background: var(--success-color);
            color: white;
            border-radius: 5px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.2);
            z-index: 10000;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: slideIn 0.3s ease-out;
        }
        
        .notification.error {
            background: var(--danger-color);
        }
        
        .notification.warning {
            background: var(--warning-color);
        }
        
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        
        /* 模态框 */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 10001;
            justify-content: center;
            align-items: center;
        }
        
        .modal.active {
            display: flex;
        }
        
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 10px;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .modal-title {
            font-size: 1.5rem;
            color: var(--secondary-color);
        }
        
        .close-modal {
            background: none;
            border: none;
            font-size: 1.5rem;
            cursor: pointer;
            color: #666;
        }
        
        /* 选项卡 */
        .tabs {
            display: flex;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 20px;
        }
        
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.3s;
        }
        
        .tab.active {
            border-bottom-color: var(--primary-color);
            color: var(--primary-color);
            font-weight: 600;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
    </style>
</head>
<body>
    <!-- 加载动画 -->
    <div class="loader" id="loader">
        <div class="spinner"></div>
        <p style="margin-top: 20px; color: var(--primary-color); font-weight: 600;">正在加载数据...</p>
    </div>
    
    <!-- 模态框 -->
    <div class="modal" id="infoModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 class="modal-title" id="modalTitle">信息</h3>
                <button class="close-modal" onclick="closeModal()">&times;</button>
            </div>
            <div id="modalContent">
                <!-- 动态内容 -->
            </div>
        </div>
    </div>
    
    <div class="container fade-in">
        <!-- 头部 -->
        <div class="header">
            <h1><i class="fas fa-chart-line"></i> 学术开源项目分析平台</h1>
            <p class="subtitle">
                基于 {{ stats.total_projects }} 个开源项目的多维度数据分析与可视化
            </p>
        </div>
        
        <!-- 搜索框 -->
        <div class="search-container">
            <div class="search-box">
                <input type="text" 
                       id="searchInput" 
                       class="search-input" 
                       placeholder="搜索论文名称、GitHub仓库、论文地址或GitHub链接..."
                       onkeydown="if(event.key === 'Enter') searchProjects()">
                <button class="search-button" onclick="searchProjects()">
                    <i class="fas fa-search"></i> 搜索
                </button>
                <button class="clear-button" onclick="clearSearch()">
                    <i class="fas fa-times"></i> 清空
                </button>
            </div>
            <div class="search-tips">
                提示：可以搜索项目名称、GitHub链接、论文地址等关键词
            </div>
            
            <!-- 搜索结果 -->
            <div class="search-results" id="searchResults">
                <div class="search-result-header">
                    <div class="search-result-count" id="searchResultCount">
                        搜索结果 (0)
                    </div>
                    <button onclick="clearSearch()" style="background: none; border: none; color: #666; cursor: pointer;">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="search-result-list" id="searchResultList">
                    <!-- 搜索结果将动态插入到这里 -->
                </div>
            </div>
        </div>
        
        <!-- 控制面板 -->
        <div class="control-panel">
            <div class="info-badge" onclick="showTimeInfo()">
                <i class="fas fa-calendar-alt"></i>
                {% if stats.time_range.start and stats.time_range.end %}
                时间范围: {{ stats.time_range.start }} 至 {{ stats.time_range.end }}
                {% else %}
                时间范围: 无数据
                {% endif %}
            </div>
            <div class="info-badge" onclick="showDataInfo()">
                <i class="fas fa-database"></i>
                数据版本: {{ current_time }}
            </div>
            <div>
                <button onclick="exportData()" class="info-badge">
                    <i class="fas fa-download"></i> 导出数据
                </button>
                <button onclick="refreshData()" class="info-badge">
                    <i class="fas fa-sync-alt"></i> 刷新
                </button>
            </div>
        </div>
        
        <!-- 统计卡片 -->
        <div class="stats-grid">
            <div class="stat-card highlight">
                <div class="stat-icon" style="background: var(--success-color);">
                    <i class="fas fa-project-diagram"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">{{ stats.total_projects }}</div>
                    <div class="stat-label">总项目数量</div>
                    {% if stats.time_range.days %}
                    <div style="font-size: 0.9rem; color: #888;">
                        覆盖 {{ stats.time_range.days }} 天
                    </div>
                    {% endif %}
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon" style="background: var(--primary-color);">
                    <i class="fas fa-star"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">{{ "%.2f"|format(stats.score_stats.total.mean) if stats.score_stats.total.mean else "0.00" }}</div>
                    <div class="stat-label">平均总分</div>
                    <div style="font-size: 0.9rem; color: #888;">
                        范围: {{ "%.2f"|format(stats.score_stats.total.min) if stats.score_stats.total.min else "0.00" }} - {{ "%.2f"|format(stats.score_stats.total.max) if stats.score_stats.total.max else "0.00" }}
                    </div>
                </div>
            </div>
            
            <div class="stat-card">
                <div class="stat-icon" style="background: var(--warning-color);">
                    <i class="fas fa-trophy"></i>
                </div>
                <div class="stat-content">
                    <div class="stat-value">{{ stats.categories.high_score }}</div>
                    <div class="stat-label">高分项目(>30分)</div>
                    <div style="font-size: 0.9rem; color: #888;">
                        占比: {{ "%.1f"|format(stats.categories.high_score/stats.total_projects*100) if stats.total_projects > 0 else "0.0" }}%
                    </div>
                </div>
            </div>
    
        </div>
        
        <!-- 选项卡 -->
        <div class="chart-section">
            <div class="tabs">
                <div class="tab active" onclick="switchTab('timeline')">
                    <i class="fas fa-timeline"></i> 时间轴分析
                </div>
                <div class="tab" onclick="switchTab('statistics')">
                    <i class="fas fa-chart-bar"></i> 统计分析
                </div>
                <div class="tab" onclick="switchTab('details')">
                    <i class="fas fa-table"></i> 详细数据
                </div>
            </div>
            
            <!-- 时间轴分析选项卡 -->
            <div id="timelineTab" class="tab-content active">
                <div class="chart-container">
                    {{ timeline_chart|safe }}
                </div>
            </div>
            
            <!-- 统计分析选项卡 -->
            <div id="statisticsTab" class="tab-content">
                <div class="charts-grid">
                    <div class="chart-container">
                        <div class="chart-title">得分分布分析</div>
                        {{ stat_charts.distribution|safe }}
                    </div>
                    <div class="chart-container">
                        <div class="chart-title">指标关系分析</div>
                        {{ stat_charts.scatter|safe }}
                    </div>
                    <div class="chart-container">
                        <div class="chart-title">时间趋势分析</div>
                        {{ stat_charts.trend|safe }}
                    </div>
                    <div class="chart-container">
                        <div class="chart-title">项目分类分析</div>
                        {{ stat_charts.pie|safe }}
                    </div>
                </div>
            </div>
            
            <!-- 详细数据选项卡 -->
            <div id="detailsTab" class="tab-content">
                <div style="background: var(--light-bg); padding: 20px; border-radius: 8px;">
                    <h3 style="margin-bottom: 15px; color: var(--secondary-color);">
                        <i class="fas fa-file-alt"></i> 详细分析报告
                    </h3>
                    
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px;">
                        <div>
                            <h4><i class="fas fa-calendar"></i> 时间维度分析</h4>
                            <ul style="padding-left: 20px; margin-top: 10px;">
                                <li>分析时间跨度: <strong>{{ stats.time_range.days if stats.time_range.days else 0 }} 天</strong></li>
                                <li>覆盖 {{ stats.time_distribution.weeks }} 个发表周</li>
                                <li>跨 {{ stats.time_distribution.years }} 个年份</li>
                                {% if stats.time_distribution.peak_month %}
                                <li>最活跃月份: <strong>{{ stats.time_distribution.peak_month }}</strong></li>
                                {% endif %}
                            </ul>
                        </div>
                        
                        <div>
                            <h4><i class="fas fa-chart-pie"></i> 项目分类分析</h4>
                            <ul style="padding-left: 20px; margin-top: 10px;">
                                <li>高分项目: {{ stats.categories.high_score }} 个</li>
                                <li>高贡献项目: {{ stats.categories.high_contrib }} 个</li>
                                <li>高活跃项目: {{ stats.categories.high_active }} 个</li>
                            </ul>
                        </div>
                        
                        <div>
                            <h4><i class="fas fa-chart-line"></i> 得分统计分析</h4>
                            <ul style="padding-left: 20px; margin-top: 10px;">
                                <li>中位数: {{ "%.2f"|format(stats.score_stats.total.median) if stats.score_stats.total.median else "0.00" }}</li>
                                <li>标准差: {{ "%.2f"|format(stats.score_stats.total.std) if stats.score_stats.total.std else "0.00" }}</li>
                                <li>Q1 (25%分位): {{ "%.2f"|format(stats.score_stats.total.q1) if stats.score_stats.total.q1 else "0.00" }}</li>
                                <li>Q3 (75%分位): {{ "%.2f"|format(stats.score_stats.total.q3) if stats.score_stats.total.q3 else "0.00" }}</li>
                            </ul>
                        </div>
                    </div>
                    
                    <!-- Top项目表格 -->
                    <h4 style="margin-top: 30px; color: var(--secondary-color);">
                        <i class="fas fa-crown"></i> Top 10 高分项目
                    </h4>
                    <div style="overflow-x: auto;">
                        <table class="data-table">
                            <thead>
                                <tr>
                                    <th>排名</th>
                                    <th>项目名称</th>
                                    <th>总分</th>
                                    <th>贡献度</th>
                                    <th>活跃度</th>
                                    <th>发表时间</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% if data_summary.top_projects %}
                                    {% for project in data_summary.top_projects %}
                                    <tr>
                                        <td>{{ loop.index }}</td>
                                        <td>{{ project.repo_name }}</td>
                                        <td><strong>{{ "%.2f"|format(project.总分) }}</strong></td>
                                        <td>{{ "%.2f"|format(project.贡献度得分) }}</td>
                                        <td>{{ "%.2f"|format(project.活跃度得分) }}</td>
                                        <td>{{ project.发表时间 }}</td>
                                    </tr>
                                    {% endfor %}
                                {% else %}
                                    <tr>
                                        <td colspan="6" style="text-align: center; padding: 20px; color: #666;">
                                            暂无数据
                                        </td>
                                    </tr>
                                {% endif %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 页脚 -->
        <div class="footer">
            <p>
                <strong>学术开源项目分析报告</strong><br>
                生成时间: {{ current_time }} | 数据版本: 1.0.0 | 项目数量: {{ stats.total_projects }}
            </p>
            <div class="footer-links">
                <a href="#" onclick="showHelp()"><i class="fas fa-question-circle"></i> 使用帮助</a>
                <a href="#" onclick="showMethodology()"><i class="fas fa-book"></i> 分析方法</a>
                <a href="#" onclick="showAbout()"><i class="fas fa-info-circle"></i> 关于系统</a>
            </div>
        </div>
    </div>
    
    <script>
        // 全局数据
        const appData = {{ data_summary|tojson }};
        const projectData = {{ project_data|tojson }};
        
        // 页面加载完成后隐藏加载动画
        window.addEventListener('load', function() {
            document.getElementById('loader').classList.remove('active');
            
            // 为主时间轴图表添加点击事件
            document.addEventListener('plotly_click', function(data) {
                if (data.points && data.points[0] && data.points[0].customdata) {
                    const paperUrl = data.points[0].customdata[6];
                    if (paperUrl && paperUrl.trim() !== '') {
                        window.open(paperUrl.trim(), '_blank');
                    }
                }
            });
        });
        
        // 搜索功能
        function searchProjects() {
            const searchInput = document.getElementById('searchInput');
            const searchTerm = searchInput.value.trim();
            
            if (!searchTerm) {
                showNotification('请输入搜索关键词', 'warning');
                return;
            }
            
            // 过滤项目数据
            const searchResults = projectData.filter(project => {
                const searchLower = searchTerm.toLowerCase();
                return (
                    (project.repo_name && project.repo_name.toLowerCase().includes(searchLower)) ||
                    (project.github链接 && project.github链接.toLowerCase().includes(searchLower)) ||
                    (project.论文地址 && project.论文地址.toLowerCase().includes(searchLower))
                );
            });
            
            // 显示搜索结果
            const searchResultsDiv = document.getElementById('searchResults');
            const searchResultCount = document.getElementById('searchResultCount');
            const searchResultList = document.getElementById('searchResultList');
            
            searchResultCount.textContent = `搜索结果 (${searchResults.length})`;
            
            if (searchResults.length === 0) {
                searchResultList.innerHTML = `
                    <div class="search-result-item">
                        <div class="result-title">未找到匹配的项目</div>
                        <p>请尝试其他搜索关键词</p>
                    </div>
                `;
            } else {
                let html = '';
                searchResults.forEach((project, index) => {
                    html += `
                        <div class="search-result-item">
                            <div class="result-title">${project.repo_name || '未命名项目'}</div>
                            <div class="result-stats">
                                <div class="stat-item">
                                    <i class="fas fa-star" style="color: ${getColor('warning')};"></i>
                                    <span>总分: ${project.总分 ? project.总分.toFixed(2) : '0.00'}</span>
                                </div>
                                <div class="stat-item">
                                    <i class="fas fa-hand-sparkles" style="color: ${getColor('success')};"></i>
                                    <span>贡献度: ${project.贡献度得分 ? project.贡献度得分.toFixed(2) : '0.00'}</span>
                                </div>
                                <div class="stat-item">
                                    <i class="fas fa-bolt" style="color: ${getColor('danger')};"></i>
                                    <span>活跃度: ${project.活跃度得分 ? project.活跃度得分.toFixed(2) : '0.00'}</span>
                                </div>
                            </div>
                            <div class="result-links">
                                ${project.github链接 ? `<a href="${project.github链接}" target="_blank" class="result-link">
                                    <i class="fab fa-github"></i> GitHub仓库
                                </a>` : ''}
                                ${project.论文地址 ? `<a href="${project.论文地址}" target="_blank" class="result-link">
                                    <i class="fas fa-file-alt"></i> 论文地址
                                </a>` : ''}
                            </div>
                            ${project.发表时间 ? `<div style="margin-top: 8px; font-size: 0.85rem; color: #888;">
                                <i class="fas fa-calendar-alt"></i> 发表时间: ${project.发表时间}
                            </div>` : ''}
                        </div>
                    `;
                });
                searchResultList.innerHTML = html;
            }
            
            searchResultsDiv.classList.add('active');
            showNotification(`找到 ${searchResults.length} 个匹配的项目`, 'success');
        }
        
        // 清空搜索
        function clearSearch() {
            document.getElementById('searchInput').value = '';
            document.getElementById('searchResults').classList.remove('active');
            document.getElementById('searchResultList').innerHTML = '';
            document.getElementById('searchResultCount').textContent = '搜索结果 (0)';
        }
        
        // 获取颜色
        function getColor(type) {
            switch(type) {
                case 'primary': return '{{ primary_color }}';
                case 'secondary': return '{{ secondary_color }}';
                case 'success': return '{{ success_color }}';
                case 'warning': return '{{ warning_color }}';
                case 'danger': return '{{ danger_color }}';
                default: return '{{ primary_color }}';
            }
        }
        
        // 选项卡切换
        function switchTab(tabName) {
            // 更新选项卡样式
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // 激活选中的选项卡
            event.target.closest('.tab').classList.add('active');
            document.getElementById(tabName + 'Tab').classList.add('active');
            
            // 重置图表大小
            setTimeout(() => {
                Plotly.Plots.resize(document.getElementById('plotly-timeline'));
            }, 100);
        }
        
        // 显示通知
        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.className = `notification ${type}`;
            notification.innerHTML = `
                <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
                ${message}
            `;
            
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.style.animation = 'slideOut 0.3s ease-in';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }
        
        // 模态框功能
        function showModal(title, content) {
            document.getElementById('modalTitle').textContent = title;
            document.getElementById('modalContent').innerHTML = content;
            document.getElementById('infoModal').classList.add('active');
        }
        
        function closeModal() {
            document.getElementById('infoModal').classList.remove('active');
        }
        
        // 导出数据功能
        function exportData() {
            try {
                const blob = new Blob([JSON.stringify(appData, null, 2)], {type: 'application/json'});
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'academic_projects_analysis.json';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                showNotification('数据导出成功！', 'success');
            } catch (error) {
                showNotification('导出失败: ' + error.message, 'error');
            }
        }
        
        // 刷新数据
        function refreshData() {
            showNotification('刷新功能需要后端支持，目前为静态页面', 'warning');
        }
        
        // 信息对话框
        function showTimeInfo() {
            const content = `
                <p><strong>时间范围分析：</strong></p>
                <ul>
                    <li>开始时间: ${appData.stats.time_range.start || '无数据'}</li>
                    <li>结束时间: ${appData.stats.time_range.end || '无数据'}</li>
                    <li>总天数: ${appData.stats.time_range.days || 0} 天</li>
                    <li>覆盖周数: ${appData.stats.time_distribution.weeks || 0} 周</li>
                    <li>覆盖月份: ${appData.stats.time_distribution.months || 0} 个月</li>
                </ul>
            `;
            showModal('时间范围信息', content);
        }
        
        function showDataInfo() {
            const content = `
                <p><strong>数据信息：</strong></p>
                <ul>
                    <li>数据版本: 1.0.0</li>
                    <li>生成时间: ${appData.generated_at}</li>
                    <li>总记录数: ${appData.total_records || 0}</li>
                    <li>数据来源: 学术论文数据库 + GitHub仓库评分</li>
                    <li>处理状态: 已完成</li>
                </ul>
                <p style="margin-top: 15px; color: #666; font-size: 0.9rem;">
                    注：所有数据均为聚合分析结果，原始数据已进行脱敏处理。
                </p>
            `;
            showModal('数据信息', content);
        }
        
        function showHelp() {
            const content = `
                <p><strong>使用说明：</strong></p>
                <ol>
                    <li><strong>时间轴分析：</strong>查看项目按发表时间的分布情况</li>
                    <li><strong>统计分析：</strong>查看各种统计图表和分布</li>
                    <li><strong>详细数据：</strong>查看详细的分析报告和Top项目</li>
                </ol>
                <p><strong>交互功能：</strong></p>
                <ul>
                    <li>点击时间轴上的散点可以跳转到论文页面</li>
                    <li>鼠标悬停在图表上可以查看详细信息</li>
                    <li>使用右上角的按钮可以导出数据和刷新</li>
                    <li>点击统计卡片可以查看详细信息</li>
                </ul>
                <p><strong>搜索功能：</strong></p>
                <ul>
                    <li>在顶部搜索框输入关键词搜索项目</li>
                    <li>支持搜索项目名称、GitHub链接、论文地址</li>
                    <li>搜索结果会显示在搜索框下方</li>
                    <li>点击搜索结果中的链接可以直接访问</li>
                </ul>
                <p><strong>快捷键：</strong></p>
                <ul>
                    <li>Ctrl+S: 导出数据</li>
                    <li>F1: 显示帮助</li>
                    <li>Enter: 执行搜索</li>
                    <li>ESC: 关闭模态框</li>
                </ul>
            `;
            showModal('使用帮助', content);
        }
        
        function showMethodology() {
            const content = `
                <p><strong>分析方法说明：</strong></p>
                <p>1. <strong>数据来源：</strong></p>
                <ul>
                    <li>论文数据：从学术数据库获取的论文详情</li>
                    <li>评分数据：基于GitHub仓库的贡献度和活跃度计算</li>
                </ul>
                <p>2. <strong>得分计算：</strong></p>
                <ul>
                    <li>总分 = 贡献度得分 + 活跃度得分</li>
                    <li>活跃度占比 = 活跃度得分 / 总分</li>
                </ul>
                <p>3. <strong>分类标准：</strong></p>
                <ul>
                    <li>高分项目：总分 > 30</li>
                    <li>高贡献项目：贡献度得分 > 5</li>
                    <li>高活跃项目：活跃度占比 > 60%</li>
                </ul>
                <p>4. <strong>时间分析：</strong></p>
                <ul>
                    <li>按周聚合项目发表时间</li>
                    <li>同周内项目按顺序排列</li>
                    <li>气泡大小基于总分（平方根缩放）</li>
                </ul>
            `;
            showModal('分析方法', content);
        }
        
        function showAbout() {
            const content = `
                <p><strong>学术开源项目分析平台 v1.0.0</strong></p>
                <p>功能特点：</p>
                <ul>
                    <li>多维度数据分析</li>
                    <li>交互式时间轴（支持点击跳转）</li>
                    <li>智能项目分类和筛选</li>
                    <li>全文搜索功能</li>
                    <li>数据导出功能</li>
                    <li>响应式设计</li>
                </ul>
                <p>技术栈：</p>
                <ul>
                    <li>前端：HTML5 + CSS3 + JavaScript</li>
                    <li>图表：Plotly.js</li>
                    <li>数据处理：Python + Pandas</li>
                    <li>样式：Font Awesome图标库</li>
                </ul>
                <p style="margin-top: 15px; color: #666; font-size: 0.9rem;">
                    生成时间：${new Date().toLocaleString()}
                </p>
            `;
            showModal('关于系统', content);
        }
        
        // 添加键盘快捷键
        document.addEventListener('keydown', function(e) {
            // Ctrl+S 保存
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                exportData();
            }
            // F1 显示帮助
            if (e.key === 'F1') {
                e.preventDefault();
                showHelp();
            }
            // ESC 关闭模态框
            if (e.key === 'Escape') {
                closeModal();
            }
        });
        
        // 点击模态框外部关闭
        document.getElementById('infoModal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
        
        // 图表自适应
        window.addEventListener('resize', function() {
            const plotDiv = document.querySelector('.js-plotly-plot');
            if (plotDiv) {
                Plotly.Plots.resize(plotDiv);
            }
        });
        
        // 初始化
        console.log('学术开源项目分析平台已加载');
        console.log('统计数据:', appData.stats);
        console.log('项目数据:', projectData.length, '条记录');
    </script>
</body>
</html>
        ''')
        
        # 渲染模板
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html = template.render(
            title="学术开源项目分析报告",
            timeline_chart=pio.to_html(timeline_chart, full_html=False, include_plotlyjs='cdn', div_id='plotly-timeline'),
            stat_charts={
                'distribution': pio.to_html(stat_charts['distribution'], full_html=False, include_plotlyjs=False),
                'scatter': pio.to_html(stat_charts['scatter'], full_html=False, include_plotlyjs=False),
                'trend': pio.to_html(stat_charts['trend'], full_html=False, include_plotlyjs=False),
                'pie': pio.to_html(stat_charts['pie'], full_html=False, include_plotlyjs=False)
            },
            stats=stats,
            data_summary=data_summary,
            project_data=project_data,
            current_time=current_time,
            primary_color=Config.PRIMARY_COLOR,
            secondary_color=Config.SECONDARY_COLOR,
            success_color=Config.SUCCESS_COLOR,
            warning_color=Config.WARNING_COLOR,
            danger_color=Config.DANGER_COLOR,
            chart_height=Config.CHART_HEIGHT
        )
        
        return html

# --- 6. 主程序 ---
def main():
    """主函数"""
    logger = Logger()
    logger.section("学术开源项目分析平台启动")
    
    try:
        # 1. 数据加载
        logger.log("开始加载数据...")
        processor = DataProcessor()
        
        df_papers = processor.safe_read_jsonl(Config.PAPER_FILE_PATH)
        df_scores = processor.safe_read_jsonl(Config.SCORED_FILE_PATH)
        
        if df_papers is None or df_scores is None:
            raise ValueError("数据加载失败")
        
        logger.log(f"论文数据: {len(df_papers)} 条记录")
        logger.log(f"评分数据: {len(df_scores)} 条记录")
        
        # 2. 数据合并与验证
        logger.log("合并数据...")
        df_combined = pd.merge(df_papers, df_scores, on='github链接', how='inner')
        
        required_cols = ['发表时间', '总分', '贡献度得分', '活跃度得分', 'repo_name', 'github链接', '论文地址']
        df_clean = processor.validate_data(df_combined, required_cols)
        logger.log(f"有效数据: {len(df_clean)} 条记录")
        
        # 3. 特征工程
        logger.log("计算衍生特征...")
        df_processed = processor.calculate_derived_features(df_clean)
        
        # 4. 统计分析
        logger.log("执行统计分析...")
        analyzer = StatisticsAnalyzer(df_processed)
        stats = analyzer.calculate_basic_stats()
        data_summary = analyzer.get_summary_for_json()
        
        # 准备搜索数据
        search_data = df_processed[['repo_name', '总分', '贡献度得分', '活跃度得分', 
                                   '发表时间', 'github链接', '论文地址']].copy()
        search_data['发表时间'] = search_data['发表时间'].dt.strftime('%Y-%m-%d')
        project_data = search_data.to_dict('records')
        
        # 保存统计摘要（使用自定义JSON编码器）
        with open(Config.OUTPUT_DATA_JSON, 'w', encoding='utf-8') as f:
            json.dump(data_summary, f, ensure_ascii=False, indent=2, cls=JSONEncoder)
        
        logger.log(f"统计摘要已保存到: {Config.OUTPUT_DATA_JSON}")
        
        # 5. 生成图表
        logger.log("生成可视化图表...")
        chart_gen = ChartGenerator()
        
        timeline_chart = chart_gen.create_timeline_chart(df_processed, stats)
        
        stat_charts = {
            'distribution': chart_gen.create_score_distribution_chart(df_processed),
            'scatter': chart_gen.create_scatter_matrix(df_processed),
            'trend': chart_gen.create_trend_chart(df_processed),
            'pie': chart_gen.create_category_pie_chart(df_processed, stats)
        }
        
        # 6. 生成HTML报告
        logger.log("生成HTML报告...")
        html_gen = HTMLGenerator()
        
        # 准备传递给HTML的数据
        html_data_summary = {
            'top_projects': data_summary['top_projects'],
            'stats': data_summary['stats'],
            'generated_at': data_summary['generated_at'],
            'total_records': data_summary['total_records']
        }
        
        html_content = html_gen.generate_html(
            timeline_chart, 
            stat_charts, 
            data_summary['stats'],
            html_data_summary,
            project_data
        )
        
        with open(Config.OUTPUT_HTML, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # 7. 性能统计
        logger.section("执行完成")
        logger.log(f"✓ 数据记录: {stats['total_projects']} 个项目")
        logger.log(f"✓ 时间范围: {stats['time_range']['days']} 天")
        logger.log(f"✓ 高分项目: {stats['categories']['high_score']} 个")
        logger.log(f"✓ 搜索数据: {len(project_data)} 条记录")
        logger.log(f"✓ 文件生成: {Config.OUTPUT_HTML}")
        logger.log(f"✓ 数据摘要: {Config.OUTPUT_DATA_JSON}")
        logger.log(f"✓ 执行时间: {logger.performance('总耗时')}")
        
        print("\n" + "🎉" * 30)
        print("🎉 分析报告已生成！")
        print("🎉" * 30)
        print("\n📊 打开以下文件查看报告:")
        print(f"   • {os.path.abspath(Config.OUTPUT_HTML)}")
        print(f"   • {os.path.abspath(Config.OUTPUT_DATA_JSON)}")
        
        print("\n📈 关键发现:")
        print(f"   • 平均总分: {stats['score_stats']['total']['mean']:.2f}")
        print(f"   • 高分项目: {stats['categories']['high_score']} 个 ({stats['categories']['high_score']/stats['total_projects']*100:.1f}%)")
        print(f"   • 最活跃月份: {stats['time_distribution']['peak_month'] or '无数据'}")
        
        print("\n🔍 新功能:")
        print("   • 搜索功能：支持按项目名称、GitHub链接、论文地址搜索")
        print("   • 时间轴恢复原始样式：使用Viridis色阶，气泡大小更美观")
        print("   • 点击跳转：双击时间轴上的散点可以跳转到论文页面")
        
        print("\n🔧 功能特性:")
        print("   • 响应式设计，支持手机/平板/电脑")
        print("   • 交互式图表，支持点击跳转")
        print("   • 全文搜索功能，快速定位项目")
        print("   • 数据导出功能 (Ctrl+S)")
        print("   • 详细统计分析和可视化")
        
    except Exception as e:
        logger.log(f"程序执行失败: {str(e)}", "ERROR")
        logger.log(traceback.format_exc(), "DEBUG")
        sys.exit(1)

if __name__ == "__main__":
    main()