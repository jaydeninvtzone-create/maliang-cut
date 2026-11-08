# 计划合同 v2

根字段：`version:2`, `name`（ASCII 字母数字下划线短横线）、`canvas`（width,height,fps）、`clips`、可选 `captions`。
每个 clip：`id`, `source`（相对 plan.json 的授权文件路径）, `in`,`out`（源时间秒）, `at`（目标开始秒）, `speed`（0.5至2）, `volume`（0至2）, `track`（默认main）, `spoken`（是否真人口播）, `purpose`,`method`,`reason`（非空）, `transform`（可选 scale_x/scale_y/transform_x/transform_y/rotation/alpha）。
主轨从0连续排列；同轨不得重叠。叠加画面另用track，默认原音音量不可暗中置零。速度变化必须由语义和用户目的支持。
每个 caption：`text`,`at`,`duration`，可选size（默认8）、y（默认-0.8），坐标是剪映原生单位，非像素。字幕时间为剪完后时间；代码不会猜测ASR或字级卡点。

`build` 支持裁切源时段、速度、保留原音、独立视频层、静态位置/缩放/旋转/透明度、可编辑字幕。蒙版/资源特效由当前宿主在剪映实现并记录；本版本不谎称所有效果都可脚本化。
`preview` 仅支持单main轨、默认位置、无字幕的粗剪预览。它明确拒绝不能一致呈现的计划。
`verify` 输出技术证据，仍需完整正常速度音画检查。

所有命令 `--help` 可查看参数。输出路径不得包含已有文件。源文件必须在 `--media-root` 中；拒绝符号链接越界。不要为方便把整个磁盘设为素材根。

每个clip增加 `decision`：`route`为native/external；`verification`写本镜头实际需要的检查动作；`alternatives`列有意义的备选及tradeoff。简单直切无需制造第二方案，可留空数组并用`comparison_not_needed`说明原因。外部方法需`native_gap`写明原生为何不满足。本包validate/build共同检查，缺少字段或空值会拒绝生成草稿；机器只能检查结构，不能自动判断理由的审美质量。

示例：`"decision":{"route":"native","alternatives":[],"comparison_not_needed":"本句只需保留原片反应，无需额外效果","verification":"正常速度听切点，确认词尾完整、表情未被截断"}`。

build回执绑定每个片段ID、选择理由、实际速度/音量/变换参数，视觉验收初始为PENDING。旧v1计划需重新看该镜头后补decision并改为v2；不自动给全部镜头套同一比较理由。

## 关键帧动作（0.2.0）
clip可带keyframes，支持uniform_scale、position_x、position_y、rotation、alpha，每项至少两个{time,value}点。time为变速后的片段局部秒，从0开始严格递增，不超过片段长度；不是源时间或全片时间。位置是剪映单位，非像素。
例如：`"keyframes":{"uniform_scale":[{"time":0,"value":1},{"time":0.6,"value":1.18},{"time":2,"value":1.18}]}`表示推近后停留，不自动添加缓动。不将此例套用所有镜头。uniform_scale要求初始X/Y缩放相等。build写入原生数据并记录参数；preview明确拒绝此类计划。新增映射尚未通过原生播放观感验收。

## 内置局部聚焦

用于在一条已有剪辑计划的原生镜头里短暂放大操作区或作品细节。下例对片段 cut-07 在第 0.2 秒开始推进，第 0.6 秒到达，停到 1.2 秒，第 1.6 秒回位。秒数是变速后的片段内时间。scale 是到达后的绝对缩放，x/y 可省略，或按本计划的位置坐标填写。用实际镜头确认重点和字幕不被遮挡。

```powershell
python scripts/maliang.py focus project/plan.json --media-root project --clip cut-07 --name episode_v2 --out project/plan-focus.json --start 0.2 --arrive 0.6 --leave 1.2 --end 1.6 --scale 1.35 --reason "让观众看清导出按钮" --verification "在剪映播放本段，确认按钮完整且字幕清晰"
python scripts/maliang.py build project/plan-focus.json --media-root project --out project/drafts/episode_v2
```

新计划存于原计划同目录，以保留相对素材路径。命令对指定片段写入现有的可编辑关键帧格式，保留原计划、时长和字幕。已有位置或缩放关键帧时返回提示，避免覆盖已有运动。打开新草稿后按正常速度核对动作与画面，再沿原流程导出。
