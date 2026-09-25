# 旧 gap 批次终态：453 / 500 accepted

固定 solver `923b25ecb0b9d6d0e2d3f149fccef431b5403f99`、runner `9db8247f9a864a3279f3bd315aa09d8ad7dd5206`，原批次7200秒上限未延长。共454格启动，453格accepted；091/k4在整个批次期限末尾独立E0超时，46格未启动。总墙钟7201.783秒，尾部清理1.783秒；不存在存活评分子进程。真实计数：748次native E2/748 attempts，454次独立E0启动，0 fallback与unknown。不能将它作为完整100图×1–5核新成绩，缺口不补历史值、不恢复重计时。

accepted原件已按连续区间001–453归档、推送并enqueue。最终归档分支固定提交为 `6cecdd9f8a15d21a32256b4bb8e61a907cf102d9`；root用ls-remote核对远端，前两段commit均为其祖先，补足其journal无push时间戳的发布证据。enqueue并不证明中央成绩台已经接收。失败格仍保留在原summary及091-k4过程原件，尚未打包为该accepted-only成绩feed。

旧runner在各检查点反复序列化含完整在线ledger的汇总，440格时JSON已353,608,497字节，观察到主进程RSS约2.81GiB。这是工程开销证据，不是已量化的唯一超时原因。新cut-retime批次采用compact summary（标量/路径/哈希），细节留在各格文件；新solver属于独立批次，不混入本次结果。
