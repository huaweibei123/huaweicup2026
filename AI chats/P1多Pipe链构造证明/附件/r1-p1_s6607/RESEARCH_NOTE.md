# P1 / 情况A：完整重入链的FIFO阻塞、单切返程错位包与可验证下界

研究身份：s6607 专项；不替代其他P1/P2/P3研究。

固定源码入口：`Vioano/huaweicup2026 @ 161cdb35de11b0d174a5a0ca149aa36657af2abd`。

**本交付没有执行官方solver、E0、E1或E2；没有取得100图ZIP原始字节；没有新报008或全100成绩。** 本地执行的是合成微图上的自有中层模型、两键构造和数学单测。完整调用账见 `experiments/ledger.json`、`experiments/tests_receipt.json`；访问账见 `ACCESS_AND_EXECUTION_MANIFEST.json`。

## 0. 先交代实际读取

全文读到：性能报告、下界说明、component_pack.py、bounded_tasks.py、P1 evaluator、schedule_step1/2/3.py、stub_multicore_cut_and_schedule.py、config、008/k4保存的run.json和plan、official.log。

部分读到：evaluation_validation.py的Task联合判环段；contest_io.py的trace生成段；full500索引前100行。没有核验全部500行。

008/result.json.gz通过GitHub连接器读到前60行base64，只把前32行（1440压缩字节）转入容器，解出12136字节JSON前缀；没有到达GZip EOF，没有验证完整CRC或整个结果文件SHA。前缀原件和解码脚本均保留。trace.json.gz只取得路径及run中的哈希，未读取。

ZIP：只读到15,375,730字节的元信息和Git blob SHA。容器直连DNS失败；web读取返回DisabledError；连接器UTF-8 fetch拒绝ZIP，contents/base64读取返回空content。故008原始张量大小、全部依赖和100图原件均未取得。不能把历史聊天描述冒充本次原图核验。

局部字节核验：config与保存的official.log匹配连接器返回的Git blob SHA；保存的008 plan匹配run记录的SHA-256 `e0855525fe442beeb4eab84a35d564067fe8efde1aed6585eca12303409e44c3`。

## 1. 本轮结论

1. 对真正保留在Task内部、且Step1访问计算块连续的 `M(a) -> V+(b) -> M(c)`，完整链的返程M排在下一链入口M之前。这不只是两条完整链串行：整段V还会堵住本核其他M操作。它允许构造一个普适的“保链阻塞或拆链DDR”析取下界。
2. 可直接生成合法P1方案的一种办法是：只切返程接口，Task内混放“下一批前缀”和“上一批返程”。不能把“相同core上细切很多Task”等同于可流水化；混合相位必须放进同一个Task。
3. 切口必须计完整跨界张量集合，包括skip/bypass的大张量，而非只看紧邻节点的标量输出。共享输入复制、原输出标记也要按官方谓词核算。
4. 增加重叠仍可能变慢。合成微图中，同样增加1000 cycles M/V重叠，小切口模型7002→6207，大切口模型7002→7704。简单代理选择器在大切口上也选错；最终适配器只在保守上界通过时采用，否则回退同一固定算法。
5. 本轮不能证明008已最优、必能改善或能推动五核均值超过3.85。核心待核验项是008是否通过“保留依赖真链”识别、最便宜完整界面的字节/服务量、以及编译后实际内存复用边。

## 2. 真实语义与中层模型

### 2.1 两种图必须分开

令 `G_contract` 是stub用于Task依赖的COPY收缩图；令 `G_retain` 只保留原非COPY直接边和非COPY→原tensor→非COPY边。

P1用前者约束不同Task，但构造Task内部图时删除原COPY，再按边界重建COPY，并非把每条COPY桥的计算依赖都直接保留下来。因此 `G_contract` 上的长链，不自动等于Task内部的同一条长链。

静态反例：`M100 -> x60 -> COPY_IN -> y60 -> V100`。两计算同Task时，重建成 `M100 -> COPY_OUT(x)` 与 `COPY_IN(y) -> V100`；保留依赖关键路径101，而不是200。不得把收缩关键路径200作为普适下界。原型严格快路径拒绝COPY桥。

### 2.2 编译映射与实际运行

一个Task S经过：

`S -> 边界COPY图 -> Step1序列 -> Step2含SPILL的seq_ext -> (执行DAG H_S, 各Pipe FIFO)`。

Step1是确定性reverse DFS。Step2沿序列进行alloc、瞬态容量检查、execute、末次消费free；已有DDR backing时SPILL不一定另写一份。Step3逐Pipe固定使用seq_ext的投影，不能跳过堵住的队首。

Step3的编译过程另外按全局allocation rank发射片上分配，按消费者引用计数释放虚拟容量；容量额度先有VIRGIN额度，释放后的额度带旧读者/写者来源。复用额度时，为全部旧读者补WAR边；死输出则补WAW边。它们进入交给P1的execution_graph。最终多核重放用的是这个图与固定FIFO，不重新执行编译阶段的全局allocation-rank策略。

所以“SPILL=0”“实际驻留峰值很低”都不等于没有复用边，更不等于没有串行约束。

每核仅一个active Task。设前一核内Task为prev，跨核数据前驱集合为P_remote：

`r(S) = max(0, F(prev)+100, max_{P_remote}(F(P)+1000))`，不存在的项略去；还必须等所有数据前驱Task完成。

100与1000不是一概相加。一个Task的最后COPY_OUT、SPILL等没有结束，就不能释放后继。

DDR是全局共享服务池，容量1。每个必要COPY的独占服务量为 `max(1,ceil(bytes/60))`；不得把DDR总量除以K，也不得用 `ceil(总bytes/60)`替代逐COPY取整之和。

### 2.3 三种界

- **普适下界**：只取每个合法计划必需的工作与因果约束，或对互斥计划类别做穷尽析取。
- **固定计划下界**：已经固定S/core/FIFO/MEM后，取 `lambda(S)=LP(H_S + FIFO)`，COPY用独占时长；再在Task联合DAG上叠加100/1000等待取最长路。它只约束该计划。
- **代理**：忽略共享DDR动态、内存补边或收尾开销的预测式，只用于提案，不具有上下界身份。

`audit_compiled_plan.py`提供第二类的只读审计：实际调用冻结编译函数，导出FIFO、MEM边、固定Task最长路径证书，再计算固定计划门控最长路。这个脚本在本环境没有执行。

## 3. 008读到什么，以及不能据此推什么

保存的run：108个8-op计算组件，864 compute ops，4Task；每核M62532、V59292；E0=123060；scheduled COPY 2,654,424 B，partition/spill added均0。历史solver整进程0.04077637498秒、E0进程0.12752787498秒，不是本轮测量。

结果前缀：每Task有560条内存复用边；local Step3 makespan122133；每核L1峰值36864B、UB峰值37056B。首链M4为824–1982；V6..11从1982连续至4178，时长582/150/150/582/150/582，总2196；返程M12为4178–5336；下一链M52从5336开始。

这些证实了所见前缀的串行现象，但前缀没有560条边的端点，更未独立复演全部108链。因此不能给FIFO与MEM编造耗时贡献率，也不能直接对008全图认证以下真链定理。

## 4. 完整重入链的阻塞定理

### 4.1 条件

独立计算组件具有唯一计算拓扑顺序（允许前向skip边），无穿越被删除COPY的计算桥，无组件间共享张量；每链word为 `M(a_i), V_1,...,V_h, M(c_i)`，V总量b_i。考虑一条没有切Task的完整链。要求Step1在当前Task内将它的计算节点作为连续块访问。严格识别器的私人输入/单生产者/无内部输出tap条件保证了所研究形态的这种连续性。

一般复杂DAG不能直接套此条件。

### 4.2 证明

一条完整链i在M FIFO中的两次M之间没有其他M操作。入口A_i结束后，返程C_i成为本链后续M队首；它必须等待中间真实依赖V链。因此从A_i开始到C_i结束的整个区间，其他M操作都不能在本核执行。

这个区间至少有 `ell_i=a_i+b_i+c_i` 长。两条完整链的该区间在同一核上不能重叠，哪怕它们不在同一个Task：同Task由FIFO，不同Task由P1完整释放门控。

对全部计算属于同类链的图，设完整链集合I、拆链集合S，普通M总工作为W_M，则：

`K C >= W_M + sum_{i in I} b_i`。

证明方法是把每条完整链实际M工作换成其整个被独占/阻塞的区间，再加拆链M操作的实际忙时；这些时间集合在每核上互不重叠。内存和DDR等待只可能扩大完整链的阻塞区间，故忽略它们不损害下界。

这比只计算 `sum_{I} ell_i / K` 更强，因为拆开的链仍然必须支付其M工作量。

### 4.3 对008数值的条件性推论

若原图最终通过上述真链识别，则a=c=1158，b=2196，ell=4512。任何保留全部链完整的4核计划，至少一核有27条链，故：

`C >= 27*4512 = 121824`。

123060/121824−1≈1.01458%，而相对当前时长最多能减少约1.00439%。这说明该**受限算法类**已接近其计算下界；不是对允许拆链的P1最优值作认证。原图若不满足保留依赖条件，这个专用界必须撤回。

## 5. 两键构造：单切返程错位包

每链在最后一个M之前切一次：`P_i = M(a)->V+(b)`，`R_i=M(c)`。链整体核归属不变；不进行跨核数据交接。

将每核待切链分为大小q的包B0,...,B(m−1)。发出：

```
T0 = P(B0)
T1 = P(B1) ∪ R(B0)
T2 = P(B2) ∪ R(B1)
...
Tm = R(B(m−1))
```

未切链作为若干完整包在这些Task之前发出。每个原compute op恰好映射到一个上述Task；原COPY不进入mapping。新Task ID只是非负整数标签，原op/tensor IDs与图完全不改。core_schedules写每核的上述Task列表。

### 5.1 联合无环与释放

组件间没有依赖。每条被切链的数据边只可能留在Task内，或从包含P的wave j前进到包含R的wave j+1。同核顺序边也严格向前。所有链片段仍在同一核，因此没有反向跨核边；Task数据边与所有core序边的并图无环。

R(Bj)直到Tj完整结束后才放入下一个Task执行。此时已等待Tj内所有计算和COPY结束，再支付100。并未“提前释放一个已产出的tensor”来偷用P2/P3自由度。

### 5.2 为什么选返程方向

prefix至少含M→V，深于单独的return M；在所声明形态下，Step1先访问prefix计算块，再访问旧return块。固定M顺序成为“新A的批次，旧C的批次”；V顺序为新prefix的V链批次。因此旧C有机会覆盖新V。

相反，切入口得到A与V→C。后者更深，混合Task的Step1可能先访问旧V→C再访问新A；q=1时M FIFO为旧C→新A，旧V又先于旧C，于是旧V、旧C、新A全部串行。两种切法即便搬运字节一样，也不等价。

## 6. 精确理想响应、门控与参数

这里仅考虑已经确定FIFO、共同释放、无动态DDR及额外MEM阻塞的计算模型。

一个混合Task含u条新prefix和v个已释放return，有：

`F(u,v) = max(u*a + v*c, a+b+(u−1)*max(a,b))`，u>0；u=0时F=vc。

前一项是M流A批次再C批次；后一项是二阶段M→V流水的最后V完成时间。两者取max即所有计算结束。证明也可由递推 `A_j=j*a; V_j=max(A_j,V_(j−1))+b` 得到。

等大包q、m包、每核n=mq条链，令mu=max(a,b)、kappa=min(a,b)：

`F0=q*mu+kappa`

`Fq=max(q*(a+c),q*mu+kappa)`

`Cideal=F0+(m−1)*Fq+q*c+m*100`。

这已经把Task完整释放和m次100门控计入，但仍未计DDR和内存补边，所以不叫官方成绩。

若Fq=q*mu+kappa，则 `Cideal=n*mu+q*c+n*(kappa+100)/q`，连续松弛的驻点是 `q*=sqrt(n*(kappa+100)/c)`。

若Fq=q*(a+c)，则 `Cideal=n*(a+c)+q*(mu−a)+kappa+n*100/q`；仅在该分支条件下，驻点为 `sqrt(n*100/(mu−a))`（mu>a）。分支交界也是候选。非整包、DDR、容量会破坏这些“理想参数最优”结论。实现使用保守容量上限和一个解析批量尺度，不把它称为最佳E0包宽，不做E0参数扫描。

原型还允许只切s条链。用一个明确标注的代理：

`G=(q*ell−Fq−100)/q`

`proxy(s)=max((N*ell−G*s)/K, D0+delta*s)`。

交点给出连续s*，最多检查两个邻近包边界及0/N端点，总共最多4个代理值；不是评分搜索。该代理没有全计填充/排空成本，微图B已证实它会选错。

## 7. DDR、容量和保守采用门禁

### 7.1 完整边界计数

对tensor t，P_t是其非COPY生产者所在Task集合，C_t是消费者Task集合，H_t表示原COPY_OUT标记。官方重建实例数：

`N_in(t)=|C_t \ P_t|`

`N_out(t)=sum_{p in P_t} 1[H_t or C_t empty or C_t\{p} nonempty]`。

按每个tensor的size逐项累计bytes和逐COPY取整service。该式不含SPILL；只有证明无SPILL后，才能把它当完整调度COPY量。extra定义遵循官方相对原图COPY量，而不混淆cross_task_traffic。

私有单生产者内部tensor跨一次界，通常新增一写一读，代价2*size和2*ceil(size/60)。已有原输出、共享外部输入、零字节以及多Task消费需要完整谓词，不能一律2*size。

### 7.2 不同于“峰值小”的充分条件

对每个Task、每种片上pos，取这个Task所有不同本地tensor（原DDR转UB）的size总和S_pos，要求S_pos≤capacity_pos。

这是很保守的条件，但能证明Step2无需SPILL；所有首次allocation总量不超过初始VIRGIN额度，所以Step3不用消耗带旧来源的回收额度，也就不生成MEMORY_REUSE边。零byte额度不改变这个论证。条件不是必要条件；超出时只能说该证书失败，不能断言必spill或必失败。

当前源码还有官方Step3与多核事件循环迭代预算的充分检查。真实数值仍须受官方整数/浮点/EPS实现域约束；不宣称对任意大整数输入完成程序级形式验证。

### 7.3 保守包络

最多2K条MTE COPY同时访问DDR。在公平服务的数学语义中，每请求的服务率至少1/(2K)，故独占服务b的COPY可用2K*b+1作为保守延迟包络（+1容纳cycle取整）。

在无MEM复用的充分条件下，用该COPY延迟、固定FIFO和真实100门控计算各核Task最长路总和，得到候选上界Uenv。若：

`Uenv < ceil(N/K)*ell`，

就可在所声明数学/数值条件下证明候选优于任意保全链计划，特别是这个严格形态下的冻结fallback。否则适配器回退同一个bounded_tasks算法，不查询历史best。

这不是“候选一定差”的判据；包络可能过于保守。缺少原图/官方回归时，它也不是对冻结浮点程序的外部形式验证。

## 8. 普适下界一：完整链阻塞或拆链搬运

### 8.1 每条拆链的最低服务代价

在唯一spine上，tensor生产于位置p、最后消费者位于l，则它跨过的所有候选切口恰为p,...,l−1。用差分数组累计每个切口完整跨界集合的服务代价，避免重复计算同tensor的多个消费者。

严格内部tensor没有原输出tap，则 `delta_j=2*sum_{t crosses j} max(1,ceil(size_t/60))`，每链的普适拆链代价 `delta=min_j delta_j`。

一条spine如果从Task A进入B后再回A，就产生A→B→A的Task环；合法方案不允许。因此任何拆链至少存在一个真正的spine边界，必须支付其完整跨界集合的服务。私有内部tensor保证不同链的这些必要服务实例不重复。

### 8.2 同构闭式证书

N条同构链；ell=a+b+c；M普通工作m=a+c；D0为必需外部读写服务；s为拆链条数。每个合法计划都满足：

`C >= ceil((N*m+(N−s)*b)/K)`  （M普通工作+完整链必然阻塞）

`C >= ell*ceil((N−s)/K)`       （完整链计数）

`C >= D0+s*delta`             （必要DDR服务）

所以：

`L_obstruct = min_{s=0..N} max(ceil((N*ell−s*b)/K), ell*ceil((N−s)/K), D0+s*delta)`。

再与普适资源/因果下界取max。

这是普适下界，因为s穷尽每个计划的类别；不是把某个候选的FIFO边强加给所有方案。前两项单调不增、第三项单调不减，二分交叉点及邻居即可精确求min，O(logN)，不是计划搜索。

### 8.3 给定目标T的反证证书

必要拆链数：

`s_min=max(0, ceil((N*ell−K*T)/b), N−K*floor(T/ell))`。

DDR允许的最大拆链数：`s_max=min(N, floor((T−D0)/delta))`（delta>0，且T≥D0；其余情形分开处理）。如果s_min>s_max，T不可达。验证只需读界面证书并检查两个整数不等式。

**008条件性数值门槛**：如果其原图通过严格识别、所报无spill的2,654,424B均对应这类私人必要边界，则D0≥ceil(2654424/60)=44241。取T=62738，s_min=108，即全部108链都必须拆。DDR又要求delta≤171；delta为2倍逐tensor COPY服务和，因此至少须存在服务和≤85、合计bytes≤5100B的完整切口。大于5100B就不可能在这组条件下达到62738。

同理T=90000要求至少切58链，并要求最低界面合计bytes≤23640B。这是必要条件；并未从008原图测得该界面，也不是存在这样的界面就能达到目标。

### 8.4 异构的可验证松弛

设W_M为全部普通M工作，b_i为完整链造成的M阻塞量，delta_i为每链拆分最低DDR服务。任取alpha∈[0,1]：

`C >= alpha*W_M/K + (1−alpha)*D0 + sum_i min(alpha*b_i/K,(1−alpha)*delta_i)`。

证明：对实际拆链集合，把M阻塞界和DDR界作凸组合，再逐链取较小项只会降低右侧。函数是凹分段线性的，折点 `alpha_i=K*delta_i/(b_i+K*delta_i)`；排序扫描可在O(N logN)个算术操作内求最大值。交付保存有理数alpha，验证无需相信优化器，只需代入式子。自动图识别器当前限同构；异构接口接受已认证的b_i、delta_i。

## 9. 普适下界二：双阈值资源窗口，O(n logn)

从G_retain和官方必要边界谓词构造每个资源上的必要job `(r_i,d_i,q_i)`。r_i为必然释放下界，q_i为执行完后的必然后续时长。普通op用max(1,cycles)；必要输入COPY选一项必需读实例，q取消费者的最大必要尾部；输出相应取最大必要释放的生产者实例。不同tensor选择不同服务实例。完整定义与已读Q1_LOWER_BOUNDS.md一致，不加入候选FIFO。

对资源容量c（Pipe为K，DDR为1），任取阈值r*,q*和非空集合S={i:r_i≥r*,q_i≥q*}：

`C >= r*+q*+ceil(sum_{i in S}d_i/c)`。

证明：S全部必需工作必须落在[r*,C−q*]，区间服务总容量为c(C−r*−q*)。DDR可抢占/公平共享也不影响该工作守恒式。

算法：q坐标压缩；叶值初始为c*q；按r从大到小激活job；激活(r,d,q_i)时，对所有q_threshold≤q_i的叶子做前缀+d；查询最大值，然后加当前r并除c向上取整。只查询q_threshold≤已激活最大q，否则会误把空集合当证书。每job一次前缀更新，O(J logJ)。

证书包括resource、r*、q*、入选数量、sum d、c与下界。独立验证扫描job列表重算集合与和，O(J)；从原图重建job另需图解析、拓扑、输入输出谓词核验，不能忽略这一成本。现有验证器在job优化部分使用独立线性核验，但解析/必要job生成与计算器复用同一实现，并非外部形式验证。

小例：一个(0,1,0)，两个(100,100,100)，c=1。工作量界201，逐job因果界300；窗口挑后两项得到400。交付实际测试了这个例子，并用1200个随机小资源集合/容量组合与朴素所有阈值枚举对照。

若某个已核验原图的合法E0成绩U与普适证书L相等，才能认证最优；若只U/L接近1，则报告差距上界。现在没有100图原始字节和逐行完整成绩核验，故本交付不认证其中任何具体官方图已最优。

## 10. 已执行微实验与失败场景

输入均为自造JSON；官方config字节不变。a=c=1000，b=1500，两独立链，K=1；私人输入/输出各60B。没有改动官方数据，亦没有把这些输入冒充官方case008。

| 微图 / 模式 | Task | 自有模型cycles | M/V重叠 | partition extra B |
|---|---:|---:|---:|---:|
| A 60B返程接口 / 完整同Task | 1 | 7002 | 0 | 0 |
| A / 返程错位 | 3 | 6207 | 1000 | 240 |
| A / 入口错位 | 3 | 7206 | 0 | 240 |
| A / 完整链各自Task | 2 | 7104 | 0 | 0 |
| A / auto代理候选 | 3 | 6207 | 1000 | 240 |
| B 30000B返程接口 / 完整同Task | 1 | 7002 | 0 | 0 |
| B / 返程错位 | 3 | 7704 | 1000 | 120000 |
| B / auto代理候选 | 3 | 7704 | 1000 | 120000 |

这些模型实例中，“所有本地tensor总量≤容量”与“独占COPY模型的DDR区间互不重叠”都通过。因而是所声明数学语义的精确预言，但**未用官方E0回归确认，不能写进官方成绩栏**。

B证明了代理会选错。A的保守上界6221小于保链计算下界7000，采用门禁通过；B的包络9215不满足门禁，最终适配器应回退。单测已验证这两条分支。没有通过门禁不表示不存在更好的合法拆法。

C是一个skip微图：M产出30000B大张量，reduce产出60B标量，normalize同时读二者。切在reduce后，完整界面30060B，额外60120B，不是只搬60B标量的120B。此项只做静态边界计数，结果见C-interface.json。

调用预算与实账：8个自有原型CLI子进程，单进程10秒超时上限，全部退出0，无重试；外层从创建子进程前到退出后测时，覆盖启动、导入、读图、构造、模型计算、方案fsync发布、诊断落盘和退出。范围0.61402–0.69830秒，中位0.64742秒，不能与他机官方solver墙钟等同比较。平台Python3.13.5/Linux x86_64，单worker，未清cache，宿主机是否独占未知。

数学/模型单测15项运行两次，均通过。每轮含1200组窗口界vs朴素枚举、400组拆链数界vs全枚举、100组异构有理对偶、32个等包响应和75个不等包响应、600个结构plan等。它们是小对象正确性对照，不是对官方参数做暴力评分搜索。第二轮对应最终迭代预算保护版本；完整日志与代码版本分别保存。

### 尚未执行的最小官方预算

第一组：A的whole/return/entry三个计划，3E0，检验模型预言与方向性。

第二组：B的whole/return及C的切口计划，3E0，检验“重叠增加仍变慢”和完整界面计数。

第三组：取到匹配SHA的008原图后，先识别并导出实际编译约束，再只比较K4旧完整方案与一个固定构造候选，2E0。前三组总上限8E0，1worker，每次60秒上限，首次身份不匹配、非法计划或理论断言反例即停，不自动扫q/s，不启动全100。K5与其他同族图不在这份最小预算内。

以上只是建议的后续预算，本会话实际官方调用仍是0。

## 11. 代码、复杂度与复现入口

`p1_phase_cut.py`：构造、识别、COPY计数、无MEM充分条件、中层模型、保守采用门禁。这个模块不是官方评估器。默认CLI的auto输出候选，不等于已采用；部署请用下述适配器。

`integrate_frozen.py`：对本地冻结checkout做Git blob/config身份检查，调用严格候选和固定bounded fallback，最后用官方derive/validate_task_order校验两键plan。未在本环境执行。

`audit_compiled_plan.py`：读原图与两键plan，调用冻结编译器，导出实际FIFO和MEM边及固定计划下界；未执行，不等同E0。

`lower_bounds_extensions.py`：普适必要job、O(nlogn)双阈值窗口、线性见证核验、O(logN)同构阻塞/切分界、O(NlogN)异构有理对偶。

在严格单生产者/私人spine形态，若m按展开后的op依赖及tensor incidence计，核心分包、切口差分和模型最长路为O((n+m)log(n+m))级；通用结构校验器还包含最近eligible COPY收缩，显式最坏附加O(nX)，X为原COPY数。交付没有把该通用校验器偷偷算成严格线性。固定h的同构链族不做指数分区或FIFO搜索。双阈值界的O(JlogJ)是job已构造后的复杂度，原二部图多生产者×多消费者展开另计。

```
# 当前包内的合成微图构造与中层预测；换一个输出目录以免覆盖原件。
python -B p1_phase_cut.py experiments/inputs/A-small-interface.json \
  --cores 1 --config original/config.txt --mode return-cut --packet 1 \
  --output NEW_plan.json --diagnostics NEW_model.json

# 原型单测，不调用官方代码。
python -B test_research.py

# 在用户本机的冻结checkout接入唯一固定fallback；本会话未执行。
python -B integrate_frozen.py INPUT_GRAPH.json --repo /path/to/frozen-checkout \
  --cores 4 --output NEW_plan.json --diagnostics NEW_diagnostics.json

# 仅编译审计，不能把输出当普适下界。
python -B audit_compiled_plan.py INPUT_GRAPH.json NEW_plan.json \
  --repo /path/to/frozen-checkout --output NEW_compiled_audit.json

# 最终质量必须由未修改E0裁决。
python -B /path/to/frozen-checkout/data/raw/a/official/code/multicore_cut_evaluate_problem_1.py \
  INPUT_GRAPH.json NEW_plan.json \
  --config /path/to/frozen-checkout/data/raw/a/official/data/config.txt \
  --output NEW_E0.json --trace-output NEW_trace.json --log-output NEW_official.log
```

E0命令没有在本会话执行。所有NEW路径均应指向新实验目录。whole500性能均值、旧历史best以及其它研究人员的051/016/024、048/071/044实验都未被本轮改写或混入。
