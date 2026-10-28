# A–B–C Multi-Agent Review / 三 Agent 充分性·必要性审查 MVP

## 目标与逻辑

- A Orchestrator 总调度：整合 B、C 的独立报告，提出建议和补证实验。程序负责确定性调度与规则决策。
- B Sufficiency 充分性：方案 X 是否足以实现目标 Y？理论形式 `X => Y`。
- C Necessity 必要性：目标 Y 是否必须依赖特定方案 X？理论形式 `Y => X`。特别要求审查替代方案和反事实。

**非常重要**：本工具是实务条件审查，不是数学形式化证明。AI 的“通过”不能替代实测证据。非必要不等于没有商业价值；一个可替代方案仍可能有价格、服务或集成优势。

## 运行环境

Python 3.10+，OpenAI API key（单独计费）；需网络访问 OpenAI API。

```bash
cd ABC_Agents_MVP
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
export OPENAI_API_KEY="your-key"       # Windows PowerShell: $env:OPENAI_API_KEY="your-key"
python abc_agents.py --input example_input.json --output review.json
# 可选，开启第二轮 B/C 交叉质询（调用次数更多）：
python abc_agents.py --input example_input.json --output review_debate.json --cross-examine
```

可选设置模型：`export ABC_AGENTS_MODEL=gpt-4.1-mini`。

## 输入与输出

编辑 `example_input.json`，把目标 Y、方案 X、成功标准、证据、限制条件补全。每条证据最好包含：证据ID、日期、源文件/URL、可信程度、确切数字。

输出 `review.json` 包含：

- `B_sufficiency`: 充分性判断、证据、反例、缺口、验证实验
- `C_necessity`: 必要性判断、替代方案、反事实、缺口
- `deterministic_decision`: 由程序根据两项结果生成，不能被 A 改写
- `A_orchestrator`: 综合风险、分歧、按优先级排序的下一步实验

## 确定性调度

```text
Input X/Y/evidence
  -> B, C 并发独立审查 (asyncio.gather)
  -> [可选] B, C 交叉质询，保留首轮报告
  -> 程序规则引擎 (policy.decide)
  -> A 综合两份报告
  -> JSON 审查报告
```

这套调度确保 B 和 C 都运行，避免只靠自然语言 prompt 让 A 自己决定是否叫 B、C。

## 验证

无需 API key 的规则引擎单元测试：

```bash
python -m unittest discover -s tests -v
python -m py_compile abc_agents.py policy.py
```

真实 API 联调需自备 API key；本仓库没有伪造运行结果。

## 上线前的改造建议

1. 增加证据库（文件/网页检索、来源可信度、时效、引用ID），让 B、C 都只能引用可回溯证据。
2. 针对数值KPI增加确定性计算模块（Python/SQL），避免直接由 LLM 计算。
3. 对法律、采购、资金或个人数据相关任务加入人工批准，审查通过不触发自动付款/提交。
4. 加入审计日志、访问权限、成本预算、失败重试、模型输出评估基准和版本追踪。
5. 可加入固定两轮审查：第一次发现缺口后由用户/数据检索补证，第二次重新运行 B、C；不能让 Agent 自动虚构补证。
6. 真实因果“必要/充分”最好用消融测试、对照组、反事实数据与形式化规则验证，而不是用语言模型的置信度打分。
