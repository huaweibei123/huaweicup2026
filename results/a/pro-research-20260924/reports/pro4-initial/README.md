# Huawei Cup A / Route 4 evidence

先读 `REPORT_ZH.md`。本包是独立研究原型，不是全100例×2–5核×三问的完成验收。

## 内容与证据口径

保留117次成功的未修改官方E0 CLI运行（14个正式case及2次微图运行），另有60个合成图、240次未修改官方E0 API标签。56个唯一方案的Step1/2证书诊断不是56次完整E0。构造超时与Banker拒绝记录没有删除。完整结果和源文件哈希见 `analysis/evidence_inventory.json`、`audit/` 与 `experiments/`。

另有1次交付可移植性E0烟雾测试，不计入117次研究调用；case008方案一致，结果仅input_plan文件名元数据不同。种子固定的CPU训练复跑与原记录所有非计时字段一致，原始训练计时未被替换。

原始测量源码保留在 `audit/measured_source/`。`src/` 仅对路径做可移植调整，差异见 `audit/portability_patch.diff`；新增 `predict_router.py` 使用安全JSON模型权重，CPU已做启动测试，并复现训练质量字段，CUDA/MPS入口尚未实测。历史日志内的 `/mnt/data/...` 是原运行路径，不应手动改写这些证据。

## 准备

实测：Python3.13.5、Linux、CPU。准确依赖版本见 `audit/installed_versions.json`。普通构造/官方评估只需Python标准库；fast构造另需NumPy；训练/推理另需PyTorch和scikit-learn。当前赛事团队环境若锁定Python3.12，须先复核该环境，不把当前Linux3.13结果冒充跨平台零差分。

在本文件所在目录运行：

```bash
python verify_evidence.py
python bootstrap_official.py
```

第一步校验所有交付payload，第二步校验114份官方原件并解压100例JSON。原始JSON不重复放进ZIP，统一来自随包的 `official-cases.zip`。不得改动 `official/code` 和 `official/data/config.txt`。

也可将环境变量 `HUAWEI_OFFICIAL` 指向已有、经过哈希核验的官方目录，其内须包含 `code/` 和 `data/`。

## 生成并官方确认一个结果

```bash
python src/solve_fast.py official/data/case_002.json output_case002.plan.json \
  --cores 4 --problem 2 --budget 60 --work run_case002
```

至多尝试粗归属基线、frontier1和frontierp。`run_case002/solver.json` 保存所有阶段状态及完整内部耗时。最终plan只来自E0已确认结果。`--budget` 是内部软期限：启动、取消与落盘可能使外部墙钟略超限；严格提交环境需外层父进程预留余量并守护已确认基线。本轮最大图实测120.596秒对120秒内部预算，不声称严格120秒硬截止。

默认按最短makespan选中，次要数据搬运指标另报告；不隐藏它。尤其case014的新候选更快但spill显著增多，应同时保留Pareto备选，见 `analysis/pareto_archive.json`。Q1不会启用singleton细化，本轮没有Q1新主算法。

不使用NumPy时可运行相同接口 `src/solve.py`；大图可能来不及生成细化候选而回退基线。

## 独立检查零spill证书

```bash
python src/certify_plan.py official/data/case_002.json output_case002.plan.json
```

只支持经过显式检查的single-producer、边界COPY、singleton计划域；报告的是分桶串行分配峰值，不是物理并发峰值，也不证明Step3/跨核执行图可行。输出unsupported_or_invalid不能理解成“有spill”。

## 复现机制反例和学习小实验

```bash
python src/micro_extendability.py
python src/synthetic.py
python src/train_router.py
python src/predict_router.py official/data/case_008.json --device cpu
```

这些脚本会重写各自实验目录，新运行结果不要和本次冻结数据混为一谈；先复制一份工作目录。合成集按图族分为36训练/12验证/12测试。网络只给候选优先级建议，不是E2，也不绕过官方确认。`--device cuda`/`--device mps` 仅为未来环境提供显式可用性检查，当前没有相应硬件验证。

## 文件导航

`src/core.py`、`fast_construct.py`：非学习构造；`banker.py`：保守安全完成原型及反例。

`experiments/dev_a`、`dev_b`、`dev_c`、`admission_fix`、`holdout`：正式图的小实验。`holdout_a` 是未完成批次保留的前缀，完整留出批次以 `holdout` 为准。开发留出不是队内封存测试。

`experiments/cross_problem`：同方案Q3与Q1实验；`deadline`、`deadline_fast`：包含子进程启动的单实例计时；`synthetic`：原始合成图、各候选计划及240份完整结果。

`analysis/learning`：模型、数据划分、损失配置及全部测试选择；`analysis/certificate_audit.json` 和 `guarded_certificate_audit.json`：56例证书核对；`audit/literature_sources.json`：一手论文、作者代码及官方文档的精确来源。

原始数据/官方代码沿用题目材料权利。本包不包含前三路原回答中尚未取得字节的新证据ZIP，也不包含缺失的旧295份历史完整result.json。
