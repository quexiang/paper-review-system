"""期刊推荐引擎 — 根据论文内容智能匹配最合适的投稿期刊"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════════
# 期刊数据库（50+ 期刊/会议，含中英文，覆盖CS/AI/NLP/科学计量等方向）
# ═══════════════════════════════════════════════════════════════════

JOURNAL_DB: list[dict] = [
    # ── NLP / AI 顶会 ──
    {"name": "ACL (Annual Meeting of the ACL)", "level": "CCF-A", "type": "conference",
     "scope": ["NLP", "计算语言学", "文本生成", "语义分析", "大语言模型"],
     "if": "", "accept_rate": "~22%", "review_cycle": "3-4个月",
     "desc": "NLP领域最顶级会议，征稿覆盖大语言模型、文本分析、语义理解等前沿方向。"},
    {"name": "EMNLP (Empirical Methods in NLP)", "level": "CCF-B", "type": "conference",
     "scope": ["NLP", "实证研究", "文本挖掘", "信息抽取", "NLP系统评估"],
     "if": "", "accept_rate": "~25%", "review_cycle": "3-4个月",
     "desc": "聚焦NLP实证方法与系统评估，对应用型论文友好，审稿周期适中。"},
    {"name": "NeurIPS (Neural Information Processing Systems)", "level": "CCF-A", "type": "conference",
     "scope": ["机器学习", "深度学习", "大语言模型", "AI应用", "优化算法"],
     "if": "", "accept_rate": "~26%", "review_cycle": "4-5个月",
     "desc": "机器学习顶会，近年LLM相关论文占比高，要求方法创新性突出。"},
    {"name": "ICLR (International Conference on Learning Representations)", "level": "CCF-A", "type": "conference",
     "scope": ["表征学习", "深度学习", "大模型训练", "模型评估", "迁移学习"],
     "if": "", "accept_rate": "~31%", "review_cycle": "4-5个月",
     "desc": "深度学习领域顶会，对模型设计与训练方法类论文接受度较高。"},
    {"name": "AAAI (AAAI Conference on AI)", "level": "CCF-A", "type": "conference",
     "scope": ["人工智能", "机器学习", "NLP", "计算机视觉", "AI应用系统"],
     "if": "", "accept_rate": "~22%", "review_cycle": "4个月",
     "desc": "AI综合顶会，覆盖范围广，对AI+领域应用的跨学科研究包容性强。"},
    {"name": "NAACL (North American Chapter of the ACL)", "level": "CCF-B", "type": "conference",
     "scope": ["NLP", "计算语言学", "文本分析", "对话系统", "NLP应用"],
     "if": "", "accept_rate": "~28%", "review_cycle": "3-4个月",
     "desc": "NLP三大顶会之一，论文接受率略高于ACL，适合有一定创新但非颠覆性的工作。"},
    {"name": "COLING (Intl. Conf. on Computational Linguistics)", "level": "CCF-B", "type": "conference",
     "scope": ["计算语言学", "NLP", "机器翻译", "文本挖掘", "语言资源"],
     "if": "", "accept_rate": "~30%", "review_cycle": "3-4个月",
     "desc": "计算语言学传统顶会，对NLP应用系统接受度高，审稿较ACL温和。"},

    # ── 信息科学 / 学术出版 ──
    {"name": "Scientometrics", "level": "SCI Q1", "type": "journal",
     "scope": ["科学计量学", "学术评价", "同行评议", "引用分析", "科研政策"],
     "if": "2.9", "accept_rate": "~30%", "review_cycle": "2-4个月",
     "desc": "科学计量学权威期刊，核心征稿范围为学术评价方法、同行评议研究，与审稿系统主题完美契合。"},
    {"name": "JASIST (J. Assoc. Inf. Sci. Technol.)", "level": "SCI Q1", "type": "journal",
     "scope": ["信息科学", "学术出版", "文本挖掘", "信息检索", "知识组织"],
     "if": "3.5", "accept_rate": "~25%", "review_cycle": "3-5个月",
     "desc": "信息科学顶刊，长期关注学术出版自动化、文本挖掘在学术评价中的应用。"},
    {"name": "Journal of Informetrics", "level": "SCI Q1", "type": "journal",
     "scope": ["信息计量学", "科学评价", "引用分析", "科研指标", "学术影响力"],
     "if": "3.2", "accept_rate": "~28%", "review_cycle": "2-4个月",
     "desc": "信息计量学顶刊，关注学术评价量化方法与指标研究。"},
    {"name": "Quantitative Science Studies", "level": "SCI Q1", "type": "journal",
     "scope": ["科学学", "定量分析", "研究方法论", "科学评价", "科研大数据"],
     "if": "3.8", "accept_rate": "~25%", "review_cycle": "2-3个月",
     "desc": "定量科学方法期刊，聚焦科学评价量化指标与方法论。"},
    {"name": "Research Policy", "level": "SCI Q1", "type": "journal",
     "scope": ["科研政策", "创新管理", "学术评价", "科技治理", "R&D管理"],
     "if": "8.1", "accept_rate": "~15%", "review_cycle": "4-6个月",
     "desc": "科研政策领域顶刊，对学术评价工具创新研究有很高接受度，IF高达8.1。"},
    {"name": "PLOS ONE", "level": "SCI Q2", "type": "journal",
     "scope": ["多学科", "方法论", "实证研究", "数据分析", "开放科学"],
     "if": "2.9", "accept_rate": "~50%", "review_cycle": "1-3个月",
     "desc": "最大综合性OA期刊之一，覆盖所有学科，审稿快速，对方法类研究包容性强。"},
    {"name": "Scientific Reports", "level": "SCI Q2", "type": "journal",
     "scope": ["多学科", "自然科学研究", "方法论", "数据驱动研究"],
     "if": "3.8", "accept_rate": "~48%", "review_cycle": "1-2个月",
     "desc": "Nature子刊，覆盖面广，对严谨的实验方法论研究接受度高。"},
    {"name": "PeerJ", "level": "SCI Q2", "type": "journal",
     "scope": ["生命科学", "环境科学", "计算机科学", "方法论"],
     "if": "2.7", "accept_rate": "~55%", "review_cycle": "1-2个月",
     "desc": "以审稿效率和透明度著称的OA期刊，适合方法创新和实验验证类论文。"},
    {"name": "PeerJ Computer Science", "level": "SCI Q2", "type": "journal",
     "scope": ["计算机科学", "AI应用", "数据科学", "软件工程"],
     "if": "2.5", "accept_rate": "~50%", "review_cycle": "1-2个月",
     "desc": "计算机科学OA期刊，对AI应用系统论文友好，发表门槛适中。"},
    {"name": "Learned Publishing", "level": "SCI Q2 / SSCI Q2", "type": "journal",
     "scope": ["学术出版", "同行评议", "期刊管理", "学术交流", "出版伦理"],
     "if": "2.2", "accept_rate": "~35%", "review_cycle": "2-3个月",
     "desc": "学术出版领域核心期刊，专注同行评议创新与出版流程优化。"},

    # ── 计算机应用 / AI应用 ──
    {"name": "Expert Systems with Applications", "level": "SCI Q1", "type": "journal",
     "scope": ["专家系统", "AI应用", "知识工程", "决策支持", "智能系统"],
     "if": "8.5", "accept_rate": "~18%", "review_cycle": "2-3个月",
     "desc": "AI应用顶刊，IF高，对实际系统设计与评估类论文友好，审稿效率高。"},
    {"name": "Information Processing & Management", "level": "SCI Q1 / CCF-B", "type": "journal",
     "scope": ["信息处理", "文本挖掘", "NLP应用", "信息检索", "知识管理"],
     "if": "8.6", "accept_rate": "~20%", "review_cycle": "2-4个月",
     "desc": "信息处理顶刊，关注NLP与AI技术在信息管理中的实际应用。"},
    {"name": "Knowledge-Based Systems", "level": "SCI Q1", "type": "journal",
     "scope": ["知识系统", "机器学习", "数据挖掘", "推荐系统", "NLP"],
     "if": "7.2", "accept_rate": "~22%", "review_cycle": "2-3个月",
     "desc": "知识系统顶刊，对AI驱动的方法创新和应用系统接受度良好。"},
    {"name": "Neurocomputing", "level": "SCI Q1", "type": "journal",
     "scope": ["神经网络", "深度学习", "模式识别", "NLP", "AI系统"],
     "if": "6.0", "accept_rate": "~30%", "review_cycle": "2-3个月",
     "desc": "神经网络与计算智能期刊，审稿较快，对AI应用类论文友好。"},
    {"name": "Applied Soft Computing", "level": "SCI Q1", "type": "journal",
     "scope": ["软计算", "模糊系统", "进化算法", "智能系统", "AI应用"],
     "if": "7.2", "accept_rate": "~25%", "review_cycle": "2-4个月",
     "desc": "应用软计算期刊，对智能系统设计与评估类论文有较好接受度。"},
    {"name": "Engineering Applications of AI", "level": "SCI Q1", "type": "journal",
     "scope": ["AI工程应用", "智能系统", "自动化", "NLP系统", "AI评估"],
     "if": "7.5", "accept_rate": "~22%", "review_cycle": "2-3个月",
     "desc": "AI工程应用顶刊，关注AI系统实际部署与效果评估。"},
    {"name": "Computers & Education", "level": "SCI Q1 / SSCI Q1", "type": "journal",
     "scope": ["教育技术", "AI教育", "学术写作", "自动化评价", "教育数据挖掘"],
     "if": "12.0", "accept_rate": "~12%", "review_cycle": "3-5个月",
     "desc": "教育技术顶刊，IF极高，对AI驱动的学术写作与评价工具有较高关注。"},
    {"name": "Journal of Academic Librarianship", "level": "SCI Q3", "type": "journal",
     "scope": ["学术图书馆", "信息素养", "学术出版", "科研支持", "学术交流"],
     "if": "1.5", "accept_rate": "~45%", "review_cycle": "2-3个月",
     "desc": "学术图书馆学期刊，对学术出版创新和科研支持工具类论文友好。"},

    # ── 计算机综合 ──
    {"name": "ACM Computing Surveys", "level": "SCI Q1", "type": "journal",
     "scope": ["计算机综述", "AI综述", "NLP综述", "系统综述", "方法综述"],
     "if": "16.6", "accept_rate": "~10%", "review_cycle": "3-6个月",
     "desc": "计算机综述顶刊，影响因子极高，适合系统性综述类论文。"},
    {"name": "IEEE T-PAMI", "level": "SCI Q1 / CCF-A", "type": "journal",
     "scope": ["模式识别", "机器学习", "计算机视觉", "深度学习", "AI理论"],
     "if": "24.3", "accept_rate": "~12%", "review_cycle": "4-8个月",
     "desc": "人工智能与模式识别顶刊，适合有严格理论推导和实验验证的论文。"},
    {"name": "IEEE Access", "level": "SCI Q2", "type": "journal",
     "scope": ["电子工程", "计算机科学", "AI应用", "多学科"],
     "if": "3.4", "accept_rate": "~40%", "review_cycle": "1-2个月",
     "desc": "IEEE OA期刊，审稿极快，发表门槛适中，适合快速发表应用型研究。"},
    {"name": "Journal of Supercomputing", "level": "SCI Q2", "type": "journal",
     "scope": ["高性能计算", "分布式系统", "AI系统", "大数据处理"],
     "if": "2.5", "accept_rate": "~35%", "review_cycle": "2-3个月",
     "desc": "超级计算期刊，对涉及大规模数据处理和系统效率的论文有偏好。"},

    # ── 中文期刊 ──
    {"name": "中文信息学报 (J. of Chinese Information Processing)", "level": "CCF-B / 北大核心", "type": "journal",
     "scope": ["中文NLP", "计算语言学", "文本挖掘", "信息检索", "语言资源"],
     "if": "1.8", "accept_rate": "~30%", "review_cycle": "2-4个月",
     "desc": "中文信息处理领域权威期刊，关注中文NLP与文本分析技术创新。"},
    {"name": "计算机学报 (Chinese Journal of Computers)", "level": "CCF-A / 北大核心", "type": "journal",
     "scope": ["计算机科学", "AI", "体系结构", "软件工程", "算法理论"],
     "if": "3.2", "accept_rate": "~15%", "review_cycle": "3-6个月",
     "desc": "中国计算机领域顶刊，对AI方向的原创性研究论文有高要求。"},
    {"name": "软件学报 (Journal of Software)", "level": "CCF-A / 北大核心", "type": "journal",
     "scope": ["软件工程", "AI", "NLP", "知识工程", "系统软件"],
     "if": "2.8", "accept_rate": "~18%", "review_cycle": "3-5个月",
     "desc": "中国软件领域顶刊，对AI系统架构与工程实践类论文有较好接受度。"},
    {"name": "情报学报 (Journal of the China Society for S&T Info)", "level": "CSSCI / 北大核心", "type": "journal",
     "scope": ["情报学", "信息分析", "学术评价", "知识管理", "科学计量"],
     "if": "2.5", "accept_rate": "~25%", "review_cycle": "2-4个月",
     "desc": "中国情报学顶刊，关注信息分析方法创新，与审稿评价主题契合。"},
    {"name": "图书情报工作 (Library and Information Service)", "level": "CSSCI / 北大核心", "type": "journal",
     "scope": ["图书情报", "信息管理", "学术出版", "知识服务", "科研评价"],
     "if": "2.1", "accept_rate": "~30%", "review_cycle": "1-3个月",
     "desc": "中国图书情报学核心期刊，审稿快，对学术出版创新类论文友好。"},
    {"name": "中国图书馆学报 (J. of Library Science in China)", "level": "CSSCI / 北大核心", "type": "journal",
     "scope": ["图书馆学", "学术交流", "信息组织", "知识管理", "数字出版"],
     "if": "3.5", "accept_rate": "~15%", "review_cycle": "3-5个月",
     "desc": "中国图书馆学顶刊，对学术交流模式创新研究有较高关注。"},
    {"name": "现代情报 (Journal of Modern Information)", "level": "CSSCI / 北大核心", "type": "journal",
     "scope": ["情报学", "信息分析", "数据科学", "知识管理", "信息服务"],
     "if": "1.8", "accept_rate": "~35%", "review_cycle": "1-2个月",
     "desc": "中国情报学重要期刊，审稿快，对信息分析方法与应用类论文友好。"},
]


def recommend_journals(
    text: str,
    overall_score: float = 60,
    exclude: list[str] | None = None,
    limit: int = 10,
) -> list[dict]:
    """根据论文内容 + 评分，智能推荐最佳投稿期刊

    Args:
        text: 论文全文
        overall_score: 论文质量评分 (0-100)
        exclude: 需要排除的期刊名列表
        limit: 返回数量 (default 5)

    Returns:
        [{name, level, match, reason, if, accept_rate, review_cycle}]
    """
    tl = text.lower()
    exclude = exclude or []

    # ── 计算每本期刊的匹配度 ────────────────────────
    scored: list[tuple[float, dict]] = []

    for j in JOURNAL_DB:
        if j["name"] in exclude:
            continue

        # 1. 主题匹配度 (50分) — 论文关键词命中期刊scope
        keyword_hits = sum(1 for kw in j["scope"] if kw.lower() in tl)
        keyword_score = min(50, keyword_hits * 12.5)  # 4 hits = 50分

        # 2. 质量适配度 (25分) — 评分与期刊级别匹配
        level_rank = 0
        lvl = j["level"]
        if "CCF-A" in lvl or ("SCI Q1" in lvl and "Q2" not in lvl) or "ABS 4" in lvl:
            level_rank = 1
        elif "CCF-B" in lvl or "SCI Q2" in lvl or "CSSCI" in lvl:
            level_rank = 2
        else:
            level_rank = 3

        if overall_score >= 75:
            quality_score = 25 if level_rank <= 2 else 15
        elif overall_score >= 55:
            quality_score = 25 if level_rank == 2 else (20 if level_rank == 3 else 18)
        else:
            quality_score = 25 if level_rank >= 2 else 15
        quality_score = min(25, quality_score)

        # 3. 创新性匹配 (15分) — 检测论文中的创新关键词
        innovation_kw = ['novel', 'new method', 'propose', 'first', 'outperform',
                         '创新', '提出', '首次', '突破', 'state-of-the-art', 'sota']
        innov_hits = sum(1 for kw in innovation_kw if kw in tl)
        innovation_score = min(15, innov_hits * 3)

        # 4. 实证性匹配 (10分) — 检测实验和数据证据
        empirical_kw = ['experiment', 'result', 'accuracy', 'f1', 'baseline',
                        '实验', '结果', '准确率', '数据', 'evaluate']
        empir_hits = sum(1 for kw in empirical_kw if kw in tl)
        empirical_score = min(10, empir_hits * 2)

        total = keyword_score + quality_score + innovation_score + empirical_score
        scored.append((total, j))

    # ── 排序：取 Top N ─────────────────────────────
    scored.sort(key=lambda x: x[0], reverse=True)

    result = []
    for total, j in scored[:limit]:
        # 生成具体的匹配理由
        matched_scope = [s for s in j["scope"] if s.lower() in tl]

        if matched_scope:
            reason = f"论文涉及{matched_scope[0]}领域，与{j['name'].split("(")[0].strip()}的征稿方向直接契合。" + (f" 期刊级别 {j['level']}，与稿件质量水平（{overall_score:.0f}分）" + ("高度" if overall_score >= 75 else "较为" if overall_score >= 55 else "基本") + "匹配。" if overall_score else "。")
        else:
            reason = j["desc"]

        result.append({
            "name": j["name"],
            "level": j["level"],
            "match": f"{total:.0f}%",
            "reason": reason,
            "if": j["if"],
            "accept_rate": j["accept_rate"],
            "review_cycle": j["review_cycle"],
        })

    return result
