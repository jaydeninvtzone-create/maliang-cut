# 可选ASR：范围、安装和许可

命令：`python scripts/maliang.py asr INPUT.wav --model-dir MODEL_DIR --out NEW_DIR --language zh`。模型目录需已有`model.int8.onnx`和`tokens.txt`，支持固定SenseVoiceSmall int8 2024-07-17文件哈希。不同模型/缺文件/缺依赖准确报错，不自动下载、联网调用或切付费服务。当前支持Windows与sherpa-onnx1.13.8（内置ONNX Runtime1.28.2），CPU单线程；原生遥测关闭API在加载前调用，另禁Python网络入口。这是进程内措施，不等于OS沙箱或抓包证明。

依赖：`requirements-asr.txt`独立可选。引擎是Apache-2.0；SenseVoiceSmall模型权重受独立FunASR Model Open Source License Agreement v1.1约束，包含署名、保留模型名、参考学习、终止和修订等条款。不要把模型与本适配代码统称无条件Apache或无限制商用。公开包不含模型、不修改原许可。

官方依据：
- [sherpa SenseVoice Python API](https://k2-fsa.github.io/sherpa/onnx/sense-voice/python-api.html)
- [FunASR模型许可](https://github.com/modelscope/FunASR/blob/main/MODEL_LICENSE)；本包附有[所审协议全文](../licenses/FunASR-MODEL_LICENSE)。
- [sherpa引擎](https://github.com/k2-fsa/sherpa-onnx)

## 输入和输出

输入为授权本地16kHz/单声道/16位PCM WAV，最长30秒。先将原视频音轨转换成新的工作副本，不改原件。任何已有校正稿优先复用，避免重复识别。

输出：`raw.json`保留模型原始字段、`transcript.txt`保留原始识别文本、`receipt.json`记录音频哈希/长度/参数/时间支持范围。`use_itn=False`关闭逆文本规范化，不把“不要，不要删掉”主动清理成另一句话。识别本身仍可能错字、漏字，不能称绝对逐字准确。

模型timestamps是本段token起点估计，不是强制对齐、不含可靠词尾、不区分说话人。不要用“下一个token起点”伪造已经校准的词尾；不得自动导出成品SRT并称验收。对数字、否定词、口误、自我纠正和专名逐段回听。

## 长素材

这是短段适配器，未宣称长片端到端转写已验。分块时先在自然停顿附近选择窗口，确保每段≤30秒，保留每块原片起点和覆盖范围；必要重叠用于回听衔接，但不要未经核听去重。合并时将本段token估计加原片起点用于定位，仍保留每块raw结果。

分块只是识别工作单元，绝不是成片剪点。完整覆盖、跨块断词、重复覆盖和原意校正完成后，Codex才能提出语义删改，并在实际音频切点核听。

## 当前证据

适配器异常/原样输出单测通过；本版本真实CPU推理尚未完成。未用mock测试替代真实识别；在空闲内存足够时再用明确标记的短测试输入补一次实际调用。
